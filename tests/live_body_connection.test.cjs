const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const markup = fs.readFileSync(path.join(__dirname, '../src/aicognitive_mind/static/live_body.html'), 'utf8');

function fixture({ hidden = false, voice = true, register } = {}) {
  const calls = [];
  const listeners = {};
  const context = vm.createContext({
    AbortSignal,
    EventSource: class {
      constructor() { calls.push('connect'); }
      addEventListener() {}
      close() { calls.push('close'); }
    },
    bodyFetch: async () => {
      calls.push('register');
      return register ? register() : { ok: true };
    },
    bodySessionId: 'phone',
    consumeExpressionOutputs: async () => { if (voice) calls.push('drain'); },
    document: { hidden, addEventListener: (name, handler) => { listeners[name] = handler; } },
    hearingEnabled: true,
    lastPlaybackState: 'idle',
    microphoneStream: null,
    mouthEvents: { close: () => calls.push('close') },
    realtimeRequested: false,
    reportVoiceFailure() {},
    talkBusy: false,
    talkEnabled: false,
    voiceEnabled: voice,
    window: { addEventListener: (name, handler) => { listeners[name] = handler; } },
  });
  const connectionSource = markup.slice(
    markup.indexOf('    function connectMouthEvents()'),
    markup.indexOf('    async function showMindResult('),
  );
  vm.runInContext(connectionSource, context);
  const listenerSource = markup.slice(
    markup.indexOf('    document.addEventListener("visibilitychange"'),
    markup.indexOf('    window.addEventListener("beforeunload"'),
  );
  context.checkForBodyPageUpdate = () => {};
  context.refreshSharedVoiceSettings = () => {};
  context.refreshConnectedHostStatus = () => {};
  vm.runInContext(listenerSource, context);
  return { calls, context, listeners };
}

test('foreground recovery registers, reopens speech events, and drains queued output', async () => {
  const page = fixture();
  await page.context.resumeBodyConnection();
  assert.deepEqual(page.calls, ['register', 'close', 'connect', 'drain']);
});

test('visibility and page restoration both recover the Body connection', async () => {
  for (const event of ['visibilitychange', 'pageshow']) {
    const page = fixture();
    page.listeners[event]();
    await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual(page.calls, ['register', 'close', 'connect', 'drain']);
  }
});

test('hidden and simultaneous wake-ups do not create competing connections', async () => {
  const hidden = fixture({ hidden: true });
  await hidden.context.resumeBodyConnection();
  assert.deepEqual(hidden.calls, []);

  let release;
  const pending = new Promise(resolve => { release = resolve; });
  const page = fixture({ register: () => pending });
  const first = page.context.resumeBodyConnection();
  await page.context.resumeBodyConnection();
  assert.deepEqual(page.calls, ['register']);
  release({ ok: true });
  await first;
  assert.deepEqual(page.calls, ['register', 'close', 'connect', 'drain']);
});

test('Voice Off remains off while the page connection is recovered', async () => {
  const page = fixture({ voice: false });
  await page.context.resumeBodyConnection();
  assert.deepEqual(page.calls, ['register', 'close']);
});

test('a failed drain permits a later recovery attempt', async () => {
  const page = fixture();
  page.context.consumeExpressionOutputs = async () => { throw new Error('offline'); };
  await page.context.resumeBodyConnection();
  page.context.consumeExpressionOutputs = async () => page.calls.push('drain');
  await page.context.resumeBodyConnection();
  assert.equal(page.calls.filter(call => call === 'register').length, 2);
  assert.equal(page.calls.at(-1), 'drain');
});

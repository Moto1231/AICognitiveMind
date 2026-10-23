const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../src/aicognitive_mind/static/live_body.html'), 'utf8');

function body({ hidden = false, voice = true, register } = {}) {
  const calls = [];
  const listeners = {};
  const context = vm.createContext({
    document: { hidden, addEventListener: (name, handler) => { listeners[name] = handler; } },
    window: { addEventListener: (name, handler) => { listeners[name] = handler; } },
    original: { close: () => calls.push('close') },
    bodyFetch: async () => {
      calls.push('register');
      return register ? register() : { ok: true };
    },
    EventSource: class {
      constructor() { calls.push('connect'); }
      addEventListener() {}
      close() { calls.push('close'); }
    },
    consumeExpressionOutputs: async () => { if (voice) calls.push('drain'); },
    checkForBodyPageUpdate() {}, refreshSharedVoiceSettings() {}, refreshConnectedHostStatus() {},
  });
  vm.runInContext(`let voiceEnabled = ${voice}; let mouthEvents = original; const bodySessionId = 'phone';`, context);
  vm.runInContext(source.slice(source.indexOf('    function connectMouthEvents()'),
    source.indexOf('    async function showMindResult(')), context);
  vm.runInContext(source.slice(source.indexOf('    document.addEventListener("visibilitychange"'),
    source.indexOf('    window.addEventListener("beforeunload"')), context);
  return { context, calls, listeners, resume: () => vm.runInContext('resumeBodyConnection()', context) };
}

test('foreground restore registers before reconnecting speech and draining queued output', async () => {
  const page = body();
  await page.resume();
  assert.deepEqual(page.calls, ['register', 'close', 'connect', 'drain']);
});

test('both returning visibility and browser page restoration reconnect the Body', async () => {
  for (const event of ['visibilitychange', 'pageshow']) {
    const page = body();
    page.listeners[event]();
    await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual(page.calls, ['register', 'close', 'connect', 'drain']);
  }
});

test('hidden pages do not take over the active Body registration', async () => {
  const page = body({ hidden: true });
  await page.resume();
  assert.deepEqual(page.calls, []);
});

test('simultaneous restore events share one reconnect', async () => {
  let release;
  const pending = new Promise(resolve => { release = resolve; });
  const page = body({ register: () => pending });
  const first = page.resume();
  await page.resume();
  assert.deepEqual(page.calls, ['register']);
  release({ ok: true });
  await first;
  assert.deepEqual(page.calls, ['register', 'close', 'connect', 'drain']);
});

test('voice off stays off during recovery', async () => {
  const page = body({ voice: false });
  await page.resume();
  assert.deepEqual(page.calls, ['register', 'close']);
});

test('registration failures are reported as failures and permit later retries', async () => {
  const page = body({ register: () => ({ ok: false }) });
  assert.equal(await vm.runInContext('registerActiveBodySession()', page.context), false);
  await page.resume();
  await page.resume();
  assert.equal(page.calls.filter(call => call === 'register').length, 3);
});

test('a failed output drain does not prevent the next recovery attempt', async () => {
  const page = body();
  page.context.consumeExpressionOutputs = async () => { throw new Error('offline'); };
  await page.resume();
  page.context.consumeExpressionOutputs = async () => page.calls.push('drain');
  await page.resume();
  assert.equal(page.calls.filter(call => call === 'register').length, 2);
  assert.equal(page.calls.at(-1), 'drain');
});

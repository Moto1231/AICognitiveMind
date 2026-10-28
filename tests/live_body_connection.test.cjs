const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const markup = fs.readFileSync(path.join(__dirname, '../src/aicognitive_mind/static/live_body.html'), 'utf8');

function fixture({ hidden = false, focused = true, voice = true, register } = {}) {
  const calls = [];
  const listeners = {};
  let isFocused = focused;
  const ownershipStatus = { dataset: {}, textContent: '' };
  const controls = Array.from({ length: 6 }, () => ({ disabled: false }));
  const context = vm.createContext({
    AbortSignal,
    EventSource: class {
      constructor() { calls.push('connect'); }
      addEventListener() {}
      close() { calls.push('close'); }
    },
    bodyFetch: async (_url, options = {}) => {
      const payload = JSON.parse(options.body || '{}');
      calls.push(payload.release ? 'release' : 'register');
      const response = register ? await register(payload) : null;
      return response || { ok: true, status: 200, json: async () => ({ active: true, replaced: false }) };
    },
    bodySessionId: 'phone',
    bodyOwnershipActive: false,
    bodyOwnershipReleasePending: false,
    bodyOwnershipStatus: ownershipStatus,
    visionToggle: controls[0], hearingToggle: controls[1], voiceToggle: controls[2],
    interactionMessage: controls[3], sendInteractionButton: controls[4], clearInteractionButton: controls[5],
    consumeExpressionOutputs: async () => { if (voice) calls.push('drain'); },
    document: { hidden, hasFocus: () => isFocused, addEventListener: (name, handler) => { listeners[name] = handler; } },
    hearingEnabled: false,
    visionEnabled: false,
    lastPlaybackState: 'idle',
    localStorage: { getItem: () => null },
    microphoneStream: null,
    mouthEvents: null,
    realtimeRequested: false,
    reportVoiceFailure() {},
    responseErrorMessage: async () => 'registration failed',
    setStatus() {}, stopTalking() {}, cancelBodySpeech() {}, disableVision() {}, disableHearing() {},
    enableVision: async () => {}, enableHearing: async () => {},
    talkBusy: false,
    talkEnabled: false,
    voiceEnabled: voice,
    window: { addEventListener: (name, handler) => {
      listeners[name] = (...args) => {
        if (name === 'blur') isFocused = false;
        if (name === 'focus') isFocused = true;
        return handler(...args);
      };
    } },
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
  return { calls, context, listeners, ownershipStatus, controls };
}

test('foreground recovery registers, reopens speech events, and drains queued output', async () => {
  const page = fixture();
  await page.context.resumeBodyConnection();
  assert.deepEqual(page.calls, ['register', 'connect', 'drain']);
  assert.equal(page.context.bodyOwnershipActive, true);
  assert.equal(page.ownershipStatus.textContent, 'Active Body');
});

test('visibility and page restoration both recover the Body connection', async () => {
  for (const event of ['visibilitychange', 'pageshow']) {
    const page = fixture();
    page.listeners[event]();
    await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual(page.calls, ['register', 'connect', 'drain']);
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
  release({ ok: true, status: 200, json: async () => ({ active: true, replaced: false }) });
  await first;
  assert.deepEqual(page.calls, ['register', 'connect', 'drain']);
});

test('Voice Off remains off while the page connection is recovered', async () => {
  const page = fixture({ voice: false });
  await page.context.resumeBodyConnection();
  assert.deepEqual(page.calls, ['register']);
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

test('a competing fresh owner pauses this window instead of stealing output', async () => {
  const payloads = [];
  const page = fixture({ register: payload => {
    payloads.push(payload);
    return { ok: false, status: 409, json: async () => ({ detail: 'busy' }) };
  } });
  await page.context.resumeBodyConnection();
  await page.context.registerActiveBodySession();
  assert.deepEqual(page.calls, ['register', 'register']);
  assert.equal(page.context.bodyOwnershipActive, false);
  assert.equal(page.ownershipStatus.textContent, 'Body paused');
  assert.ok(page.controls.every(control => control.disabled));
  assert.equal(payloads[0].takeover, true);
  assert.equal(payloads[1].takeover, false);
});

test('losing focus releases ownership, closes speech events, and disables controls', async () => {
  const page = fixture();
  await page.context.resumeBodyConnection();
  page.listeners.blur();
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(page.calls, ['register', 'connect', 'drain', 'close', 'release']);
  assert.equal(page.context.bodyOwnershipActive, false);
  assert.ok(page.controls.every(control => control.disabled));
});

test('foreground acquisition explicitly takes over while routine renewal does not', async () => {
  const payloads = [];
  const page = fixture({ register: payload => {
    payloads.push(payload);
    return { ok: true, status: 200, json: async () => ({ active: true, replaced: payload.takeover }) };
  } });
  await page.context.resumeBodyConnection();
  await page.context.registerActiveBodySession();
  assert.equal(payloads[0].takeover, true);
  assert.equal(payloads[1].takeover, false);
});

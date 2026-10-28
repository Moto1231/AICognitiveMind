const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const markup = fs.readFileSync(path.join(__dirname, '../src/aicognitive_mind/static/live_body.html'), 'utf8');
function section(start, end) { return markup.slice(markup.indexOf(start), markup.indexOf(end)); }
const source = section('    function cancelSensoryObservation(', '    function bodyIsBusy(') +
  section('    async function perceiveVision(', '    function recordAudioWindow(') +
  section('    async function perceiveAudio(', '    async function runVisionLoop(') +
  section('    async function runVisionLoop(', '    function startSensoryLoop(') +
  section('    function disableVision(', '    async function enableHearing(') +
  section('    function disableHearing(', '    function toggleVision(');
const settle = () => new Promise(resolve => setImmediate(resolve));
function deferred() {
  let resolve, reject;
  const promise = new Promise((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
}
function fixture() {
  const requests = [], statuses = [], results = [], timers = new Map();
  let nextTimer = 0;
  const stream = { getTracks: () => [{ stop() {} }] };
  const context = vm.createContext({
    AbortController, Map, Error,
    sensoryRequests: new Map(), sensoryRequestInFlight: false, SENSORY_REQUEST_TIMEOUT_MS: 150_000,
    window: { setTimeout(callback, ms) { const id = ++nextTimer; timers.set(id, { callback, ms }); return id; },
      clearTimeout(id) { timers.delete(id); }, speechSynthesis: { speaking: false } },
    bodyOwnershipActive: true,
    visionEnabled: true, hearingEnabled: true, sensoryLoopGeneration: 1, hearingGeneration: 1,
    cameraStream: stream, microphoneStream: stream, recorder: null,
    liveScene: { readyState: 2, videoWidth: 960, videoHeight: 540, style: {} }, video: {}, audioMeter: { style: {} },
    canvas: { getContext: () => ({ drawImage() {} }), toDataURL: () => 'data:image/jpeg;base64,frame' },
    frameSignature: () => [100], lastFrameSignature: [0], lastMotionCaptureAt: 0,
    performance: { now: () => 10_000 }, MOTION_PIXEL_DELTA: 22, MOTION_PIXEL_RATIO: 0.07, MOTION_CAPTURE_COOLDOWN_MS: 2500,
    VISION_INTERVAL_MS: 250, document: { hidden: false }, sendInteractionButton: { disabled: false },
    talkEnabled: false, talkBusy: false, talkSpeaking: false, voiceEnabled: false,
    recordAudioWindow: async () => ({ blob: {}, durationMs: 1000, hasSpeechEnergy: true }),
    blobToDataUrl: async () => 'data:audio/webm;base64,speech',
    setStatus() {}, setSenseStatus: (modality, message, state) => statuses.push({ modality, message, state }),
    showMindResult: async (result, options) => results.push({ result, options }),
    responseErrorMessage: async response => response.detail || 'Request failed',
    delay: async () => {}, localStorage: { setItem() {} }, refreshToggleUi() {}, startSensoryLoop() {},
    stopTalking() {}, stopAudioMeter() {},
    bodyFetch: (url, options) => {
      const response = deferred();
      options.signal.addEventListener('abort', () => response.reject(new Error('Request aborted')), { once: true });
      requests.push({ url, options, response });
      return response.promise;
    },
  });
  vm.runInContext(source, context);
  return { context, requests, statuses, results, timers };
}
function start(ui, modality) {
  return modality === 'vision' ? ui.context.perceiveVision(1) : ui.context.perceiveAudio(1);
}

test('both sensory requests stop waiting at the browser deadline and release the busy state', async () => {
  for (const modality of ['vision', 'audio']) {
    const ui = fixture();
    const pending = start(ui, modality);
    const failure = assert.rejects(pending, error => {
      assert.equal(error.message, 'Interpretation timed out.');
      assert.equal(error.evidenceAccepted, false, 'An unacknowledged upload cannot be called saved.');
      ui.context.reportSenseFailure(modality, error);
      return true;
    });
    await settle();
    assert.equal(ui.requests.length, 1);
    assert.equal(ui.context.sensoryRequestInFlight, true);
    const timer = [...ui.timers.values()][0];
    assert.equal(timer.ms, 150_000);
    timer.callback();
    await failure;
    assert.equal(ui.requests[0].options.signal.aborted, true);
    assert.equal(ui.context.sensoryRequestInFlight, false);
    assert.equal(ui.context.sensoryRequests.size, 0);
    assert.equal(ui.timers.size, 0);
    assert.equal(ui.statuses.at(-1).state, 'error');
    assert.doesNotMatch(ui.statuses.at(-1).message, /saved|saving/i);
    ui.context.lastFrameSignature = [0];
    ui.context.lastMotionCaptureAt = 0;
    const recovered = start(ui, modality);
    await settle();
    assert.equal(ui.requests.length, 2);
    ui.requests[1].response.resolve({ ok: true, json: async () => ({ interpretation: 'Recovered observation' }) });
    await recovered;
    assert.equal(ui.statuses.at(-1).state, 'success');
  }
});

test('an intentional audio conversation has its own bounded deadline and still releases capture on timeout', async () => {
  const ui = fixture();
  ui.context.voiceEnabled = true;
  const pending = start(ui, 'audio');
  const failure = assert.rejects(pending, /Interpretation timed out/);
  await settle();
  assert.equal(JSON.parse(ui.requests[0].options.body).conversation, true);
  const timer = [...ui.timers.values()][0];
  assert.equal(timer.ms, 300_000);
  timer.callback();
  await failure;
  assert.equal(ui.requests[0].options.signal.aborted, true);
  assert.equal(ui.context.sensoryRequestInFlight, false);
  assert.equal(ui.context.sensoryRequests.size, 0);
  assert.equal(ui.timers.size, 0);
});

test('a background Body cannot upload Hearing or Vision observations', async () => {
  const ui = fixture();
  ui.context.document.hidden = true;
  ui.context.bodyOwnershipActive = false;
  const hearing = ui.context.runHearingLoop(1);
  await settle();
  await hearing;
  assert.equal(ui.requests.length, 0);
  assert.equal(ui.context.sensoryRequestInFlight, false);

  const vision = fixture();
  vision.context.document.hidden = true;
  vision.context.bodyOwnershipActive = false;
  await vision.context.runVisionLoop(1);
  assert.equal(vision.requests.length, 0);
});

test('a successful header does not show interpreted success before the JSON body finishes', async () => {
  const ui = fixture();
  const pending = start(ui, 'vision');
  await settle();
  const body = deferred();
  ui.requests[0].response.resolve({ ok: true, json: () => body.promise });
  await settle();
  assert.equal(ui.statuses.at(-1).message, 'Processing frame…');
  assert.equal(ui.context.sensoryRequestInFlight, true);
  body.resolve({ interpretation: 'The preserved frame.' });
  await pending;
  assert.equal(ui.statuses.at(-1).state, 'success');
  assert.equal(ui.results.length, 1);
  assert.equal(ui.context.sensoryRequestInFlight, false);
});

test('invalid response JSON never displays interpreted success', async () => {
  const ui = fixture();
  const pending = start(ui, 'audio');
  const failure = assert.rejects(pending, /Invalid JSON/);
  await settle();
  ui.requests[0].response.resolve({ ok: true, json: async () => { throw new Error('Invalid JSON'); } });
  await failure;
  assert.equal(ui.statuses.some(status => status.state === 'success'), false);
  assert.equal(ui.results.length, 0);
  assert.equal(ui.context.sensoryRequestInFlight, false);
});

test('turning a sense off cancels only its request and keeps concurrent work busy', async () => {
  const ui = fixture();
  const vision = start(ui, 'vision');
  const visionStopped = assert.rejects(vision, /aborted/);
  const audio = start(ui, 'audio');
  const audioStopped = assert.rejects(audio, /aborted/);
  await settle();
  ui.context.disableVision();
  await visionStopped;
  assert.equal(ui.requests[0].options.signal.aborted, true);
  assert.equal(ui.requests[1].options.signal.aborted, false);
  assert.equal(ui.context.sensoryRequestInFlight, true);
  assert.equal(ui.statuses.at(-1).state, 'idle');
  ui.context.disableHearing();
  await audioStopped;
  assert.equal(ui.requests[1].options.signal.aborted, true);
  assert.equal(ui.context.sensoryRequestInFlight, false);
  assert.equal(ui.results.length, 0);
});

test('generation restarts cannot submit duplicate work or publish old success', async () => {
  for (const modality of ['vision', 'audio']) {
    const ui = fixture();
    const pending = start(ui, modality);
    await settle();
    ui.context.sensoryLoopGeneration = 2;
    await ui.context[modality === 'vision' ? 'perceiveVision' : 'perceiveAudio'](2);
    assert.equal(ui.requests.length, 1);
    ui.requests[0].response.resolve({ ok: true, json: async () => ({ interpretation: 'Old result' }) });
    await pending;
    assert.equal(ui.statuses.some(status => status.state === 'success'), false);
    assert.equal(ui.results.length, 0);
    assert.equal(ui.context.sensoryRequestInFlight, false);
    ui.context.lastFrameSignature = [0];
    ui.context.lastMotionCaptureAt = 0;
    const next = ui.context[modality === 'vision' ? 'perceiveVision' : 'perceiveAudio'](2);
    await settle();
    assert.equal(ui.requests.length, 2, 'The new loop recovers after the prior request settles.');
    ui.requests[1].response.resolve({ ok: true, json: async () => ({ interpretation: 'Current result' }) });
    await next;
    assert.equal(ui.results.length, 1);
  }
});

test('a shared loop restart suppresses the other sense stale success or error and releases it', async () => {
  for (const outcome of ['success', 'error']) {
    const ui = fixture();
    const hearing = ui.context.runHearingLoop(1);
    await settle();
    ui.context.disableVision();
    assert.equal(ui.requests[0].options.signal.aborted, false);
    assert.equal(ui.context.sensoryRequestInFlight, true);
    if (outcome === 'success') {
      ui.requests[0].response.resolve({ ok: true, json: async () => ({ interpretation: 'Old audio' }) });
    } else {
      ui.requests[0].response.reject(new Error('Late audio failure'));
    }
    await hearing;
    assert.equal(ui.context.sensoryRequestInFlight, false);
    assert.equal(ui.context.sensoryRequests.size, 0);
    assert.equal(ui.results.length, 0);
    assert.equal(ui.statuses.filter(status => status.modality === 'audio').length, 1);
    assert.equal(ui.statuses.filter(status => status.modality === 'audio')[0].state, 'working');
  }
});

test('an explicit server saved-evidence failure reports the preserved evidence truthfully', () => {
  for (const prefix of ['', 'Reasoning-host interpretation failed for vision: RuntimeError: ']) {
    const ui = fixture();
    ui.context.reportSenseFailure('vision', new Error(prefix + 'Sensory evidence was saved, but the reasoning host did not complete its interpretation within 120 seconds.'));
    assert.equal(ui.statuses.at(-1).state, 'warning');
    assert.match(ui.statuses.at(-1).message, /^Evidence saved; interpretation failed:/);
  }
});

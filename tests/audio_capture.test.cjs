const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const markup = fs.readFileSync(path.join(__dirname, '../src/aicognitive_mind/static/live_body.html'), 'utf8');
function section(start, end) { return markup.slice(markup.indexOf(start), markup.indexOf(end)); }
const source = section('    function recordAudioWindow(', '    let lastFrameSignature') +
  section('    async function perceiveAudio(', '    async function runVisionLoop(');
const settle = () => new Promise(resolve => setImmediate(resolve));
function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
}

function fixture() {
  const intervals = new Map(), recorders = [], requests = [], statuses = [], results = [], chats = [];
  const raw = Uint8Array.from([0x1a, 0x45, 0xdf, 0xa3, 0x00, 0x12, 0x34, 0x56]);
  let now = 0, sample = 128, intervalSequence = 0, decoderConstructions = 0, mouthDrains = 0;
  let response = { interpretation: 'Recorded speech.' };
  class Recorder {
    static isTypeSupported() { return true; }
    constructor(stream, options = {}) {
      this.stream = stream;
      this.mimeType = options.mimeType || 'audio/webm';
      this.state = 'inactive';
      this.listeners = new Map();
      this.emitData = true;
      recorders.push(this);
    }
    addEventListener(name, callback) {
      if (!this.listeners.has(name)) this.listeners.set(name, []);
      this.listeners.get(name).push(callback);
    }
    emit(name, event = {}) { for (const callback of this.listeners.get(name) || []) callback(event); }
    start() { this.state = 'recording'; }
    stop() {
      this.state = 'inactive';
      if (this.emitData) this.emit('dataavailable', { data: new Blob([raw], { type: this.mimeType }) });
      this.emit('stop');
    }
  }
  class ForbiddenDecoder {
    constructor() { decoderConstructions++; throw new Error('Browser must not decode captured media again.'); }
  }
  const context = vm.createContext({
    Blob, Uint8Array, Math, MediaRecorder: Recorder,
    AudioContext: ForbiddenDecoder,
    window: { MediaRecorder: Recorder, AudioContext: ForbiddenDecoder, speechSynthesis: { speaking: false },
      setInterval(callback) { const id = ++intervalSequence; intervals.set(id, callback); return id; },
      clearInterval(id) { intervals.delete(id); } },
    performance: { now: () => now },
    hearingEnabled: true, sensoryLoopGeneration: 1,
    microphoneStream: { id: 'selected-microphone' }, recorder: null,
    audioAnalyser: { fftSize: 16, getByteTimeDomainData(samples) { samples.fill(sample); } },
    AUDIO_MAX_DURATION_MS: 30_000, AUDIO_IDLE_WINDOW_MS: 4000,
    AUDIO_SILENCE_MS: 900, AUDIO_SPEECH_THRESHOLD: 0.012,
    sensoryRequests: new Map(), talkEnabled: false, talkBusy: false, talkSpeaking: false, voiceEnabled: false,
    preferredAudioMimeType: () => 'audio/webm;codecs=opus',
    delay: async () => {}, setStatus() {},
    setSenseStatus: (modality, message, state) => statuses.push({ modality, message, state }),
    blobToDataUrl: async blob => `data:${blob.type};base64,${Buffer.from(await blob.arrayBuffer()).toString('base64')}`,
    requestSensoryObservation: async (modality, payload) => {
      requests.push({ modality, payload });
      return response;
    },
    showMindResult: async result => results.push(result),
    appendChatMessage: (role, text) => chats.push({ role, text }),
    consumeExpressionOutputs: async () => { mouthDrains++; return true; },
    reportVoiceFailure(error) { statuses.push({ state: 'error', message: error.message }); },
  });
  vm.runInContext(source, context);
  return { context, raw, intervals, recorders, requests, statuses, results, chats,
    get decoderConstructions() { return decoderConstructions; },
    get mouthDrains() { return mouthDrains; },
    response(value) { response = value; },
    tick(time, amplitude) {
      now = time;
      sample = amplitude;
      for (const callback of [...intervals.values()]) callback();
    } };
}

function finishSpeech(ui) {
  ui.tick(100, 144);
  ui.tick(200, 128);
  ui.tick(1500, 128);
}

test('capture uses its existing analyser for speech energy and preserves recorder bytes', async () => {
  const ui = fixture();
  const pending = ui.context.recordAudioWindow(1);
  finishSpeech(ui);
  const recording = await pending;
  assert.equal(recording.hasSpeechEnergy, true);
  assert.equal(recording.durationMs, 1500);
  assert.equal(recording.blob.type, 'audio/webm;codecs=opus');
  assert.deepEqual(new Uint8Array(await recording.blob.arrayBuffer()), ui.raw);
  assert.equal(ui.intervals.size, 0);
  assert.equal(ui.context.recorder, null);
  assert.equal(ui.decoderConstructions, 0);
});

test('speech reaches interpretation without a browser decoder or altered media bytes', async () => {
  const ui = fixture();
  const pending = ui.context.perceiveAudio(1);
  finishSpeech(ui);
  await pending;
  assert.equal(ui.requests.length, 1);
  const { modality, payload } = ui.requests[0];
  assert.equal(modality, 'audio');
  assert.equal(payload.duration_ms, 1500);
  assert.equal(payload.source, 'browser-microphone');
  assert.equal(payload.conversation, false);
  assert.deepEqual(Buffer.from(payload.audio_data_url.split(',')[1], 'base64'), Buffer.from(ui.raw));
  assert.equal(ui.decoderConstructions, 0);
  assert.equal(ui.results.length, 1);
  assert.equal(ui.chats.length, 0);
  assert.equal(ui.mouthDrains, 0);
});

test('Voice-on fallback explicitly requests conversation and sends its reply through the existing Mouth queue', async () => {
  const ui = fixture();
  ui.context.voiceEnabled = true;
  ui.response({ interpretation: 'Recognized question.', response_text: 'Yes, your recording reached me.' });
  ui.context.speakIntent = () => { throw new Error('The response must not create duplicate direct speech.'); };
  const pending = ui.context.perceiveAudio(1);
  finishSpeech(ui);
  await pending;
  assert.equal(ui.requests[0].payload.conversation, true);
  assert.deepEqual(ui.chats, [{ role: 'mind', text: 'Yes, your recording reached me.' }]);
  assert.equal(ui.mouthDrains, 1);
  assert.equal(ui.results.length, 1);
});

test('an observation without a conversational response does not create a chat reply or speech drain', async () => {
  const ui = fixture();
  ui.context.voiceEnabled = true;
  ui.response({ interpretation: 'No intelligible speech recognized.', response_text: '' });
  const pending = ui.context.perceiveAudio(1);
  finishSpeech(ui);
  await pending;
  assert.equal(ui.requests[0].payload.conversation, true);
  assert.equal(ui.chats.length, 0);
  assert.equal(ui.mouthDrains, 0);
});

test('quiet and low-level microphone noise do not upload recordings', async () => {
  for (const amplitude of [128, 129]) {
    const ui = fixture();
    const pending = ui.context.perceiveAudio(1);
    ui.tick(100, amplitude);
    ui.tick(4000, amplitude);
    await pending;
    assert.equal(ui.requests.length, 0);
    assert.match(ui.statuses.at(-1).message, /no speech detected/);
    assert.equal(ui.statuses.at(-1).state, 'info');
    assert.equal(ui.intervals.size, 0);
    assert.equal(ui.decoderConstructions, 0);
  }
});

test('a missing recorder chunk is reported only while passive hearing still owns capture', async () => {
  const ui = fixture();
  const pending = ui.context.perceiveAudio(1);
  ui.recorders[0].emitData = false;
  finishSpeech(ui);
  await pending;
  assert.equal(ui.requests.length, 0);
  assert.match(ui.statuses.at(-1).message, /No audio chunk received/);
});

test('realtime takeover after capture does not upload or show a false missing-chunk warning', async () => {
  for (const mode of ['talkEnabled', 'talkBusy']) {
    for (const recording of [null, { blob: {}, durationMs: 1500, hasSpeechEnergy: true }]) {
      const ui = fixture();
      const capture = deferred();
      ui.context.recordAudioWindow = () => capture.promise;
      const pending = ui.context.perceiveAudio(1);
      ui.context[mode] = true;
      capture.resolve(recording);
      await pending;
      assert.equal(ui.requests.length, 0);
      assert.equal(ui.statuses.length, 0);
    }
  }
});

test('realtime takeover during blob conversion cannot submit the superseded clip', async () => {
  const ui = fixture();
  const conversion = deferred();
  ui.context.blobToDataUrl = () => conversion.promise;
  const pending = ui.context.perceiveAudio(1);
  finishSpeech(ui);
  await settle();
  ui.context.talkEnabled = true;
  conversion.resolve('data:audio/webm;base64,speech');
  await pending;
  assert.equal(ui.requests.length, 0);
  assert.equal(ui.statuses.length, 0);
});

test('a stopped or replaced hearing generation cannot upload a pending conversion', async () => {
  for (const change of ['disable', 'generation']) {
    const ui = fixture();
    const conversion = deferred();
    ui.context.blobToDataUrl = () => conversion.promise;
    const pending = ui.context.perceiveAudio(1);
    finishSpeech(ui);
    await settle();
    if (change === 'disable') ui.context.hearingEnabled = false;
    else ui.context.sensoryLoopGeneration++;
    conversion.resolve('data:audio/webm;base64,speech');
    await pending;
    assert.equal(ui.requests.length, 0);
    assert.equal(ui.statuses.length, 0);
  }
});

test('recorder failures release capture state and a subsequent recording can proceed', async () => {
  const ui = fixture();
  const failed = ui.context.recordAudioWindow(1);
  const rejected = assert.rejects(failed, /Microphone disconnected/);
  ui.recorders[0].state = 'inactive';
  ui.recorders[0].emit('error', { error: new Error('Microphone disconnected') });
  await rejected;
  assert.equal(ui.intervals.size, 0);
  assert.equal(ui.context.recorder, null);
  const recovered = ui.context.perceiveAudio(1);
  finishSpeech(ui);
  await recovered;
  assert.equal(ui.requests.length, 1);
  assert.equal(ui.results.length, 1);
});

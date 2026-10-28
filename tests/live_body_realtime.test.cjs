const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const markup = fs.readFileSync(path.join(__dirname, '../src/aicognitive_mind/static/live_body.html'), 'utf8');
const startup = markup.slice(markup.indexOf('    function stopTalking('), markup.indexOf('    async function consumeExpressionOutputs()'));
const hearingControls = markup.slice(markup.indexOf('    async function enableHearing()'), markup.indexOf('    interactionForm.addEventListener'));
const playback = markup.slice(markup.indexOf('    function cancelBodySpeech('), markup.indexOf('    function resumeTalking()'));
const settle = () => new Promise(resolve => setImmediate(resolve));
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done; }); return { promise, resolve }; };
function realtimeStartup({ status = { realtime: { available: true, scope: 'session-a' } }, statusOk = true, statusError = null,
  statusWait = null, sdpWait = null, sdpScope = 'session-a', beforeSpeakStatus = null, abortImmediately = false } = {}) {
  const requests = [], messages = [], peers = [], controllers = [];
  let microphoneRequests = 0, speech = 0, tracksStopped = 0;
  const track = { kind: 'audio', enabled: true, readyState: 'live', stop() { tracksStopped++; this.readyState = 'ended'; } };
  const stream = { getAudioTracks: () => [track], getTracks: () => [track] };
  class Peer {
    constructor() { peers.push(this); this.tracks = []; }
    addTrack(value) { this.tracks.push(value); }
    addEventListener() {}
    createDataChannel() {
      const listeners = {};
      return this.channel = { readyState: 'open', addEventListener(type, callback) { listeners[type] = callback; }, listeners,
        close() { this.closed = true; listeners.close?.(); }, send() {} };
    }
    async createOffer() { return { type: 'offer', sdp: 'synthetic-offer' }; }
    async setLocalDescription(offer) { this.localDescription = offer; }
    async setRemoteDescription(answer) { this.remoteDescription = answer; }
    close() { this.closed = true; }
  }
  const context = vm.createContext({
    window: { RTCPeerConnection: Peer, speechSynthesis: { cancel() {} } }, RTCPeerConnection: Peer,
    AbortSignal: { timeout: milliseconds => ({ aborted: abortImmediately, milliseconds }) },
    navigator: { mediaDevices: { getUserMedia: async () => { microphoneRequests++; return stream; } } },
    RealtimeTurns: class { constructor(options) { Object.assign(this, options); controllers.push(this); } handle() { this.handled = true; } close() { this.closed = true; } },
    talkEnabled: false, talkBusy: false, talkListening: false, talkSpeaking: false, talkRestartTimer: null,
    realtimeRequested: false, realtimeGeneration: 0, realtimeScope: null, realtimeTurns: null, realtimePeer: null, realtimeMicrophone: null, realtimeEvents: null, realtimeAudio: null,
    microphoneStream: stream, hearingEnabled: true, voiceEnabled: true, hearingGeneration: 0,
    visionEnabled: false, recorder: null, activeSpeechAudio: null, audioMeter: { style: {} }, sensoryLoopGeneration: 0,
    hearingToggle: { disabled: false }, localStorage: { setItem() {} },
    setStatus: message => messages.push(message), cancelBodySpeech() {}, clearTimeout() {},
    bodyMediaConstraints: () => ({ audio: true }), requestedLookDuration: () => null,
    startAudioMeter: async () => {}, stopAudioMeter() {}, refreshToggleUi() {}, setSenseStatus() {}, startSensoryLoop() {},
    connectMouthEvents() {}, resumeBodyConnection() {}, refreshSharedVoiceSettings() {}, cancelSensoryObservation() {}, speakIntent: async () => { speech++; },
    bodyFetch: async (url, options = {}) => {
      requests.push({ url, method: options.method || 'GET', body: options.body });
      if (options.signal?.aborted) throw new Error('Request timed out.');
      if (url === '/v1/body/hosts/status') {
        if (statusWait) await statusWait.promise;
        if (statusError) throw statusError;
        const value = requests.length > 2 && beforeSpeakStatus ? beforeSpeakStatus : status;
        return { ok: statusOk, json: async () => value };
      }
      assert.equal(url, '/v1/body/realtime/session');
      if (sdpWait) await sdpWait.promise;
      return { ok: true, headers: { get: () => sdpScope }, text: async () => 'synthetic-answer' };
    },
  });
  vm.runInContext(startup + hearingControls, context);
  return { context, requests, messages, peers, controllers, track, microphoneRequests: () => microphoneRequests,
    tracksStopped: () => tracksStopped, speech: () => speech };
}
test('unavailable or unreadable capability creates no RTC session and retains Hearing microphone', async () => {
  for (const options of [{ status: { realtime: { available: false } } }, { status: {} }, { statusOk: false }, { statusError: new Error('offline') }]) {
    const ui = realtimeStartup(options); await ui.context.startTalking({ realtime: true });
    assert.equal(ui.peers.length, 0); assert.equal(ui.microphoneRequests(), 0); assert.equal(ui.tracksStopped(), 0);
    assert.equal(ui.context.talkEnabled, false); assert.equal(ui.context.talkBusy, false);
  }
});

test('automatic Hearing and Voice keep the current-host audio path even when Realtime is available', async () => {
  for (const connected of [true, false]) {
    const ui = realtimeStartup({ status: { connected, realtime: { available: true, scope: 'session-a' } } });
    ui.context.hearingEnabled = false;
    await ui.context.enableHearing();
    await settle();
    assert.equal(ui.context.hearingEnabled, true);
    assert.equal(ui.context.talkEnabled, false);
    assert.equal(ui.context.talkBusy, false);
    assert.equal(ui.peers.length, 0);
    assert.equal(ui.requests.length, 0, 'An available API key must not select another reasoning host.');
    ui.context.voiceEnabled = false;
    ui.context.toggleVoice();
    await settle();
    assert.equal(ui.context.voiceEnabled, true);
    assert.equal(ui.requests.length, 0);
    assert.equal(ui.peers.length, 0);
  }
});
test('explicit Realtime uses the existing microphone; Voice off retains it', async () => {
  const ui = realtimeStartup(); await ui.context.startTalking({ realtime: true });
  assert.equal(ui.microphoneRequests(), 0); assert.equal(ui.peers.length, 1); assert.equal(ui.peers[0].tracks[0], ui.track);
  assert.deepEqual(JSON.parse(JSON.stringify(ui.peers[0].remoteDescription)), { type: 'answer', sdp: 'synthetic-answer' });
  ui.context.toggleVoice(); assert.equal(ui.context.talkEnabled, false); assert.equal(ui.peers[0].closed, true);
  assert.equal(ui.tracksStopped(), 0); assert.equal(ui.context.hearingEnabled, true);
});
test('Hearing off releases microphone and stale SDP or events cannot revive connection', async () => {
  const wait = deferred(); const ui = realtimeStartup({ sdpWait: wait });
  const starting = ui.context.startTalking({ realtime: true }); await settle(); ui.context.disableHearing(); wait.resolve(); await starting;
  assert.equal(ui.context.talkEnabled, false); assert.equal(ui.tracksStopped(), 1); assert.equal(ui.peers[0].closed, true);
  assert.equal(ui.peers[0].remoteDescription, undefined);
  ui.peers[0].channel.listeners.open(); ui.peers[0].channel.listeners.message({ data: '{}' });
  assert.equal(ui.context.talkListening, false); assert.equal(ui.controllers[0].handled, undefined);
});
test('Voice off during capability lookup cannot acquire peer or post SDP', async () => {
  const wait = deferred(); const ui = realtimeStartup({ statusWait: wait });
  const starting = ui.context.startTalking({ realtime: true }); await settle(); ui.context.toggleVoice(); wait.resolve(); await starting;
  assert.equal(ui.requests.length, 1); assert.equal(ui.peers.length, 0); assert.equal(ui.context.talkBusy, false);
});
test('a timed-out capability request fails closed and leaves the shared microphone usable', async () => {
  const ui = realtimeStartup({ abortImmediately: true }); await ui.context.startTalking({ realtime: true });
  assert.equal(ui.context.talkEnabled, false); assert.equal(ui.context.talkBusy, false);
  assert.equal(ui.peers.length, 0); assert.equal(ui.tracksStopped(), 0);
  assert.match(ui.messages.at(-1), /timed out/);
});
test('Hearing off control remains available while SDP is pending', async () => {
  const wait = deferred(); const ui = realtimeStartup({ sdpWait: wait }); ui.context.hearingEnabled = false;
  await ui.context.enableHearing();
  const connecting = ui.context.startTalking({ realtime: true });
  await settle(); assert.equal(ui.context.hearingToggle.disabled, false);
  assert.equal(ui.requests.at(-1).url, '/v1/body/realtime/session'); ui.context.toggleHearing(); wait.resolve(); await connecting;
  assert.equal(ui.context.hearingEnabled, false); assert.equal(ui.context.talkEnabled, false); assert.equal(ui.tracksStopped(), 1);
});
test('portal scope must match SDP and be freshly checked before committed speech', async () => {
  const mismatch = realtimeStartup({ sdpScope: 'session-b' }); await mismatch.context.startTalking({ realtime: true });
  assert.equal(mismatch.context.talkEnabled, false); assert.equal(mismatch.peers[0].remoteDescription, undefined);
  const ui = realtimeStartup({ beforeSpeakStatus: { realtime: { available: true, scope: 'session-b' } } }); await ui.context.startTalking({ realtime: true });
  await ui.controllers[0].speak('Committed answer.', () => true);
  assert.equal(ui.speech(), 0); assert.equal(ui.context.talkEnabled, false); assert.equal(ui.controllers[0].closed, true);
});
function speechFixture({ pendingFetch = null } = {}) {
  const played = []; const track = { enabled: true };
  class Audio {
    constructor(src) { this.src = src; this.events = {}; played.push(this); }
    addEventListener(type, callback) { this.events[type] = callback; }
    async play() { this.started = true; }
    pause() { this.paused = true; }
  }
  const context = vm.createContext({
    Audio, AbortSignal, URL: { createObjectURL: () => 'blob:voice', revokeObjectURL() {} }, window: { speechSynthesis: { cancel() {} } },
    voiceEnabled: true, hearingEnabled: true, speechGeneration: 0, activeSpeechOwner: null, lastPlaybackState: "idle", activeSpeechDone: null, activeSpeechAudio: null, talkSpeaking: false,
    microphoneStream: { getAudioTracks: () => [track] }, sharedVoicePack: {}, setStatus() {}, applyBodyAudioOutput: async () => {},
    bodyFetch: async () => { if (pendingFetch) await pendingFetch.promise; return { ok: true, blob: async () => ({}) }; },
    setTimeout: () => 1, clearTimeout() {},
  });
  vm.runInContext(playback, context); return { context, played, track };
}
test('mic stays muted and speech promise stays pending throughout Fish playback', async () => {
  const ui = speechFixture(); let finished = false;
  const speaking = ui.context.speakIntent({ text: 'Committed.' }).then(() => { finished = true; }); await settle();
  assert.equal(ui.played.length, 1); assert.equal(ui.played[0].started, true); assert.equal(ui.track.enabled, false); assert.equal(finished, false);
  ui.played[0].events.ended(); await speaking; assert.equal(ui.track.enabled, true); assert.equal(finished, true);
});
test('Voice cancellation during Fish fetch or playback prevents stale audio and restores Hearing', async () => {
  const wait = deferred(); const ui = speechFixture({ pendingFetch: wait }); const speaking = ui.context.speakIntent({ text: 'Committed.' });
  ui.context.voiceEnabled = false; ui.context.cancelBodySpeech(); wait.resolve(); await speaking;
  assert.equal(ui.played.length, 0); assert.equal(ui.track.enabled, true);
  const active = speechFixture(); const playing = active.context.speakIntent({ text: 'Committed.' }); await settle();
  active.context.voiceEnabled = false; active.context.cancelBodySpeech(); await playing;
  assert.equal(active.played[0].paused, true); assert.equal(active.track.enabled, true);
});

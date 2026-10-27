const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const markup = fs.readFileSync(path.join(__dirname, '../src/aicognitive_mind/static/live_body.html'), 'utf8');
function section(start, end) { return markup.slice(markup.indexOf(start), markup.indexOf(end)); }
const source = section('    async function bodyFetch(', '  </script>') +
  section('    async function refreshConnectedHostStatus(', '    function setSenseStatus(') +
  section('    function bodyIsBusy(', '    async function checkForBodyPageUpdate(') +
  section('    function cancelBodySpeech(', '    function resumeTalking(') +
  section('    function stopTalking(', '    async function startTalking(') +
  section('    async function consumeExpressionOutputs(', '    async function registerActiveBodySession(');
const settle = () => new Promise(resolve => setImmediate(resolve));
function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
}

function fixture({ fishStatus = 200, audioMode = 'play', browserMode = 'start', paused = false,
  ackFailures = 0, hostStatus = {}, hostStatusCode = 200,
  initialQueue = [{ delivery: 'voice-1', text: 'Committed answer.' }] } = {}) {
  const calls = [], audios = [], utterances = [], statuses = [], sources = [], timers = new Map();
  const queue = [...initialQueue];
  const track = { enabled: true };
  let timerSequence = 0, resumeCount = 0, cancelCount = 0, nextResponse = null;
  class Audio {
    constructor(src) { this.src = src; this.events = {}; audios.push(this); }
    addEventListener(name, callback) { this.events[name] = callback; }
    play() {
      calls.push({ stage: 'play' });
      if (audioMode === 'reject') return Promise.reject(new Error('Autoplay prevented'));
      if (audioMode === 'never') return new Promise(() => {});
      return Promise.resolve();
    }
    pause() { this.paused = true; }
  }
  class EventSource {
    constructor(url) { this.url = url; this.events = {}; sources.push(this); }
    addEventListener(name, callback) { this.events[name] = callback; }
    close() { this.closed = true; }
  }
  class SpeechSynthesisUtterance { constructor(text) { this.text = text; } }
  const speechSynthesis = {
    paused,
    cancel() { cancelCount++; },
    resume() { resumeCount++; this.paused = false; },
    speak(utterance) {
      utterances.push(utterance);
      if (browserMode === 'reject') queueMicrotask(() => utterance.onerror({ error: 'not-allowed' }));
      else if (browserMode === 'start' && !this.paused) queueMicrotask(() => utterance.onstart());
    },
  };
  const context = vm.createContext({
    Audio, EventSource, SpeechSynthesisUtterance, AbortSignal, Headers, Set,
    URL: { createObjectURL: () => 'blob:synthetic-voice', revokeObjectURL() {} },
    window: { speechSynthesis },
    voiceEnabled: true, hearingEnabled: true, speechGeneration: 0, activeSpeechDone: null,
    activeSpeechAudio: null, activeSpeechOwner: null, lastPlaybackState: "idle", talkSpeaking: false, mouthPollBusy: false, mouthDrainRequested: false,
    realtimeRequested: false, realtimeGeneration: 0, realtimeTurns: null, realtimeEvents: null, realtimePeer: null, realtimeMicrophone: null, realtimeScope: null, realtimeAudio: null, talkEnabled: false, talkListening: false, talkBusy: false, talkRestartTimer: null,
    mouthEvents: null, playedMouthDeliveries: new Set(), bodySessionId: 'synthetic-body',
    microphoneStream: { getAudioTracks: () => [track] }, sharedVoicePack: {}, voices: [],
    recorder: null, sensoryRequestInFlight: false, sendInteractionButton: { disabled: false },
    document: { hidden: false }, connectedHostStatus: { dataset: {}, textContent: '' },
    setStatus: message => statuses.push(message), loadVoices() {}, applyVoicePack() {},
    applyBodyAudioOutput: async () => {},
    responseErrorMessage: async response => (await response.json()).detail,
    setTimeout(callback, ms) { const id = ++timerSequence; timers.set(id, { callback, ms }); return id; },
    clearTimeout(id) { timers.delete(id); },
    fetch: async (url, options = {}) => {
      calls.push({ stage: url, options });
      if (url === '/v1/body/hosts/status') return new Response(JSON.stringify(hostStatus), { status: hostStatusCode });
      if (url === '/v1/body/mouth/next') {
        if (nextResponse) { const response = nextResponse; nextResponse = null; return response; }
        const head = queue[0];
        return new Response(JSON.stringify(head ? { text: head.text } : null), {
          headers: head ? { 'X-Body-Delivery': head.delivery } : {},
        });
      }
      if (url.startsWith('/v1/body/mouth/ack?')) {
        if (ackFailures-- > 0) return new Response('{}', { status: 503 });
        if (queue[0]?.delivery === new URL(url, 'https://example.test').searchParams.get('delivery_id')) queue.shift();
        return new Response('{"acknowledged":true}');
      }
      if (url === '/v1/body/speech/fish-audio') {
        return fishStatus === 200 ? new Response(new Uint8Array([1, 2, 3])) :
          new Response('{"detail":"Synthesizer unavailable"}', { status: fishStatus });
      }
      throw new Error('Unexpected request: ' + url);
    },
  });
  vm.runInContext(source, context);
  return { context, queue, calls, audios, utterances, statuses, sources, timers, track, speechSynthesis,
    get resumeCount() { return resumeCount; }, get cancelCount() { return cancelCount; },
    nextResponse(response) { nextResponse = response; },
    fire(ms) {
      const [id, timer] = [...timers.entries()].find(([, timer]) => timer.ms === ms) || [];
      assert.ok(timer, `Expected a ${ms}ms timer`); timers.delete(id); timer.callback();
    },
  };
}

function acknowledgments(ui) { return ui.calls.filter(call => call.stage.startsWith('/v1/body/mouth/ack?')); }

test('the durable Mouth receipt is acknowledged only after completed playback', async () => {
  const ui = fixture();
  const pending = ui.context.consumeExpressionOutputs();
  await settle();
  assert.equal(ui.audios.length, 1);
  assert.equal(acknowledgments(ui).length, 0);
  assert.equal(ui.queue.length, 1);
  assert.equal(ui.track.enabled, false);
  assert.equal(ui.context.bodyIsBusy(), true, 'A page update cannot interrupt active Mouth delivery.');
  ui.audios[0].events.ended();
  assert.equal(await pending, true);
  assert.equal(acknowledgments(ui).length, 1);
  assert.equal(ui.queue.length, 0);
  assert.equal(ui.track.enabled, true);
  assert.equal(ui.context.mouthPollBusy, false);
  assert.equal(ui.context.bodyIsBusy(), false);
  assert.equal(ui.calls.find(call => call.stage === '/v1/body/mouth/next').options.acknowledgeDelivery, undefined);
});

test('failed Fish and browser playback retain the receipt and surface the failure without replaying', async () => {
  const ui = fixture({ audioMode: 'reject', browserMode: 'reject' });
  ui.context.connectMouthEvents();
  ui.sources[0].events['voice-ready']();
  await settle(); await settle();
  assert.equal(acknowledgments(ui).length, 0);
  assert.equal(ui.queue.length, 1);
  assert.match(ui.statuses.at(-1), /Voice playback failed:.*not-allowed/);
  assert.equal(ui.context.mouthPollBusy, false);
  assert.equal(ui.audios.length, 1);
  assert.equal(ui.utterances.length, 1);
  assert.equal(ui.track.enabled, true);
});

test('Voice cancellation retains the unplayed intent and does not acknowledge it', async () => {
  for (const voiceOff of [true, false]) {
    const ui = fixture();
    const pending = ui.context.consumeExpressionOutputs();
    await settle();
    if (voiceOff) ui.context.voiceEnabled = false;
    // Realtime failure also cancels speech while Voice itself remains enabled.
    ui.context.cancelBodySpeech();
    assert.equal(await pending, false);
    assert.equal(acknowledgments(ui).length, 0);
    assert.equal(ui.queue.length, 1);
    assert.equal(ui.audios[0].paused, true);
    assert.equal(ui.track.enabled, true);
  }
});

test('Realtime failure leaves independently queued Mouth playback and its microphone mute intact', async () => {
  const ui = fixture();
  const pending = ui.context.consumeExpressionOutputs();
  await settle();
  assert.equal(ui.context.activeSpeechOwner, 'mouth');
  assert.equal(ui.context.lastPlaybackState, 'started');
  ui.context.stopTalking('Realtime tool import failed.');
  assert.equal(ui.audios[0].paused, undefined);
  assert.equal(ui.context.lastPlaybackState, 'started');
  assert.equal(ui.track.enabled, false);
  assert.equal(acknowledgments(ui).length, 0);
  ui.audios[0].events.ended();
  assert.equal(await pending, true);
  assert.equal(ui.context.lastPlaybackState, 'completed');
  assert.equal(acknowledgments(ui).length, 1);
});

test('Realtime teardown cancels its own speech without acknowledging or affecting the Mouth queue', async () => {
  const ui = fixture();
  const pending = ui.context.speakIntent({ text: 'Realtime reply.' }, () => true, async () => true, 'realtime');
  await settle();
  assert.equal(ui.context.activeSpeechOwner, 'realtime');
  ui.context.stopTalking('Realtime voice disconnected.');
  assert.equal(await pending, false);
  assert.equal(ui.context.lastPlaybackState, 'cancelled');
  assert.equal(ui.audios[0].paused, true);
  assert.equal(acknowledgments(ui).length, 0);
  assert.equal(ui.queue.length, 1);
});

test('host reconciliation can close unavailable Realtime without interrupting current-host Mouth speech', async () => {
  const ui = fixture({ hostStatus: {
    connected: true, host: { name: 'Existing host' }, requests: {},
    realtime: { available: false, scope: 'same-account-session' },
  } });
  const pending = ui.context.consumeExpressionOutputs();
  await settle();
  ui.context.realtimeRequested = true;
  ui.context.talkEnabled = true;
  ui.context.realtimeScope = 'same-account-session';
  await ui.context.refreshConnectedHostStatus();
  assert.equal(ui.context.talkEnabled, false);
  assert.equal(ui.audios[0].paused, undefined);
  assert.equal(ui.context.connectedHostStatus.dataset.state, 'connected');
  ui.audios[0].events.ended();
  assert.equal(await pending, true);
  assert.equal(acknowledgments(ui).length, 1);
});

test('an ended authenticated account session still cancels all stale speech without acknowledging it', async () => {
  const ui = fixture({ hostStatusCode: 401 });
  const pending = ui.context.consumeExpressionOutputs();
  await settle();
  await ui.context.refreshConnectedHostStatus();
  assert.equal(await pending, false);
  assert.equal(ui.audios[0].paused, true);
  assert.equal(ui.context.lastPlaybackState, 'cancelled');
  assert.equal(acknowledgments(ui).length, 0);
  assert.equal(ui.queue.length, 1);
});

test('a browser utterance that never starts fails at the start deadline, not the speaking-duration deadline', async () => {
  const ui = fixture({ fishStatus: 502, browserMode: 'never' });
  const pending = ui.context.consumeExpressionOutputs();
  const failure = assert.rejects(pending, /Voice playback did not start/);
  await settle();
  assert.deepEqual([...ui.timers.values()].map(timer => timer.ms), [10_000]);
  ui.fire(10_000);
  await failure;
  assert.equal(acknowledgments(ui).length, 0);
  assert.equal(ui.queue.length, 1);
  assert.equal(ui.context.mouthPollBusy, false);
  assert.equal(ui.track.enabled, true);
  assert.equal(ui.timers.size, 0);
  assert.ok(ui.cancelCount >= 2, 'A timed-out utterance must be cancelled before it can start late.');
});

test('an ended event without observed playback start cannot acknowledge silent speech', async () => {
  const ui = fixture({ fishStatus: 502, browserMode: 'never' });
  const pending = ui.context.consumeExpressionOutputs();
  const failure = assert.rejects(pending, /Voice playback did not start/);
  await settle();
  ui.utterances[0].onend();
  await failure;
  assert.equal(acknowledgments(ui).length, 0);
  assert.equal(ui.queue.length, 1);
  assert.equal(ui.context.mouthPollBusy, false);
  assert.equal(ui.track.enabled, true);
});

test('a media play promise that never starts is bounded before the browser fallback', async () => {
  const ui = fixture({ audioMode: 'never', browserMode: 'reject' });
  const pending = ui.context.consumeExpressionOutputs();
  const failure = assert.rejects(pending, /not-allowed/);
  await settle();
  assert.deepEqual([...ui.timers.values()].map(timer => timer.ms), [10_000]);
  ui.fire(10_000);
  await failure;
  assert.equal(ui.audios[0].paused, true);
  assert.equal(ui.queue.length, 1);
  assert.equal(acknowledgments(ui).length, 0);
});

test('paused browser speech resumes and receives the long deadline only after it starts', async () => {
  const ui = fixture({ fishStatus: 502, paused: true });
  const pending = ui.context.consumeExpressionOutputs();
  await settle();
  assert.equal(ui.resumeCount, 1);
  assert.deepEqual([...ui.timers.values()].map(timer => timer.ms), [180_000]);
  assert.equal(acknowledgments(ui).length, 0);
  ui.utterances[0].onend();
  assert.equal(await pending, true);
  assert.equal(ui.queue.length, 0);
  assert.equal(acknowledgments(ui).length, 1);
});

test('an acknowledgment retry never replays audio that already finished', async () => {
  const ui = fixture({ ackFailures: 1 });
  const pending = ui.context.consumeExpressionOutputs();
  const failure = assert.rejects(pending, /acknowledgment failed/);
  await settle();
  ui.audios[0].events.ended();
  await failure;
  assert.equal(ui.queue.length, 1);
  assert.equal(ui.audios.length, 1);
  assert.equal(await ui.context.consumeExpressionOutputs(), true);
  assert.equal(ui.audios.length, 1);
  assert.equal(acknowledgments(ui).length, 2);
  assert.equal(ui.queue.length, 0);
});

test('concurrent SSE and response drains share one playback and one acknowledgment', async () => {
  const ui = fixture();
  const first = ui.context.consumeExpressionOutputs();
  await settle();
  assert.equal(await ui.context.consumeExpressionOutputs(), false);
  assert.equal(ui.audios.length, 1);
  ui.audios[0].events.ended();
  assert.equal(await first, true);
  assert.equal(ui.audios.length, 1);
  assert.equal(acknowledgments(ui).length, 1);
});

test('a readiness event during the final empty response is retained until the busy drain can recheck', async () => {
  const ui = fixture({ initialQueue: [] });
  const oldEmptyResponse = deferred();
  ui.nextResponse(oldEmptyResponse.promise);
  const first = ui.context.consumeExpressionOutputs();
  await settle();
  ui.queue.push({ delivery: 'arrived-during-drain', text: 'New committed answer.' });
  assert.equal(await ui.context.consumeExpressionOutputs(), false);
  oldEmptyResponse.resolve(new Response('null'));
  await settle();
  assert.equal(ui.audios.length, 1);
  ui.audios[0].events.ended();
  await first;
  assert.equal(ui.queue.length, 0);
  assert.equal(acknowledgments(ui).length, 1);
});

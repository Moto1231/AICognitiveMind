const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const markup = fs.readFileSync(path.join(__dirname, '../src/aicognitive_mind/static/live_body.html'), 'utf8');
const start = markup.indexOf('    async function startTalking() {');
const end = markup.indexOf('\n    async function consumeExpressionOutputs()', start);
assert.ok(start >= 0 && end > start, 'Realtime startup exists');

function realtimeStartup({ status = {}, statusOk = true, statusError = null } = {}) {
  const requests = [];
  const messages = [];
  const peers = [];
  let microphoneRequests = 0;
  const track = { kind: 'audio' };
  class Peer {
    constructor() { peers.push(this); this.tracks = []; }
    addTrack(value) { this.tracks.push(value); }
    createDataChannel() { return { addEventListener() {} }; }
    async createOffer() { return { type: 'offer', sdp: 'synthetic-offer' }; }
    async setLocalDescription(offer) { this.localDescription = offer; }
    async setRemoteDescription(answer) { this.remoteDescription = answer; }
  }
  const context = vm.createContext({
    window: { RTCPeerConnection: Peer }, RTCPeerConnection: Peer,
    navigator: { mediaDevices: { getUserMedia: async constraints => {
      microphoneRequests += 1;
      assert.deepEqual(JSON.parse(JSON.stringify(constraints)), { audio: true });
      return { getAudioTracks: () => [track] };
    } } },
    talkEnabled: false, talkBusy: false, talkListening: false,
    realtimePeer: null, realtimeMicrophone: null, realtimeEvents: null,
    setStatus: message => messages.push(message),
    stopTalking: message => { messages.push(message); context.talkEnabled = false; context.talkBusy = false; },
    bodyMediaConstraints: () => ({ audio: true }),
    bodyFetch: async (url, options = {}) => {
      requests.push({ url, method: options.method || 'GET', body: options.body });
      if (url === '/v1/body/hosts/status') {
        if (statusError) throw statusError;
        return { ok: statusOk, json: async () => status };
      }
      assert.equal(url, '/v1/body/realtime/session');
      return { ok: true, text: async () => 'synthetic-answer' };
    },
  });
  vm.runInContext(markup.slice(start, end), context);
  return { context, requests, messages, peers, microphoneRequests: () => microphoneRequests };
}

test('an unavailable account Realtime capability blocks microphone and session creation', async () => {
  const reason = 'Realtime voice is not configured for this account.';
  const ui = realtimeStartup({ status: { realtime: { available: false, reason } } });
  await ui.context.startTalking();
  assert.deepEqual(ui.requests, [{ url: '/v1/body/hosts/status', method: 'GET', body: undefined }]);
  assert.equal(ui.microphoneRequests(), 0);
  assert.equal(ui.peers.length, 0);
  assert.equal(ui.context.talkEnabled, false);
  assert.deepEqual(ui.messages, [reason]);
});

test('missing or unreadable Realtime capability never starts capture or posts a session', async () => {
  for (const options of [{ status: {} }, { statusOk: false }, { statusError: new Error('offline') }]) {
    const ui = realtimeStartup(options);
    await ui.context.startTalking();
    assert.equal(ui.microphoneRequests(), 0);
    assert.equal(ui.peers.length, 0);
    assert.equal(ui.requests.length, 1);
    assert.equal(ui.requests[0].url, '/v1/body/hosts/status');
    assert.match(ui.messages.at(-1), /Realtime voice is unavailable|availability could not be checked/);
    assert.equal(ui.context.talkEnabled, false);
  }
});

test('an available Realtime capability preserves microphone and SDP session startup', async () => {
  const ui = realtimeStartup({ status: { realtime: { available: true } } });
  await ui.context.startTalking();
  assert.deepEqual(ui.requests, [
    { url: '/v1/body/hosts/status', method: 'GET', body: undefined },
    { url: '/v1/body/realtime/session', method: 'POST', body: 'synthetic-offer' },
  ]);
  assert.equal(ui.microphoneRequests(), 1);
  assert.equal(ui.peers.length, 1);
  assert.equal(ui.peers[0].tracks.length, 1);
  assert.deepEqual(JSON.parse(JSON.stringify(ui.peers[0].remoteDescription)), { type: 'answer', sdp: 'synthetic-answer' });
  assert.equal(ui.context.talkEnabled, true);
  assert.equal(ui.messages.at(-1), 'Connecting Axiom voice…');
});

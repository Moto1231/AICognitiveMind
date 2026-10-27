const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const markup = fs.readFileSync(path.join(__dirname, '../src/aicognitive_mind/static/live_body.html'), 'utf8');
const source = markup.slice(markup.indexOf('    async function registerActiveBodySession('), markup.indexOf('    async function showMindResult('));
function fixture() {
  const requests = [];
  const context = vm.createContext({
    AbortSignal,
    hearingEnabled: true, voiceEnabled: true, document: { hidden: false },
    microphoneStream: { getAudioTracks: () => [{ readyState: 'live', enabled: true }] },
    realtimeRequested: false, talkEnabled: false, talkBusy: false, lastPlaybackState: 'idle',
    bodyFetch: async (url, options) => { requests.push({ url, options }); },
  });
  vm.runInContext(source, context);
  return { context, requests, state: () => JSON.parse(requests.at(-1).options.body).client_state };
}

test('the active Body heartbeat reports only bounded operational flags for the current receiving page', async () => {
  const ui = fixture();
  await ui.context.registerActiveBodySession();
  const state = ui.state();
  assert.deepEqual(state, {
    client_revision: '20261027-host-recovery', hearing: true, voice: true, page_visible: true,
    microphone_live: true, microphone_enabled: true, voice_mode: 'connected_host', last_playback: 'idle',
  });
  assert.equal(ui.requests[0].url, '/v1/body/session/active');
  assert.equal(ui.requests[0].options.method, 'POST');
  assert.equal(ui.requests[0].options.headers['Content-Type'], 'application/json');
  assert.deepEqual(Object.keys(JSON.parse(ui.requests[0].options.body)), ['client_state']);
});

test('hidden, muted and stopped inputs remain distinct from voice selection and playback status', async () => {
  const ui = fixture();
  ui.context.document.hidden = true;
  ui.context.lastPlaybackState = 'completed';
  ui.context.microphoneStream = { getAudioTracks: () => [{ readyState: 'live', enabled: false }] };
  await ui.context.registerActiveBodySession();
  assert.equal(ui.state().page_visible, false);
  assert.equal(ui.state().microphone_live, true);
  assert.equal(ui.state().microphone_enabled, false);
  assert.equal(ui.state().last_playback, 'completed');
  ui.context.hearingEnabled = false;
  ui.context.voiceEnabled = false;
  ui.context.microphoneStream = { getAudioTracks: () => [{ readyState: 'ended', enabled: true }] };
  await ui.context.registerActiveBodySession();
  assert.equal(ui.state().hearing, false);
  assert.equal(ui.state().voice, false);
  assert.equal(ui.state().voice_mode, 'off');
  assert.equal(ui.state().microphone_live, false);
  assert.equal(ui.state().microphone_enabled, false);
});

test('only an explicitly selected Realtime connection reports the Realtime mode', async () => {
  const ui = fixture();
  ui.context.talkBusy = true;
  await ui.context.registerActiveBodySession();
  assert.equal(ui.state().voice_mode, 'connected_host', 'An unrelated text request is not a Realtime connection.');
  ui.context.realtimeRequested = true;
  await ui.context.registerActiveBodySession();
  assert.equal(ui.state().voice_mode, 'realtime');
});

test('heartbeat requests never overlap and a failed request does not suppress later state', async () => {
  const ui = fixture();
  let reject;
  const pending = new Promise((resolve, fail) => { reject = fail; });
  let attempts = 0;
  ui.context.bodyFetch = async () => { attempts++; await pending; };
  const first = ui.context.registerActiveBodySession();
  await ui.context.registerActiveBodySession();
  assert.equal(attempts, 1);
  reject(new Error('Synthetic network failure; no error text belongs in client_state.'));
  await first;
  ui.context.bodyFetch = async () => { attempts++; };
  await ui.context.registerActiveBodySession();
  assert.equal(attempts, 2);
  assert.equal(ui.context.registerActiveBodySession.inFlight, false);
});

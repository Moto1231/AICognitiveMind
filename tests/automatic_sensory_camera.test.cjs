const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const markup = fs.readFileSync(
  path.join(__dirname, '../src/aicognitive_mind/static/live_body.html'), 'utf8'
);
const cameraRequest = markup.slice(
  markup.indexOf('    async function checkForHostCameraRequest()'),
  markup.indexOf('    let pageSourceSnapshot = null;')
);
const settle = () => new Promise(resolve => setImmediate(resolve));

test('native camera delivery completes while automatic interpretation is still pending', async () => {
  let resolveInterpretation;
  let interpretationFinished = false;
  const interpretation = new Promise(resolve => { resolveInterpretation = resolve; });
  const calls = [];
  const deliveries = [];
  const messages = [];
  const image = 'data:image/jpeg;base64,bmF0aXZlLWNhbWVyYS1mcmFtZQ==';
  const stream = { getVideoTracks: () => [{}], getTracks: () => [] };
  const context = vm.createContext({
    visionEnabled: true,
    boundedLookActive: false,
    hostCameraRequestBusy: false,
    hostCameraNextPollAt: 0,
    hostCameraPollDelayMs: 2500,
    MAX_LOOK_SECONDS: 30,
    cameraStream: stream,
    liveScene: { srcObject: stream, paused: false, videoWidth: 1280, videoHeight: 720 },
    canvas: {
      width: 0,
      height: 0,
      getContext: () => ({ drawImage() {} }),
      toDataURL: () => image,
    },
    delay: async () => {},
    setStatus: message => messages.push(message),
    responseErrorMessage: async () => 'Request failed',
    bodyFetch: async (url, options = {}) => {
      calls.push(url);
      if (url === '/v1/body/camera/request') {
        return { ok: true, status: 200, json: async () => ({ request_id: 'camera-1', seconds: 1 }) };
      }
      if (url === '/v1/body/eyes/observe') {
        await interpretation;
        interpretationFinished = true;
        return { ok: true, json: async () => ({ interpretation: 'A camera frame.' }) };
      }
      assert.equal(url, '/v1/body/camera/complete');
      deliveries.push(JSON.parse(options.body));
      return { ok: true };
    },
  });
  vm.runInContext(cameraRequest, context);

  const capture = context.checkForHostCameraRequest();
  try {
    await settle();
    assert.equal(interpretationFinished, false);
    assert.equal(deliveries.length, 1,
      'The host must receive its native image before it can consume an interpretation queued back to it.');
    assert.deepEqual(deliveries[0], {
      request_id: 'camera-1', image_data_url: image, width: 960, height: 540,
    });
    assert.ok(calls.includes('/v1/body/eyes/observe'), 'Automatic sensory admission must still occur.');
  } finally {
    resolveInterpretation();
    await capture;
  }
  assert.equal(context.hostCameraRequestBusy, false);
  assert.equal(interpretationFinished, true);
  assert.ok(messages.some(message => message.includes('delivered to reasoning host')));
});

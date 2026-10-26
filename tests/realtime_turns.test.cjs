const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const source = fs.readFileSync(path.join(__dirname, '../src/aicognitive_mind/static/realtime_turns.js'), 'utf8');
const loaded = import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const settle = () => new Promise(resolve => setImmediate(resolve));
const context = { summary: 'Current voice conversation.', participants: [] };

async function fixture(options = {}) {
  const { RealtimeTurns } = await loaded;
  const sent = [], spoken = [], failures = [];
  let timeout;
  const controller = new RealtimeTurns({
    send: event => sent.push(event),
    speak: async (text, current) => { if (current()) spoken.push(text); },
    fail: reason => failures.push(reason),
    setTimer: callback => { timeout = callback; return 1; }, clearTimer() {},
    ...options,
  });
  let nextId = 0;
  const call = (name, args, result, extra = {}) => {
    const id = extra.id || `call-${++nextId}`;
    controller.handle({ type: 'response.mcp_call.in_progress', item_id: id });
    controller.handle({ type: 'response.mcp_call_arguments.done', item_id: id, arguments: JSON.stringify(args) });
    const item = { id, type: 'mcp_call', name, server_label: 'axiom', output: JSON.stringify(result), ...extra };
    controller.handle({ type: 'response.output_item.done', item });
    return item;
  };
  const ready = () => controller.handle({ type: 'conversation.item.done', item: {
    type: 'mcp_list_tools', server_label: 'axiom', tools: [{ name: 'begin_interaction' }, { name: 'complete_interaction' }],
  } });
  const transcript = (text = 'Hello Axiom.', id = 'audio-1') => controller.handle({
    type: 'conversation.item.input_audio_transcription.completed', transcript: text, item_id: id,
  });
  const begin = (args = {}, result = {}) => call('begin_interaction', { user_message: 'Hello Axiom.', ...args }, {
    status: 'ready_to_reason', idempotency_key: 'key-1', host_working_context: context, ...result,
  });
  const complete = (args = {}, result = {}, extra = {}) => call('complete_interaction', {
    user_message: 'Hello Axiom.', response_text: 'Hello Will.', idempotency_key: 'key-1', host_working_context: context, ...args,
  }, { status: 'interaction_committed', interaction_trace_id: 'key-1', host_working_context: context, ...result }, extra);
  const done = (id, output = []) => controller.handle({ type: 'response.done', response: { id, status: 'completed', output } });
  const beginReady = async () => { begin(); done('begin-phase'); await settle(); };
  return { controller, sent, spoken, failures, ready, transcript, call, begin, beginReady, complete, done, timeout: () => timeout() };
}

test('transcription waits for real MCP tool import and preserves session startup instructions', async () => {
  const ui = await fixture();
  ui.controller.handle({ type: 'session.created', session: { instructions: 'Restore foundational skills and ask when unsure.' } });
  ui.transcript();
  ui.controller.handle({ type: 'mcp_list_tools.completed' });
  await settle();
  assert.equal(ui.sent.length, 0);
  ui.ready(); await settle();
  assert.equal(ui.sent.length, 1);
  assert.match(ui.sent[0].response.instructions, /Restore foundational skills and ask when unsure/);
  assert.match(ui.sent[0].response.instructions, /Hello Axiom\./);
});

test('raw model text can never reach speech; exact committed completion speaks once', async () => {
  const ui = await fixture(); ui.ready(); ui.transcript(); await settle();
  ui.controller.handle({ type: 'response.output_text.done', text: 'Uncommitted text.' });
  assert.deepEqual(ui.spoken, []);
  await ui.beginReady();
  const item = ui.complete();
  assert.deepEqual(ui.spoken, []);
  ui.done('response-1'); await settle();
  ui.controller.handle({ type: 'response.output_item.done', item });
  ui.done('response-1'); await settle();
  assert.deepEqual(ui.spoken, ['Hello Will.']);
  assert.deepEqual(ui.failures, []);
});

test('response.done before MCP completion waits for terminal item and duplicate progress cannot strand it', async () => {
  const ui = await fixture(); ui.ready(); ui.transcript(); await settle();
  ui.controller.handle({ type: 'response.created', response: { id: 'r1' } });
  ui.controller.handle({ type: 'response.mcp_call.in_progress', response_id: 'r1', item_id: 'begin' });
  ui.controller.handle({ type: 'response.mcp_call.in_progress', response_id: 'r1', item_id: 'begin' });
  ui.done('r1', [{ id: 'begin', type: 'mcp_call', name: 'begin_interaction', arguments: '{"user_message":"Hello Axiom."}', server_label: 'axiom', output: null, error: null }]);
  assert.equal(ui.sent.length, 1);
  ui.call('begin_interaction', { user_message: 'Hello Axiom.' }, {
    status: 'ready_to_reason', idempotency_key: 'key-1', host_working_context: context,
  }, { id: 'begin' });
  await settle();
  assert.equal(ui.sent.length, 2);
  ui.done('r1');
  assert.equal(ui.sent.length, 2);
  ui.controller.handle({ type: 'response.created', response: { id: 'r2' } });
  ui.complete(); ui.done('r2'); await settle();
  assert.deepEqual(ui.spoken, ['Hello Will.']);
});

test('exact transcript, successful begin status, key, receipt, and payload identity are required', async () => {
  const variants = [
    async ui => ui.begin({ user_message: 'A different turn.' }),
    async ui => ui.begin({}, { status: 'failed' }),
    async ui => ui.begin({}, { idempotency_key: 123 }),
    async ui => { await ui.beginReady(); ui.complete({ idempotency_key: 'other' }); },
    async ui => { await ui.beginReady(); ui.complete({ user_message: 'different' }); },
    async ui => { await ui.beginReady(); ui.complete({}, { interaction_trace_id: 'other' }); },
    async ui => { await ui.beginReady(); ui.complete(); ui.complete({ response_text: 'Replaced answer.' }); },
    async ui => { ui.begin(); ui.begin(); },
  ];
  for (const variant of variants) {
    const ui = await fixture(); ui.ready(); ui.transcript(); await settle(); await variant(ui); ui.done('r'); await settle();
    assert.deepEqual(ui.spoken, []);
    assert.equal(ui.failures.length, 1);
  }
});

test('MCP content wrappers parse but error-bearing receipts never authorize speech', async () => {
  for (const error of [undefined, { message: 'failed' }]) {
    const ui = await fixture(); ui.ready(); ui.transcript(); await settle(); await ui.beginReady();
    ui.complete({}, { structuredContent: { status: 'interaction_committed', interaction_trace_id: 'key-1', host_working_context: context } }, { error });
    ui.done('r'); await settle();
    assert.deepEqual(ui.spoken, error ? [] : ['Hello Will.']);
  }
  const ui = await fixture(); ui.ready(); ui.transcript(); await settle();
  ui.call('begin_interaction', { user_message: 'Hello Axiom.' }, { content: [{ type: 'text', text: JSON.stringify({
    status: 'ready_to_reason', idempotency_key: 'key-1', host_working_context: context,
  }) }] });
  ui.done('begin-phase'); await settle();
  ui.complete(); ui.done('r'); await settle();
  assert.deepEqual(ui.spoken, ['Hello Will.']);
});

test('failed completion gets one unchanged retry and a changed retry fails closed', async () => {
  for (const changed of [false, true]) {
    const ui = await fixture(); ui.ready(); ui.transcript(); await settle(); await ui.beginReady();
    ui.complete({}, { status: 'failed' }); ui.done('r1'); await settle();
    assert.equal(ui.sent.length, 3);
    ui.complete(changed ? { response_text: 'A changed answer.' } : {}); ui.done('r2'); await settle();
    assert.deepEqual(ui.spoken, changed ? [] : ['Hello Will.']);
    assert.equal(ui.failures.length, changed ? 1 : 0);
  }
  const ui = await fixture(); ui.ready(); ui.transcript(); await settle(); await ui.beginReady();
  ui.complete({}, { status: 'failed' }); ui.done('r1'); await settle();
  ui.complete({}, { status: 'failed' }); ui.done('r2'); await settle();
  assert.equal(ui.failures.length, 1);
  assert.deepEqual(ui.spoken, []);
});

test('queued turns wait for playback completion and inherit committed bounded context', async () => {
  let release;
  const spoken = [];
  const ui = await fixture({ speak: text => { spoken.push(text); return new Promise(resolve => { release = resolve; }); } });
  ui.ready(); ui.transcript(); ui.transcript('Next question.', 'audio-2'); ui.transcript('Next question.', 'audio-2'); await settle();
  await ui.beginReady(); ui.complete(); ui.done('r1'); await settle();
  assert.equal(ui.sent.length, 2);
  release(); await settle();
  assert.equal(ui.sent.length, 3);
  assert.match(ui.sent[2].response.instructions, /Next question/);
  assert.match(ui.sent[2].response.instructions, /Current voice conversation/);
  assert.deepEqual(spoken, ['Hello Will.']);
  ui.controller.close();
});

test('close, tool import failure, invalid context, timeout, and tool-free response withhold speech', async () => {
  for (const action of [
    async ui => { ui.controller.close(); ui.begin(); ui.complete(); },
    async ui => ui.controller.handle({ type: 'mcp_list_tools.failed' }),
    async ui => { await ui.beginReady(); ui.complete({}, { host_working_context: { summary: 'x'.repeat(2001) } }); },
    async ui => ui.timeout(),
    async ui => {},
  ]) {
    const ui = await fixture(); ui.ready(); ui.transcript(); await settle(); await action(ui); ui.done('r1'); await settle();
    assert.deepEqual(ui.spoken, []);
    assert.equal(ui.controller.closed, true);
  }
});

test('tool-import readiness has a finite deadline even before a transcript can start', async () => {
  const ui = await fixture(); ui.transcript(); ui.timeout(); await settle();
  assert.equal(ui.sent.length, 0); assert.equal(ui.controller.closed, true);
  assert.match(ui.failures[0], /tools did not become ready/);
});

test('requested camera work waits for successful begin and cancellation discards a late observation', async () => {
  let calls = 0, release;
  const prepared = new Promise(resolve => { release = resolve; });
  const ui = await fixture({ prepare: async () => { calls++; return prepared; } });
  ui.ready(); ui.transcript(); await settle(); assert.equal(calls, 0);
  ui.begin(); assert.equal(calls, 0);
  ui.done('begin-phase'); await settle(); assert.equal(calls, 1); assert.equal(ui.sent.length, 1);
  ui.controller.close(); release('Observed evidence.'); await settle();
  assert.equal(ui.sent.length, 1); assert.deepEqual(ui.spoken, []);
});

test('prepared camera evidence and recalled context persist through completion retry continuations', async () => {
  const ui = await fixture({ prepare: async () => 'Camera evidence receipt sha256:abc.' });
  ui.ready(); ui.transcript(); await settle(); await ui.beginReady();
  assert.match(ui.sent[1].response.instructions, /sha256:abc/);
  ui.complete({}, { status: 'failed' }); ui.done('completion-1'); await settle();
  assert.match(ui.sent[2].response.instructions, /sha256:abc/);
  assert.match(ui.sent[2].response.instructions, /Current voice conversation/);
  ui.controller.close();
});

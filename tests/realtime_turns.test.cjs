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
  const ready = (additional = []) => controller.handle({ type: 'conversation.item.done', item: {
    type: 'mcp_list_tools', server_label: 'axiom', tools: ['begin_interaction', 'complete_interaction', ...additional].map(name => ({ name })),
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
  const beginReady = async (result = {}) => { begin({}, result); done('begin-phase'); await settle(); };
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

const naming = (count, complete = false) => ({
  experience_count: count, status: complete ? 'complete' : count < 1000 ? 'prohibited' : count < 2000 ? 'eligible' : 'required',
  selection_complete: complete, is_named: complete, has_pronouns: complete,
  autonomous_choice_allowed: !complete && count >= 1000,
  choice_required: !complete && count >= 2000, choice_required_before_completion: !complete && count >= 1999,
  eligible_at_event: 1000, required_at_event: 2000,
});
const choiceArguments = { user_message: 'Hello Axiom.', candidate_name: 'Delta', candidate_pronouns: 'they/them', rationale: 'A considered first joint choice.' };
const choiceReceipt = { accepted: true, candidate_name: 'Delta', current_name: 'Delta', candidate_pronouns: 'they/them', current_pronouns: 'they/them' };
const blockedNaming = {
  status: 'naming_choice_required', naming: naming(2000),
  presentation: { allowed: false, report_persistence_error: false, answer_frozen: true },
};

test('optional first choice may be deferred with either a current or a stale tool catalog', async () => {
  for (const tools of [[], ['propose_self_name']]) {
    const ui = await fixture(); ui.ready(tools); ui.transcript(); await settle();
    await ui.beginReady({ naming: naming(1000) });
    ui.complete({}, { naming: naming(1001), presentation: { allowed: true } }); ui.done('complete'); await settle();
    assert.deepEqual(ui.spoken, ['Hello Will.']); assert.deepEqual(ui.failures, []);
  }
});

test('a required or upcoming naming deadline with a stale catalog requests reconnect once', async () => {
  for (const count of [1999, 2000]) {
    let preparations = 0;
    const ui = await fixture({ prepare: async () => { preparations++; return ''; } });
    ui.ready(); ui.transcript(); await settle(); await ui.beginReady({ naming: naming(count) });
    ui.controller.handle({ type: 'error', error: { message: 'A later duplicate failure.' } });
    assert.equal(ui.controller.closed, true); assert.equal(ui.failures.length, 1);
    assert.match(ui.failures[0], /Reconnect voice.*required name and pronoun choice tool/);
    assert.equal(preparations, 0); assert.deepEqual(ui.spoken, []); assert.equal(ui.sent.length, 1);
  }
});

test('a refreshed tool catalog permits the required autonomous first choice before speech', async () => {
  const ui = await fixture(); ui.ready(); ui.transcript(); await settle();
  ui.begin({}, { naming: naming(1999) });
  ui.ready(['propose_self_name']); ui.done('begin-phase'); await settle();
  assert.match(ui.sent[1].response.instructions, /Before ordinary completion, choose your own name and pronouns/);
  ui.call('propose_self_name', choiceArguments, choiceReceipt); ui.done('choice'); await settle();
  assert.deepEqual(ui.spoken, []);
  assert.match(ui.sent[2].response.instructions, /joint naming choice committed/);
  ui.complete({}, { naming: naming(2001, true), presentation: { allowed: true } }); ui.done('complete'); await settle();
  assert.deepEqual(ui.spoken, ['Hello Will.']); assert.deepEqual(ui.failures, []);
});

test('a late naming deadline holds the frozen answer, accepts a choice, and preserves the completion retry allowance', async () => {
  const ui = await fixture(); ui.ready(['propose_self_name']); ui.transcript(); await settle();
  await ui.beginReady({ naming: naming(1998) });
  ui.complete({}, blockedNaming); ui.done('blocked'); await settle();
  assert.equal(ui.controller.closed, false); assert.deepEqual(ui.failures, []); assert.deepEqual(ui.spoken, []);
  assert.match(ui.sent[2].response.instructions, /ordinary answer is frozen/);
  assert.match(ui.sent[2].response.instructions, /"response_text":"Hello Will\."/);
  ui.call('propose_self_name', choiceArguments, choiceReceipt); ui.done('choice'); await settle();
  assert.match(ui.sent[3].response.instructions, /exactly these unchanged arguments/);
  ui.complete({}, { status: 'failed' }); ui.done('uncertain-complete'); await settle();
  assert.deepEqual(ui.spoken, []); assert.deepEqual(ui.failures, []);
  ui.complete({}, { naming: naming(2002, true), presentation: { allowed: true } }); ui.done('committed'); await settle();
  assert.deepEqual(ui.spoken, ['Hello Will.']); assert.deepEqual(ui.failures, []);
});

test('naming recovery cannot replace the held answer or complete before its choice commits', async () => {
  for (const action of [
    ui => ui.complete(),
    ui => { ui.call('propose_self_name', choiceArguments, choiceReceipt); ui.complete({ response_text: 'A replacement answer.' }); },
  ]) {
    const ui = await fixture(); ui.ready(['propose_self_name']); ui.transcript(); await settle();
    await ui.beginReady({ naming: naming(1998) }); ui.complete({}, blockedNaming); ui.done('blocked'); await settle();
    action(ui); ui.done('invalid-retry'); await settle();
    assert.equal(ui.failures.length, 1); assert.deepEqual(ui.spoken, []);
  }
});

test('a naming deadline reached on an uncertain retry is resolved before retrying again', async () => {
  const ui = await fixture(); ui.ready(['propose_self_name']); ui.transcript(); await settle();
  await ui.beginReady({ naming: naming(1998) });
  ui.complete({}, { status: 'failed' }); ui.done('uncertain'); await settle();
  ui.complete({}, blockedNaming); ui.done('blocked'); await settle();
  assert.match(ui.sent[3].response.instructions, /ordinary answer is frozen/);
  assert.doesNotMatch(ui.sent[3].response.instructions, /Retry the failed completion once/);
  ui.call('propose_self_name', choiceArguments, choiceReceipt); ui.done('choice'); await settle();
  ui.complete({}, { naming: naming(2001, true), presentation: { allowed: true } }); ui.done('committed'); await settle();
  assert.deepEqual(ui.spoken, ['Hello Will.']); assert.deepEqual(ui.failures, []);
});

test('naming calls require an imported tool, actual transcript, eligibility, and a matching accepted pair', async () => {
  const variants = [
    { tools: [], assessment: naming(1000), args: choiceArguments, receipt: choiceReceipt, reconnect: true },
    { assessment: naming(999), args: choiceArguments, receipt: choiceReceipt },
    { args: { ...choiceArguments, user_message: 'A different human turn.' }, receipt: choiceReceipt },
    { args: { ...choiceArguments, candidate_pronouns: ' ' }, receipt: choiceReceipt },
    { args: choiceArguments, receipt: { ...choiceReceipt, accepted: false } },
    { args: choiceArguments, receipt: { ...choiceReceipt, current_name: 'Other' } },
    { args: choiceArguments, receipt: { ...choiceReceipt, current_pronouns: 'she/her' } },
    { args: choiceArguments, receipt: { ...choiceReceipt, candidate_name: 'Other' } },
    { args: choiceArguments, receipt: choiceReceipt, extra: { error: { message: 'Governance failed.' } } },
  ];
  for (const variant of variants) {
    const ui = await fixture(); ui.ready(variant.tools || ['propose_self_name']); ui.transcript(); await settle();
    await ui.beginReady({ naming: variant.assessment || naming(1000) });
    ui.call('propose_self_name', variant.args, variant.receipt, variant.extra); ui.done('choice'); await settle();
    assert.equal(ui.failures.length, 1); assert.deepEqual(ui.spoken, []);
    if (variant.reconnect) assert.match(ui.failures[0], /Reconnect voice/);
  }
});

test('established identity stays established during ordinary work and cannot be chosen twice in a turn', async () => {
  const ui = await fixture(); ui.ready(['propose_self_name']); ui.transcript(); await settle();
  await ui.beginReady({ naming: naming(2000, true) });
  assert.match(ui.sent[1].response.instructions, /Preserve the established name and pronouns/);
  assert.doesNotMatch(ui.sent[1].response.instructions, /choose your own name and pronouns together with propose_self_name/);
  ui.complete({}, { naming: naming(2001, true) }); ui.done('complete'); await settle();
  assert.deepEqual(ui.spoken, ['Hello Will.']); assert.deepEqual(ui.failures, []);
  const duplicate = await fixture(); duplicate.ready(['propose_self_name']); duplicate.transcript(); await settle();
  await duplicate.beginReady({ naming: naming(1000) });
  duplicate.call('propose_self_name', choiceArguments, choiceReceipt);
  duplicate.call('propose_self_name', choiceArguments, choiceReceipt); duplicate.done('choice'); await settle();
  assert.equal(duplicate.failures.length, 1); assert.deepEqual(duplicate.spoken, []);
});

test('explicit presentation denial and malformed naming blocks never authorize voice', async () => {
  for (const receipt of [
    { presentation: { allowed: false, report_persistence_error: false } },
    { naming: naming(2000), presentation: { allowed: true } },
    { ...blockedNaming, naming: naming(1000) },
    { ...blockedNaming, presentation: { allowed: true } },
  ]) {
    const ui = await fixture(); ui.ready(['propose_self_name']); ui.transcript(); await settle();
    await ui.beginReady({ naming: naming(1998) }); ui.complete({}, receipt); ui.done('withheld'); await settle();
    assert.equal(ui.failures.length, 1); assert.deepEqual(ui.spoken, []);
  }
});

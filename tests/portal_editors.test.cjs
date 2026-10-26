const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../src/aicognitive_mind/static/portal.js'), 'utf8');
const editorFunctions = [
  'selectedEndpoint', 'renderTaskProfileEndpointOptions', 'fillSelect', 'modelCapabilityLabel', 'capabilityDocumentationSource',
  'loadEndpointIntoForm', 'renderEndpointModelStatus', 'endpointFormIsValid', 'syncEndpointDraft',
  'updateEndpointEditorState', 'editEndpoint', 'cancelEndpointEdit', 'saveProviderEndpoints',
  'refreshProviderEndpoints',
  'removeEndpoint', 'discoverTaskProfileModels', 'addTaskProfileEndpoint', 'applyEndpointTemplate',
  'prepareProviderConnections', 'saveProviderConnections', 'cancelProviderConnections', 'probeEndpointToolCalling',
  'selectedMcpServer', 'syncMcpServerForm', 'updateMcpEditorState', 'editMcpServer',
  'cancelMcpEdit', 'renderMcpServerOptions', 'loadMcpServerIntoForm', 'renderMcpTools',
  'addMcpServer', 'saveMcpServers', 'removeMcpServer', 'discoverMcpTools',
  'allTaskNames', 'renderTaskProfiles', 'taskEndpointOptions', 'selectedTaskBehaviorIds',
  'taskBehaviorCatalog',
  'taskProfileConfiguration', 'updateTaskSaveState', 'renderTaskBehaviorSelection',
  'syncTaskProviderRotation',
  'renderFallbackSelectors', 'openTaskProfile', 'closeTaskProfile', 'discardTaskProfileChanges',
  'saveTaskProfile',
  'updateTaskFoundationEditor', 'cancelTaskFoundationEdit', 'editTaskFoundation', 'saveTaskFoundation',
  'renderHostBehaviors', 'updateBehaviorSaveState', 'refreshHostBehaviors', 'editHostBehaviors',
  'cancelHostBehaviorEdit', 'addHostBehavior', 'saveHostBehaviors',
];

class Element {
  constructor(tag = 'input') {
    this.tagName = tag.toUpperCase();
    this.value = '';
    this.children = [];
    this.disabled = false;
    this.checked = false;
    this.listeners = {};
    this.dataset = {};
    this.style = {};
    this.attributes = {};
    this.classes = new Set();
    this.classList = {
      toggle: (name, on) => on ? this.classes.add(name) : this.classes.delete(name),
      add: name => this.classes.add(name), remove: name => this.classes.delete(name),
      contains: name => this.classes.has(name),
    };
  }
  get options() { return this.children; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return this.attributes[name] ?? null; }
  addEventListener(name, listener) { this.listeners[name] = listener; }
  focus() {}
}

function editor({ apiHandler } = {}) {
  let endpointSequence = 0;
  const el = new Proxy({}, { get: (target, name) => target[name] ||= new Element() });
  const state = {
    providerEndpoints: [{ id: 'openai', name: 'OpenAI - GPT', provider_name: 'OpenAI', model: 'gpt-test',
      base_url: 'https://provider.example/v1', api_key: 'test-key', models: ['gpt-test'], model_capabilities: {} }],
    activeEndpointId: 'openai', endpointDraft: null, endpointEditBaseline: '', endpointDiscovering: false,
    providerEndpointRevision: 0,
    mcpServers: [{ id: 'tools', name: 'Tools', url: 'https://tools.example/mcp', bearer_token: '',
      enabled: true, tools: [{ name: 'lookup', enabled: true }] }],
    activeMcpServerId: 'tools', mcpServerDraft: null, mcpEditBaseline: '', integrationSaving: false,
    taskModelAssignments: [{ task: 'vision', provider: 'openai', model: 'gpt-test',
      fallbacks: [{ provider: 'OpenAI - GPT', model: 'gpt-test' }] }],
    taskBehaviors: [], taskFoundations: {}, hostBehaviors: [], activeTaskProfile: null,
    taskFoundationDraft: null, taskFoundationSaving: false,
    hostBehaviorDraft: null, hostBehaviorSaving: false, hostBehaviorRevision: 0,
  };
  const calls = [];
  const toasts = [];
  const context = vm.createContext({
    state, el, URL, COMMON_ENDPOINT_PRESETS: [], crypto: { randomUUID: () => ++endpointSequence === 1 ? 'new-id' : `new-id-${endpointSequence}` },
    taskModelLabels: { reasoning: 'Reasoning', vision: 'Vision', audio_voice: 'Audio/Voice' },
    displayLabel: value => value,
    Option: class extends Element {
      constructor(label, value) { super('option'); this.textContent = label; this.value = value; }
    },
    document: { createElement: tag => new Element(tag), createTextNode: value => value },
    renderTaskProfiles() {}, refreshTaskModelAssignments: async () => {}, toast: (...args) => toasts.push(args),
    resetEndpointApiKeyVisibility() {}, toggleEndpointApiKeyVisibility() {},
    api: async (url, options = {}) => {
      const body = options.body ? JSON.parse(options.body) : undefined;
      calls.push({ url, body });
      if (apiHandler) return apiHandler(url, body, options);
      return body;
    },
  });
  const presetsStart = source.indexOf('const COMMON_ENDPOINT_PRESETS = [');
  const presetsEnd = source.indexOf('\n];', presetsStart);
  vm.runInContext(source.slice(presetsStart, presetsEnd + 3), context);
  for (const name of editorFunctions) {
    const start = source.search(new RegExp(`^(?:async )?function ${name}\\(`, 'm'));
    assert.ok(start >= 0, `${name} exists`);
    const next = source.slice(start + 1).search(/^(?:async )?function |^const |^let |^for |^document\.|^el\.|^if \(/m);
    vm.runInContext(source.slice(start, next < 0 ? source.length : start + 1 + next), context);
  }
  for (const name of ['resetEndpointApiKeyVisibility', 'toggleEndpointApiKeyVisibility']) {
    const start = source.search(new RegExp(`^(?:async )?function ${name}\\(`, 'm'));
    if (start < 0) continue;
    const next = source.slice(start + 1).search(/^(?:async )?function |^const |^let |^for |^document\.|^el\.|^if \(/m);
    vm.runInContext(source.slice(start, next < 0 ? source.length : start + 1 + next), context);
  }
  const primaryHandler = source.indexOf('el.taskProviderSelect.addEventListener("change", () => {');
  const primaryHandlerEnd = source.indexOf('\n});', primaryHandler);
  vm.runInContext(source.slice(primaryHandler, primaryHandlerEnd + 4), context);
  const behaviorBindings = source.indexOf('if (el.hostBehaviorSearch) el.hostBehaviorSearch.addEventListener');
  const behaviorBindingsEnd = source.indexOf('if (el.taskProfileBack)', behaviorBindings);
  vm.runInContext(source.slice(behaviorBindings, behaviorBindingsEnd), context);
  context.loadEndpointIntoForm();
  context.loadMcpServerIntoForm();
  return { ...context, calls, toasts };
}

test('missing capability details stay explicitly unverified without losing a saved model selection', () => {
  const ui = editor();
  const endpoint = ui.state.providerEndpoints[0];
  endpoint.models = ['other-model'];
  const before = JSON.stringify(endpoint);
  ui.loadEndpointIntoForm();
  assert.equal(ui.el.endpointModelSelect.value, endpoint.model);
  const saved = ui.el.endpointModelSelect.options.find(option => option.value === endpoint.model);
  assert.match(saved.textContent, /Capabilities not supplied; compatibility unverified/);
  assert.match(saved.textContent, /\(saved\)/);
  assert.match(ui.el.endpointModelStatus.textContent, /Capabilities not supplied; compatibility unverified/);
  assert.ok(ui.el.endpointModelStatus.children.includes(' · Tool calling has not been tested'));
  assert.equal(JSON.stringify(endpoint), before);
  assert.equal(ui.calls.length, 0);
});

test('provider documentation labels distinguish speech output and keep live tool verification separate', () => {
  const ui = editor();
  const endpoint = ui.state.providerEndpoints[0];
  endpoint.model = 'models/gemini-3.8-flash-tts';
  endpoint.models = [endpoint.model];
  endpoint.model_capabilities = { [endpoint.model]: ['Text Input', 'Audio Output'] };
  endpoint.model_capability_sources = {
    [endpoint.model]: 'https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash-tts',
  };
  ui.loadEndpointIntoForm();
  const option = ui.el.endpointModelSelect.options.find(item => item.value === endpoint.model);
  assert.match(option.textContent, /Text Input · Audio Output/);
  assert.doesNotMatch(option.textContent, /Tools|compatibility unverified/);
  const link = ui.el.endpointModelStatus.children.find(item => item?.tagName === 'A');
  assert.equal(link.href, endpoint.model_capability_sources[endpoint.model]);
  assert.equal(link.textContent, 'Documented capabilities (not tested)');
  assert.equal(link.rel, 'noopener noreferrer');
  assert.ok(ui.el.endpointModelStatus.children.includes(' · Tool calling has not been tested'));
  ui.state.endpointProbe = { endpointId: endpoint.id, model: endpoint.model,
    baseUrl: endpoint.base_url, message: 'Tool calling test failed: incompatible model' };
  ui.renderEndpointModelStatus(endpoint);
  assert.ok(ui.el.endpointModelStatus.children.includes(' · Tool calling test failed: incompatible model'));
  assert.equal(ui.state.providerEndpoints[0].model, 'models/gemini-3.8-flash-tts');
});

test('documented and mixed capability sources link only to trusted provider documentation', () => {
  const ui = editor();
  const endpoint = ui.state.providerEndpoints[0];
  endpoint.model_capabilities = { [endpoint.model]: ['Text', 'Tools'] };
  for (const source of [
    'https://developers.openai.com/api/docs/models/gpt-5.5',
    'https://console.groq.com/docs/model/openai/gpt-oss-20b',
    'https://inference-docs.cerebras.ai/capabilities/tool-use',
    'https://docs.sambanova.ai/docs/en/features/function-calling',
    'https://sambanova.ai/blog/start-building-with-lightning-fast-gpt-oss-120b-on-sambacloud',
    'https://docs.mistral.ai/models/mistral-medium-3-5-26-04',
    'https://openrouter.ai/openai/gpt-chat-latest',
  ]) {
    endpoint.model_capability_sources = { [endpoint.model]: 'provider_metadata+' + source };
    ui.renderEndpointModelStatus(endpoint);
    const link = ui.el.endpointModelStatus.children.find(item => item?.tagName === 'A');
    assert.equal(link?.href, source);
    assert.equal(link.textContent, 'Provider metadata + documented capabilities (not tested)');
  }
  for (const source of [
    'javascript:alert(1)', 'data:text/html,unsafe', 'http://docs.mistral.ai/models/a',
    'https://docs.mistral.ai.evil.example/models/a', 'https://docs.mistral.ai@evil.example/models/a',
    'https://docs.mistral.ai:444/models/a', 'https://docs.mistral.ai/../login',
    'https://ai.google.dev/gemini-api/docs/models/a?redirect=https://evil.example',
    'provider_metadata+javascript:alert(1)',
  ]) {
    endpoint.model_capability_sources = { [endpoint.model]: source };
    ui.renderEndpointModelStatus(endpoint);
    assert.equal(ui.el.endpointModelStatus.children.some(item => item?.tagName === 'A'), false, source);
  }
});

test('refresh displays enriched saved model labels without discovering again or changing configuration', async () => {
  let saved;
  const ui = editor({ apiHandler: async () => ({ items: [{ ...saved,
    model_capabilities: { [saved.model]: ['Text', 'Tools'] },
    model_capability_sources: { [saved.model]: 'https://inference-docs.cerebras.ai/capabilities/tool-use' },
  }], revision: 9 }) });
  saved = { ...ui.state.providerEndpoints[0] };
  const assignments = JSON.stringify(ui.state.taskModelAssignments);
  await ui.refreshProviderEndpoints();
  const option = ui.el.endpointModelSelect.options.find(item => item.value === saved.model);
  assert.match(option.textContent, /Text · Tools/);
  assert.doesNotMatch(option.textContent, /Capabilities not supplied/);
  assert.equal(ui.state.providerEndpoints[0].api_key, saved.api_key);
  assert.equal(ui.state.providerEndpoints[0].model, saved.model);
  assert.equal(JSON.stringify(ui.state.taskModelAssignments), assignments);
  assert.equal(ui.calls.length, 1);
  assert.equal(ui.calls[0].url, '/v1/admin/provider-endpoints');
  assert.equal(ui.calls[0].body, undefined);
  assert.equal(ui.state.endpointDraft, null);
});

test('endpoint fields stay locked until Edit and Save requires a valid changed draft', () => {
  const ui = editor();
  assert.equal(ui.el.taskProfileEndpointName.disabled, true);
  assert.equal(ui.el.saveProviderEndpoints.disabled, true);
  ui.editEndpoint();
  assert.equal(ui.el.taskProfileEndpointName.disabled, false);
  assert.equal(ui.el.saveProviderEndpoints.disabled, true);
  ui.el.taskProfileEndpointName.value = 'Changed';
  ui.syncEndpointDraft();
  assert.equal(ui.el.saveProviderEndpoints.disabled, false);
  assert.equal(ui.state.providerEndpoints[0].name, 'OpenAI - GPT');
  ui.el.endpointModelId.value = '';
  ui.syncEndpointDraft();
  assert.equal(ui.el.saveProviderEndpoints.disabled, true);
  ui.cancelEndpointEdit();
  assert.equal(ui.el.taskProfileEndpointName.value, 'OpenAI - GPT');
  assert.equal(ui.el.taskProfileEndpointName.disabled, true);
});

test('five provider connections remain drafts until Save and Cancel preserves saved connections', () => {
  const ui = editor();
  const before = JSON.stringify(ui.state.providerEndpoints);
  const assignments = JSON.stringify(ui.state.taskModelAssignments);
  ui.prepareProviderConnections();
  assert.equal(ui.state.providerSetupDraft.length, 5);
  assert.equal(new Set(ui.state.providerSetupDraft.map(item => item.id)).size, 5);
  assert.deepEqual(Array.from(ui.state.providerSetupDraft, item => item.provider_name).sort(),
    ['Cerebras', 'Google Gemini (OpenAI-compatible)', 'OpenRouter', 'SambaNova', 'Together AI'].sort());
  assert.ok(ui.state.providerSetupDraft.every(item => !item.api_key && !item.model && !item.models.length));
  assert.equal(JSON.stringify(ui.state.providerEndpoints), before);
  assert.equal(JSON.stringify(ui.state.taskModelAssignments), assignments);
  assert.equal(ui.el.endpointEditButton.disabled, true);
  assert.equal(ui.el.providerSetupList.children.length, 5);
  assert.ok(ui.el.providerSetupList.children.every(item => item.textContent.includes('Tool calling has not been tested')));
  assert.equal(ui.calls.length, 0);
  ui.cancelProviderConnections();
  assert.equal(ui.state.providerSetupDraft, null);
  assert.equal(ui.el.providerSetupPanel.classes.has('hidden'), true);
  assert.equal(JSON.stringify(ui.state.providerEndpoints), before);
  assert.equal(ui.el.endpointEditButton.disabled, false);
});

test('saving new provider profiles preserves fresh server connections and avoids duplicate providers', async () => {
  const existing = { id: 'cerebras-existing', name: 'My Cerebras', provider_name: 'Cerebras',
    base_url: 'https://api.cerebras.ai/v1', api_key: 'existing-key', model: 'my-model', models: [] };
  const ui = editor({ apiHandler: async (url, body, options) =>
    options.method === 'PUT' ? { ...body, revision: 24 } : { items: [existing], revision: 23 } });
  const assignments = JSON.stringify(ui.state.taskModelAssignments);
  ui.prepareProviderConnections();
  await ui.saveProviderConnections();
  assert.equal(ui.calls.length, 2);
  assert.equal(ui.calls[1].url, '/v1/admin/provider-endpoints');
  assert.equal(ui.calls[1].body.items.length, 5);
  assert.equal(ui.calls[1].body.expected_revision, 23);
  assert.equal(ui.state.providerEndpointRevision, 24);
  assert.deepEqual(ui.calls[1].body.items.find(item => item.id === existing.id), existing);
  assert.equal(ui.calls[1].body.items.filter(item => item.base_url === existing.base_url).length, 1);
  assert.equal(JSON.stringify(ui.state.taskModelAssignments), assignments);
  assert.equal(ui.state.providerSetupDraft, null);
  assert.equal(ui.el.taskProfileApiKey.disabled, true);
  assert.equal(ui.state.providerEndpoints.filter(item => !item.api_key && !item.model).length, 4);
});

test('existing Groq and Mistral connections are preserved while five additional providers are prepared and saved', async () => {
  const existing = [
    { id: 'groq-saved', name: 'Existing Groq', provider_name: 'Groq',
      base_url: 'https://api.groq.com/openai/v1', api_key: 'groq-test-key', model: 'groq-saved-model', models: ['groq-saved-model'] },
    { id: 'mistral-saved', name: 'Existing Mistral', provider_name: 'Mistral AI',
      base_url: 'https://api.mistral.ai/v1', api_key: 'mistral-test-key', model: 'mistral-saved-model', models: ['mistral-saved-model'] },
  ];
  const ui = editor({ apiHandler: async (_url, body, options) =>
    options.method === 'PUT' ? { items: body.items, revision: 13 } : { items: existing, revision: 12 } });
  ui.state.providerEndpoints = existing.map(item => ({ ...item, models: [...item.models] }));
  ui.state.providerEndpointRevision = 12;
  ui.state.activeEndpointId = 'groq-saved';
  ui.state.taskModelAssignments = [{ task: 'memory_recall', provider: 'groq-saved', model: 'groq-saved-model', fallbacks: [] }];
  const before = JSON.stringify(ui.state.providerEndpoints);
  const assignments = JSON.stringify(ui.state.taskModelAssignments);
  ui.prepareProviderConnections();
  assert.equal(ui.state.providerSetupDraft.length, 5);
  assert.equal(ui.state.providerSetupDraft.some(item => item.provider_name === 'Mistral AI'), false);
  assert.equal(ui.state.providerSetupDraft.find(item => item.provider_name === 'Together AI').base_url, 'https://api.together.ai/v1');
  assert.equal(JSON.stringify(ui.state.providerEndpoints), before);
  await ui.saveProviderConnections();
  assert.equal(ui.calls.length, 2);
  assert.equal(ui.calls[1].body.expected_revision, 12);
  assert.equal(ui.state.providerEndpoints.length, 7);
  assert.deepEqual(JSON.parse(JSON.stringify(ui.state.providerEndpoints.slice(0, 2))), existing);
  assert.equal(ui.state.providerEndpoints.filter(item => !item.api_key && !item.model).length, 5);
  assert.equal(JSON.stringify(ui.state.taskModelAssignments), assignments);
  assert.equal(ui.state.providerEndpointRevision, 13);
});

test('failed provider profile save keeps the isolated batch available to retry or cancel', async () => {
  const ui = editor({ apiHandler: async (_url, _body, options) => {
    if (options.method === 'PUT') throw new Error('Save failed');
    return { items: [] };
  } });
  const before = JSON.stringify(ui.state.providerEndpoints);
  ui.prepareProviderConnections();
  const draft = JSON.stringify(ui.state.providerSetupDraft);
  await ui.saveProviderConnections();
  assert.equal(JSON.stringify(ui.state.providerSetupDraft), draft);
  assert.equal(JSON.stringify(ui.state.providerEndpoints), before);
  assert.equal(ui.el.saveProviderConnections.disabled, false);
  assert.equal(ui.el.cancelProviderConnections.disabled, false);
  assert.equal(ui.state.integrationSaving, false);
});

test('daily provider rotation is a saved task setting and Return rolls back an unsaved selection', async () => {
  const ui = editor();
  ui.openTaskProfile('vision');
  assert.equal(ui.el.taskProviderRotation.value, 'ordered');
  ui.el.taskProviderRotation.value = 'daily_round_robin';
  ui.syncTaskProviderRotation();
  assert.equal(ui.el.saveTaskProfile.disabled, false);
  ui.discardTaskProfileChanges();
  assert.equal(ui.state.taskModelAssignments[0].provider_rotation, undefined);
  ui.openTaskProfile('vision');
  ui.el.taskProviderRotation.value = 'daily_round_robin';
  ui.syncTaskProviderRotation();
  await ui.saveTaskProfile();
  assert.equal(ui.calls[0].body.items[0].provider_rotation, 'daily_round_robin');
  assert.equal(ui.state.taskModelAssignments[0].provider_rotation, 'daily_round_robin');
  assert.equal(ui.el.taskProviderRotation.value, 'daily_round_robin');
});

test('tool-calling probe reports its actual result and editing invalidates the earlier result', async () => {
  const ui = editor({ apiHandler: async () => ({ tool_calling_verified: true }) });
  ui.editEndpoint();
  await ui.probeEndpointToolCalling();
  assert.equal(ui.calls[0].url, '/v1/admin/provider-endpoints/probe');
  assert.equal(ui.calls[0].body.model, 'gpt-test');
  assert.equal(ui.calls[0].body.api_key, 'test-key');
  assert.equal(ui.state.endpointProbe.message, 'Tool calling verified in current test');
  assert.equal(ui.state.endpointProbing, false);
  assert.equal(ui.state.providerEndpoints[0].model, 'gpt-test');
  ui.el.endpointModelId.value = 'different-model';
  ui.syncEndpointDraft();
  assert.equal(ui.state.endpointProbe, null);
  assert.ok(ui.el.endpointModelStatus.children.some(text => String(text).includes('Tool calling has not been tested')));
});

test('a failed tool-calling probe reports failure without converting it into verified readiness', async () => {
  const ui = editor({ apiHandler: async () => ({ tool_calling_verified: false, message: 'Provider returned text instead of a tool call' }) });
  await ui.probeEndpointToolCalling();
  assert.equal(ui.state.endpointProbe.message, 'Provider returned text instead of a tool call');
  assert.equal(ui.toasts[0][1], true);
  assert.equal(ui.calls.length, 1);
  assert.equal(ui.state.endpointDraft, null);
  assert.equal(ui.state.endpointProbing, false);
});

test('a pending tool-calling probe locks provider and MCP changes and never displays premature proof', async () => {
  let resolveProbe;
  const ui = editor({ apiHandler: () => new Promise(resolve => { resolveProbe = resolve; }) });
  ui.editEndpoint();
  ui.editMcpServer();
  const request = ui.probeEndpointToolCalling();
  assert.equal(ui.state.endpointProbing, true);
  assert.equal(ui.state.endpointProbe, null);
  assert.equal(ui.el.endpointProbeButton.disabled, true);
  assert.equal(ui.el.taskProfileDiscover.disabled, true);
  assert.equal(ui.el.taskProfileApiKey.disabled, true);
  assert.equal(ui.el.saveProviderEndpoints.disabled, true);
  assert.equal(ui.el.mcpServerName.disabled, true);
  assert.equal(ui.el.saveMcpServers.disabled, true);
  await ui.probeEndpointToolCalling();
  assert.equal(ui.calls.length, 1);
  resolveProbe({ tool_calling_verified: true });
  await request;
  assert.equal(ui.state.endpointProbing, false);
  assert.equal(ui.el.taskProfileApiKey.disabled, false);
  assert.equal(ui.el.mcpServerName.disabled, false);
  assert.equal(ui.state.endpointProbe.message, 'Tool calling verified in current test');
});

test('a tool-calling response for superseded credentials or model cannot mark the new draft verified', async () => {
  let resolveProbe;
  const ui = editor({ apiHandler: () => new Promise(resolve => { resolveProbe = resolve; }) });
  ui.editEndpoint();
  const request = ui.probeEndpointToolCalling();
  // A background update can replace state even while the form is locked.
  ui.state.endpointDraft = { ...ui.state.endpointDraft, api_key: 'new-key', model: 'new-model' };
  resolveProbe({ tool_calling_verified: true });
  await request;
  assert.equal(ui.state.endpointProbe, null);
  assert.equal(ui.state.endpointProbing, false);
  assert.equal(ui.state.endpointDraft.model, 'new-model');
  assert.equal(ui.toasts.length, 0);
  assert.ok(ui.el.endpointModelStatus.children.some(text => String(text).includes('Tool calling has not been tested')));
});

test('endpoint saves send the loaded revision and preserve a stale draft instead of retrying', async () => {
  const ui = editor({ apiHandler: () => { throw Object.assign(new Error('Conflict'), { status: 409 }); } });
  ui.state.providerEndpointRevision = 9;
  const original = JSON.stringify(ui.state.providerEndpoints);
  ui.editEndpoint();
  ui.el.taskProfileEndpointName.value = 'My edited endpoint';
  ui.syncEndpointDraft();
  await ui.saveProviderEndpoints();
  assert.equal(ui.calls.length, 1);
  assert.equal(ui.calls[0].body.expected_revision, 9);
  assert.equal(JSON.stringify(ui.state.providerEndpoints), original);
  assert.equal(ui.state.endpointDraft.name, 'My edited endpoint');
  assert.equal(ui.state.providerEndpointRevision, 9);
  assert.equal(ui.el.saveProviderEndpoints.disabled, false);
  assert.match(ui.toasts[0][0], /Cancel, refresh and review/);
});

test('endpoint removal supplies the loaded revision and preserves saved records after a conflict', async () => {
  const ui = editor({ apiHandler: () => { throw Object.assign(new Error('Conflict'), { status: 409 }); } });
  ui.state.providerEndpointRevision = 11;
  const original = JSON.stringify(ui.state.providerEndpoints);
  await ui.removeEndpoint();
  assert.equal(ui.calls.length, 1);
  assert.equal(ui.calls[0].body.expected_revision, 11);
  assert.equal(JSON.stringify(ui.state.providerEndpoints), original);
  assert.match(ui.toasts[0][0], /Refresh and review/);
});

test('endpoint refresh cannot replace the revision or values after an edit begins', async () => {
  let resolveRefresh;
  const ui = editor({ apiHandler: () => new Promise(resolve => { resolveRefresh = resolve; }) });
  const pending = ui.refreshProviderEndpoints();
  ui.editEndpoint();
  ui.el.taskProfileEndpointName.value = 'Draft endpoint';
  ui.syncEndpointDraft();
  resolveRefresh({ items: [{ ...ui.state.providerEndpoints[0], name: 'Concurrent endpoint' }], revision: 8 });
  await pending;
  assert.equal(ui.state.providerEndpointRevision, 0);
  assert.equal(ui.state.providerEndpoints[0].name, 'OpenAI - GPT');
  assert.equal(ui.el.taskProfileEndpointName.value, 'Draft endpoint');
});

test('adding an endpoint creates an isolated draft and Cancel discards it', () => {
  const ui = editor();
  ui.addTaskProfileEndpoint();
  assert.equal(ui.state.providerEndpoints.length, 1);
  assert.equal(ui.state.endpointDraft.id, 'new-id');
  assert.equal(ui.state.endpointDraft.name, '');
  assert.equal(ui.state.endpointDraft.base_url, '');
  assert.equal(ui.state.endpointDraft.model, '');
  assert.equal(ui.el.endpointTemplateField.classes.has('hidden'), false);
  assert.equal(ui.el.endpointTemplateSelect.disabled, false);
  assert.equal(ui.el.endpointTemplateSelect.children.some(option => option.value === 'openai'), true);
  assert.equal(ui.el.saveProviderEndpoints.disabled, true);
  ui.cancelEndpointEdit();
  assert.equal(ui.state.endpointDraft, null);
  assert.equal(ui.state.activeEndpointId, 'openai');
});

test('Add can use a saved endpoint as a deeply isolated template with a separate identity', () => {
  const ui = editor();
  const original = ui.state.providerEndpoints[0];
  original.models = ['gpt-test', 'gpt-next'];
  original.model_capabilities = { 'gpt-test': ['Text'] };
  original.model_capability_sources = { 'gpt-test': 'provider_metadata' };
  original.model_capability_exclusions = { 'gpt-test': ['Tools'] };
  const before = JSON.stringify(original);
  const assignments = JSON.stringify(ui.state.taskModelAssignments);
  ui.addTaskProfileEndpoint();
  const newId = ui.state.endpointDraft.id;
  ui.el.endpointTemplateSelect.value = original.id;
  ui.applyEndpointTemplate();
  const draft = ui.state.endpointDraft;
  assert.equal(draft.id, newId);
  assert.notEqual(draft.id, original.id);
  assert.equal(draft.name, 'OpenAI - GPT copy');
  assert.equal(draft.provider_name, original.provider_name);
  assert.equal(draft.base_url, original.base_url);
  assert.equal(draft.api_key, 'test-key');
  assert.equal(draft.model, '');
  assert.deepEqual([...draft.models], ['gpt-test', 'gpt-next']);
  assert.deepEqual([...draft.model_capabilities['gpt-test']], ['Text']);
  assert.equal(draft.model_capability_sources['gpt-test'], 'provider_metadata');
  assert.deepEqual([...draft.model_capability_exclusions['gpt-test']], ['Tools']);
  assert.equal(ui.el.taskProfileEndpointName.value, draft.name);
  assert.equal(ui.el.taskProfileApiKey.value, 'test-key');
  assert.equal(ui.el.saveProviderEndpoints.disabled, true);
  draft.models.push('draft-only-model');
  draft.model_capabilities['gpt-test'].push('Vision');
  draft.model_capability_sources['gpt-test'] = 'draft-only-source';
  draft.model_capability_exclusions['gpt-test'].push('Vision');
  assert.equal(JSON.stringify(original), before);
  assert.equal(JSON.stringify(ui.state.taskModelAssignments), assignments);
  ui.cancelEndpointEdit();
  assert.equal(ui.state.endpointDraft, null);
  assert.equal(ui.state.providerEndpoints.length, 1);
  assert.equal(ui.state.activeEndpointId, original.id);
  assert.equal(JSON.stringify(original), before);
  assert.equal(ui.calls.length, 0);
});

test('saving a renamed template with a different model preserves the original and its task references', async () => {
  const ui = editor();
  const before = JSON.stringify(ui.state.providerEndpoints[0]);
  const assignments = JSON.stringify(ui.state.taskModelAssignments);
  ui.addTaskProfileEndpoint();
  ui.el.endpointTemplateSelect.value = 'openai';
  ui.applyEndpointTemplate();
  ui.el.taskProfileEndpointName.value = 'OpenAI - Different model';
  ui.el.endpointModelId.value = 'gpt-next';
  ui.syncEndpointDraft();
  assert.equal(ui.el.saveProviderEndpoints.disabled, false);
  await ui.saveProviderEndpoints();
  assert.equal(ui.state.providerEndpoints.length, 2);
  assert.equal(JSON.stringify(ui.state.providerEndpoints.find(item => item.id === 'openai')), before);
  const added = ui.state.providerEndpoints.find(item => item.id === 'new-id');
  assert.equal(added.name, 'OpenAI - Different model');
  assert.equal(added.model, 'gpt-next');
  assert.equal(added.api_key, 'test-key');
  assert.equal(JSON.stringify(ui.state.taskModelAssignments), assignments);
  assert.equal(ui.state.endpointDraft, null);
  assert.equal(ui.el.taskProfileEndpointName.disabled, true);
});

test('Add, template selection, discovery, and Save create an independent endpoint with a new model', async () => {
  const ui = editor({ apiHandler: async (url, body) => url.endsWith('/discover')
    ? { models: ['gpt-test', 'gpt-next'], model_capabilities: { 'gpt-next': ['Vision'] } }
    : body });
  const original = JSON.stringify(ui.state.providerEndpoints[0]);
  const assignments = JSON.stringify(ui.state.taskModelAssignments);
  ui.addTaskProfileEndpoint();
  ui.el.endpointTemplateSelect.value = 'openai';
  ui.applyEndpointTemplate();
  ui.el.taskProfileEndpointName.value = 'Vision endpoint';
  ui.syncEndpointDraft();
  await ui.discoverTaskProfileModels();
  assert.equal(ui.calls[0].body.id, 'new-id');
  assert.equal(ui.calls[0].body.api_key, 'test-key');
  assert.equal(ui.state.endpointDraft.model, '');
  assert.equal(ui.el.saveProviderEndpoints.disabled, true);
  ui.el.endpointModelId.value = 'gpt-next';
  ui.syncEndpointDraft();
  await ui.saveProviderEndpoints();
  const added = ui.state.providerEndpoints.find(item => item.id === 'new-id');
  assert.equal(added.name, 'Vision endpoint');
  assert.equal(added.model, 'gpt-next');
  assert.deepEqual([...added.models], ['gpt-test', 'gpt-next']);
  assert.deepEqual([...added.model_capabilities['gpt-next']], ['Vision']);
  assert.equal(JSON.stringify(ui.state.providerEndpoints.find(item => item.id === 'openai')), original);
  assert.equal(JSON.stringify(ui.state.taskModelAssignments), assignments);
  assert.equal(ui.calls.filter(call => call.url.endsWith('/discover')).length, 1);
  assert.equal(ui.calls.filter(call => call.url === '/v1/admin/provider-endpoints').length, 1);
});

test('clearing an Add template restores the blank draft without changing its new identity', () => {
  const ui = editor();
  ui.addTaskProfileEndpoint();
  ui.el.endpointTemplateSelect.value = 'openai';
  ui.applyEndpointTemplate();
  ui.el.endpointTemplateSelect.value = '';
  ui.applyEndpointTemplate();
  assert.equal(ui.state.endpointDraft.id, 'new-id');
  for (const field of ['name', 'provider_name', 'base_url', 'api_key', 'model']) {
    assert.equal(ui.state.endpointDraft[field], '', `${field} is reset`);
  }
  assert.equal(ui.state.endpointDraft.models.length, 0);
  assert.equal(ui.el.saveProviderEndpoints.disabled, true);
  assert.equal(ui.el.taskProfileDiscover.disabled, true);
  assert.equal(ui.state.providerEndpoints.length, 1);
  assert.equal(ui.calls.length, 0);
});

test('API key visibility changes only its presentation and resets after Cancel', () => {
  const ui = editor();
  assert.equal(ui.el.taskProfileApiKey.classes.has('is-masked'), true);
  assert.equal(ui.el.endpointApiKeyVisibility.textContent, 'Show API key');
  ui.toggleEndpointApiKeyVisibility();
  assert.equal(ui.el.taskProfileApiKey.classes.has('is-masked'), true);
  ui.editEndpoint();
  ui.toggleEndpointApiKeyVisibility();
  assert.equal(ui.el.taskProfileApiKey.classes.has('is-masked'), false);
  assert.equal(ui.el.endpointApiKeyVisibility.textContent, 'Hide API key');
  assert.match(ui.el.endpointApiKeyHelp.textContent, /visible/);
  assert.equal(ui.el.taskProfileApiKey.value, 'test-key');
  assert.equal(ui.state.endpointDraft.api_key, 'test-key');
  ui.toggleEndpointApiKeyVisibility();
  assert.equal(ui.el.taskProfileApiKey.classes.has('is-masked'), true);
  assert.equal(ui.el.endpointApiKeyVisibility.textContent, 'Show API key');
  ui.toggleEndpointApiKeyVisibility();
  ui.cancelEndpointEdit();
  assert.equal(ui.el.taskProfileApiKey.classes.has('is-masked'), true);
  assert.equal(ui.el.endpointApiKeyVisibility.textContent, 'Show API key');
  assert.equal(ui.state.providerEndpoints[0].api_key, 'test-key');
  assert.equal(ui.calls.length, 0);
});

test('Discover Models works on a selected saved endpoint and holds the result in a draft until Save', async () => {
  const ui = editor({ apiHandler: async () => ({
    models: ['gpt-test', 'gpt-next'], model_capabilities: { 'gpt-next': ['Text', 'Vision'] },
    model_capability_sources: { 'gpt-next': 'provider_metadata' },
    model_capability_exclusions: { 'gpt-next': ['Tools'] },
  }) });
  const original = JSON.stringify(ui.state.providerEndpoints[0]);
  const assignments = JSON.stringify(ui.state.taskModelAssignments);
  assert.equal(ui.state.endpointDraft, null);
  assert.equal(ui.el.taskProfileEndpointName.disabled, true);
  assert.equal(ui.el.taskProfileDiscover.disabled, false);
  await ui.discoverTaskProfileModels();
  assert.equal(ui.calls.length, 1);
  assert.equal(ui.calls[0].url, '/v1/admin/provider-endpoints/discover');
  assert.equal(ui.calls[0].body.id, 'openai');
  assert.equal(ui.calls[0].body.api_key, 'test-key');
  assert.equal(ui.state.endpointDraft.id, 'openai');
  assert.deepEqual([...ui.state.endpointDraft.models], ['gpt-test', 'gpt-next']);
  assert.deepEqual([...ui.state.endpointDraft.model_capabilities['gpt-next']], ['Text', 'Vision']);
  assert.deepEqual([...ui.state.endpointDraft.model_capability_exclusions['gpt-next']], ['Tools']);
  assert.equal(JSON.stringify(ui.state.providerEndpoints[0]), original);
  assert.equal(JSON.stringify(ui.state.taskModelAssignments), assignments);
  assert.equal(ui.el.taskProfileEndpointName.disabled, false);
  assert.equal(ui.el.saveProviderEndpoints.disabled, false);
  ui.cancelEndpointEdit();
  assert.equal(ui.state.endpointDraft, null);
  assert.equal(JSON.stringify(ui.state.providerEndpoints[0]), original);
});

test('a new endpoint can discover models before it has a name or chosen model', async () => {
  const ui = editor({ apiHandler: async () => ({ models: ['only-model'] }) });
  ui.addTaskProfileEndpoint();
  ui.el.taskProfileBaseUrl.value = 'https://new-provider.example/v1';
  ui.el.taskProfileApiKey.value = 'new-test-key';
  ui.syncEndpointDraft();
  assert.equal(ui.el.taskProfileDiscover.disabled, false);
  assert.equal(ui.el.saveProviderEndpoints.disabled, true);
  await ui.discoverTaskProfileModels();
  assert.equal(ui.calls.length, 1);
  assert.equal(ui.calls[0].body.base_url, 'https://new-provider.example/v1');
  assert.equal(ui.calls[0].body.api_key, 'new-test-key');
  assert.ok(ui.calls[0].body.name.trim());
  assert.equal(ui.state.endpointDraft.name, '');
  assert.equal(ui.state.endpointDraft.model, 'only-model');
  assert.equal(ui.el.saveProviderEndpoints.disabled, true);
  ui.el.taskProfileBaseUrl.value = 'invalid';
  ui.syncEndpointDraft();
  assert.equal(ui.el.taskProfileDiscover.disabled, true);
});

test('model discovery blocks duplicate requests and locks editable controls until the response arrives', async () => {
  let resolveDiscovery;
  const pending = new Promise(resolve => { resolveDiscovery = resolve; });
  const ui = editor({ apiHandler: async () => pending });
  const discovery = ui.discoverTaskProfileModels();
  assert.equal(ui.calls.length, 1);
  assert.equal(ui.state.endpointDiscovering, true);
  for (const name of ['taskProfileDiscover', 'taskProfileEndpointSelect', 'taskProfileAddEndpoint',
    'taskProfileEndpointName', 'taskProfileApiKey', 'endpointModelSelect', 'endpointModelId',
    'endpointTemplateSelect', 'endpointCancelButton', 'saveProviderEndpoints']) {
    assert.equal(ui.el[name].disabled, true, `${name} is locked while discovering`);
  }
  await ui.discoverTaskProfileModels();
  assert.equal(ui.calls.length, 1);
  resolveDiscovery({ models: ['gpt-test', 'gpt-next'] });
  await discovery;
  assert.equal(ui.state.endpointDiscovering, false);
  assert.equal(ui.el.taskProfileDiscover.disabled, false);
  assert.equal(ui.el.taskProfileEndpointName.disabled, false);
  assert.equal(ui.el.endpointCancelButton.disabled, false);
});

test('pending endpoint discovery blocks MCP Save and preserves its dirty draft until discovery finishes', async () => {
  let resolveDiscovery;
  const pending = new Promise(resolve => { resolveDiscovery = resolve; });
  const ui = editor({ apiHandler: async (url, body) => url.endsWith('/discover') ? pending : body });
  ui.editMcpServer();
  ui.el.mcpServerName.value = 'Unsaved MCP name';
  ui.syncMcpServerForm();
  const dirtyDraft = JSON.stringify(ui.state.mcpServerDraft);
  assert.equal(ui.el.saveMcpServers.disabled, false);
  const discovery = ui.discoverTaskProfileModels();
  assert.equal(ui.state.endpointDiscovering, true);
  assert.equal(ui.el.saveMcpServers.disabled, true);
  assert.equal(ui.el.mcpServerName.disabled, true);
  await ui.saveMcpServers();
  assert.equal(ui.calls.length, 1);
  assert.equal(ui.calls[0].url, '/v1/admin/provider-endpoints/discover');
  assert.equal(JSON.stringify(ui.state.mcpServerDraft), dirtyDraft);
  assert.equal(ui.state.mcpServers[0].name, 'Tools');
  resolveDiscovery({ models: ['gpt-test', 'gpt-next'] });
  await discovery;
  assert.equal(ui.state.endpointDiscovering, false);
  assert.equal(ui.el.saveMcpServers.disabled, false);
  assert.equal(ui.el.mcpServerName.disabled, false);
  assert.equal(JSON.stringify(ui.state.mcpServerDraft), dirtyDraft);
  await ui.saveMcpServers();
  assert.equal(ui.calls.length, 2);
  assert.equal(ui.calls[1].url, '/v1/admin/mcp/servers');
  assert.equal(ui.state.mcpServers[0].name, 'Unsaved MCP name');
  assert.equal(ui.state.mcpServerDraft, null);
  assert.equal(ui.el.taskProfileDiscover.disabled, false);
  assert.equal(ui.el.endpointCancelButton.disabled, false);
});

test('a failed model discovery keeps the draft intact and unlocks the editor for retry', async () => {
  let failing = true;
  const ui = editor({ apiHandler: async () => {
    if (failing) throw new Error('Provider unavailable');
    return { models: ['gpt-test', 'gpt-next'] };
  } });
  ui.editEndpoint();
  ui.el.taskProfileEndpointName.value = 'Unsaved name';
  ui.syncEndpointDraft();
  const draft = JSON.stringify(ui.state.endpointDraft);
  const original = JSON.stringify(ui.state.providerEndpoints[0]);
  await ui.discoverTaskProfileModels();
  assert.equal(ui.state.endpointDiscovering, false);
  assert.equal(JSON.stringify(ui.state.endpointDraft), draft);
  assert.equal(JSON.stringify(ui.state.providerEndpoints[0]), original);
  assert.equal(ui.el.taskProfileDiscover.disabled, false);
  assert.equal(ui.el.taskProfileEndpointName.disabled, false);
  assert.equal(ui.el.endpointCancelButton.disabled, false);
  assert.equal(ui.toasts.some(([message, error]) => message === 'Provider unavailable' && error), true);
  failing = false;
  await ui.discoverTaskProfileModels();
  assert.equal(ui.calls.length, 2);
  assert.deepEqual([...ui.state.endpointDraft.models], ['gpt-test', 'gpt-next']);
});

test('saving endpoint model updates primary and fallback references then locks the form', async () => {
  const ui = editor();
  ui.editEndpoint();
  ui.el.endpointModelId.value = 'gpt-next';
  ui.syncEndpointDraft();
  await ui.saveProviderEndpoints();
  assert.equal(ui.calls.length, 2);
  assert.equal(ui.state.providerEndpoints[0].model, 'gpt-next');
  assert.equal(ui.state.taskModelAssignments[0].model, 'gpt-next');
  assert.equal(ui.state.taskModelAssignments[0].fallbacks[0].provider, 'openai');
  assert.equal(ui.state.taskModelAssignments[0].fallbacks[0].model, 'gpt-next');
  assert.equal(ui.state.endpointDraft, null);
  assert.equal(ui.el.taskProfileEndpointName.disabled, true);
  assert.equal(ui.el.saveProviderEndpoints.disabled, true);
});

test('MCP server and tool changes require Edit and do not alter saved records before Save', async () => {
  const ui = editor();
  assert.equal(ui.el.mcpServerName.disabled, true);
  const readOnlyToggle = ui.el.mcpToolList.children[0].children[1].children[0];
  assert.equal(readOnlyToggle.disabled, true);
  ui.editMcpServer();
  assert.equal(ui.el.saveMcpServers.disabled, true);
  const toggle = ui.el.mcpToolList.children[0].children[1].children[0];
  assert.equal(toggle.disabled, false);
  toggle.checked = false;
  toggle.listeners.change();
  assert.equal(ui.el.saveMcpServers.disabled, false);
  assert.equal(ui.state.mcpServers[0].tools[0].enabled, true);
  await ui.saveMcpServers();
  assert.equal(ui.state.mcpServers[0].tools[0].enabled, false);
  assert.equal(ui.state.mcpServerDraft, null);
  assert.equal(ui.el.mcpServerName.disabled, true);
  assert.equal(ui.el.saveMcpServers.disabled, true);
});

test('invalid MCP URL keeps Save disabled and Cancel restores configuration', () => {
  const ui = editor();
  ui.editMcpServer();
  ui.el.mcpServerUrl.value = 'invalid';
  ui.syncMcpServerForm();
  assert.equal(ui.el.saveMcpServers.disabled, true);
  ui.cancelMcpEdit();
  assert.equal(ui.el.mcpServerUrl.value, 'https://tools.example/mcp');
  assert.equal(ui.state.mcpServers[0].url, 'https://tools.example/mcp');
});

test('removing endpoint clears its primary and fallback task references', async () => {
  const ui = editor();
  await ui.removeEndpoint();
  assert.equal(ui.state.providerEndpoints.length, 0);
  assert.equal(ui.state.taskModelAssignments[0].provider, '');
  assert.equal(ui.state.taskModelAssignments[0].fallbacks.length, 0);
  assert.equal(ui.el.endpointEditButton.disabled, true);
});

test('key-loaded endpoint options and selected value use a distinct class', () => {
  const ui = editor();
  ui.renderTaskProfileEndpointOptions();
  assert.equal(ui.el.taskProfileEndpointSelect.children[1].classes.has('credential-loaded'), true);
  assert.equal(ui.el.taskProfileEndpointSelect.classes.has('credential-loaded'), true);
});

test('Reasoning honors explicit Administrator behavior selections including protected rows', async () => {
  const ui = editor();
  ui.state.hostBehaviors = [
    { id: 'protected', name: 'Protected', instruction: 'Required', protected: true, enabled: true },
    { id: 'optional', name: 'Optional', instruction: 'Optional', protected: false, enabled: true },
  ];
  ui.state.taskModelAssignments.push({ task: 'reasoning', provider: 'connected-host', model: 'host-model',
    behavior_ids: [], fallbacks: [{ provider: 'openai', model: 'gpt-test' }] });
  ui.openTaskProfile('reasoning');
  assert.equal(ui.el.taskProfileAssignmentSection.classes.has('hidden'), false);
  assert.equal(ui.el.taskProfileFallbackList.children.length, 1);
  assert.equal(ui.el.taskProviderSelect.options.some(option => option.value === 'connected-host'), true);
  assert.equal(ui.el.taskProviderSelect.options.find(option => option.value === 'openai').textContent, 'OpenAI - GPT');
  assert.equal(ui.el.saveTaskProfile.disabled, true);
  const protectedToggle = ui.el.taskProfileBehaviorSelection.children[0].children[0];
  assert.equal(protectedToggle.checked, false);
  assert.equal(protectedToggle.disabled, false);
  const optionalToggle = ui.el.taskProfileBehaviorSelection.children[1].children[0];
  optionalToggle.checked = true;
  optionalToggle.listeners.change();
  assert.equal(ui.el.saveTaskProfile.disabled, false);
  await ui.saveTaskProfile();
  const assignment = ui.calls.at(-1).body.items.find(item => item.task === 'reasoning');
  assert.deepEqual([...assignment.behavior_ids].sort(), ['optional']);
  assert.equal(ui.el.saveTaskProfile.disabled, true);
});

test('task selection uses the endpoint saved model for primary and fallback', () => {
  const ui = editor();
  ui.openTaskProfile('vision');
  ui.state.providerEndpoints.push({ id: 'next', name: 'Next endpoint', model: 'next-model', api_key: '' });
  ui.el.taskProviderSelect.value = 'next';
  ui.el.taskProviderSelect.listeners.change();
  const assignment = ui.state.taskModelAssignments.find(item => item.task === 'vision');
  assert.equal(assignment.provider, 'next');
  assert.equal(assignment.model, 'next-model');
  const fallbackSelect = ui.el.taskProfileFallbackList.children[0].children[0].children[0];
  fallbackSelect.value = 'next';
  fallbackSelect.listeners.change();
  assert.equal(assignment.fallbacks[0].provider, 'next');
  assert.equal(assignment.fallbacks[0].model, 'next-model');
});

test('Return discards unsaved task edits so another task Save cannot persist them', () => {
  const ui = editor();
  ui.openTaskProfile('vision');
  ui.el.taskProviderSelect.value = '';
  ui.el.taskProviderSelect.listeners.change();
  assert.equal(ui.el.saveTaskProfile.disabled, false);
  ui.closeTaskProfile();
  assert.equal(ui.state.taskModelAssignments[0].provider, 'openai');
  assert.equal(ui.state.taskModelAssignments[0].model, 'gpt-test');
  ui.openTaskProfile('reasoning');
  assert.equal(ui.state.taskModelAssignments[0].provider, 'openai');
});

test('legacy task model survives same endpoint selection and behavior-only saves', async () => {
  const ui = editor();
  ui.state.providerEndpoints[0].model = '';
  ui.state.hostBehaviors = [{ id: 'optional', name: 'Optional', instruction: 'Optional', enabled: true }];
  ui.openTaskProfile('vision');
  ui.el.taskProviderSelect.value = 'openai';
  ui.el.taskProviderSelect.listeners.change();
  assert.equal(ui.state.taskModelAssignments[0].model, 'gpt-test');
  const optionalToggle = ui.el.taskProfileBehaviorSelection.children[0].children[0];
  optionalToggle.checked = true;
  optionalToggle.listeners.change();
  assert.equal(ui.el.saveTaskProfile.disabled, false);
  ui.state.providerEndpoints.push({ id: 'unconfigured', name: 'Unconfigured', model: '' });
  ui.el.taskProviderSelect.value = 'unconfigured';
  ui.el.taskProviderSelect.listeners.change();
  assert.equal(ui.state.taskModelAssignments[0].model, '');
  assert.equal(ui.el.saveTaskProfile.disabled, false);
  await ui.saveTaskProfile();
  assert.equal(ui.calls.length, 0);
  assert.equal(ui.toasts.some(([message, error]) => message.includes('Save a model') && error), true);
});

test('clearing primary and fallback selections saves an unassigned task and preserves other configuration', async () => {
  const ui = editor();
  const voice = { task: 'audio_voice', provider: 'fish', model: 'saved-voice',
    voice_reference_id: 'custom-voice', fallbacks: [] };
  ui.state.taskModelAssignments.push(voice);
  const endpoints = JSON.stringify(ui.state.providerEndpoints);
  ui.state.taskModelAssignments[0].behavior_ids = [];
  ui.openTaskProfile('vision');
  ui.el.taskProviderSelect.value = '';
  ui.el.taskProviderSelect.listeners.change();
  const fallback = ui.el.taskProfileFallbackList.children[0].children[0].children[0];
  fallback.value = '';
  fallback.listeners.change();
  assert.equal(ui.el.saveTaskProfile.disabled, false);
  await ui.saveTaskProfile();
  assert.equal(ui.calls.length, 1);
  const saved = ui.calls[0].body.items.find(item => item.task === 'vision');
  assert.equal(saved.provider, '');
  assert.equal(saved.model, '');
  assert.deepEqual(saved.fallbacks, []);
  assert.deepEqual(saved.behavior_ids, []);
  assert.deepEqual(ui.calls[0].body.items.find(item => item.task === 'audio_voice'), voice);
  assert.equal(JSON.stringify(ui.state.providerEndpoints), endpoints);
  assert.equal(ui.el.saveTaskProfile.disabled, true);
  ui.openTaskProfile('vision');
  assert.equal(ui.el.taskProviderSelect.value, '');
  assert.equal(ui.state.taskModelAssignments[0].fallbacks.length, 0);
});

test('clearing only the primary keeps configured fallbacks and Cancel restores selections', async () => {
  const ui = editor();
  ui.openTaskProfile('vision');
  const before = JSON.stringify(ui.state.taskModelAssignments[0]);
  ui.el.taskProviderSelect.value = '';
  ui.el.taskProviderSelect.listeners.change();
  ui.discardTaskProfileChanges();
  assert.equal(JSON.stringify(ui.state.taskModelAssignments[0]), before);
  assert.equal(ui.calls.length, 0);
  ui.openTaskProfile('vision');
  ui.el.taskProviderSelect.value = '';
  ui.el.taskProviderSelect.listeners.change();
  await ui.saveTaskProfile();
  assert.equal(ui.calls.length, 1);
  assert.equal(ui.calls[0].body.items[0].provider, '');
  assert.equal(ui.calls[0].body.items[0].fallbacks[0].provider, 'OpenAI - GPT');
});

test('task cards retain the task names for icon decoration', () => {
  const ui = editor();
  ui.renderTaskProfiles();
  const card = ui.el.taskProfileList.children.find(item => item.children[0].textContent === 'Vision');
  assert.equal(card.dataset.keepLabel, 'true');
  assert.equal(card.children[0].tagName, 'STRONG');
  assert.equal(card.children[0].textContent, 'Vision');
});

test('Task selection only offers behaviors saved in the library', () => {
  const ui = editor();
  ui.state.hostBehaviorSnapshot = JSON.stringify([{ id: 'saved', name: 'Saved', instruction: 'Saved instruction', enabled: true }]);
  ui.state.hostBehaviors = [{ id: 'unsaved', name: 'Unsaved', instruction: 'Unsaved instruction', enabled: true }];
  ui.openTaskProfile('vision');
  const labels = ui.el.taskProfileBehaviorSelection.children;
  assert.equal(labels.length, 1);
  assert.equal(labels[0].children[1].children[0].textContent, 'Saved');
});

test('protected behavior settings are editable only in an isolated Administrator draft with a revisioned Save', async () => {
  const ui = editor({ apiHandler: (url, body) => url === '/v1/admin/host-behaviors'
    ? { items: body.items, revision: 8 } : { items: [] } });
  ui.state.hostBehaviors = [{ id: 'core', name: 'Core', instruction: 'Default instruction', enabled: true,
    required: true, protected: true, priority: 1 }];
  ui.state.hostBehaviorRevision = 7;
  ui.state.hostBehaviorSnapshot = JSON.stringify(ui.state.hostBehaviors);
  ui.renderHostBehaviors();
  assert.equal(ui.el.hostBehaviorList.children[0].children[0].children[0].children[1].readOnly, true);
  assert.equal(ui.el.saveHostBehaviors.disabled, true);
  ui.editHostBehaviors();
  let row = ui.el.hostBehaviorList.children[0];
  const name = row.children[0].children[0].children[1];
  const instruction = row.children[0].children[2].children[1];
  assert.equal(name.readOnly, false);
  assert.equal(row.children[1].children[0].children[0].disabled, false);
  name.value = 'Administrator Core'; name.listeners.input();
  instruction.value = 'New instruction'; instruction.listeners.input();
  row.children[1].children[0].children[0].checked = false;
  row.children[1].children[0].children[0].listeners.change();
  assert.equal(ui.state.hostBehaviors[0].name, 'Core');
  assert.equal(ui.state.hostBehaviors[0].enabled, true);
  ui.cancelHostBehaviorEdit();
  assert.equal(ui.state.hostBehaviorDraft, null);
  assert.equal(ui.el.hostBehaviorList.children[0].children[0].children[0].children[1].value, 'Core');
  ui.editHostBehaviors();
  row = ui.el.hostBehaviorList.children[0];
  const protectedFlag = row.children[1].children[2].children[0];
  protectedFlag.checked = false; protectedFlag.listeners.change();
  row.children[1].children[0].children[0].checked = false;
  row.children[1].children[0].children[0].listeners.change();
  await ui.saveHostBehaviors();
  const saved = ui.calls.find(call => call.url === '/v1/admin/host-behaviors').body;
  assert.equal(saved.expected_revision, 7);
  assert.equal(saved.items[0].protected, false);
  assert.equal(saved.items[0].enabled, false);
  assert.equal(ui.state.hostBehaviorDraft, null);
  assert.equal(ui.state.hostBehaviorRevision, 8);
  assert.equal(ui.el.hostBehaviorList.children[0].children[0].children[0].children[1].readOnly, true);
});

test('a large behavior library searches and selects one editor without rendering every instruction', () => {
  const ui = editor();
  ui.state.hostBehaviors = Array.from({ length: 1000 }, (_, index) => ({
    id: `behavior-${index}`, name: `Behavior ${index}`, instruction: `Instruction ${index}`,
    priority: index, enabled: true,
  }));
  ui.state.hostBehaviorSnapshot = JSON.stringify(ui.state.hostBehaviors);
  ui.renderHostBehaviors();
  assert.equal(ui.el.hostBehaviorSelect.options.length, 1000);
  assert.equal(ui.el.hostBehaviorList.children.length, 1);
  assert.equal(ui.el.hostBehaviorList.children[0].children[0].children[0].children[1].value, 'Behavior 0');
  ui.el.hostBehaviorSearch.value = 'Instruction 97';
  ui.el.hostBehaviorSearch.listeners.input();
  assert.equal(ui.el.hostBehaviorSelect.options.length, 11);
  assert.match(ui.el.hostBehaviorSummary.textContent, /1000 behaviors · 11 matches/);
  ui.el.hostBehaviorSelect.value = 'behavior-975';
  ui.el.hostBehaviorSelect.listeners.change();
  assert.equal(ui.el.hostBehaviorList.children.length, 1);
  assert.equal(ui.el.hostBehaviorList.children[0].children[0].children[0].children[1].value, 'Behavior 975');
  ui.el.hostBehaviorSearch.value = 'no matching instruction';
  ui.el.hostBehaviorSearch.listeners.input();
  assert.equal(ui.el.hostBehaviorSelect.disabled, true);
  assert.match(ui.el.hostBehaviorList.children[0].textContent, /No behaviors match/);
  assert.equal(ui.calls.length, 0);
});

test('behavior selection and search retain all draft edits until one revisioned Save', async () => {
  const ui = editor({ apiHandler: (_url, body) => ({ items: body.items, revision: 9 }) });
  ui.state.hostBehaviors = [
    { id: 'a', name: 'First', instruction: 'First saved instruction', priority: 1, enabled: true },
    { id: 'b', name: 'Second', instruction: 'Second saved instruction', priority: 2, enabled: true },
  ];
  ui.state.hostBehaviorRevision = 8;
  const original = ui.state.hostBehaviorSnapshot = JSON.stringify(ui.state.hostBehaviors);
  ui.editHostBehaviors();
  let name = ui.el.hostBehaviorList.children[0].children[0].children[0].children[1];
  name.value = 'First edited'; name.listeners.input();
  assert.equal(ui.el.hostBehaviorSelect.options[0].textContent, 'First edited');
  ui.el.hostBehaviorSearch.value = 'Second'; ui.el.hostBehaviorSearch.listeners.input();
  let instruction = ui.el.hostBehaviorList.children[0].children[0].children[2].children[1];
  instruction.value = 'Second edited instruction'; instruction.listeners.input();
  ui.el.hostBehaviorSearch.value = ''; ui.el.hostBehaviorSearch.listeners.input();
  ui.el.hostBehaviorSelect.value = 'a'; ui.el.hostBehaviorSelect.listeners.change();
  assert.equal(ui.el.hostBehaviorList.children[0].children[0].children[0].children[1].value, 'First edited');
  assert.equal(JSON.stringify(ui.state.hostBehaviors), original);
  assert.equal(ui.calls.length, 0);
  await ui.saveHostBehaviors();
  assert.equal(ui.calls.length, 1);
  assert.equal(ui.calls[0].body.expected_revision, 8);
  assert.equal(ui.calls[0].body.items[0].name, 'First edited');
  assert.equal(ui.calls[0].body.items[1].instruction, 'Second edited instruction');
  assert.equal(ui.state.hostBehaviorRevision, 9);
  assert.equal(ui.state.hostBehaviorDraft, null);
  assert.match(ui.el.hostBehaviorSummary.textContent, /Read-only/);
});

test('behavior Cancel restores the catalog after editing across selections and adding or removing entries', () => {
  const ui = editor();
  ui.state.hostBehaviors = [
    { id: 'a', name: 'First', instruction: 'First instruction', priority: 1, enabled: true },
    { id: 'b', name: 'Second', instruction: 'Second instruction', priority: 2, enabled: true },
  ];
  const original = ui.state.hostBehaviorSnapshot = JSON.stringify(ui.state.hostBehaviors);
  ui.editHostBehaviors();
  ui.el.hostBehaviorSelect.value = 'b'; ui.el.hostBehaviorSelect.listeners.change();
  const instruction = ui.el.hostBehaviorList.children[0].children[0].children[2].children[1];
  instruction.value = 'Unsaved second'; instruction.listeners.input();
  ui.el.hostBehaviorSearch.value = 'not found'; ui.el.hostBehaviorSearch.listeners.input();
  ui.addHostBehavior();
  assert.equal(ui.el.hostBehaviorSearch.value, '');
  assert.equal(ui.el.hostBehaviorList.children[0].children[0].children[0].children[1].value, 'New Behavior');
  ui.el.hostBehaviorList.children[0].children[1].children[3].listeners.click();
  assert.equal(ui.state.hostBehaviorDraft.length, 2);
  ui.cancelHostBehaviorEdit();
  assert.equal(JSON.stringify(ui.state.hostBehaviors), original);
  assert.equal(ui.state.hostBehaviorDraft, null);
  ui.el.hostBehaviorSelect.value = 'b'; ui.el.hostBehaviorSelect.listeners.change();
  assert.equal(ui.el.hostBehaviorList.children[0].children[0].children[2].children[1].value, 'Second instruction');
  assert.equal(ui.calls.length, 0);
});

test('behavior Save rejects invalid hidden draft entries and preserves selection on server failure', async () => {
  const ui = editor({ apiHandler: async () => { throw new Error('Revision conflict'); } });
  ui.state.hostBehaviors = [
    { id: 'a', name: 'First', instruction: 'First instruction', priority: 1, enabled: true },
    { id: 'b', name: 'Second', instruction: 'Second instruction', priority: 2, enabled: true },
  ];
  ui.state.hostBehaviorSnapshot = JSON.stringify(ui.state.hostBehaviors);
  ui.editHostBehaviors();
  ui.state.hostBehaviorDraft[0].name = '';
  ui.el.hostBehaviorSelect.value = 'b'; ui.el.hostBehaviorSelect.listeners.change();
  assert.equal(ui.el.saveHostBehaviors.disabled, true);
  assert.match(ui.el.hostBehaviorSummary.textContent, /Complete all draft fields/);
  await ui.saveHostBehaviors();
  assert.equal(ui.calls.length, 0);
  ui.state.hostBehaviorDraft[0].name = 'First edited';
  ui.updateBehaviorSaveState();
  await ui.saveHostBehaviors();
  assert.equal(ui.calls.length, 1);
  assert.equal(ui.state.activeHostBehaviorId, 'b');
  assert.equal(ui.state.hostBehaviorDraft[0].name, 'First edited');
  assert.equal(ui.state.hostBehaviors[0].name, 'First');
  assert.equal(ui.el.hostBehaviorSelect.disabled, false);
  assert.match(ui.el.hostBehaviorSummary.textContent, /Unsaved changes/);
  assert.equal(ui.toasts.at(-1)[0], 'Revision conflict');
});

test('a pending behavior Save locks navigation and editing until its result is known', async () => {
  let finish;
  const ui = editor({ apiHandler: (_url, body) => new Promise(resolve => {
    finish = () => resolve({ items: body.items, revision: 3 });
  }) });
  ui.state.hostBehaviors = [
    { id: 'a', name: 'First', instruction: 'First instruction', priority: 1, enabled: true },
    { id: 'b', name: 'Second', instruction: 'Second instruction', priority: 2, enabled: true },
  ];
  ui.state.hostBehaviorRevision = 2;
  ui.state.hostBehaviorSnapshot = JSON.stringify(ui.state.hostBehaviors);
  ui.editHostBehaviors();
  const name = ui.el.hostBehaviorList.children[0].children[0].children[0].children[1];
  name.value = 'First edited'; name.listeners.input();
  const pending = ui.saveHostBehaviors();
  assert.equal(ui.el.hostBehaviorSearch.disabled, true);
  assert.equal(ui.el.hostBehaviorSelect.disabled, true);
  assert.equal(ui.el.cancelHostBehaviors.disabled, true);
  assert.equal(ui.el.hostBehaviorList.children[0].children[0].children[0].children[1].readOnly, true);
  ui.el.hostBehaviorSearch.value = 'Second'; ui.el.hostBehaviorSearch.listeners.input();
  ui.el.hostBehaviorSelect.value = 'b'; ui.el.hostBehaviorSelect.listeners.change();
  assert.equal(ui.state.activeHostBehaviorId, 'a');
  assert.equal(ui.state.hostBehaviorQuery || '', '');
  finish(); await pending;
  assert.equal(ui.state.hostBehaviorDraft, null);
  assert.equal(ui.state.hostBehaviors[0].name, 'First edited');
  assert.equal(ui.el.hostBehaviorSearch.disabled, false);
  assert.equal(ui.el.hostBehaviorSelect.disabled, false);
});

test('task foundations use independent revisioned drafts, preserve blanks, and cancel on Return', async () => {
  let foundations = { vision: 'Original foundation', reasoning: 'Keep reasoning' };
  const ui = editor({ apiHandler: (url, body) => {
    assert.equal(url, '/v1/admin/cognitive-configuration');
    if (body) foundations = { ...foundations, ...body.task_foundations };
    return { revision: body ? 4 : 3, task_foundations: foundations };
  } });
  ui.state.taskFoundations = { ...foundations };
  const assignments = JSON.stringify(ui.state.taskModelAssignments);
  ui.openTaskProfile('vision');
  assert.equal(ui.el.taskProfileFoundation.readOnly, true);
  await ui.editTaskFoundation();
  assert.equal(ui.el.taskProfileFoundation.readOnly, false);
  assert.equal(ui.el.taskFoundationSave.disabled, true);
  ui.el.taskProfileFoundation.value = 'Unsaved';
  ui.updateTaskFoundationEditor();
  ui.closeTaskProfile();
  assert.equal(ui.state.taskFoundationDraft, null);
  assert.equal(foundations.vision, 'Original foundation');
  ui.openTaskProfile('vision');
  await ui.editTaskFoundation();
  ui.el.taskProfileFoundation.value = '';
  ui.updateTaskFoundationEditor();
  assert.equal(ui.el.taskFoundationSave.disabled, false);
  await ui.saveTaskFoundation();
  const saved = ui.calls.find(call => call.body).body;
  assert.equal(saved.expected_revision, 3);
  assert.deepEqual(Object.keys(saved.task_foundations), ['vision']);
  assert.equal(saved.task_foundations.vision, '');
  assert.equal(foundations.reasoning, 'Keep reasoning');
  assert.equal(ui.state.taskFoundations.vision, '');
  assert.equal(ui.el.taskProfileFoundation.readOnly, true);
  assert.equal(JSON.stringify(ui.state.taskModelAssignments), assignments);
});

test('a pending behavior refresh cannot promote an old draft to a newer catalog revision', async () => {
  let resolveRefresh;
  const ui = editor({ apiHandler: () => new Promise(resolve => { resolveRefresh = resolve; }) });
  const original = { id: 'behavior', name: 'Original', instruction: 'Original instruction', priority: 10, enabled: true };
  ui.state.hostBehaviors = [original];
  ui.state.hostBehaviorSnapshot = JSON.stringify([original]);
  ui.state.hostBehaviorRevision = 7;
  const pending = ui.refreshHostBehaviors();
  ui.editHostBehaviors();
  ui.state.hostBehaviorDraft[0].name = 'Draft name';
  resolveRefresh({ items: [{ ...original, name: 'Concurrent name' }], revision: 8 });
  await pending;
  assert.equal(ui.state.hostBehaviorRevision, 7);
  assert.equal(ui.state.hostBehaviors[0].name, 'Original');
  assert.equal(ui.state.hostBehaviorDraft[0].name, 'Draft name');
  assert.equal(JSON.parse(ui.state.hostBehaviorSnapshot)[0].name, 'Original');
});

function skillsEditor(apiHandler) {
  const elements = {};
  const calls = [];
  const downloads = [];
  const context = vm.createContext({
    document: {
      getElementById: id => {
        if (!elements[id]) {
          elements[id] = new Element();
          elements[id].add = option => elements[id].append(option);
        }
        return elements[id];
      },
      createElement: () => ({ click() { downloads.push(this); } }),
    },
    Option: class extends Element {
      constructor(label, value) { super('option'); this.textContent = label; this.value = value; }
    },
    Blob, URL: { createObjectURL: () => 'blob:skill', revokeObjectURL() {} },
    api: async (url, options = {}) => {
      calls.push({ url, method: options.method || 'GET', body: options.body && JSON.parse(options.body) });
      return apiHandler(url, options);
    },
  });
  vm.runInContext(source.slice(source.indexOf('let skillDraftSha = null;')), context);
  return { ...context, elements, calls, downloads };
}

const requiredSkills = [
  { slug: 'axiom-continuity', name: 'Axiom Continuity', required: true, protected: true, enabled: true, content: 'Continuity instructions.', revision: 4 },
  { slug: 'axiom-current-state', name: 'Axiom Current State', required: true, protected: true, enabled: true, content: 'Current-state instructions.', revision: 2 },
];

test('Administrator edits required Mind skills in an isolated revisioned draft even when GitHub is unavailable', async () => {
  const configurations = requiredSkills.map(item => ({ ...item }));
  const ui = skillsEditor(async (url, options) => {
    if (url === '/v1/admin/skill-configurations') return { items: configurations };
    if (url === '/v1/admin/skills') return { items: requiredSkills, drafts_available: false, drafts_error: 'GitHub access is unavailable.' };
    if (url.endsWith('/validate')) return { valid: true };
    if (options.method === 'PUT') {
      const payload = JSON.parse(options.body);
      const index = configurations.findIndex(item => url.endsWith(item.slug));
      configurations[index] = { ...payload, revision: payload.revision + 1 };
      return configurations[index];
    }
  });
  await ui.refreshSkillDrafts();
  const el = ui.elements;
  assert.deepEqual(el.skillsList.options.map(option => option.textContent), [
    'New Mind skill', 'New GitHub draft', 'Axiom Continuity · Mind', 'Axiom Current State · Mind',
  ]);
  assert.equal(el.skillsList.options[1].disabled, true);
  assert.equal(el.skillsList.value, 'mind:axiom-continuity');
  assert.equal(el.skillsContent.value, 'Continuity instructions.');
  assert.equal(el.skillsContent.readOnly, true);
  assert.equal(el.skillsSlug.readOnly, true);
  assert.equal(el.skillsSave.disabled, true);
  assert.equal(el.skillsPrepare.disabled, false);
  assert.match(el.skillsStatus.textContent, /Custom drafts unavailable.*GitHub/);
  assert.doesNotMatch(el.skillsStatus.textContent, /Drafts loaded/);
  await el.skillsSave.listeners.click();
  assert.equal(ui.calls.some(call => call.method === 'PUT'), false);
  el.skillsEdit.listeners.click();
  assert.equal(el.skillsContent.readOnly, false);
  assert.equal(el.skillsEnabled.disabled, false);
  assert.equal(el.skillsSave.disabled, true);
  el.skillsContent.value = 'Unsaved content.';
  el.skillsRequired.checked = false;
  ui.updateSkillEditorState();
  assert.equal(el.skillsSave.disabled, false);
  assert.equal(configurations[0].required, true);
  await el.skillsCancel.listeners.click();
  assert.equal(el.skillsContent.value, 'Continuity instructions.');
  assert.equal(el.skillsRequired.checked, true);
  el.skillsEdit.listeners.click();
  el.skillsName.value = 'My Continuity';
  el.skillsContent.value = 'Administrator instructions.';
  el.skillsEnabled.checked = false;
  el.skillsRequired.checked = false;
  el.skillsProtected.checked = false;
  await el.skillsSave.listeners.click();
  const saved = ui.calls.find(call => call.method === 'PUT');
  assert.equal(saved.url, '/v1/admin/skill-configurations/axiom-continuity');
  assert.equal(saved.body.revision, 4);
  assert.equal(saved.body.enabled, false);
  assert.equal(saved.body.required, false);
  assert.equal(saved.body.protected, false);
  assert.equal(el.skillsName.value, 'My Continuity');
  assert.equal(el.skillsContent.readOnly, true);
  await el.skillsPrepare.listeners.click();
  assert.equal(ui.downloads.length, 1);
  assert.equal(ui.downloads[0].download, 'axiom-continuity-SKILL.md');
});

test('GitHub drafts retain their SHA save workflow separately from effective Mind settings', async () => {
  const ui = skillsEditor(async (url, options) => {
    if (url === '/v1/admin/skill-configurations') return { items: requiredSkills };
    if (url === '/v1/admin/skills') return {
      items: [...requiredSkills, { slug: 'custom-skill', path: 'skills/drafts/custom-skill/SKILL.md', source: 'github_draft' }],
      drafts_available: true, drafts_error: null,
    };
    if (options.method === 'PUT') return { sha: 'new-sha', commit: '123456789' };
    return { content: 'Custom instructions.', sha: 'old-sha' };
  });
  await ui.refreshSkillDrafts();
  const el = ui.elements;
  el.skillsList.value = 'github:custom-skill';
  await ui.loadSkillSelection('github:custom-skill');
  assert.equal(el.skillsContent.readOnly, true);
  el.skillsEdit.listeners.click();
  assert.equal(el.skillsContent.readOnly, false);
  assert.equal(el.skillsSlug.readOnly, true);
  el.skillsContent.value = 'Updated instructions.';
  await el.skillsSave.listeners.click();
  const saved = ui.calls.find(call => call.method === 'PUT');
  assert.equal(saved.url, '/v1/admin/skills/custom-skill?source=github_draft');
  assert.equal(saved.body.content, 'Updated instructions.');
  assert.equal(saved.body.sha, 'old-sha');
  assert.equal(ui.calls.filter(call => call.method === 'PUT').length, 1);
  assert.match(el.skillsStatus.textContent, /Saved draft to GitHub/);
});

test('A slow skill read cannot overwrite the selection made after it', async () => {
  let finishFirst;
  const ui = skillsEditor(async url => {
    if (url === '/v1/admin/skill-configurations') return { items: requiredSkills };
    if (url === '/v1/admin/skills') return { items: [
      { slug: 'first-draft', path: 'skills/drafts/first-draft/SKILL.md' },
      { slug: 'second-draft', path: 'skills/drafts/second-draft/SKILL.md' },
    ], drafts_available: true };
    if (url.includes('/first-draft?')) return new Promise(resolve => { finishFirst = resolve; });
    return { content: 'Second draft instructions.', sha: 'second-sha' };
  });
  await ui.refreshSkillDrafts();
  const first = ui.loadSkillSelection('github:first-draft');
  ui.elements.skillsList.value = 'github:second-draft';
  await ui.loadSkillSelection('github:second-draft');
  finishFirst({ content: 'Old selection instructions.', sha: 'first-sha' });
  await first;
  assert.equal(ui.elements.skillsSlug.value, 'second-draft');
  assert.equal(ui.elements.skillsContent.value, 'Second draft instructions.');
  assert.equal(ui.elements.skillsSave.disabled, true);
});

test('a pending skill catalog refresh cannot overwrite an Administrator draft', async () => {
  let reads = 0;
  let resolveRefresh;
  const ui = skillsEditor(async url => {
    if (url === '/v1/admin/skill-configurations') {
      if (++reads > 1) return new Promise(resolve => { resolveRefresh = resolve; });
      return { items: requiredSkills };
    }
    return { items: requiredSkills, drafts_available: false };
  });
  await ui.refreshSkillDrafts();
  const pending = ui.refreshSkillDrafts();
  ui.elements.skillsEdit.listeners.click();
  ui.elements.skillsContent.value = 'Draft typed while refresh was pending';
  resolveRefresh({ items: requiredSkills.map(item => ({ ...item, revision: item.revision + 1, content: 'Concurrent content' })) });
  await pending;
  assert.equal(ui.elements.skillsContent.value, 'Draft typed while refresh was pending');
  assert.equal(ui.elements.skillsContent.readOnly, false);
  assert.equal(ui.skillPayload().revision, 4);
});

test('Administrator can save an intentionally blank Mind skill while GitHub still requires content', async () => {
  let configurations = requiredSkills.map(item => ({ ...item }));
  const ui = skillsEditor(async (url, options) => {
    if (options.method === 'PUT') {
      const body = JSON.parse(options.body);
      configurations = configurations.map(item => item.slug === body.slug ? { ...body, revision: body.revision + 1 } : item);
      return configurations[0];
    }
    if (url === '/v1/admin/skill-configurations') return { items: configurations };
    return { items: configurations, drafts_available: true };
  });
  await ui.refreshSkillDrafts();
  ui.elements.skillsEdit.listeners.click();
  ui.elements.skillsContent.value = '';
  ui.updateSkillEditorState();
  assert.equal(ui.elements.skillsSave.disabled, false);
  await ui.elements.skillsSave.listeners.click();
  assert.equal(ui.calls.find(call => call.method === 'PUT').body.content, '');
  assert.equal(ui.elements.skillsContent.value, '');
  await ui.loadSkillSelection('new:github');
  ui.elements.skillsSlug.value = 'new-draft';
  ui.updateSkillEditorState();
  assert.equal(ui.elements.skillsSave.disabled, true);
});

function foundationsView(apiHandler) {
  const elements = Object.fromEntries(['foundationSelfName', 'foundationPronouns', 'foundationDevelopment',
    'foundationValues', 'foundationCommitments', 'foundationRelationships', 'foundationStatus']
    .map(id => [id, new Element()]));
  const calls = [];
  const state = { foundationIdentity: null };
  const context = vm.createContext({
    state, document: { getElementById: id => elements[id] || null },
    api: async (url, options = {}, authenticated) => {
      calls.push({ url, method: options.method || 'GET', body: options.body, authenticated });
      return JSON.parse(JSON.stringify(await apiHandler(url, options)));
    },
  });
  for (const name of ['displayLabel', 'foundationIdentityText', 'renderIdentityConfiguration',
    'refreshIdentityConfiguration', 'refreshFoundations']) {
    const start = source.search(new RegExp(`^(?:async )?function ${name}\\(`, 'm'));
    assert.ok(start >= 0, `${name} exists`);
    const next = source.slice(start + 1).search(/^(?:async )?function |^const |^let |^for |^document\.|^el\.|^if \(/m);
    vm.runInContext(source.slice(start, next < 0 ? source.length : start + 1 + next), context);
  }
  return { ...context, elements, calls };
}

test('Foundations loads the complete identity as readable text without interpreting markup', async () => {
  const identity = { revision: 'current', identity: { self_name: '<img src=x onerror=alert(1)>', pronouns: 'she/her',
    foundational_values: ['Care', 'Curiosity'], commitments: ['Listen'],
    relationships: [{ label: 'Will', facts: ['Collaborator', 'Has a son'] }] }, developmental_state: 'genesis' };
  const ui = foundationsView(() => identity);
  await ui.refreshIdentityConfiguration();
  const el = ui.elements;
  assert.equal(el.foundationSelfName.textContent, identity.identity.self_name);
  assert.equal(el.foundationSelfName.children.length, 0);
  assert.equal(el.foundationPronouns.textContent, 'she/her');
  assert.equal(el.foundationDevelopment.textContent, 'genesis');
  assert.equal(el.foundationValues.textContent, 'Care\nCuriosity');
  assert.equal(el.foundationCommitments.textContent, 'Listen');
  assert.equal(el.foundationRelationships.textContent, 'Label: Will\nFacts: Collaborator\nHas a son');
  assert.equal(el.foundationStatus.textContent, 'Identity loaded.');
  assert.equal(ui.state.foundationIdentity.revision, 'current');
});

test('Foundations distinguishes unavailable identity from unselected and empty identity fields', async () => {
  const ui = foundationsView(() => ({ identity: { self_name: null, pronouns: null,
    foundational_values: [], commitments: [], relationships: [] }, developmental_state: 'genesis' }));
  ui.renderIdentityConfiguration();
  for (const name of ['SelfName', 'Pronouns', 'Development', 'Values', 'Commitments', 'Relationships']) {
    assert.equal(ui.elements['foundation' + name].textContent, 'Unknown');
  }
  await ui.refreshIdentityConfiguration();
  assert.equal(ui.elements.foundationSelfName.textContent, 'Not selected');
  assert.equal(ui.elements.foundationPronouns.textContent, 'Unknown');
  for (const name of ['Values', 'Commitments', 'Relationships']) {
    assert.equal(ui.elements['foundation' + name].textContent, 'None recorded');
  }
});

test('refreshing Foundations only reads identity and does not fetch or write startup configuration', async () => {
  const ui = foundationsView(() => ({ identity: { self_name: 'Axiom' } }));
  await ui.refreshFoundations();
  assert.deepEqual(ui.calls, [{ url: '/v1/admin/identity', method: 'GET', body: undefined, authenticated: true }]);
  assert.equal(ui.elements.foundationStatus.textContent, 'Identity loaded.');
});

test('an older identity response cannot overwrite a newer refresh', async () => {
  const requests = [];
  const ui = foundationsView(() => new Promise(resolve => requests.push(resolve)));
  const older = ui.refreshIdentityConfiguration();
  const newer = ui.refreshIdentityConfiguration();
  assert.match(ui.elements.foundationStatus.textContent, /Loading identity/);
  requests[1]({ revision: 'new', identity: { self_name: 'Current name' } });
  await newer;
  requests[0]({ revision: 'old', identity: { self_name: 'Older name' } });
  await older;
  assert.equal(ui.elements.foundationSelfName.textContent, 'Current name');
  assert.equal(ui.state.foundationIdentity.revision, 'new');
  assert.equal(ui.elements.foundationStatus.textContent, 'Identity loaded.');
});

test('an older identity failure cannot clear a successful newer refresh', async () => {
  const requests = [];
  const ui = foundationsView(() => new Promise((resolve, reject) => requests.push({ resolve, reject })));
  const older = ui.refreshIdentityConfiguration();
  const newer = ui.refreshIdentityConfiguration();
  requests[1].resolve({ revision: 'new', identity: { self_name: 'Current name' } });
  await newer;
  requests[0].reject(new Error('Earlier request failed'));
  await older;
  assert.equal(ui.elements.foundationSelfName.textContent, 'Current name');
  assert.equal(ui.state.foundationIdentity.revision, 'new');
  assert.equal(ui.elements.foundationStatus.textContent, 'Identity loaded.');
});

test('a failed current identity refresh clears old identity and reports the failure', async () => {
  let reads = 0;
  const ui = foundationsView(() => {
    if (++reads > 1) throw new Error('Identity is unavailable');
    return { identity: { self_name: 'Old name', pronouns: 'she/her', foundational_values: ['Care'],
      commitments: ['Listen'], relationships: [{ label: 'Will' }] }, developmental_state: 'genesis' };
  });
  await ui.refreshIdentityConfiguration();
  await ui.refreshIdentityConfiguration();
  assert.equal(ui.state.foundationIdentity, null);
  for (const name of ['SelfName', 'Pronouns', 'Development', 'Values', 'Commitments', 'Relationships']) {
    assert.equal(ui.elements['foundation' + name].textContent, 'Unknown');
  }
  assert.equal(ui.elements.foundationStatus.textContent, 'Identity is unavailable');
  assert.equal(ui.calls.length, 2);
});

function currentStatePortal({ diagnosticsHandler, bodySettings = true, fallbackSettings = bodySettings, voiceHandler } = {}) {
  const elements = new Proxy({}, { get: (target, id) => {
    if (!target[id]) {
      target[id] = new Element();
      target[id].appendChild = child => target[id].append(child);
    }
    return target[id];
  } });
  const calls = [];
  const requests = [];
  const updates = [];
  const toasts = [];
  const failures = { diagnostics: null };
  const state = { mode: 'mind', adminAuthorized: false, activeTaskProfile: null };
  const identity = { self_name: null, pronouns: 'she/her', developmental_state: 'genesis' };
  const fields = {
    identity: { value: identity, status: 'current', source: 'persistent_mind_identity', observed_at: '2026-10-25T20:00:00Z' },
    mood: { value: null, status: 'unknown' }, locality: { value: null, status: 'unknown' },
    who_is_present: { value: null, status: 'unknown' }, who_is_speaking: { value: null, status: 'unknown' },
    current_context: { value: 'Current interaction', status: 'current' },
  };
  const status = { mind: { identity, developmental_state: 'genesis', created_at: '2026-10-25T00:00:00Z' },
    integration: {}, durable_memory_count: 1, journal_experience_count: 2,
    administration: { body_settings_available: bodySettings, body_fallback_settings_available: fallbackSettings } };
  const context = vm.createContext({
    state, el: elements, filters: { admin: {}, mind: {} },
    document: { getElementById: id => elements[id], createElement: tag => new Element(tag) },
    displayLabel: value => value, formatBrowserDateTime: value => value,
    validateAdmin: async () => { state.adminAuthorized = true; return true; },
    refreshMemory() { updates.push('memory'); }, refreshJournal() { updates.push('journal'); },
    refreshHostBehaviors() { updates.push('behaviors'); }, refreshTaskModelAssignments() { updates.push('tasks'); },
    refreshTaskBehaviors() {}, refreshProviderEndpoints() { updates.push('endpoints'); }, refreshMcpServers() {},
    refreshSkillDrafts() {}, refreshDeviceInventory() {}, refreshFoundations() {}, toast: (...args) => toasts.push(args),
    api: async (url, options = {}) => {
      calls.push(url);
      requests.push({ url, method: options.method || 'GET', body: options.body && JSON.parse(options.body) });
      if (url === '/v1/admin/body/voice/settings') {
        if (voiceHandler) return voiceHandler(options);
        return { revision: 3, rate: 1.2, pitch: 0.9, volume: 0.8, voiceName: 'Saved voice' };
      }
      if (url === '/v1/admin/body/fallback') return { enabled: true, runtime_override: null, deployment_default: true };
      if (url === '/v1/portal/status') return status;
      if (url === '/v1/admin/diagnostics') {
        if (diagnosticsHandler) return diagnosticsHandler();
        if (failures.diagnostics) throw failures.diagnostics;
        return { current_state: { fields }, performance: { samples: [
          { status: 200, duration_ms: 5, time: '2026-10-25T20:00:00Z', operation: 'State read' },
        ] } };
      }
      throw new Error('Unexpected API request: ' + url);
    },
  });
  vm.runInContext(source.match(/^let diagnosticsRevision = .*;$/m)[0], context);
  for (const name of ['setMode', 'bodySettingsAvailable', 'bodyFallbackSettingsAvailable', 'renderBodySettingsAvailability', 'updateVoiceSliderReadouts',
    'loadVoiceSettings', 'saveVoiceSettings', 'refreshBodyFallbackSettings', 'saveBodyFallbackSettings',
    'enterAdminMode', 'renderStatus', 'refreshStatus', 'refresh',
    'formatCurrentIdentity', 'refreshDiagnostics', 'refreshAdmin']) {
    const start = source.search(new RegExp(`^(?:async )?function ${name}\\(`, 'm'));
    assert.ok(start >= 0, `${name} exists`);
    const next = source.slice(start + 1).search(/^(?:async )?function |^const |^let |^document\.|^if \(|^refresh\(\);/m);
    vm.runInContext(source.slice(start, next < 0 ? source.length : start + 1 + next), context);
  }
  return { ...context, elements, calls, requests, updates, toasts, fields, status, failures };
}

test('entering Administration again loads current diagnostics instead of retaining earlier state', async () => {
  const ui = currentStatePortal();
  await ui.enterAdminMode();
  assert.equal(ui.calls.filter(url => url === '/v1/admin/diagnostics').length, 1);
  ui.setMode('mind');
  ui.fields.current_context.value = 'New interaction';
  await ui.enterAdminMode();
  assert.equal(ui.calls.filter(url => url === '/v1/admin/diagnostics').length, 2);
  const rows = ui.elements.cognitiveStateSummary.children;
  assert.equal(rows.at(-1).children[1].textContent, 'New interaction');
});

test('Refresh loads diagnostics once while in Administration and does not request them in Mind view', async () => {
  const ui = currentStatePortal();
  await ui.refresh();
  assert.equal(ui.calls.includes('/v1/admin/diagnostics'), false);
  await ui.enterAdminMode();
  ui.calls.length = 0;
  await ui.refresh();
  assert.equal(ui.calls.filter(url => url === '/v1/admin/diagnostics').length, 1);
  ui.calls.length = 0;
  await ui.refreshAdmin();
  assert.equal(ui.calls.filter(url => url === '/v1/admin/diagnostics').length, 1);
});

test('an unchosen self-name leaves explicit headings and a useful identity summary without guessing physical state', async () => {
  const ui = currentStatePortal();
  const original = JSON.stringify(ui.status);
  ui.renderStatus(ui.status);
  for (const id of ['mindName', 'selfName', 'adminMindName']) {
    assert.equal(ui.elements[id].textContent, 'Self-name not set');
  }
  ui.state.adminAuthorized = true;
  await ui.refreshDiagnostics();
  const rows = ui.elements.cognitiveStateSummary.children;
  assert.match(rows[0].children[1].textContent, /Persistent cognitive Mind; self-name not set/);
  assert.match(rows[0].children[1].textContent, /pronouns: she\/her/);
  assert.equal(rows[0].children[1].title, 'current | persistent_mind_identity | 2026-10-25T20:00:00Z');
  for (const row of rows.slice(1, 5)) assert.equal(row.children[1].textContent, 'Unknown');
  assert.equal(JSON.parse(ui.elements.currentStateDiagnostics.textContent).fields.identity.value.self_name, null);
  assert.equal(JSON.stringify(ui.status), original);
  ui.status.mind.identity.self_name = 'Chosen Name';
  ui.renderStatus(ui.status);
  for (const id of ['mindName', 'selfName', 'adminMindName']) {
    assert.equal(ui.elements[id].textContent, 'Chosen Name');
  }
  assert.match(ui.formatCurrentIdentity(ui.status.mind.identity), /self-name: Chosen Name/);
  assert.equal(ui.formatCurrentIdentity(null), 'Unknown');
});

test('a failed diagnostics refresh replaces earlier state rows with the current load failure', async () => {
  const ui = currentStatePortal();
  ui.state.adminAuthorized = true;
  await ui.refreshDiagnostics();
  assert.equal(ui.elements.cognitiveStateSummary.children.length, 6);
  assert.equal(ui.elements.apiActivityList.children.length, 1);
  ui.failures.diagnostics = new Error('Service unavailable');
  await ui.refreshDiagnostics();
  assert.equal(ui.elements.cognitiveStateSummary.children.length, 0);
  assert.equal(ui.elements.cognitiveStateSummary.textContent, 'Cannot load current state: Service unavailable');
  assert.equal(ui.elements.currentStateDiagnostics.textContent, 'Cannot load state: Service unavailable');
  assert.equal(ui.elements.apiActivityList.children.length, 0);
  assert.equal(ui.elements.apiActivitySummary.textContent, 'API activity unavailable.');
  assert.equal(ui.elements.apiActivityList.textContent, 'Cannot load API activity: Service unavailable');
  ui.failures.diagnostics = null;
  await ui.refreshDiagnostics();
  assert.equal(ui.elements.cognitiveStateSummary.children.length, 6);
  assert.equal(JSON.parse(ui.elements.currentStateDiagnostics.textContent).fields.identity.source, 'persistent_mind_identity');
});

test('an older diagnostics success or failure cannot replace a newer refresh result', async () => {
  for (const olderFails of [false, true]) {
    const pending = [];
    const ui = currentStatePortal({ diagnosticsHandler: () => new Promise((resolve, reject) => pending.push({ resolve, reject })) });
    ui.state.adminAuthorized = true;
    const older = ui.refreshDiagnostics();
    const newer = ui.refreshDiagnostics();
    const payload = context => ({ current_state: { fields: {
      ...ui.fields, current_context: { status: 'current', value: context },
    } }, performance: { samples: [] } });
    pending[1].resolve(payload('Latest interaction'));
    await newer;
    const latest = ui.elements.currentStateDiagnostics.textContent;
    if (olderFails) pending[0].reject(new Error('Older request failed'));
    else pending[0].resolve(payload('Older interaction'));
    await older;
    assert.equal(ui.elements.currentStateDiagnostics.textContent, latest);
    assert.equal(ui.elements.cognitiveStateSummary.children.at(-1).children[1].textContent, 'Latest interaction');
    assert.equal(ui.calls.length, 2);
  }
});


test('account-scoped Admin refresh skips global Body settings while other available data refreshes', async () => {
  const ui = currentStatePortal({ bodySettings: false });
  ui.state.mode = 'admin';
  ui.state.adminAuthorized = true;
  ui.state.status = { administration: { body_settings_available: true } };
  await ui.refreshAdmin();
  assert.equal(ui.calls[0], '/v1/portal/status');
  assert.equal(ui.calls.some(url => url.startsWith('/v1/admin/body/')), false);
  assert.equal(ui.calls.includes('/v1/admin/diagnostics'), true);
  for (const update of ['memory', 'journal', 'behaviors', 'tasks', 'endpoints']) assert.ok(ui.updates.includes(update));
  for (const name of ['voiceRate', 'voicePitch', 'voiceVolume', 'voiceName', 'saveVoiceSettings']) {
    assert.equal(ui.elements[name].disabled, true);
  }
  assert.equal(ui.elements.voiceSettingsStatus.textContent, 'Unavailable for this account.');
  assert.equal(ui.toasts.length, 0);
  await ui.saveVoiceSettings();
  await ui.saveBodyFallbackSettings();
  assert.equal(ui.calls.some(url => url.startsWith('/v1/admin/body/')), false);
});

test('authorized root Admin loads and saves voice settings after current capabilities are known', async () => {
  const ui = currentStatePortal();
  await ui.enterAdminMode();
  assert.equal(ui.calls[0], '/v1/portal/status');
  assert.equal(ui.calls.filter(url => url === '/v1/admin/body/voice/settings').length, 1);
  assert.equal(ui.calls.filter(url => url === '/v1/admin/body/fallback').length, 1);
  assert.equal(ui.elements.voiceRate.value, '1.2');
  assert.equal(ui.elements.voiceName.value, 'Saved voice');
  assert.equal(ui.elements.saveVoiceSettings.disabled, false);
  assert.equal(ui.elements.voiceSettingsStatus.textContent, '');
  ui.elements.voiceName.value = 'Changed voice';
  await ui.saveVoiceSettings();
  assert.deepEqual(ui.requests.find(request => request.method === 'POST').body, {
    expected_revision: 3, rate: 1.2, pitch: 0.9, volume: 0.8, voice_name: 'Changed voice',
  });
});

test('anonymous or unknown-scope refresh cannot request or save deployment Body settings', async () => {
  const ui = currentStatePortal();
  await ui.refresh();
  await ui.loadVoiceSettings();
  await ui.saveVoiceSettings();
  await ui.refreshBodyFallbackSettings();
  await ui.saveBodyFallbackSettings();
  assert.deepEqual(ui.calls, ['/v1/portal/status']);
  assert.equal(ui.elements.saveVoiceSettings.disabled, true);
  ui.state.adminAuthorized = true;
  delete ui.status.administration.body_settings_available;
  await ui.refresh();
  await ui.loadVoiceSettings();
  await ui.saveVoiceSettings();
  assert.equal(ui.calls.some(url => url.startsWith('/v1/admin/body/')), false);
});

test('a failed permitted voice read disables Save and does not stop other Admin refreshes', async () => {
  const ui = currentStatePortal({ voiceHandler: () => { throw new Error('Voice store unavailable'); } });
  await ui.enterAdminMode();
  assert.equal(ui.elements.saveVoiceSettings.disabled, true);
  assert.equal(ui.elements.voiceRate.disabled, true);
  assert.equal(ui.elements.voiceSettingsStatus.textContent, 'Voice store unavailable');
  for (const update of ['memory', 'journal', 'behaviors', 'tasks', 'endpoints']) assert.ok(ui.updates.includes(update));
  await ui.saveVoiceSettings();
  assert.equal(ui.requests.some(request => request.method === 'POST'), false);
});

test('switching to account scope clears loaded root voice values and ignores an in-flight read', async () => {
  let resolveVoice;
  const ui = currentStatePortal({ voiceHandler: () => new Promise(resolve => { resolveVoice = resolve; }) });
  ui.state.adminAuthorized = true;
  ui.renderStatus(ui.status);
  const pending = ui.loadVoiceSettings();
  ui.status.administration.body_settings_available = false;
  ui.elements.voiceName.value = 'Previously loaded root voice';
  ui.renderStatus(ui.status);
  resolveVoice({ revision: 4, rate: 1.5, voiceName: 'Old root voice' });
  await pending;
  assert.equal(ui.elements.voiceName.value, '');
  assert.equal(ui.elements.voiceRate.value, '1');
  assert.equal(ui.elements.saveVoiceSettings.disabled, true);
  assert.equal(ui.state.voiceSettingsLoaded, false);
  assert.equal(ui.elements.voiceSettingsStatus.textContent, 'Unavailable for this account.');
  assert.equal(ui.toasts.length, 0);
});


test('scoped voice settings can refresh and save while the deployment fallback switch stays unavailable', async () => {
  const ui = currentStatePortal({ bodySettings: true, fallbackSettings: false });
  await ui.enterAdminMode();
  assert.equal(ui.calls.includes('/v1/admin/body/voice/settings'), true);
  assert.equal(ui.calls.includes('/v1/admin/body/fallback'), false);
  assert.equal(ui.elements.saveVoiceSettings.disabled, false);
  assert.equal(ui.elements.saveBodyFallbackSetting.disabled, true);
  await ui.saveBodyFallbackSettings();
  assert.equal(ui.calls.includes('/v1/admin/body/fallback'), false);
  ui.elements.voiceName.value = 'Account voice';
  await ui.saveVoiceSettings();
  assert.equal(ui.requests.find(request => request.method === 'POST').body.voice_name, 'Account voice');
});

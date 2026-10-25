const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../src/aicognitive_mind/static/portal.js'), 'utf8');
const editorFunctions = [
  'selectedEndpoint', 'renderTaskProfileEndpointOptions', 'fillSelect', 'modelCapabilityLabel',
  'loadEndpointIntoForm', 'renderEndpointModelStatus', 'endpointFormIsValid', 'syncEndpointDraft',
  'updateEndpointEditorState', 'editEndpoint', 'cancelEndpointEdit', 'saveProviderEndpoints',
  'removeEndpoint', 'discoverTaskProfileModels', 'addTaskProfileEndpoint', 'applyEndpointTemplate',
  'selectedMcpServer', 'syncMcpServerForm', 'updateMcpEditorState', 'editMcpServer',
  'cancelMcpEdit', 'renderMcpServerOptions', 'loadMcpServerIntoForm', 'renderMcpTools',
  'addMcpServer', 'saveMcpServers', 'removeMcpServer', 'discoverMcpTools',
  'allTaskNames', 'renderTaskProfiles', 'taskEndpointOptions', 'selectedTaskBehaviorIds',
  'taskBehaviorCatalog',
  'taskProfileConfiguration', 'updateTaskSaveState', 'renderTaskBehaviorSelection',
  'renderFallbackSelectors', 'openTaskProfile', 'closeTaskProfile', 'discardTaskProfileChanges',
  'saveTaskProfile',
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
  const el = new Proxy({}, { get: (target, name) => target[name] ||= new Element() });
  const state = {
    providerEndpoints: [{ id: 'openai', name: 'OpenAI - GPT', provider_name: 'OpenAI', model: 'gpt-test',
      base_url: 'https://provider.example/v1', api_key: 'test-key', models: ['gpt-test'], model_capabilities: {} }],
    activeEndpointId: 'openai', endpointDraft: null, endpointEditBaseline: '', endpointDiscovering: false,
    mcpServers: [{ id: 'tools', name: 'Tools', url: 'https://tools.example/mcp', bearer_token: '',
      enabled: true, tools: [{ name: 'lookup', enabled: true }] }],
    activeMcpServerId: 'tools', mcpServerDraft: null, mcpEditBaseline: '', integrationSaving: false,
    taskModelAssignments: [{ task: 'vision', provider: 'openai', model: 'gpt-test',
      fallbacks: [{ provider: 'OpenAI - GPT', model: 'gpt-test' }] }],
    taskBehaviors: [], taskFoundations: {}, hostBehaviors: [], activeTaskProfile: null,
  };
  const calls = [];
  const toasts = [];
  const context = vm.createContext({
    state, el, COMMON_ENDPOINT_PRESETS: [], crypto: { randomUUID: () => 'new-id' },
    taskModelLabels: { reasoning: 'Reasoning', vision: 'Vision', audio_voice: 'Audio/Voice' },
    displayLabel: value => value,
    Option: class extends Element {
      constructor(label, value) { super('option'); this.textContent = label; this.value = value; }
    },
    document: { createElement: tag => new Element(tag), createTextNode: value => value },
    renderTaskProfiles() {}, toast: (...args) => toasts.push(args),
    resetEndpointApiKeyVisibility() {}, toggleEndpointApiKeyVisibility() {},
    api: async (url, options) => {
      const body = JSON.parse(options.body);
      calls.push({ url, body });
      if (apiHandler) return apiHandler(url, body, options);
      return body;
    },
  });
  for (const name of editorFunctions) {
    const start = source.search(new RegExp(`^(?:async )?function ${name}\\(`, 'm'));
    assert.ok(start >= 0, `${name} exists`);
    const next = source.slice(start + 1).search(/^(?:async )?function |^const /m);
    vm.runInContext(source.slice(start, next < 0 ? source.length : start + 1 + next), context);
  }
  for (const name of ['resetEndpointApiKeyVisibility', 'toggleEndpointApiKeyVisibility']) {
    const start = source.search(new RegExp(`^(?:async )?function ${name}\\(`, 'm'));
    if (start < 0) continue;
    const next = source.slice(start + 1).search(/^(?:async )?function |^const /m);
    vm.runInContext(source.slice(start, next < 0 ? source.length : start + 1 + next), context);
  }
  const primaryHandler = source.indexOf('el.taskProviderSelect.addEventListener("change", () => {');
  const primaryHandlerEnd = source.indexOf('\n});', primaryHandler);
  vm.runInContext(source.slice(primaryHandler, primaryHandlerEnd + 4), context);
  context.loadEndpointIntoForm();
  context.loadMcpServerIntoForm();
  return { ...context, calls, toasts };
}

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
  assert.equal(ui.el.taskProfileEndpointName.value, draft.name);
  assert.equal(ui.el.taskProfileApiKey.value, 'test-key');
  assert.equal(ui.el.saveProviderEndpoints.disabled, true);
  draft.models.push('draft-only-model');
  draft.model_capabilities['gpt-test'].push('Vision');
  draft.model_capability_sources['gpt-test'] = 'draft-only-source';
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

test('Reasoning exposes endpoint and fallbacks, saves selected behaviors, and locks protected behaviors', async () => {
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
  assert.equal(protectedToggle.checked, true);
  assert.equal(protectedToggle.disabled, true);
  const optionalToggle = ui.el.taskProfileBehaviorSelection.children[1].children[0];
  optionalToggle.checked = true;
  optionalToggle.listeners.change();
  assert.equal(ui.el.saveTaskProfile.disabled, false);
  await ui.saveTaskProfile();
  const assignment = ui.calls.at(-1).body.items.find(item => item.task === 'reasoning');
  assert.deepEqual([...assignment.behavior_ids].sort(), ['optional', 'protected']);
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
  { slug: 'axiom-continuity', name: 'Axiom Continuity', required: true, read_only: true },
  { slug: 'axiom-current-state', name: 'Axiom Current State', required: true, read_only: true },
];

test('Skills shows named required instructions when custom drafts are unavailable and blocks saving them', async () => {
  const ui = skillsEditor(async url => {
    if (url === '/v1/admin/skills') return { items: requiredSkills, drafts_available: false, drafts_error: 'GitHub access is unavailable.' };
    if (url.endsWith('/validate')) return { valid: true };
    return { ...requiredSkills.find(item => url.endsWith(item.slug)), content: 'Required instructions.', sha: null };
  });
  await ui.refreshSkillDrafts();
  const el = ui.elements;
  assert.deepEqual(el.skillsList.options.map(option => option.textContent), [
    'New skill', 'Axiom Continuity (required)', 'Axiom Current State (required)',
  ]);
  assert.equal(el.skillsList.options[0].disabled, true);
  assert.equal(el.skillsList.value, 'axiom-continuity');
  assert.equal(el.skillsContent.value, 'Required instructions.');
  assert.equal(el.skillsContent.readOnly, true);
  assert.equal(el.skillsSlug.readOnly, true);
  assert.equal(el.skillsSave.disabled, true);
  assert.equal(el.skillsPrepare.disabled, false);
  assert.match(el.skillsStatus.textContent, /Custom drafts unavailable.*GitHub/);
  assert.doesNotMatch(el.skillsStatus.textContent, /Drafts loaded/);
  await el.skillsSave.listeners.click();
  assert.equal(ui.calls.some(call => call.method === 'PUT'), false);
  await el.skillsPrepare.listeners.click();
  assert.equal(ui.downloads.length, 1);
  assert.equal(ui.downloads[0].download, 'axiom-continuity-SKILL.md');
});

test('Skills preserves custom draft editing and prevents a new draft from replacing a required skill', async () => {
  const ui = skillsEditor(async (url, options) => {
    if (url === '/v1/admin/skills') return {
      items: [...requiredSkills, { slug: 'custom-skill', required: false, read_only: false }],
      drafts_available: true, drafts_error: null,
    };
    if (options.method === 'PUT') return { sha: 'new-sha', commit: '123456789' };
    return { content: 'Custom instructions.', sha: 'old-sha' };
  });
  await ui.refreshSkillDrafts();
  const el = ui.elements;
  el.skillsList.value = 'custom-skill';
  await ui.loadSkillSelection('custom-skill');
  assert.equal(el.skillsContent.readOnly, false);
  assert.equal(el.skillsSlug.readOnly, false);
  el.skillsContent.value = 'Updated instructions.';
  await el.skillsSave.listeners.click();
  const saved = ui.calls.find(call => call.method === 'PUT');
  assert.equal(saved.url, '/v1/admin/skills/custom-skill');
  assert.equal(saved.body.content, 'Updated instructions.');
  assert.equal(saved.body.sha, 'old-sha');
  await ui.loadSkillSelection('');
  el.skillsSlug.value = 'axiom-continuity';
  el.skillsContent.value = 'Replacement instructions.';
  ui.updateSkillEditorState();
  assert.equal(el.skillsSlug.readOnly, false);
  assert.equal(el.skillsSave.disabled, true);
  await el.skillsSave.listeners.click();
  assert.equal(ui.calls.filter(call => call.method === 'PUT').length, 1);
});

test('A slow skill read cannot overwrite the selection made after it', async () => {
  let finishFirst;
  const ui = skillsEditor(async url => {
    if (url === '/v1/admin/skills') return { items: requiredSkills, drafts_available: true };
    if (url.endsWith('axiom-continuity')) return new Promise(resolve => { finishFirst = resolve; });
    return { ...requiredSkills[1], content: 'Current-state instructions.', sha: null };
  });
  const first = ui.refreshSkillDrafts();
  await new Promise(resolve => setImmediate(resolve));
  ui.elements.skillsList.value = 'axiom-current-state';
  await ui.loadSkillSelection('axiom-current-state');
  finishFirst({ ...requiredSkills[0], content: 'Old selection instructions.', sha: null });
  await first;
  assert.equal(ui.elements.skillsSlug.value, 'axiom-current-state');
  assert.equal(ui.elements.skillsContent.value, 'Current-state instructions.');
  assert.equal(ui.elements.skillsSave.disabled, true);
});

function currentStatePortal({ diagnosticsHandler } = {}) {
  const elements = new Proxy({}, { get: (target, id) => {
    if (!target[id]) {
      target[id] = new Element();
      target[id].appendChild = child => target[id].append(child);
    }
    return target[id];
  } });
  const calls = [];
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
    integration: {}, durable_memory_count: 1, journal_experience_count: 2 };
  const context = vm.createContext({
    state, el: elements, filters: { admin: {}, mind: {} },
    document: { getElementById: id => elements[id], createElement: tag => new Element(tag) },
    displayLabel: value => value, formatBrowserDateTime: value => value,
    validateAdmin: async () => { state.adminAuthorized = true; return true; },
    refreshMemory() {}, refreshJournal() {}, refreshHostBehaviors() {}, refreshTaskModelAssignments() {},
    refreshTaskBehaviors() {}, refreshProviderEndpoints() {}, refreshMcpServers() {}, loadVoiceSettings() {},
    refreshBodyFallbackSettings() {}, refreshSkillDrafts() {}, refreshDeviceInventory() {}, toast() {},
    api: async url => {
      calls.push(url);
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
  for (const name of ['setMode', 'enterAdminMode', 'renderStatus', 'refreshStatus', 'refresh',
    'formatCurrentIdentity', 'refreshDiagnostics', 'refreshAdmin']) {
    const start = source.search(new RegExp(`^(?:async )?function ${name}\\(`, 'm'));
    assert.ok(start >= 0, `${name} exists`);
    const next = source.slice(start + 1).search(/^(?:async )?function |^const |^let |^document\.|^if \(|^refresh\(\);/m);
    vm.runInContext(source.slice(start, next < 0 ? source.length : start + 1 + next), context);
  }
  return { ...context, elements, calls, fields, status, failures };
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

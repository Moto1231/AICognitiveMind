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
  'removeEndpoint', 'discoverTaskProfileModels', 'addTaskProfileEndpoint',
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
    this.classes = new Set();
    this.classList = {
      toggle: (name, on) => on ? this.classes.add(name) : this.classes.delete(name),
      add: name => this.classes.add(name), remove: name => this.classes.delete(name),
    };
  }
  get options() { return this.children; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute() {}
  addEventListener(name, listener) { this.listeners[name] = listener; }
  focus() {}
}

function editor() {
  const el = new Proxy({}, { get: (target, name) => target[name] ||= new Element() });
  const state = {
    providerEndpoints: [{ id: 'openai', name: 'OpenAI - GPT', provider_name: 'OpenAI', model: 'gpt-test',
      base_url: 'https://provider.example/v1', api_key: 'test-key', models: ['gpt-test'], model_capabilities: {} }],
    activeEndpointId: 'openai', endpointDraft: null, endpointEditBaseline: '',
    mcpServers: [{ id: 'tools', name: 'Tools', url: 'https://tools.example/mcp', bearer_token: '',
      enabled: true, tools: [{ name: 'lookup', enabled: true }] }],
    activeMcpServerId: 'tools', mcpServerDraft: null, mcpEditBaseline: '', integrationSaving: false,
    taskModelAssignments: [{ task: 'vision', provider: 'openai', model: 'gpt-test',
      fallbacks: [{ provider: 'OpenAI - GPT', model: 'gpt-test' }] }],
    taskBehaviors: [], taskFoundations: {}, hostBehaviors: [], activeTaskProfile: null,
  };
  const calls = [];
  const context = vm.createContext({
    state, el, COMMON_ENDPOINT_PRESETS: [], crypto: { randomUUID: () => 'new-id' },
    taskModelLabels: { reasoning: 'Reasoning', vision: 'Vision', audio_voice: 'Audio/Voice' },
    displayLabel: value => value,
    Option: class extends Element {
      constructor(label, value) { super('option'); this.textContent = label; this.value = value; }
    },
    document: { createElement: tag => new Element(tag), createTextNode: value => value },
    renderTaskProfiles() {}, toast() {},
    api: async (url, options) => {
      const body = JSON.parse(options.body);
      calls.push({ url, body });
      return body;
    },
  });
  for (const name of editorFunctions) {
    const start = source.search(new RegExp(`^(?:async )?function ${name}\\(`, 'm'));
    assert.ok(start >= 0, `${name} exists`);
    const next = source.slice(start + 1).search(/^(?:async )?function |^const /m);
    vm.runInContext(source.slice(start, next < 0 ? source.length : start + 1 + next), context);
  }
  const primaryHandler = source.indexOf('el.taskProviderSelect.addEventListener("change", () => {');
  const primaryHandlerEnd = source.indexOf('\n});', primaryHandler);
  vm.runInContext(source.slice(primaryHandler, primaryHandlerEnd + 4), context);
  context.loadEndpointIntoForm();
  context.loadMcpServerIntoForm();
  return { ...context, calls };
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
  assert.equal(ui.el.saveProviderEndpoints.disabled, true);
  ui.cancelEndpointEdit();
  assert.equal(ui.state.endpointDraft, null);
  assert.equal(ui.state.activeEndpointId, 'openai');
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

test('legacy task model survives same endpoint selection and behavior-only saves', () => {
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
  assert.equal(ui.el.saveTaskProfile.disabled, true);
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

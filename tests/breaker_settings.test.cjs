const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(
  path.join(__dirname, '../src/aicognitive_mind/static/portal.js'), 'utf8',
);

class Element {
  constructor() {
    this.value = '';
    this.textContent = '';
    this.readOnly = false;
    this.disabled = false;
  }
}

function breakerEditor(apiHandler) {
  const elements = new Proxy({}, { get: (target, id) => target[id] ||= new Element() });
  const state = {
    breakerSettings: null, breakerDraft: null, breakerSaving: false,
    breakerResetting: false, breakerLoadRevision: 0,
  };
  const calls = [];
  const context = vm.createContext({
    state,
    document: { getElementById: id => elements[id] },
    window: { confirm: () => true },
    displayLabel: value => String(value).replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase()),
    api: async (url, options = {}) => {
      const body = options.body ? JSON.parse(options.body) : undefined;
      calls.push({ url, body, method: options.method || 'GET' });
      return apiHandler(url, body, options);
    },
  });
  const constantsStart = source.indexOf('const breakerFieldIds = {');
  const constantsEnd = source.indexOf('function breakerFormPayload', constantsStart);
  vm.runInContext(source.slice(constantsStart, constantsEnd), context);
  const names = [
    'breakerFormPayload', 'breakerFormValid', 'renderBreakerSettings',
    'updateBreakerEditorState', 'refreshBreakerSettings', 'editBreakerSettings',
    'cancelBreakerSettings', 'saveBreakerSettings', 'resetBreakerHealth',
  ];
  const starts = names.map(name => {
    const start = source.search(new RegExp(`^(?:async )?function ${name}\\(`, 'm'));
    assert.ok(start >= 0, `${name} exists`);
    return start;
  });
  for (let index = 0; index < names.length; index += 1) {
    const end = starts[index + 1]
      ?? source.indexOf('\nfunction updateTaskFoundationEditor', starts[index]);
    vm.runInContext(source.slice(starts[index], end), context);
  }
  return { ...context, elements, calls };
}

const snapshot = {
  revision: 3,
  consecutive_failure_limit: 5,
  rolling_failure_limit: 35,
  rolling_window_size: 100,
  provider_request_timeout_seconds: 30,
  steward_assessment_timeout_seconds: 60,
  rate_limit_retry_wait_cap_seconds: 45,
  health: {
    status: 'closed', consecutive_failures: 1, rolling_failures: 7,
    rolling_sample_size: 52, rolling_window_ready: false, degraded_reviews: 3,
    last_failure_class: 'StorageTimeout',
    last_degradation_class: 'StewardAssessmentTimeout',
  },
};

test('The Breaker form loads locked and shows current operational counts', async () => {
  const ui = breakerEditor(async () => structuredClone(snapshot));
  await ui.refreshBreakerSettings();
  assert.equal(ui.elements.breakerConsecutiveLimit.value, 5);
  assert.equal(ui.elements.breakerConsecutiveLimit.readOnly, true);
  assert.equal(ui.elements.breakerEdit.disabled, false);
  assert.equal(ui.elements.breakerSave.disabled, true);
  assert.equal(ui.elements.breakerHealthStatus.textContent, 'Closed');
  assert.equal(ui.elements.breakerHealthConsecutive.textContent, '1 / 5');
  assert.equal(ui.elements.breakerHealthRolling.textContent, '7 / 35 in 52 of 100 (warming up)');
  assert.equal(ui.elements.breakerHealthDegraded.textContent, '3 in the rolling window (warning only)');
  assert.equal(ui.elements.breakerHealthLastFailure.textContent, 'StorageTimeout');
  assert.equal(ui.elements.breakerHealthLastDegradation.textContent, 'StewardAssessmentTimeout');
  assert.equal(ui.elements.breakerSettingsStatus.textContent, '');
});

test('The Breaker edits are isolated, validated, revisioned, and cancellable', async () => {
  const ui = breakerEditor(async (_url, body) => body
    ? { ...snapshot, ...body, revision: 4 }
    : structuredClone(snapshot));
  await ui.refreshBreakerSettings();
  ui.editBreakerSettings();
  assert.equal(ui.elements.breakerConsecutiveLimit.readOnly, false);
  ui.elements.breakerConsecutiveLimit.value = '40';
  ui.updateBreakerEditorState();
  assert.equal(ui.elements.breakerSave.disabled, true);
  ui.elements.breakerConsecutiveLimit.value = '4';
  ui.elements.breakerProviderTimeout.value = '20';
  ui.updateBreakerEditorState();
  assert.equal(ui.elements.breakerSave.disabled, false);
  ui.cancelBreakerSettings();
  assert.equal(ui.elements.breakerConsecutiveLimit.value, 5);
  assert.equal(ui.state.breakerDraft, null);

  ui.editBreakerSettings();
  ui.elements.breakerConsecutiveLimit.value = '4';
  ui.elements.breakerProviderTimeout.value = '20';
  await ui.saveBreakerSettings();
  const write = ui.calls.find(call => call.method === 'PUT');
  assert.deepEqual(JSON.parse(JSON.stringify(write.body)), {
    expected_revision: 3,
    consecutive_failure_limit: 4,
    rolling_failure_limit: 35,
    rolling_window_size: 100,
    provider_request_timeout_seconds: 20,
    steward_assessment_timeout_seconds: 60,
    rate_limit_retry_wait_cap_seconds: 45,
  });
  assert.equal(ui.state.breakerDraft, null);
  assert.equal(ui.elements.breakerConsecutiveLimit.readOnly, true);
});

test('a failed Breaker save preserves the draft and loaded revision', async () => {
  const ui = breakerEditor(async (_url, body) => {
    if (body) throw new Error('The Breaker settings changed; refresh before saving');
    return structuredClone(snapshot);
  });
  await ui.refreshBreakerSettings();
  ui.editBreakerSettings();
  ui.elements.breakerRollingLimit.value = '34';
  await ui.saveBreakerSettings();
  assert.equal(ui.state.breakerDraft.revision, 3);
  assert.equal(ui.elements.breakerRollingLimit.value, '34');
  assert.equal(ui.elements.breakerSettingsStatus.textContent, 'The Breaker settings changed; refresh before saving');
  assert.equal(ui.elements.breakerSave.disabled, false);
});

test('The Breaker reset is confirmed, scoped, and refreshes operational counts', async () => {
  const resetSnapshot = structuredClone(snapshot);
  resetSnapshot.health = {
    status: 'closed', consecutive_failures: 0, rolling_failures: 0,
    rolling_sample_size: 0, rolling_window_ready: false, degraded_reviews: 0,
    last_failure_class: null, last_degradation_class: null, reset_count: 1,
  };
  const ui = breakerEditor(async (url) => url.endsWith('/reset')
    ? structuredClone(resetSnapshot)
    : structuredClone(snapshot));
  await ui.refreshBreakerSettings();
  assert.equal(ui.elements.breakerReset.disabled, false);
  await ui.resetBreakerHealth();
  const reset = ui.calls.find(call => call.url.endsWith('/reset'));
  assert.equal(reset.method, 'POST');
  assert.equal(ui.elements.breakerHealthRolling.textContent, '0 / 35 in 0 of 100 (warming up)');
  assert.equal(ui.elements.breakerHealthDegraded.textContent, '0 in the rolling window (warning only)');
  assert.equal(ui.elements.breakerReset.disabled, true);
  assert.equal(ui.elements.breakerSettingsStatus.textContent, 'The Breaker was reset for this Mind.');
});

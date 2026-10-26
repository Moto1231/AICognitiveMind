const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../src/aicognitive_mind/static/portal.js'), 'utf8');
const start = source.indexOf('const BODY_DEVICE_STORAGE_KEYS = {');
const end = source.indexOf('// Render the built-in task list immediately', start);
assert.ok(start >= 0 && end > start);
const keys = {
  videoinput: 'aicognitive_mind.device.videoInput',
  audioinput: 'aicognitive_mind.device.audioInput',
  audiooutput: 'aicognitive_mind.device.audioOutput',
};
const inventory = [
  { kind: 'videoinput', deviceId: 'camera-1', label: 'Camera one' },
  { kind: 'videoinput', deviceId: 'camera-2', label: 'Camera two' },
  { kind: 'audioinput', deviceId: 'microphone-1', label: 'Microphone one' },
  { kind: 'audiooutput', deviceId: 'speaker-1', label: 'Speaker one' },
];

class Element {
  constructor(tag = 'div') {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.attributes = {};
    this.dataset = {};
    this.listeners = {};
    this.value = '';
    this.disabled = false;
    this.textContent = '';
  }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute(name, value) { this.attributes[name] = value; }
  addEventListener(name, listener) { this.listeners[name] = listener; }
  get options() { return this.children; }
}

function fixture({ saved = {}, enumerate = async () => inventory } = {}) {
  const data = new Map(Object.entries(saved).map(([kind, value]) => [keys[kind], value]));
  const elements = Object.fromEntries(['saveDeviceSelections', 'cancelDeviceSelections', 'deviceSelectionStatus']
    .map(id => [id, new Element('button')]));
  const el = Object.fromEntries(['devicePermissionStatus', 'deviceSelectionSummary', 'deviceInventoryList']
    .map(id => [id, new Element()]));
  const toasts = [];
  const writes = [];
  let failWrite = null;
  let failRead = false;
  const storage = {
    getItem(key) { if (failRead) throw Error('storage denied'); return data.get(key) ?? null; },
    setItem(key, value) {
      writes.push(['set', key, value]);
      if (failWrite?.(key, value, 'set')) throw Error('storage full');
      data.set(key, value);
    },
    removeItem(key) {
      writes.push(['remove', key]);
      if (failWrite?.(key, null, 'remove')) throw Error('storage denied');
      data.delete(key);
    },
  };
  const context = vm.createContext({
    state: { deviceInventory: [] }, el,
    document: { createElement: tag => new Element(tag), createTextNode: text => text,
      getElementById: id => elements[id] ?? null },
    localStorage: storage,
    navigator: { mediaDevices: { enumerateDevices: enumerate, addEventListener() {} } },
    toast: (...args) => toasts.push(args),
  });
  vm.runInContext(source.slice(start, end), context);
  return { ...context, data, elements, el, toasts, writes,
    failWrites: predicate => { failWrite = predicate; },
    failReads: value => { failRead = value; },
    picker: kind => el.deviceInventoryList.children
      .flatMap(section => section.children)
      .flatMap(child => child.children || [])
      .find(child => child.dataset?.deviceKind === kind),
  };
}

test('changing a device creates a draft and leaves the saved Body preference unchanged', async () => {
  const ui = fixture({ saved: { videoinput: 'camera-1' } });
  await ui.refreshDeviceInventory();
  const picker = ui.picker('videoinput');
  assert.equal(picker.value, 'camera-1');
  picker.value = 'camera-2';
  picker.listeners.change();
  assert.equal(ui.data.get(keys.videoinput), 'camera-1');
  assert.equal(ui.writes.length, 0);
  assert.equal(ui.elements.saveDeviceSelections.disabled, false);
  assert.equal(ui.elements.cancelDeviceSelections.disabled, false);
  assert.match(ui.el.deviceSelectionSummary.textContent, /Saved.*Camera one/);
  assert.match(ui.elements.deviceSelectionStatus.textContent, /Unsaved/);
});

test('Save commits the complete draft and disables clean actions; Cancel restores saved values', async () => {
  const ui = fixture({ saved: { videoinput: 'camera-1', audioinput: 'microphone-1' } });
  await ui.refreshDeviceInventory();
  ui.saveSelectedDevice('videoinput', 'camera-2');
  ui.saveSelectedDevice('audioinput', '');
  ui.saveSelectedDevice('audiooutput', 'speaker-1');
  ui.saveDeviceSelections();
  assert.equal(ui.data.get(keys.videoinput), 'camera-2');
  assert.equal(ui.data.has(keys.audioinput), false);
  assert.equal(ui.data.get(keys.audiooutput), 'speaker-1');
  assert.equal(ui.elements.saveDeviceSelections.disabled, true);
  assert.equal(ui.elements.cancelDeviceSelections.disabled, true);
  ui.saveSelectedDevice('videoinput', 'camera-1');
  ui.cancelDeviceSelectionEdit();
  assert.equal(ui.picker('videoinput').value, 'camera-2');
  assert.equal(ui.data.get(keys.videoinput), 'camera-2');
  assert.equal(ui.elements.saveDeviceSelections.disabled, true);
});

test('inventory refresh preserves an unsaved draft and a missing saved device option', async () => {
  const ui = fixture({ saved: { audiooutput: 'unplugged-speaker' } });
  await ui.refreshDeviceInventory();
  assert.equal(ui.picker('audiooutput').value, 'unplugged-speaker');
  assert.match(ui.picker('audiooutput').options.find(option => option.value === 'unplugged-speaker').textContent, /Saved.*unavailable/);
  ui.saveSelectedDevice('videoinput', 'camera-2');
  await ui.refreshDeviceInventory();
  assert.equal(ui.picker('videoinput').value, 'camera-2');
  assert.equal(ui.elements.saveDeviceSelections.disabled, false);
  ui.saveDeviceSelections();
  assert.equal(ui.data.get(keys.audiooutput), 'unplugged-speaker');
  assert.equal(ui.data.get(keys.videoinput), 'camera-2');
});

test('a device disappearing from a dirty selection disables Save without losing the draft', async () => {
  let devices = inventory;
  const ui = fixture({ enumerate: async () => devices });
  await ui.refreshDeviceInventory();
  ui.saveSelectedDevice('videoinput', 'camera-2');
  devices = inventory.filter(device => device.deviceId !== 'camera-2');
  await ui.refreshDeviceInventory();
  assert.equal(ui.picker('videoinput').value, 'camera-2');
  assert.equal(ui.elements.saveDeviceSelections.disabled, true);
  assert.equal(ui.elements.cancelDeviceSelections.disabled, false);
  ui.saveDeviceSelections();
  assert.equal(ui.writes.length, 0);
});

test('stale inventory failure cannot overwrite the latest result or draft', async () => {
  const pending = [];
  const ui = fixture({ enumerate: () => new Promise((resolve, reject) => pending.push({ resolve, reject })) });
  const first = ui.refreshDeviceInventory();
  const second = ui.refreshDeviceInventory();
  pending[1].resolve(inventory);
  await second;
  ui.picker('videoinput').value = 'camera-2';
  ui.picker('videoinput').listeners.change();
  pending[0].reject(Error('old query failure'));
  await first;
  assert.equal(ui.picker('videoinput').value, 'camera-2');
  // The second query populated the inventory; an old failure neither clears it nor reports an error.
  assert.equal(ui.state.deviceInventory.length, inventory.length);
  assert.doesNotMatch(ui.el.devicePermissionStatus.textContent, /failed/);
  const third = ui.refreshDeviceInventory();
  pending[2].resolve(inventory);
  await third;
  assert.equal(ui.picker('videoinput').value, 'camera-2');
});

test('stale inventory success cannot replace the newest device list', async () => {
  const pending = [];
  const ui = fixture({ enumerate: () => new Promise(resolve => pending.push(resolve)) });
  const first = ui.refreshDeviceInventory();
  const second = ui.refreshDeviceInventory();
  pending[1](inventory);
  await second;
  ui.saveSelectedDevice('videoinput', 'camera-2');
  pending[0]([]);
  await first;
  assert.equal(ui.state.deviceInventory.length, inventory.length);
  assert.equal(ui.elements.saveDeviceSelections.disabled, false);
});

test('a partial storage failure rolls back earlier keys and preserves the draft for retry', async () => {
  const ui = fixture({ saved: { videoinput: 'camera-1' } });
  await ui.refreshDeviceInventory();
  ui.saveSelectedDevice('videoinput', 'camera-2');
  ui.saveSelectedDevice('audioinput', 'microphone-1');
  ui.failWrites((key, value) => key === keys.audioinput && value === 'microphone-1');
  ui.saveDeviceSelections();
  assert.equal(ui.data.get(keys.videoinput), 'camera-1');
  assert.equal(ui.data.has(keys.audioinput), false);
  assert.match(ui.elements.deviceSelectionStatus.textContent, /Previous choices were restored/);
  assert.equal(ui.toasts.at(-1)[1], true);
  assert.equal(ui.elements.saveDeviceSelections.disabled, false);
  ui.failWrites(null);
  ui.saveDeviceSelections();
  assert.equal(ui.data.get(keys.videoinput), 'camera-2');
  assert.equal(ui.data.get(keys.audioinput), 'microphone-1');
});

test('an external saved-value change blocks Save until Cancel reloads it', async () => {
  const ui = fixture({ saved: { videoinput: 'camera-1' } });
  await ui.refreshDeviceInventory();
  ui.saveSelectedDevice('audioinput', 'microphone-1');
  ui.data.set(keys.videoinput, 'camera-2');
  ui.saveDeviceSelections();
  assert.equal(ui.writes.length, 0);
  assert.match(ui.elements.deviceSelectionStatus.textContent, /changed while you were editing/);
  ui.cancelDeviceSelectionEdit();
  assert.equal(ui.picker('videoinput').value, 'camera-2');
});

test('a clean inventory refresh picks up saved preferences changed elsewhere', async () => {
  const ui = fixture({ saved: { videoinput: 'camera-1' } });
  await ui.refreshDeviceInventory();
  ui.data.set(keys.videoinput, 'camera-2');
  await ui.refreshDeviceInventory();
  assert.equal(ui.picker('videoinput').value, 'camera-2');
  assert.equal(ui.elements.saveDeviceSelections.disabled, true);
  assert.equal(ui.writes.length, 0);
});

test('discarding a device draft ignores in-flight discovery and reloads persisted choices on return', async () => {
  let resolve;
  const ui = fixture({ saved: { videoinput: 'camera-1' }, enumerate: () => new Promise(done => { resolve = done; }) });
  const pending = ui.refreshDeviceInventory();
  ui.saveSelectedDevice('videoinput', 'camera-2');
  ui.discardDeviceSelectionChanges();
  resolve(inventory);
  await pending;
  assert.equal(ui.state.deviceInventory.length, 0);
  assert.equal(ui.data.get(keys.videoinput), 'camera-1');
  ui.cancelDeviceSelectionEdit();
  assert.equal(ui.picker('videoinput').value, 'camera-1');
});

test('storage read failures cannot turn saved choices into an enabled default-value Save', async () => {
  const ui = fixture({ saved: { videoinput: 'camera-1' } });
  ui.failReads(true);
  await ui.refreshDeviceInventory();
  assert.equal(ui.picker('videoinput').disabled, true);
  assert.equal(ui.elements.saveDeviceSelections.disabled, true);
  assert.match(ui.el.deviceSelectionSummary.textContent, /could not be read/);
  ui.saveDeviceSelections();
  assert.equal(ui.writes.length, 0);
  ui.failReads(false);
  ui.cancelDeviceSelectionEdit();
  assert.equal(ui.picker('videoinput').value, 'camera-1');
});

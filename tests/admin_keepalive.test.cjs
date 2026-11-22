const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../src/aicognitive_mind/static/portal.js"), "utf8");
const setup = source.slice(source.indexOf("const ADMIN_KEEPALIVE_INTERVAL_MS"), source.indexOf("function renderHostBehaviors"));
const logout = source.slice(source.indexOf("async function logout()"), source.indexOf("async function refreshStatus()"));

function workspace() {
  const timers = new Map();
  const timeouts = new Map();
  const docEvents = {};
  const pageEvents = {};
  const calls = [];
  let allowed = true;
  let redirected;
  const el = new Proxy({}, { get: () => ({ classList: { toggle() {} } }) });
  const state = { mode: "mind", adminAuthorized: false };
  const document = { hidden: false, addEventListener: (name, fn) => { docEvents[name] = fn; } };
  const context = vm.createContext({
    state, el, document, AbortController,
    window: {
      addEventListener: (name, fn) => { pageEvents[name] = fn; },
      setInterval: (fn, ms) => { const id = Symbol(); timers.set(id, { fn, ms }); return id; },
      clearInterval: id => timers.delete(id),
      setTimeout: (fn, ms) => { const id = Symbol(); timeouts.set(id, { fn, ms }); return id; },
      clearTimeout: id => timeouts.delete(id),
    },
    sessionStorage: { removeItem() {} },
    location: { replace: url => { redirected = url; } },
    toast() {},
    api: async url => {
      if (url === "/v1/admin/status" && !allowed) throw Object.assign(new Error("Locked"), { status: 401 });
    },
    fetch: (url, options) => new Promise((resolve, reject) => {
      calls.push({ url, options, resolve, reject });
      options.signal.addEventListener("abort", () => reject(new Error("aborted")), { once: true });
    }),
  });
  vm.runInContext(setup + logout, context);
  return {
    ui: context, state, timers, timeouts, calls, pageEvents, redirected: () => redirected,
    lock: () => { allowed = false; },
    visible: visible => { document.hidden = !visible; docEvents.visibilitychange(); },
    tick: () => [...timers.values()][0].fn(),
  };
}

test("only unlocked Administration starts one ten-minute timer; no immediate entry ping", async () => {
  const w = workspace();
  assert.equal(w.timers.size, 0);
  w.ui.setMode("admin");
  assert.equal(w.timers.size, 0);
  assert.equal(await w.ui.validateAdmin(), true);
  w.ui.setMode("admin");
  w.ui.setMode("admin");
  assert.equal(w.timers.size, 1);
  assert.equal(w.calls.length, 0);
  assert.equal([...w.timers.values()][0].ms, 600_000);
  const first = w.tick();
  await w.tick();
  assert.equal(w.calls.length, 1);
  const { url, options, reject } = w.calls[0];
  assert.equal(url, "/ping");
  assert.equal(options.cache, "no-store");
  assert.equal(options.credentials, "omit");
  assert.equal(options.headers, undefined);
  reject(new Error("network"));
  await first;
  const retry = w.tick();
  assert.equal(w.calls.length, 2);
  w.ui.setMode("mind");
  assert.equal(w.timers.size, 0);
  assert.equal(w.calls[1].options.signal.aborted, true);
  await retry;
});

test("visibility and page navigation stop pings; resume restarts without duplicating timers", async () => {
  const w = workspace();
  await w.ui.validateAdmin();
  w.ui.setMode("admin");
  const first = w.tick();
  w.visible(false);
  assert.equal(w.timers.size, 0);
  assert.equal(w.calls[0].options.signal.aborted, true);
  await first;
  w.visible(true);
  w.pageEvents.pageshow();
  assert.equal(w.timers.size, 1);
  assert.equal(w.calls.length, 2);
  w.pageEvents.pagehide();
  assert.equal(w.timers.size, 0);
  assert.equal(w.calls[1].options.signal.aborted, true);
  w.visible(true);
  assert.equal(w.timers.size, 0);
  w.pageEvents.pageshow();
  assert.equal(w.timers.size, 1);
  assert.equal(w.calls.length, 3);
  await w.ui.logout();
  assert.equal(w.timers.size, 0);
  assert.equal(w.calls[2].options.signal.aborted, true);
  assert.equal(w.redirected(), "/portal");
});

test("rejected Admin reauthorization immediately stops the ping", async () => {
  const w = workspace();
  await w.ui.validateAdmin();
  w.ui.setMode("admin");
  const first = w.tick();
  w.lock();
  assert.equal(await w.ui.validateAdmin(), false);
  assert.equal(w.timers.size, 0);
  assert.equal(w.calls[0].options.signal.aborted, true);
  await first;
  w.visible(true);
  assert.equal(w.timers.size, 0);
});

test("a hung ping times out and the next interval can retry", async () => {
  const w = workspace();
  await w.ui.validateAdmin();
  w.ui.setMode("admin");
  const first = w.tick();
  const [timeout] = w.timeouts.values();
  assert.equal(timeout.ms, 15_000);
  timeout.fn();
  await first;
  assert.equal(w.calls[0].options.signal.aborted, true);
  assert.equal(w.timeouts.size, 0);
  const retry = w.tick();
  assert.equal(w.calls.length, 2);
  w.calls[1].resolve();
  await retry;
});

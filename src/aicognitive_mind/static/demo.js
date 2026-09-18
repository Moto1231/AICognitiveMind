const state = {
  runtime: null,
  mind: null,
  adminPin: sessionStorage.getItem("acm_admin_pin") || "",
  mode: "user",
};

const elements = {
  engineBadge: document.getElementById("engineBadge"),
  continuityState: document.getElementById("continuityState"),
  mindGreeting: document.getElementById("mindGreeting"),
  userView: document.getElementById("userView"),
  adminView: document.getElementById("adminView"),
  userModeButton: document.getElementById("userModeButton"),
  adminModeButton: document.getElementById("adminModeButton"),
  conversation: document.getElementById("conversation"),
  chatForm: document.getElementById("chatForm"),
  messageInput: document.getElementById("messageInput"),
  sendButton: document.getElementById("sendButton"),
  initializeOverlay: document.getElementById("initializeOverlay"),
  initializeForm: document.getElementById("initializeForm"),
  selfName: document.getElementById("selfName"),
  foundationalValuesInput: document.getElementById("foundationalValuesInput"),
  refreshAdminButton: document.getElementById("refreshAdminButton"),
  providerBadge: document.getElementById("providerBadge"),
  activeModel: document.getElementById("activeModel"),
  modelSelect: document.getElementById("modelSelect"),
  switchEngineButton: document.getElementById("switchEngineButton"),
  adminMindName: document.getElementById("adminMindName"),
  developmentState: document.getElementById("developmentState"),
  createdAt: document.getElementById("createdAt"),
  foundationalValues: document.getElementById("foundationalValues"),
  memoryCount: document.getElementById("memoryCount"),
  journalCount: document.getElementById("journalCount"),
  toast: document.getElementById("toast"),
};

async function api(path, options = {}, admin = false) {
  const headers = new Headers(options.headers || {});
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (admin && state.adminPin) {
    headers.set("X-Admin-Pin", state.adminPin);
  }

  const response = await fetch(path, { ...options, headers });
  let payload = null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    payload = await response.json();
  } else {
    payload = await response.text();
  }

  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" && payload.detail
        ? payload.detail
        : `Request failed (${response.status})`;
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }
  return payload;
}

function showToast(message, error = false) {
  elements.toast.textContent = message;
  elements.toast.classList.toggle("error", error);
  elements.toast.classList.remove("hidden");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => elements.toast.classList.add("hidden"), 3200);
}

function renderRuntime(runtime) {
  state.runtime = runtime;
  const provider = runtime.provider.toUpperCase();
  elements.engineBadge.textContent = `${provider} · ${runtime.model}`;
  elements.providerBadge.textContent = provider;
  elements.activeModel.textContent = runtime.model;

  const previous = elements.modelSelect.value;
  elements.modelSelect.innerHTML = "";

  for (const model of runtime.available_models || []) {
    const option = document.createElement("option");
    option.value = `openai::${model}`;
    option.textContent = `OpenAI · ${model}`;
    elements.modelSelect.appendChild(option);
  }

  const echo = document.createElement("option");
  echo.value = "echo::deterministic-echo";
  echo.textContent = "Diagnostic · deterministic echo";
  elements.modelSelect.appendChild(echo);

  const currentValue = `${runtime.provider}::${runtime.model}`;
  const desired = [...elements.modelSelect.options].some((item) => item.value === currentValue)
    ? currentValue
    : previous;
  if (desired && [...elements.modelSelect.options].some((item) => item.value === desired)) {
    elements.modelSelect.value = desired;
  }
}

function renderMind(mind) {
  state.mind = mind;
  elements.mindGreeting.textContent = `Talk with ${mind.identity.self_name}`;
  elements.adminMindName.textContent = mind.identity.self_name;
  elements.developmentState.textContent = mind.developmental_state;
  elements.createdAt.textContent = new Date(mind.created_at).toLocaleString();
  elements.continuityState.textContent = "Mind loaded";

  elements.foundationalValues.innerHTML = "";
  const values = mind.identity.foundational_values || [];
  if (!values.length) {
    const span = document.createElement("span");
    span.className = "tag";
    span.textContent = "No values recorded";
    elements.foundationalValues.appendChild(span);
  } else {
    for (const value of values) {
      const span = document.createElement("span");
      span.className = "tag";
      span.textContent = value;
      elements.foundationalValues.appendChild(span);
    }
  }
}

function addMessage(role, text, extraClass = "") {
  const wrapper = document.createElement("div");
  wrapper.className = `message ${role === "user" ? "user-message" : "mind-message"} ${extraClass}`;

  const label = document.createElement("div");
  label.className = "message-label";
  label.textContent =
    role === "user"
      ? "YOU"
      : state.mind?.identity?.self_name?.toUpperCase() || "MIND";

  const body = document.createElement("div");
  body.className = "message-body";
  body.textContent = text;

  wrapper.append(label, body);
  elements.conversation.appendChild(wrapper);
  elements.conversation.scrollTop = elements.conversation.scrollHeight;
  return wrapper;
}

async function loadRuntime() {
  const runtime = await api("/v1/runtime");
  renderRuntime(runtime);
  return runtime;
}

async function loadMind() {
  const response = await fetch("/v1/mind");
  if (response.status === 404) {
    state.mind = null;
    elements.continuityState.textContent = "Not initialized";
    elements.initializeOverlay.classList.remove("hidden");
    return null;
  }
  if (!response.ok) {
    throw new Error(`Unable to load Mind (${response.status})`);
  }
  const mind = await response.json();
  renderMind(mind);
  elements.initializeOverlay.classList.add("hidden");
  return mind;
}

async function initializeMind(event) {
  event.preventDefault();
  const values = elements.foundationalValuesInput.value
    .split(/\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);

  try {
    const mind = await api("/v1/mind/initialize", {
      method: "POST",
      body: JSON.stringify({
        self_name: elements.selfName.value.trim(),
        foundational_values: values,
      }),
    });
    renderMind(mind);
    elements.initializeOverlay.classList.add("hidden");
    addMessage("mind", "I am initialized. My identity now exists independently of the reasoning model.");
    showToast("Mind initialized");
  } catch (error) {
    showToast(error.message, true);
  }
}

async function sendMessage(event) {
  event.preventDefault();
  const message = elements.messageInput.value.trim();
  if (!message || !state.mind) return;

  addMessage("user", message);
  elements.messageInput.value = "";
  elements.sendButton.disabled = true;
  elements.messageInput.disabled = true;
  const thinking = addMessage("mind", "Reasoning…", "thinking");

  try {
    const result = await api("/v1/mind/interactions", {
      method: "POST",
      body: JSON.stringify({ message }),
    });
    thinking.remove();
    addMessage("mind", result.response_text);
  } catch (error) {
    thinking.remove();
    addMessage("mind", `Unable to respond: ${error.message}`);
    showToast(error.message, true);
  } finally {
    elements.sendButton.disabled = false;
    elements.messageInput.disabled = false;
    elements.messageInput.focus();
  }
}

function setMode(mode) {
  state.mode = mode;
  const admin = mode === "admin";
  elements.userView.classList.toggle("hidden", admin);
  elements.adminView.classList.toggle("hidden", !admin);
  elements.userModeButton.classList.toggle("active", !admin);
  elements.adminModeButton.classList.toggle("active", admin);
}

async function validateAdmin() {
  if (state.runtime?.admin_pin_required && !state.adminPin) {
    const pin = window.prompt("Enter Admin PIN");
    if (pin === null) return false;
    state.adminPin = pin;
  }

  try {
    await api("/v1/admin/status", {}, true);
    if (state.adminPin) {
      sessionStorage.setItem("acm_admin_pin", state.adminPin);
    }
    return true;
  } catch (error) {
    if (error.status === 401) {
      sessionStorage.removeItem("acm_admin_pin");
      state.adminPin = "";
      showToast("Admin PIN was not accepted", true);
      return false;
    }
    throw error;
  }
}

async function enterAdminMode() {
  try {
    const allowed = await validateAdmin();
    if (!allowed) return;
    setMode("admin");
    await refreshAdmin();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function refreshAdmin() {
  const [runtime, mind, memories, journal] = await Promise.all([
    api("/v1/admin/status", {}, true),
    api("/v1/mind"),
    api("/v1/mind/memory"),
    api("/v1/mind/journal"),
  ]);
  renderRuntime(runtime);
  renderMind(mind);
  elements.memoryCount.textContent = memories.length.toLocaleString();
  elements.journalCount.textContent = journal.length.toLocaleString();
}

async function switchEngine() {
  const [provider, model] = elements.modelSelect.value.split("::", 2);
  if (!provider || !model) return;

  elements.switchEngineButton.disabled = true;
  const priorLabel = elements.switchEngineButton.textContent;
  elements.switchEngineButton.textContent = "Switching…";

  try {
    const runtime = await api(
      "/v1/admin/engine",
      {
        method: "POST",
        body: JSON.stringify({ provider, model }),
      },
      true,
    );
    renderRuntime(runtime);
    showToast(`Reasoning model switched to ${runtime.model}`);
    await refreshAdmin();
  } catch (error) {
    if (error.status === 401) {
      sessionStorage.removeItem("acm_admin_pin");
      state.adminPin = "";
    }
    showToast(error.message, true);
  } finally {
    elements.switchEngineButton.disabled = false;
    elements.switchEngineButton.textContent = priorLabel;
  }
}

elements.userModeButton.addEventListener("click", () => setMode("user"));
elements.adminModeButton.addEventListener("click", enterAdminMode);
elements.initializeForm.addEventListener("submit", initializeMind);
elements.chatForm.addEventListener("submit", sendMessage);
elements.refreshAdminButton.addEventListener("click", () => refreshAdmin().catch((error) => showToast(error.message, true)));
elements.switchEngineButton.addEventListener("click", switchEngine);
elements.messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    elements.chatForm.requestSubmit();
  }
});

(async function boot() {
  try {
    await Promise.all([loadRuntime(), loadMind()]);
  } catch (error) {
    elements.continuityState.textContent = "Unavailable";
    showToast(error.message, true);
  }
})();

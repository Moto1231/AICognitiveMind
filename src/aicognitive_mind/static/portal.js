const state = { status: null, memories: [], mode: "mind" };

const el = {
  connectionLabel: document.getElementById("connectionLabel"),
  mindTab: document.getElementById("mindTab"),
  adminTab: document.getElementById("adminTab"),
  mindView: document.getElementById("mindView"),
  adminView: document.getElementById("adminView"),
  mindName: document.getElementById("mindName"),
  continuityLabel: document.getElementById("continuityLabel"),
  selfName: document.getElementById("selfName"),
  developmentState: document.getElementById("developmentState"),
  createdAt: document.getElementById("createdAt"),
  foundationalValues: document.getElementById("foundationalValues"),
  memoryCount: document.getElementById("memoryCount"),
  journalCount: document.getElementById("journalCount"),
  memoryList: document.getElementById("memoryList"),
  refreshButton: document.getElementById("refreshButton"),
  adminRefreshButton: document.getElementById("adminRefreshButton"),
  protocolValue: document.getElementById("protocolValue"),
  reasoningOwner: document.getElementById("reasoningOwner"),
  identityOwner: document.getElementById("identityOwner"),
  memoryOwner: document.getElementById("memoryOwner"),
  adminMindName: document.getElementById("adminMindName"),
  adminMemoryCount: document.getElementById("adminMemoryCount"),
  adminJournalCount: document.getElementById("adminJournalCount"),
  initializeOverlay: document.getElementById("initializeOverlay"),
  initializeForm: document.getElementById("initializeForm"),
  initializeName: document.getElementById("initializeName"),
  initializeValues: document.getElementById("initializeValues"),
  memoryInspector: document.getElementById("memoryInspector"),
  closeMemoryInspector: document.getElementById("closeMemoryInspector"),
  inspectorContent: document.getElementById("inspectorContent"),
  inspectorClass: document.getElementById("inspectorClass"),
  inspectorFormedAt: document.getElementById("inspectorFormedAt"),
  inspectorGrounding: document.getElementById("inspectorGrounding"),
  inspectorAssociations: document.getElementById("inspectorAssociations"),
  inspectorRaw: document.getElementById("inspectorRaw"),
  toast: document.getElementById("toast"),
};

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const payload = response.headers.get("content-type")?.includes("application/json")
    ? await response.json()
    : await response.text();
  if (!response.ok) {
    const detail = payload && typeof payload === "object" && payload.detail
      ? payload.detail
      : `Request failed (${response.status})`;
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }
  return payload;
}

function toast(message, error = false) {
  el.toast.textContent = message;
  el.toast.classList.toggle("error", error);
  el.toast.classList.remove("hidden");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.toast.classList.add("hidden"), 3000);
}

function setMode(mode) {
  state.mode = mode;
  const admin = mode === "admin";
  el.mindView.classList.toggle("hidden", admin);
  el.adminView.classList.toggle("hidden", !admin);
  el.mindTab.classList.toggle("active", !admin);
  el.adminTab.classList.toggle("active", admin);
}

function renderStatus(status) {
  state.status = status;
  const mind = status.mind;
  const integration = status.integration;

  el.connectionLabel.textContent = `${integration.protocol} · Mind online`;
  el.mindName.textContent = mind.identity.self_name;
  el.continuityLabel.textContent = "Persistent";
  el.selfName.textContent = mind.identity.self_name;
  el.developmentState.textContent = mind.developmental_state;
  el.createdAt.textContent = new Date(mind.created_at).toLocaleString();
  el.memoryCount.textContent = Number(status.durable_memory_count).toLocaleString();
  el.journalCount.textContent = Number(status.journal_experience_count).toLocaleString();

  el.protocolValue.textContent = integration.protocol;
  el.reasoningOwner.textContent = integration.reasoning_owner;
  el.identityOwner.textContent = integration.identity_owner;
  el.memoryOwner.textContent = integration.memory_owner;
  el.adminMindName.textContent = mind.identity.self_name;
  el.adminMemoryCount.textContent = Number(status.durable_memory_count).toLocaleString();
  el.adminJournalCount.textContent = Number(status.journal_experience_count).toLocaleString();

  el.foundationalValues.innerHTML = "";
  const values = mind.identity.foundational_values || [];
  if (!values.length) {
    const tag = document.createElement("span");
    tag.className = "tag";
    tag.textContent = "No foundational values recorded";
    el.foundationalValues.appendChild(tag);
  } else {
    for (const value of values) {
      const tag = document.createElement("span");
      tag.className = "tag";
      tag.textContent = value;
      el.foundationalValues.appendChild(tag);
    }
  }
}

function renderRecordValues(container, values) {
  container.innerHTML = "";
  if (!values || !values.length) {
    const empty = document.createElement("div");
    empty.className = "record-empty";
    empty.textContent = "None";
    container.appendChild(empty);
    return;
  }

  for (const value of values) {
    const item = document.createElement("div");
    item.className = "record-value";
    item.textContent = value;
    container.appendChild(item);
  }
}

function openMemoryInspector(memory) {
  el.inspectorContent.textContent = memory.content;
  el.inspectorClass.textContent = memory.memory_class;
  el.inspectorFormedAt.textContent = new Date(memory.formed_at).toLocaleString();
  renderRecordValues(el.inspectorGrounding, memory.grounding);
  renderRecordValues(el.inspectorAssociations, memory.associations);
  el.inspectorRaw.textContent = JSON.stringify(memory, null, 2);
  el.memoryInspector.classList.remove("hidden");
  el.closeMemoryInspector.focus();
}

function closeMemoryInspector() {
  el.memoryInspector.classList.add("hidden");
}

function renderMemories(memories) {
  state.memories = memories;
  el.memoryList.innerHTML = "";
  if (!memories.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "No durable memories have been curated yet.";
    el.memoryList.appendChild(empty);
    return;
  }

  for (const memory of [...memories].reverse()) {
    const item = document.createElement("article");
    item.className = "memory-item";
    item.tabIndex = 0;
    item.setAttribute("role", "button");
    item.setAttribute("aria-label", `Inspect ${memory.memory_class} memory`);
    item.addEventListener("click", () => openMemoryInspector(memory));
    item.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openMemoryInspector(memory);
      }
    });

    const meta = document.createElement("div");
    meta.className = "memory-meta";
    const klass = document.createElement("span");
    klass.textContent = memory.memory_class;
    const formed = document.createElement("span");
    formed.textContent = new Date(memory.formed_at).toLocaleString();
    meta.append(klass, formed);

    const content = document.createElement("div");
    content.className = "memory-content";
    content.textContent = memory.content;

    item.append(meta, content);
    el.memoryList.appendChild(item);
  }
}

async function refresh() {
  try {
    const status = await api("/v1/portal/status");
    const memories = await api("/v1/mind/memory");
    renderStatus(status);
    renderMemories(memories);
    el.initializeOverlay.classList.add("hidden");
  } catch (error) {
    if (error.status === 404) {
      el.connectionLabel.textContent = "Mind not initialized";
      el.continuityLabel.textContent = "Awaiting genesis";
      el.initializeOverlay.classList.remove("hidden");
      return;
    }
    el.connectionLabel.textContent = "Unavailable";
    toast(error.message, true);
  }
}

async function initializeMind(event) {
  event.preventDefault();
  const values = el.initializeValues.value
    .split(/\n|,/)
    .map(value => value.trim())
    .filter(Boolean);

  try {
    await api("/v1/mind/initialize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        self_name: el.initializeName.value.trim(),
        foundational_values: values,
      }),
    });
    toast("Mind initialized");
    await refresh();
  } catch (error) {
    toast(error.message, true);
  }
}

el.mindTab.addEventListener("click", () => setMode("mind"));
el.adminTab.addEventListener("click", () => setMode("admin"));
el.refreshButton.addEventListener("click", () => refresh());
el.adminRefreshButton.addEventListener("click", () => refresh());
el.initializeForm.addEventListener("submit", initializeMind);
el.closeMemoryInspector.addEventListener("click", closeMemoryInspector);
el.memoryInspector.addEventListener("click", (event) => {
  if (event.target === el.memoryInspector) closeMemoryInspector();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !el.memoryInspector.classList.contains("hidden")) {
    closeMemoryInspector();
  }
});

refresh();

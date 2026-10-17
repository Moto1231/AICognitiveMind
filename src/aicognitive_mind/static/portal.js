const state = {
  status: null,
  memoryPages: {
    mind: { items: [], total: 0, hasMore: false, nextOffset: 0 },
    admin: { items: [], total: 0, hasMore: false, nextOffset: 0 },
  },
  memoryPageSize: 25,
  memoryPageSizes: { mind: 25, admin: 25 },
  memoryFilterTimers: { mind: null, admin: null },
  journals: [],
  journalTotal: 0,
  journalHasMore: false,
  journalNextOffset: 0,
  journalPageSize: 25,
  journalFilterTimer: null,
  mode: "mind",
  adminPin: sessionStorage.getItem("acm_admin_pin") || "",
  adminAuthorized: false,
  activeMemory: null,
  activeJournal: null,
  hostBehaviors: [],
  taskModelAssignments: [],
  taskBehaviors: [],
  taskFoundations: {},
  providerEndpoints: [],
  mcpServers: [],
  activeMcpServerId: null,
  activeTaskProfile: null,
  activeEndpointId: null,
  activeEndpointOriginalName: "",
  endpointDraft: null,
  endpointEditBaseline: "",
  mcpServerDraft: null,
  mcpEditBaseline: "",
  integrationSaving: false,
  deviceInventory: [],
  voiceSettingsRevision: 0,
  taskProfileSnapshot: "",
  hostBehaviorSnapshot: "",
};

const el = {
  connectionLabel: document.getElementById("connectionLabel"),
  mindTab: document.getElementById("mindTab"),
  adminTab: document.getElementById("adminTab"),
  logoutButton: document.getElementById("logoutButton"),
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
  memorySearch: document.getElementById("memorySearch"),
  memoryClassFilter: document.getElementById("memoryClassFilter"),
  associationFilter: document.getElementById("associationFilter"),
  groundingFilter: document.getElementById("groundingFilter"),
  formedFrom: document.getElementById("formedFrom"),
  formedTo: document.getElementById("formedTo"),
  memorySort: document.getElementById("memorySort"),
  clearMemoryFilters: document.getElementById("clearMemoryFilters"),
  memoryResultCount: document.getElementById("memoryResultCount"),
  memoryPageSize: document.getElementById("memoryPageSize"),
  loadMoreMemories: document.getElementById("loadMoreMemories"),
  refreshButton: document.getElementById("refreshButton"),
  adminRefreshButton: document.getElementById("adminRefreshButton"),
  adminMemoryRefreshButton: document.getElementById("adminMemoryRefreshButton"),
  protocolValue: document.getElementById("protocolValue"),
  reasoningOwner: document.getElementById("reasoningOwner"),
  identityOwner: document.getElementById("identityOwner"),
  memoryOwner: document.getElementById("memoryOwner"),
  adminMindName: document.getElementById("adminMindName"),
  adminCreatedAt: document.getElementById("adminCreatedAt"),
  adminMemoryCount: document.getElementById("adminMemoryCount"),
  adminJournalCount: document.getElementById("adminJournalCount"),
  bodyFallbackEnabled: document.getElementById("bodyFallbackEnabled"),
  bodyFallbackSource: document.getElementById("bodyFallbackSource"),
  saveBodyFallbackSetting: document.getElementById("saveBodyFallbackSetting"),
  adminMemoryList: document.getElementById("adminMemoryList"),
  adminMemorySearch: document.getElementById("adminMemorySearch"),
  adminMemoryClassFilter: document.getElementById("adminMemoryClassFilter"),
  adminAssociationFilter: document.getElementById("adminAssociationFilter"),
  adminGroundingFilter: document.getElementById("adminGroundingFilter"),
  adminFormedFrom: document.getElementById("adminFormedFrom"),
  adminFormedTo: document.getElementById("adminFormedTo"),
  adminMemorySort: document.getElementById("adminMemorySort"),
  adminClearMemoryFilters: document.getElementById("adminClearMemoryFilters"),
  adminMemoryResultCount: document.getElementById("adminMemoryResultCount"),
  adminMemoryPageSize: document.getElementById("adminMemoryPageSize"),
  adminLoadMoreMemories: document.getElementById("adminLoadMoreMemories"),
  journalRefreshButton: document.getElementById("journalRefreshButton"),
  journalSearch: document.getElementById("journalSearch"),
  journalKindFilter: document.getElementById("journalKindFilter"),
  journalFrom: document.getElementById("journalFrom"),
  journalTo: document.getElementById("journalTo"),
  journalSort: document.getElementById("journalSort"),
  clearJournalFilters: document.getElementById("clearJournalFilters"),
  journalResultCount: document.getElementById("journalResultCount"),
  journalPageSize: document.getElementById("journalPageSize"),
  journalTimeline: document.getElementById("journalTimeline"),
  loadMoreJournals: document.getElementById("loadMoreJournals"),
  journalInspector: document.getElementById("journalInspector"),
  closeJournalInspector: document.getElementById("closeJournalInspector"),
  journalInspectorKind: document.getElementById("journalInspectorKind"),
  journalInspectorOccurredAt: document.getElementById("journalInspectorOccurredAt"),
  journalStructuredDetail: document.getElementById("journalStructuredDetail"),
  journalInspectorRaw: document.getElementById("journalInspectorRaw"),
  journalEvidenceDetail: document.getElementById("journalEvidenceDetail"),
  journalEvidenceList: document.getElementById("journalEvidenceList"),
  taskProviderSelect: document.getElementById("taskProviderSelect"),
  saveProviderEndpoints: document.getElementById("saveProviderEndpoints"),
  taskProfileOverview: document.getElementById("taskProfileOverview"),
  refreshMcpServers: document.getElementById("refreshMcpServers"),
  mcpServerSelect: document.getElementById("mcpServerSelect"),
  mcpServerName: document.getElementById("mcpServerName"),
  mcpServerUrl: document.getElementById("mcpServerUrl"),
  mcpServerToken: document.getElementById("mcpServerToken"),
  mcpServerEnabled: document.getElementById("mcpServerEnabled"),
  mcpAddServer: document.getElementById("mcpAddServer"),
  mcpDiscoverTools: document.getElementById("mcpDiscoverTools"),
  mcpDeleteServer: document.getElementById("mcpDeleteServer"),
  mcpEditServer: document.getElementById("mcpEditServer"),
  mcpCancelEdit: document.getElementById("mcpCancelEdit"),
  mcpServerStatus: document.getElementById("mcpServerStatus"),
  mcpToolList: document.getElementById("mcpToolList"),
  mcpToolRunnerSelect: document.getElementById("mcpToolRunnerSelect"),
  mcpToolArguments: document.getElementById("mcpToolArguments"),
  mcpRunTool: document.getElementById("mcpRunTool"),
  mcpToolOutput: document.getElementById("mcpToolOutput"),
  saveMcpServers: document.getElementById("saveMcpServers"),
  refreshDevicesButton: document.getElementById("refreshDevicesButton"),
  devicePermissionStatus: document.getElementById("devicePermissionStatus"),
  deviceSelectionSummary: document.getElementById("deviceSelectionSummary"),
  deviceInventoryList: document.getElementById("deviceInventoryList"),
  refreshEvidenceButton: document.getElementById("refreshEvidenceButton"),
  evidenceResultCount: document.getElementById("evidenceResultCount"),
  evidenceList: document.getElementById("evidenceList"),
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
  inspectorArtifacts: document.getElementById("inspectorArtifacts"),
  inspectorRaw: document.getElementById("inspectorRaw"),
  memoryEditActions: document.getElementById("memoryEditActions"),
  editMemoryButton: document.getElementById("editMemoryButton"),
  memoryEditForm: document.getElementById("memoryEditForm"),
  editMemoryContent: document.getElementById("editMemoryContent"),
  editMemoryClass: document.getElementById("editMemoryClass"),
  editAssociations: document.getElementById("editAssociations"),
  editGrounding: document.getElementById("editGrounding"),
  cancelMemoryEdit: document.getElementById("cancelMemoryEdit"),
  hostBehaviorList: document.getElementById("hostBehaviorList"),
  addHostBehavior: document.getElementById("addHostBehavior"),
  saveHostBehaviors: document.getElementById("saveHostBehaviors"),
  refreshTaskProfiles: document.getElementById("refreshTaskProfiles"),
  taskProfileList: document.getElementById("taskProfileList"),
  taskProfileEditor: document.getElementById("taskProfileEditor"),
  taskProfileTitle: document.getElementById("taskProfileTitle"),
  taskProfileBack: document.getElementById("taskProfileBack"),
  taskProfileEndpointSection: document.getElementById("taskProfileEndpointSection"),
  taskProfileEndpointSelect: document.getElementById("taskProfileEndpointSelect"),
  taskProfileAddEndpoint: document.getElementById("taskProfileAddEndpoint"),
  taskProfileEndpointName: document.getElementById("taskProfileEndpointName"),
  taskProfileProviderName: document.getElementById("taskProfileProviderName"),
  endpointModelSelect: document.getElementById("endpointModelSelect"),
  endpointModelId: document.getElementById("endpointModelId"),
  endpointModelStatus: document.getElementById("endpointModelStatus"),
  endpointEditButton: document.getElementById("endpointEditButton"),
  endpointRemoveButton: document.getElementById("endpointRemoveButton"),
  endpointCancelButton: document.getElementById("endpointCancelButton"),
  taskProfileBaseUrl: document.getElementById("taskProfileBaseUrl"),
  taskProfileApiKey: document.getElementById("taskProfileApiKey"),
  taskProfileDiscover: document.getElementById("taskProfileDiscover"),
  taskProfileAssignmentSection: document.getElementById("taskProfileAssignmentSection"),
  taskProfileModel: document.getElementById("taskProfileModel"),
  taskProfileModels: document.getElementById("taskProfileModels"),
  taskProfileStandardModelField: document.getElementById("taskProfileStandardModelField"),
  taskProfileVoiceModelField: document.getElementById("taskProfileVoiceModelField"),
  taskProfileVoiceModel: document.getElementById("taskProfileVoiceModel"),
  taskProfileVoiceReferenceField: document.getElementById("taskProfileVoiceReferenceField"),
  taskProfileVoiceReferenceId: document.getElementById("taskProfileVoiceReferenceId"),
  taskProfileFallbackList: document.getElementById("taskProfileFallbackList"),
  taskProfileAddFallback: document.getElementById("taskProfileAddFallback"),
  taskProfileAddBehavior: document.getElementById("taskProfileAddBehavior"),
  voiceRate: document.getElementById("voiceRate"),
  voiceRateValue: document.getElementById("voiceRateValue"),
  voicePitch: document.getElementById("voicePitch"),
  voicePitchValue: document.getElementById("voicePitchValue"),
  voiceVolume: document.getElementById("voiceVolume"),
  voiceVolumeValue: document.getElementById("voiceVolumeValue"),
  voiceName: document.getElementById("voiceName"),
  voiceSettingsRevision: document.getElementById("voiceSettingsRevision"),
  saveVoiceSettings: document.getElementById("saveVoiceSettings"),
  refreshVoiceSettings: document.getElementById("refreshVoiceSettings"),
  taskProfileFoundation: document.getElementById("taskProfileFoundation"),
  taskProfileBehaviorSelection: document.getElementById("taskProfileBehaviorSelection"),
  taskProfileBehaviorName: document.getElementById("taskProfileBehaviorName"),
  taskProfileInstructions: document.getElementById("taskProfileInstructions"),
  taskProfileEnabled: document.getElementById("taskProfileEnabled"),
  taskProfileRevision: document.getElementById("taskProfileRevision"),
  saveTaskProfile: document.getElementById("saveTaskProfile"),
  toast: document.getElementById("toast"),
};

const filters = {
  mind: {
    key: "mind",
    search: el.memorySearch,
    memoryClass: el.memoryClassFilter,
    association: el.associationFilter,
    grounding: el.groundingFilter,
    from: el.formedFrom,
    to: el.formedTo,
    sort: el.memorySort,
    count: el.memoryResultCount,
    list: el.memoryList,
    loadMore: el.loadMoreMemories,
    pageSize: el.memoryPageSize,
  },
  admin: {
    key: "admin",
    search: el.adminMemorySearch,
    memoryClass: el.adminMemoryClassFilter,
    association: el.adminAssociationFilter,
    grounding: el.adminGroundingFilter,
    from: el.adminFormedFrom,
    to: el.adminFormedTo,
    sort: el.adminMemorySort,
    count: el.adminMemoryResultCount,
    list: el.adminMemoryList,
    loadMore: el.adminLoadMoreMemories,
    pageSize: el.adminMemoryPageSize,
  },
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
  const payload = response.headers.get("content-type")?.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const rawDetail = payload && typeof payload === "object" && payload.detail
      ? payload.detail
      : `Request failed (${response.status})`;
    const detail = typeof rawDetail === "string" ? rawDetail : JSON.stringify(rawDetail);
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }
  return payload;
}

function formatBrowserDateTime(value) {
  if (value == null || value === "") return "—";
  const raw = String(value).trim();
  const normalized = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/.test(raw) && !/(Z|[+-]\d{2}:?\d{2})$/i.test(raw) ? raw.replace(" ", "T") + "Z" : raw;
  const date = value instanceof Date ? value : new Date(normalized);
  if (Number.isNaN(date.getTime())) return String(value);
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
    timeZone,
  }).format(date);
}

function displayLabel(value) {
  return String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, character => character.toUpperCase());
}

function toast(message, error = false) {
  const displayMessage = typeof message === "string"
    ? message
    : message instanceof Error
      ? message.message
      : JSON.stringify(message);
  el.toast.textContent = displayMessage ?? "";
  el.toast.classList.toggle("error", error);
  el.toast.classList.remove("hidden");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.toast.classList.add("hidden"), 3000);
}

function setMode(mode) {
  if (mode === "mind" && state.activeTaskProfile) closeTaskProfile();
  state.mode = mode;
  const admin = mode === "admin";
  el.mindView.classList.toggle("hidden", admin);
  el.adminView.classList.toggle("hidden", !admin);
  el.mindTab.classList.toggle("active", !admin);
  el.adminTab.classList.toggle("active", admin);
}

async function validateAdmin() {
  const pinRequired = Boolean(state.status?.administration?.pin_required);
  if (pinRequired && !state.adminPin) {
    const pin = window.prompt("Enter Administrator PIN");
    if (pin === null) return false;
    state.adminPin = pin;
  }

  try {
    await api("/v1/admin/status", {}, true);
    state.adminAuthorized = true;
    if (state.adminPin) {
      sessionStorage.setItem("acm_admin_pin", state.adminPin);
    }
    return true;
  } catch (error) {
    state.adminAuthorized = false;
    if (error.status === 401) {
      sessionStorage.removeItem("acm_admin_pin");
      state.adminPin = "";
      toast("Administrator authorization was not accepted", true);
      return false;
    }
    throw error;
  }
}

function renderHostBehaviors() {
  el.hostBehaviorList.replaceChildren();
  for (const behavior of state.hostBehaviors) {
    const row = document.createElement("div");
    row.className = "memory-card host-behavior-card";
    const fields = document.createElement("div");
    fields.className = "host-behavior-fields";
    const nameField = document.createElement("label");
    nameField.className = "host-behavior-field";
    nameField.append(document.createTextNode("Behavior name"));
    const title = document.createElement("input");
    title.type = "text";
    title.value = behavior.name;
    title.maxLength = 120;
    title.readOnly = behavior.protected;
    title.setAttribute("aria-label", "Behavior name");
    title.addEventListener("input", () => { behavior.name = title.value; updateBehaviorSaveState(); });
    nameField.append(title);
    const instructionField = document.createElement("label");
    instructionField.className = "host-behavior-field host-behavior-instruction";
    instructionField.append(document.createTextNode("Instruction"));
    const instruction = document.createElement("textarea");
    instruction.rows = 5;
    instruction.maxLength = 4000;
    instruction.value = behavior.instruction;
    instruction.readOnly = behavior.protected;
    instruction.setAttribute("aria-label", "Instruction");
    instruction.addEventListener("input", () => { behavior.instruction = instruction.value; updateBehaviorSaveState(); });
    instructionField.append(instruction);
    const priorityField = document.createElement("label");
    priorityField.className = "host-behavior-field host-behavior-priority";
    priorityField.append(document.createTextNode("Priority"));
    const priority = document.createElement("input");
    priority.type = "number";
    priority.min = "0";
    priority.max = "10000";
    priority.value = behavior.priority;
    priority.setAttribute("aria-label", "Priority");
    priority.addEventListener("change", () => { behavior.priority = Number(priority.value); updateBehaviorSaveState(); });
    priorityField.append(priority);
    fields.append(nameField, priorityField, instructionField);
    const enabled = document.createElement("input");
    enabled.type = "checkbox";
    enabled.checked = behavior.enabled;
    enabled.disabled = behavior.protected;
    enabled.setAttribute("aria-label", "Enable behavior");
    enabled.addEventListener("change", () => { behavior.enabled = enabled.checked; updateBehaviorSaveState(); });
    const label = document.createElement("label");
    label.className = "host-behavior-enabled";
    label.append(enabled, document.createTextNode(behavior.protected ? " Enabled · Protected" : " Enabled"));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "secondary-button";
    remove.textContent = "Remove";
    remove.disabled = behavior.protected;
    remove.addEventListener("click", () => {
      state.hostBehaviors = state.hostBehaviors.filter(item => item.id !== behavior.id);
      renderHostBehaviors();
    });
    const controls = document.createElement("div");
    controls.className = "host-behavior-controls";
    controls.append(label, remove);
    row.append(fields, controls);
    el.hostBehaviorList.append(row);
  }
  updateBehaviorSaveState();
}

function updateBehaviorSaveState() {
  if (el.saveHostBehaviors) el.saveHostBehaviors.disabled =
    JSON.stringify(state.hostBehaviors) === state.hostBehaviorSnapshot ||
    state.hostBehaviors.some(item => !item.name.trim() || !item.instruction.trim());
}

async function refreshHostBehaviors() {
  const payload = await api("/v1/admin/host-behaviors", {}, true);
  state.hostBehaviors = payload.items;
  state.hostBehaviorSnapshot = JSON.stringify(state.hostBehaviors);
  renderHostBehaviors();
}

function addHostBehavior() {
  const id = "behavior-" + Date.now();
  state.hostBehaviors.push({
    id,
    name: "New Behavior",
    instruction: "Describe the behavior.",
    enabled: true,
    priority: 100,
    protected: false,
  });
  renderHostBehaviors();
}

async function saveHostBehaviors() {
  try {
    const payload = await api("/v1/admin/host-behaviors", {
      method: "PUT",
      body: JSON.stringify({ items: state.hostBehaviors }),
    }, true);
    state.hostBehaviors = payload.items;
    state.hostBehaviorSnapshot = JSON.stringify(state.hostBehaviors);
    renderHostBehaviors();
    await refreshTaskModelAssignments();
    toast("Behaviors saved");
  } catch (error) {
    toast(error.message, true);
  }
}

const taskModelLabels = {
  reasoning: "Reasoning",
  vision: "Vision",
  audio: "Audio/Transcription",
  audio_voice: "Audio/Voice",
  coding: "Coding",
  image_generation: "Drawing & Image Generation",
  summarization: "Summarizing",
  memory_recall: "Memory Recall",
  web_research: "Web Research",
  structured_extraction: "Structured Extraction",
};

function allTaskNames() {
  return [...new Set([
    ...Object.keys(taskModelLabels),
    ...state.taskModelAssignments.map(item => item.task),
    ...state.taskBehaviors.map(item => item.task),
    ...Object.keys(state.taskFoundations),
  ])].sort((a, b) => (taskModelLabels[a] || a).localeCompare(taskModelLabels[b] || b));
}

function renderTaskProfiles() {
  if (!el.taskProfileList) return;
  el.taskProfileList.replaceChildren();
  const tasks = allTaskNames();
  if (!tasks.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "Task profiles are not available yet. Refresh to retry loading the configuration.";
    el.taskProfileList.append(empty);
    return;
  }
  for (const task of tasks) {
    const assignment = state.taskModelAssignments.find(item => item.task === task) || {};
    const behavior = state.taskBehaviors.find(item => item.task === task) || {};
    const endpoint = state.providerEndpoints.find(item =>
      item.name === assignment.provider || item.id === assignment.provider
    );
    const card = document.createElement("button");
    card.type = "button";
    card.className = "task-profile-card";
    card.dataset.keepLabel = "true";
    const title = document.createElement("strong");
    title.textContent = taskModelLabels[task] || displayLabel(task);
    const detail = document.createElement("span");
    detail.textContent = endpoint?.name || (assignment.provider === "connected-host"
      ? "Connected reasoning host" : assignment.provider || "No endpoint selected");
    const behaviorStatus = document.createElement("small");
    const ids = selectedTaskBehaviorIds(task, assignment);
    behaviorStatus.textContent = `${ids.length} behavior${ids.length === 1 ? "" : "s"} selected`;
    card.append(title, detail, behaviorStatus);
    card.addEventListener("click", () => openTaskProfile(task));
    el.taskProfileList.append(card);
  }
}

function activeProfileRecords() {
  const task = state.activeTaskProfile;
  return {
    assignment: state.taskModelAssignments.find(item => item.task === task),
    behavior: state.taskBehaviors.find(item => item.task === task),
    endpoint: state.providerEndpoints.find(item => item.id === state.activeEndpointId),
  };
}

function renderTaskProfileEndpointOptions() {
  const select = el.taskProfileEndpointSelect;
  select.replaceChildren();
  const blank = document.createElement("option");
  blank.value = "";
  blank.textContent = "Choose an endpoint";
  select.append(blank);
  const endpoints = [...state.providerEndpoints];
  if (state.endpointDraft && !endpoints.some(item => item.id === state.endpointDraft.id)) endpoints.push(state.endpointDraft);
  for (const endpoint of endpoints) {
    const option = document.createElement("option");
    option.value = endpoint.id;
    option.textContent = endpoint.name || endpoint.base_url || "Unnamed endpoint";
    option.classList.toggle("credential-loaded", !!(endpoint.has_api_key || endpoint.api_key));
    if (endpoint.has_api_key || endpoint.api_key) option.textContent += " · Key loaded";
    select.append(option);
  }
  for (const preset of COMMON_ENDPOINT_PRESETS) {
    if (state.providerEndpoints.some(item => item.name === preset.name || item.base_url === preset.base_url)) continue;
    const option = document.createElement("option");
    option.value = "preset:" + preset.id;
    option.textContent = preset.name;
    select.append(option);
  }
  select.value = state.activeEndpointId || "";
  const selected = state.endpointDraft || selectedEndpoint();
  select.classList.toggle("credential-loaded", !!(selected?.has_api_key || selected?.api_key));
}

function modelCapabilityLabel(model, capabilityMap) {
  const capabilities = capabilityMap?.[model];
  return capabilities?.length ? `${model} · ${capabilities.join(" · ")}` : `${model} · Provider did not report capabilities`;
}

function fillSelect(select, values, selected, placeholder, capabilityMap = null) {
  select.replaceChildren();
  const blank = document.createElement("option");
  blank.value = "";
  blank.textContent = placeholder;
  select.append(blank);
  for (const value of [...new Set(values.filter(value => typeof value === "string" && value.trim()))]) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = capabilityMap ? modelCapabilityLabel(value, capabilityMap) : value;
    select.append(option);
  }
  if (selected && ![...select.options].some(option => option.value === selected)) {
    const option = document.createElement("option");
    option.value = selected;
    option.textContent = capabilityMap ? `${modelCapabilityLabel(selected, capabilityMap)} (saved)` : selected + " (saved)";
    select.append(option);
  }
  select.value = selected || "";
}

function taskEndpointOptions(select, selected, task = state.activeTaskProfile) {
  select.replaceChildren(new Option("Choose endpoint", ""));
  if (task === "reasoning") select.append(new Option("Connected reasoning host", "connected-host"));
  for (const endpoint of state.providerEndpoints) {
    const option = new Option(endpoint.name || "Unnamed endpoint", endpoint.id);
    option.dataset.hasKey = endpoint.has_api_key || Boolean(endpoint.api_key) ? "true" : "false";
    if (option.dataset.hasKey === "true") option.style.color = "var(--success)";
    select.append(option);
  }
  const endpoint = state.providerEndpoints.find(item => item.id === selected || item.name === selected);
  if (selected && !endpoint && selected !== "connected-host") select.append(new Option(selected + " (saved)", selected));
  select.value = endpoint?.id || selected || "";
  select.classList.toggle("endpoint-has-key", Boolean(endpoint?.has_api_key || endpoint?.api_key));
}

function selectedTaskBehaviorIds(task, assignment) {
  if (Array.isArray(assignment?.behavior_ids)) return [...assignment.behavior_ids];
  const catalog = taskBehaviorCatalog();
  return task === "reasoning" ? catalog.filter(item => !item.id.startsWith("task-") || item.id === "task-reasoning-legacy").map(item => item.id)
    : catalog.filter(item => item.id === `task-${task}-legacy`).map(item => item.id);
}

function taskBehaviorCatalog() {
  return state.hostBehaviorSnapshot ? JSON.parse(state.hostBehaviorSnapshot) : state.hostBehaviors;
}

function taskProfileConfiguration() {
  const assignment = state.taskModelAssignments.find(item => item.task === state.activeTaskProfile);
  return JSON.stringify(assignment || {});
}

function updateTaskSaveState() {
  if (!el.saveTaskProfile) return;
  const assignment = state.taskModelAssignments.find(item => item.task === state.activeTaskProfile);
  const endpoint = state.providerEndpoints.find(item => item.id === assignment?.provider || item.name === assignment?.provider);
  const invalidPrimary = assignment?.provider && assignment.provider !== "connected-host"
    && !endpoint?.model && !assignment.model;
  const invalidFallback = assignment?.fallbacks?.some(item => !item.provider || !item.model);
  el.saveTaskProfile.disabled = state.taskProfileSaving || !assignment || invalidPrimary || invalidFallback
    || taskProfileConfiguration() === state.taskProfileSnapshot;
}

function renderTaskBehaviorSelection() {
  const container = el.taskProfileBehaviorSelection;
  if (!container) return;
  const assignment = state.taskModelAssignments.find(item => item.task === state.activeTaskProfile);
  const selected = new Set(selectedTaskBehaviorIds(state.activeTaskProfile, assignment));
  const catalog = taskBehaviorCatalog();
  if (state.activeTaskProfile === "reasoning") {
    catalog.filter(item => item.protected).forEach(item => selected.add(item.id));
  }
  container.replaceChildren();
  if (!catalog.length) container.textContent = "Add and save behaviors on the Behaviors form first.";
  for (const behavior of catalog) {
    const label = document.createElement("label");
    label.className = "task-behavior-option";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    const required = state.activeTaskProfile === "reasoning" && behavior.protected;
    checkbox.checked = required || selected.has(behavior.id);
    checkbox.disabled = required;
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) selected.add(behavior.id); else selected.delete(behavior.id);
      assignment.behavior_ids = [...selected];
      updateTaskSaveState();
    });
    const text = document.createElement("span");
    const title = document.createElement("strong");
    title.textContent = behavior.name + (required ? " · Protected" : "") + (!behavior.enabled ? " · Disabled in library" : "");
    const instruction = document.createElement("small");
    instruction.textContent = behavior.instruction;
    text.append(title, instruction);
    label.append(checkbox, text);
    container.append(label);
  }
}

function renderFallbackSelectors() {
  if (!el.taskProfileFallbackList) return;
  const assignment = state.taskModelAssignments.find(item => item.task === state.activeTaskProfile);
  const fallbacks = assignment?.fallbacks || [];
  el.taskProfileFallbackList.replaceChildren();
  if (!fallbacks.length) {
    const empty = document.createElement("p");
    empty.className = "record-empty";
    empty.textContent = "No fallback endpoints configured.";
    el.taskProfileFallbackList.append(empty);
  }
  fallbacks.forEach((fallback, index) => {
    const row = document.createElement("div");
    row.className = "task-fallback-row";
    const label = document.createElement("label");
    label.className = "host-behavior-field";
    label.textContent = "Fallback endpoint " + (index + 1);
    const select = document.createElement("select");
    select.setAttribute("aria-label", label.textContent);
    taskEndpointOptions(select, fallback.provider, "fallback");
    select.addEventListener("change", () => {
      const endpoint = state.providerEndpoints.find(item => item.id === select.value);
      const sameEndpoint = endpoint && (fallback.provider === endpoint.id || fallback.provider === endpoint.name);
      fallback.provider = endpoint?.id || select.value;
      fallback.model = endpoint?.model || (sameEndpoint ? fallback.model : "");
      if (endpoint && !fallback.model) toast("Save a model for this endpoint in Endpoints, Servers & Tools first", true);
      select.classList.toggle("endpoint-has-key", Boolean(endpoint?.has_api_key || endpoint?.api_key));
      updateTaskSaveState();
    });
    label.append(select);
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "secondary-button";
    remove.textContent = "Remove";
    remove.setAttribute("aria-label", "Remove fallback " + (index + 1));
    remove.addEventListener("click", () => {
      assignment.fallbacks.splice(index, 1);
      renderFallbackSelectors();
      updateTaskSaveState();
    });
    row.append(label, remove);
    el.taskProfileFallbackList.append(row);
  });
}

function loadEndpointIntoForm() {
  const endpoint = state.endpointDraft || selectedEndpoint();
  el.taskProfileEndpointName.value = endpoint?.name || "";
  el.taskProfileProviderName.value = endpoint?.provider_name || "";
  el.taskProfileBaseUrl.value = endpoint?.base_url || "";
  el.taskProfileApiKey.value = endpoint?.api_key || "";
  el.endpointModelId.value = endpoint?.model || "";
  fillSelect(el.endpointModelSelect, endpoint?.models || [], endpoint?.model || "", "Choose a discovered model", endpoint?.model_capabilities || {});
  renderEndpointModelStatus(endpoint);
  updateEndpointEditorState();
}

function renderEndpointModelStatus(endpoint) {
  el.endpointModelStatus.replaceChildren();
  if (!endpoint) {
    el.endpointModelStatus.textContent = "Select an endpoint, then Edit to configure its model.";
    return;
  }
  const model = endpoint.model || "";
  const capabilities = endpoint.model_capabilities?.[model] || [];
  const source = endpoint.model_capability_sources?.[model] || "";
  el.endpointModelStatus.textContent = model
    ? `${model}${capabilities.length ? " · " + capabilities.join(" · ") : " · No capability metadata reported"}`
    : `${endpoint.models?.length || 0} discovered models`;
  if (source === "provider_metadata") {
    el.endpointModelStatus.append(document.createTextNode(" · Provider metadata"));
  } else if (/^https:\/\/developers\.openai\.com\/api\/docs\/models\//.test(source)) {
    const link = document.createElement("a");
    link.href = source;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "Documented capabilities (not tested)";
    el.endpointModelStatus.append(document.createTextNode(" · "), link);
  }
}

function endpointFormIsValid(endpoint) {
  return !!(endpoint?.name?.trim() && endpoint?.provider_name?.trim() && endpoint?.model?.trim()
    && /^https?:\/\/\S+$/i.test(endpoint?.base_url || ""));
}

function syncEndpointDraft() {
  const endpoint = state.endpointDraft;
  if (!endpoint) return;
  endpoint.name = el.taskProfileEndpointName.value.trim();
  endpoint.provider_name = el.taskProfileProviderName.value.trim();
  endpoint.base_url = el.taskProfileBaseUrl.value.trim();
  endpoint.api_key = el.taskProfileApiKey.value;
  endpoint.model = el.endpointModelId.value.trim();
  updateEndpointEditorState();
  renderEndpointModelStatus(endpoint);
}

function updateEndpointEditorState() {
  const editing = !!state.endpointDraft;
  const saved = selectedEndpoint();
  const busy = state.integrationSaving;
  [el.taskProfileEndpointName, el.taskProfileProviderName, el.taskProfileBaseUrl, el.taskProfileApiKey,
    el.endpointModelSelect, el.endpointModelId].forEach(input => { input.disabled = !editing || busy; });
  el.taskProfileEndpointSelect.disabled = editing || busy;
  el.taskProfileAddEndpoint.disabled = editing || busy;
  el.endpointEditButton.disabled = !saved || editing || busy;
  el.endpointRemoveButton.disabled = !saved || editing || busy;
  el.endpointCancelButton.disabled = !editing || busy;
  el.taskProfileDiscover.disabled = !editing || busy || !state.endpointDraft?.name
    || !/^https?:\/\/\S+$/i.test(state.endpointDraft?.base_url || "");
  el.saveProviderEndpoints.disabled = !editing || busy || !endpointFormIsValid(state.endpointDraft)
    || JSON.stringify(state.endpointDraft) === state.endpointEditBaseline;
}

function editEndpoint() {
  const endpoint = selectedEndpoint();
  if (!endpoint) return;
  state.endpointDraft = JSON.parse(JSON.stringify(endpoint));
  state.endpointEditBaseline = JSON.stringify(state.endpointDraft);
  state.activeEndpointOriginalName = endpoint.name;
  loadEndpointIntoForm();
  el.taskProfileEndpointName.focus();
}

function cancelEndpointEdit() {
  state.endpointDraft = null;
  state.endpointEditBaseline = "";
  if (!selectedEndpoint()) state.activeEndpointId = state.providerEndpoints[0]?.id || null;
  renderTaskProfileEndpointOptions();
  loadEndpointIntoForm();
}

function openTaskProfile(task) {
  if (state.activeTaskProfile && state.activeTaskProfile !== task) discardTaskProfileChanges();
  state.activeTaskProfile = task;
  let assignment = state.taskModelAssignments.find(item => item.task === task);
  if (!assignment) {
    assignment = { task, provider: "", model: "", fallbacks: [], behavior_ids: null, voice_reference_id: "", notes: "" };
    state.taskModelAssignments.push(assignment);
  }
  const behavior = state.taskBehaviors.find(item => item.task === task) || {};
  taskEndpointOptions(el.taskProviderSelect, assignment.provider, task);
  el.taskProfileAssignmentSection.classList.remove("hidden");
  el.taskProfileStandardModelField.classList.add("hidden");
  el.taskProfileVoiceModelField.classList.add("hidden");
  el.taskProfileVoiceReferenceField.classList.toggle("hidden", task !== "audio_voice");
  el.taskProfileTitle.textContent = taskModelLabels[task] || displayLabel(task);
  const detailIcon = document.getElementById?.("taskProfileDetailIcon");
  if (detailIcon) {
    const listCard = [...el.taskProfileList.querySelectorAll(".task-profile-card")].find(card => card.querySelector("strong")?.textContent === el.taskProfileTitle.textContent);
    const icon = listCard?.querySelector(".axiom-button-icon");
    detailIcon.replaceChildren();
    if (icon) detailIcon.appendChild(icon.cloneNode(true));
    else detailIcon.textContent = "◆";
  }
  if (el.taskProfileRevision) el.taskProfileRevision.textContent = "";
  el.taskProfileFoundation.value = state.taskFoundations[task] || "";
  el.taskProfileInstructions.value = behavior.instructions || "";
  el.taskProfileEnabled.checked = behavior.enabled !== false;
  el.taskProfileVoiceReferenceId.value = assignment.voice_reference_id || "";
  renderTaskBehaviorSelection();
  renderFallbackSelectors();
  state.taskProfileSnapshot = taskProfileConfiguration();
  updateTaskSaveState();
  el.taskProfileOverview.classList.add("hidden");
  el.taskProfileList.classList.add("hidden");
  el.taskProfileEditor.classList.remove("hidden");
}

function closeTaskProfile() {
  discardTaskProfileChanges();
  state.activeTaskProfile = null;
  el.taskProfileEditor.classList.add("hidden");
  el.taskProfileOverview.classList.remove("hidden");
  el.taskProfileList.classList.remove("hidden");
  renderTaskProfiles();
}

function discardTaskProfileChanges() {
  if (!state.activeTaskProfile || !state.taskProfileSnapshot) return;
  const index = state.taskModelAssignments.findIndex(item => item.task === state.activeTaskProfile);
  if (index >= 0) state.taskModelAssignments[index] = JSON.parse(state.taskProfileSnapshot);
  state.taskProfileSnapshot = "";
}

function selectedEndpoint() {
  return state.providerEndpoints.find(item => item.id === state.activeEndpointId) || null;
}

async function refreshProviderEndpoints() {
  if (state.endpointDraft) return;
  const payload = await api("/v1/admin/provider-endpoints", {}, true);
  state.providerEndpoints = payload.items || [];
  if (!selectedEndpoint()) state.activeEndpointId = state.providerEndpoints[0]?.id || null;
  renderTaskProfileEndpointOptions();
  loadEndpointIntoForm();
  renderTaskProfiles();
}

async function refreshTaskModelAssignments() {
  const payload = await api("/v1/admin/task-model-assignments", {}, true);
  state.taskModelAssignments = payload.items || [];
  renderTaskProfiles();
}

async function refreshTaskBehaviors() {
  const payload = await api("/v1/admin/task-behaviors", {}, true);
  state.taskBehaviors = payload.items || [];
  state.taskFoundations = payload.foundations || {};
  renderTaskProfiles();
}

async function saveProviderEndpoints() {
  syncEndpointDraft();
  if (el.saveProviderEndpoints.disabled) return;
  const endpoint = state.endpointDraft;
  const previousName = selectedEndpoint()?.name;
  state.integrationSaving = true;
  updateEndpointEditorState();
  try {
    const items = state.providerEndpoints.filter(item => item.id !== endpoint.id).concat(endpoint);
    const payload = await api("/v1/admin/provider-endpoints", {
      method: "PUT", body: JSON.stringify({ items }),
    }, true);
    state.providerEndpoints = payload.items || [];
    for (const item of state.taskModelAssignments) {
      if (item.provider === endpoint.id || (previousName && item.provider === previousName)) {
        item.provider = endpoint.id;
        item.model = endpoint.model;
      }
      for (const fallback of (item.fallbacks || [])) {
        if (fallback.provider === endpoint.id || (previousName && fallback.provider === previousName)) {
          fallback.provider = endpoint.id;
          fallback.model = endpoint.model;
        }
      }
    }
    const assignments = await api("/v1/admin/task-model-assignments", {
      method: "PUT", body: JSON.stringify({ items: state.taskModelAssignments }),
    }, true);
    state.taskModelAssignments = assignments.items || [];
    state.endpointDraft = null;
    state.endpointEditBaseline = "";
    renderTaskProfileEndpointOptions();
    loadEndpointIntoForm();
    renderTaskProfiles();
    toast("Saved endpoint and model");
  } catch (error) { toast(error.message, true); }
  finally {
    state.integrationSaving = false;
    updateEndpointEditorState();
  }
}

async function removeEndpoint() {
  const endpoint = selectedEndpoint();
  if (!endpoint || state.endpointDraft || state.integrationSaving) return;
  state.integrationSaving = true;
  updateEndpointEditorState();
  try {
    const payload = await api("/v1/admin/provider-endpoints", {
      method: "PUT",
      body: JSON.stringify({ items: state.providerEndpoints.filter(item => item.id !== endpoint.id) }),
    }, true);
    state.providerEndpoints = payload.items || [];
    const matches = provider => provider === endpoint.id || provider === endpoint.name;
    const items = state.taskModelAssignments.map(item => ({
      ...item,
      ...(matches(item.provider) ? { provider: "", model: "" } : {}),
      fallbacks: (item.fallbacks || []).filter(fallback => !matches(fallback.provider)),
    }));
    const assignments = await api("/v1/admin/task-model-assignments", {
      method: "PUT", body: JSON.stringify({ items }),
    }, true);
    state.taskModelAssignments = assignments.items || [];
    state.activeEndpointId = state.providerEndpoints[0]?.id || null;
    renderTaskProfileEndpointOptions();
    loadEndpointIntoForm();
    renderTaskProfiles();
    toast("Removed endpoint");
  } catch (error) { toast(error.message, true); }
  finally {
    state.integrationSaving = false;
    updateEndpointEditorState();
  }
}

async function saveTaskProfile() {
  const task = state.activeTaskProfile;
  if (!task || el.saveTaskProfile.disabled) return;
  state.taskProfileSaving = true;
  el.saveTaskProfile.disabled = true;
  try {
    const assignment = state.taskModelAssignments.find(item => item.task === task);
    assignment.voice_reference_id = task === "audio_voice" ? el.taskProfileVoiceReferenceId.value.trim() : assignment.voice_reference_id || "";
    const payload = await api("/v1/admin/task-model-assignments", {
      method: "PUT", body: JSON.stringify({ items: state.taskModelAssignments }),
    }, true);
    state.taskModelAssignments = payload.items || [];
    toast(`Saved ${taskModelLabels[task] || displayLabel(task)} task profile`);
    renderTaskProfiles();
    openTaskProfile(task);
  } catch (error) { toast(error.message, true); }
  finally { state.taskProfileSaving = false; updateTaskSaveState(); }
}

async function discoverTaskProfileModels() {
  syncEndpointDraft();
  const endpoint = state.endpointDraft;
  if (!endpoint) {
    toast("Choose or add an endpoint first", true);
    return;
  }
  el.taskProfileDiscover.disabled = true;
  try {
    const payload = await api("/v1/admin/provider-endpoints/discover", {
      method: "POST",
      body: JSON.stringify(endpoint),
    }, true);
    endpoint.models = payload.models || [];
    endpoint.model_capabilities = payload.model_capabilities || {};
    endpoint.model_capability_sources = payload.model_capability_sources || {};
    if (!endpoint.model && endpoint.models.length === 1) endpoint.model = endpoint.models[0];
    renderTaskProfileEndpointOptions();
    loadEndpointIntoForm();
    toast(`Discovered ${endpoint.models.length} model(s)`);
  } catch (error) {
    toast(error.message, true);
  }
  finally { updateEndpointEditorState(); }
}

const COMMON_ENDPOINT_PRESETS = [
  { id: "openai", name: "OpenAI", base_url: "https://api.openai.com/v1" },
  { id: "openrouter", name: "OpenRouter", base_url: "https://openrouter.ai/api/v1" },
  { id: "google-gemini", name: "Google Gemini (OpenAI-compatible)", base_url: "https://generativelanguage.googleapis.com/v1beta/openai" },
  { id: "groq", name: "Groq", base_url: "https://api.groq.com/openai/v1" },
  { id: "together", name: "Together AI", base_url: "https://api.together.xyz/v1" },
  { id: "fireworks", name: "Fireworks AI", base_url: "https://api.fireworks.ai/inference/v1" },
  { id: "deepseek", name: "DeepSeek", base_url: "https://api.deepseek.com" },
  { id: "mistral", name: "Mistral AI", base_url: "https://api.mistral.ai/v1" },
  { id: "cerebras", name: "Cerebras", base_url: "https://api.cerebras.ai/v1" },
  { id: "ollama", name: "Ollama (local)", base_url: "http://localhost:11434/v1" },
  { id: "lm-studio", name: "LM Studio (local)", base_url: "http://localhost:1234/v1" },
  { id: "vllm", name: "vLLM (local/self-hosted)", base_url: "http://localhost:8000/v1" },
  { id: "localai", name: "LocalAI (local/self-hosted)", base_url: "http://localhost:8080/v1" },
];
function addTaskProfileEndpointFromPreset(presetId) {
  const preset = COMMON_ENDPOINT_PRESETS.find(item => item.id === presetId);
  if (!preset) {
    toast("Choose an endpoint preset first", true);
    return;
  }
  const endpoint = {
    id: crypto.randomUUID(),
    name: preset.name,
    provider_name: preset.name,
    base_url: preset.base_url,
    api_key: "",
    model: "",
    models: [],
    model_capabilities: {},
    model_capability_sources: {},
  };
  state.endpointDraft = endpoint;
  state.endpointEditBaseline = "";
  state.activeEndpointId = endpoint.id;
  state.activeEndpointOriginalName = "";
  renderTaskProfileEndpointOptions();
  loadEndpointIntoForm();

  el.taskProfileApiKey.focus();
  toast(`Added ${preset.name}. Add credentials if required, then discover models.`);
}

function addTaskProfileEndpoint() {
  const endpoint = {
    id: crypto.randomUUID(),
    name: "",
    provider_name: "",
    base_url: "",
    api_key: "",
    model: "",
    models: [],
    model_capabilities: {},
    model_capability_sources: {},
  };
  state.endpointDraft = endpoint;
  state.endpointEditBaseline = "";
  state.activeEndpointId = endpoint.id;
  state.activeEndpointOriginalName = "";
  renderTaskProfileEndpointOptions();
  loadEndpointIntoForm();
  el.taskProfileEndpointName.focus();
}

function updateVoiceSliderReadouts() {
  if (el.voiceRateValue) el.voiceRateValue.value = Number(el.voiceRate.value).toFixed(2);
  if (el.voicePitchValue) el.voicePitchValue.value = Number(el.voicePitch.value).toFixed(2);
  if (el.voiceVolumeValue) el.voiceVolumeValue.value = Number(el.voiceVolume.value).toFixed(2);
}

async function loadVoiceSettings() {
  try {
    const settings = await api("/v1/admin/body/voice/settings", {}, true);
    state.voiceSettingsRevision = Number(settings.revision || 0);
    el.voiceRate.value = String(settings.rate ?? 1);
    el.voicePitch.value = String(settings.pitch ?? 1);
    el.voiceVolume.value = String(settings.volume ?? 1);
    el.voiceName.value = settings.voiceName || "";
    updateVoiceSliderReadouts();
    el.voiceSettingsRevision.textContent = "Revision: " + state.voiceSettingsRevision;
  } catch (error) {
    toast("Could not load voice settings: " + error.message, true);
  }
}

async function saveVoiceSettings() {
  try {
    const settings = await api("/v1/admin/body/voice/settings", {
      method: "POST",
      body: JSON.stringify({
        expected_revision: state.voiceSettingsRevision,
        rate: Number(el.voiceRate.value),
        pitch: Number(el.voicePitch.value),
        volume: Number(el.voiceVolume.value),
        voice_name: el.voiceName.value.trim(),
      }),
    }, true);
    state.voiceSettingsRevision = Number(settings.revision || 0);
    el.voiceSettingsRevision.textContent = "Revision: " + state.voiceSettingsRevision;
    toast("Voice settings saved");
  } catch (error) {
    toast("Could not save voice settings: " + error.message, true);
  }
}

async function refreshBodyFallbackSettings() {
  if (!state.adminAuthorized || !el.bodyFallbackEnabled) return;
  try {
    const settings = await api("/v1/admin/body/fallback", {}, true);
    el.bodyFallbackEnabled.checked = Boolean(settings.enabled);
    el.bodyFallbackSource.textContent = settings.runtime_override === null
      ? `Using Render deployment setting (${settings.deployment_default ? "enabled" : "disabled"}).`
      : `Runtime override active. Deployment default is ${settings.deployment_default ? "enabled" : "disabled"}.`;
  } catch (error) {
    if (el.bodyFallbackSource) el.bodyFallbackSource.textContent = `Could not load setting: ${error.message}`;
  }
}

async function saveBodyFallbackSettings() {
  if (!el.bodyFallbackEnabled) return;
  if (el.saveBodyFallbackSetting) el.saveBodyFallbackSetting.disabled = true;
  try {
    const settings = await api("/v1/admin/body/fallback", {
      method: "PUT",
      body: JSON.stringify({ enabled: el.bodyFallbackEnabled.checked }),
    }, true);
    el.bodyFallbackEnabled.checked = Boolean(settings.enabled);
    el.bodyFallbackSource.textContent = settings.runtime_override === null
      ? `Using Render deployment setting (${settings.deployment_default ? "enabled" : "disabled"}).`
      : `Runtime override active. Deployment default is ${settings.deployment_default ? "enabled" : "disabled"}.`;
    toast(`Body reasoning fallback ${settings.enabled ? "enabled" : "disabled"}`);
  } catch (error) {
    toast(`Could not save Body fallback setting: ${error.message}`, true);
    await refreshBodyFallbackSettings();
  } finally {
    if (el.saveBodyFallbackSetting) el.saveBodyFallbackSetting.disabled = false;
  }
}

async function enterAdminMode() {
  try {
    const allowed = await validateAdmin();
    if (!allowed) return;
    setMode("admin");
    await Promise.all([
      refreshMemory(filters.admin, true),
      refreshJournal(true),
      refreshHostBehaviors(),
      refreshTaskModelAssignments(),
      refreshTaskBehaviors(),
      refreshProviderEndpoints(),
      refreshMcpServers(),
      loadVoiceSettings(),
      refreshBodyFallbackSettings(),
    ]);
  } catch (error) {
    toast(error.message, true);
  }
}

function renderStatus(status) {
  state.status = status;
  const mind = status.mind;
  const integration = status.integration;

  el.connectionLabel.textContent = "MCP - Axiom Online";
  el.mindName.textContent = mind.identity.self_name;
  el.continuityLabel.textContent = "Persistent";
  el.selfName.textContent = mind.identity.self_name;
  el.developmentState.textContent = displayLabel(mind.developmental_state);
  el.createdAt.textContent = formatBrowserDateTime(mind.created_at);
  el.memoryCount.textContent = Number(status.durable_memory_count).toLocaleString();
  el.journalCount.textContent = Number(status.journal_experience_count).toLocaleString();

  // These legacy overview fields were removed from the portal markup.
  // Keep status refresh resilient when optional presentation fields are absent.
  if (el.protocolValue) el.protocolValue.textContent = integration.protocol;
  const host = status.reasoning?.active_host;
  if (el.reasoningOwner) {
    el.reasoningOwner.textContent = host
      ? `External Host: ${host.name} (${host.model})`
      : `External Host: not attached; standalone fallback ${status.reasoning?.fallback_enabled ? "enabled" : "disabled"}`;
  }
  if (el.identityOwner) el.identityOwner.textContent = integration.identity_owner;
  if (el.memoryOwner) el.memoryOwner.textContent = integration.memory_owner;
  el.adminMindName.textContent = mind.identity.self_name;
  el.adminCreatedAt.textContent = formatBrowserDateTime(mind.created_at);
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

function formatEvidenceAppraisal(appraisal) {
  if (!appraisal) return "Not Appraised";
  const provenance = (appraisal.provenance || [])
    .map((hop, index) => {
      const details = [hop.source, hop.context, hop.condition].filter(Boolean).join(" · ");
      return `${index + 1}. ${details}`;
    })
    .join("\n");
  const basis = (appraisal.basis || []).length
    ? `\nBasis: ${appraisal.basis.join("; ")}`
    : "";
  return [
    `Confidence: ${appraisal.confidence}`,
    `Weight: ${appraisal.weight}`,
    provenance ? `Provenance:\n${provenance}` : "Provenance: —",
  ].join("\n") + basis;
}

function formatResolutionReadiness(readiness) {
  if (!readiness) return "Not Assessed";
  const existing = readiness.existing || {};
  const proposed = readiness.proposed || {};
  const blockers = (readiness.blockers || []).length
    ? readiness.blockers.map((item, index) => `${index + 1}. ${item}`).join("\n")
    : "None";
  const basis = (readiness.basis || []).length
    ? readiness.basis.map((item, index) => `${index + 1}. ${item}`).join("\n")
    : "None";
  return [
    `Status: ${displayLabel(readiness.status)}`,
    `Candidate Side: ${readiness.candidate_side ? displayLabel(readiness.candidate_side) : "None"}`,
    `Candidate Value: ${readiness.candidate_value ?? "None"}`,
    `Existing Profile: support=${existing.support_count ?? 0}, sources=${existing.distinct_immediate_sources ?? 0}, confidence=${existing.confidence_floor ?? "—"}..${existing.confidence_ceiling ?? "—"}, weight=${existing.weight_floor ?? "—"}..${existing.weight_ceiling ?? "—"}`,
    `Proposed Profile: support=${proposed.support_count ?? 0}, sources=${proposed.distinct_immediate_sources ?? 0}, confidence=${proposed.confidence_floor ?? "—"}..${proposed.confidence_ceiling ?? "—"}, weight=${proposed.weight_floor ?? "—"}..${proposed.weight_ceiling ?? "—"}`,
    `Blockers:\n${blockers}`,
    `Basis:\n${basis}`,
  ].join("\n");
}

function formatEvidenceDeliberation(deliberation) {
  if (!deliberation) return "No Deliberation Recorded";
  const gaps = (deliberation.appraisal_gaps || []).join("\n");
  const contexts = (deliberation.context_observations || []).join("\n");
  const questions = (deliberation.investigation_questions || [])
    .map((question, index) => `${index + 1}. ${question}`)
    .join("\n");
  const evidenceHistory = (deliberation.current_evidence_history || [])
    .map((item, index) => {
      const meaning = item.semantic_interpretation || {};
      const scope = meaning.scope?.label ? ` · scope=${meaning.scope.label}` : "";
      return `${index + 1}. ${item.response_excerpt} [${meaning.subject || "?"} · ${meaning.attribute || "?"} = ${meaning.value ?? "?"}${scope}]`;
    })
    .join("\n");
  return [
    `Revision: ${deliberation.revision ?? 1}`,
    `Trigger: ${displayLabel(deliberation.trigger || "tension_detected")}`,
    `Current Evidence Considered: ${deliberation.current_evidence_considered ?? 0}`,
    `Current Evidence Supporting Existing: ${deliberation.current_existing_support_count ?? 0}`,
    `Current Evidence Supporting Proposed: ${deliberation.current_proposed_support_count ?? 0}`,
    `Existing Support: ${deliberation.existing_support_count ?? 0}`,
    `Proposed Support: ${deliberation.proposed_support_count ?? 0}`,
    `Semantic Scope: ${deliberation.scope?.label || "Unscoped"}`,
    `Provenance Relationship: ${displayLabel(deliberation.provenance_relationship || "unknown")}`,
    `Existing Provenance Depth: ${deliberation.existing_provenance_depth ?? 0}`,
    `Proposed Provenance Depth: ${deliberation.proposed_provenance_depth ?? 0}`,
    gaps ? `Appraisal Gaps:\n${gaps}` : "Appraisal Gaps: None",
    contexts ? `Context Observations:\n${contexts}` : "Context Observations: None",
    questions ? `Investigation Questions:\n${questions}` : "Investigation Questions: None",
    evidenceHistory ? `Retained Research Evidence:\n${evidenceHistory}` : "Retained Research Evidence: None",
    `Tension Finding:\n${deliberation.tension_finding ? JSON.stringify(deliberation.tension_finding, null, 2) : "None"}`,
    `Resolution Readiness:\n${formatResolutionReadiness(deliberation.resolution_readiness)}`,
  ].join("\n");
}

function renderMemoryArtifacts(artifacts) {
  el.inspectorArtifacts.innerHTML = "";
  if (!artifacts || !artifacts.length) {
    const empty = document.createElement("div");
    empty.className = "record-empty";
    empty.textContent = "None";
    el.inspectorArtifacts.appendChild(empty);
    return;
  }

  for (const artifact of artifacts) {
    const item = document.createElement("div");
    item.className = "record-value";
    const formedBy = displayLabel(artifact.formed_by);
    let payload;
    if (artifact.kind === "evidence_appraisal") {
      payload = formatEvidenceAppraisal(artifact.payload);
    } else if (artifact.kind === "evidence_deliberation") {
      payload = formatEvidenceDeliberation(artifact.payload);
    } else {
      payload = JSON.stringify(artifact.payload || {}, null, 2);
    }
    item.textContent = `${displayLabel(artifact.kind)} · ${formedBy}\n${payload}`;
    el.inspectorArtifacts.appendChild(item);
  }
}

function openMemoryInspector(memory, sourceMode) {
  state.activeMemory = JSON.parse(JSON.stringify(memory));
  el.inspectorContent.textContent = memory.content;
  el.inspectorClass.textContent = displayLabel(memory.memory_class);
  el.inspectorFormedAt.textContent = formatBrowserDateTime(memory.formed_at);
  renderRecordValues(el.inspectorGrounding, memory.grounding);
  renderRecordValues(el.inspectorAssociations, memory.associations);
  renderMemoryArtifacts(memory.artifacts);
  el.inspectorRaw.textContent = JSON.stringify(memory, null, 2);

  const editable = sourceMode === "admin" && state.adminAuthorized;
  el.memoryEditActions.classList.toggle("hidden", !editable);
  el.memoryEditForm.classList.add("hidden");
  el.memoryInspector.classList.remove("hidden");
  el.closeMemoryInspector.focus();
}

function closeMemoryInspector() {
  state.activeMemory = null;
  el.memoryEditForm.classList.add("hidden");
  el.memoryInspector.classList.add("hidden");
}

function beginMemoryEdit() {
  const memory = state.activeMemory;
  if (!memory || !state.adminAuthorized) return;
  el.editMemoryContent.value = memory.content;
  el.editMemoryClass.value = memory.memory_class;
  el.editAssociations.value = (memory.associations || []).join("\n");
  el.editGrounding.value = (memory.grounding || []).join("\n");
  el.memoryEditActions.classList.add("hidden");
  el.memoryEditForm.classList.remove("hidden");
  el.editMemoryContent.focus();
}

function cancelMemoryEdit() {
  el.memoryEditForm.classList.add("hidden");
  if (state.adminAuthorized) {
    el.memoryEditActions.classList.remove("hidden");
  }
}

function splitLines(value) {
  return value
    .split(/\n|,/)
    .map(item => item.trim())
    .filter(Boolean);
}

async function saveMemoryEdit(event) {
  event.preventDefault();
  const original = state.activeMemory;
  if (!original || !state.adminAuthorized) return;

  const replacement = {
    memory_class: el.editMemoryClass.value,
    formed_at: original.formed_at,
    content: el.editMemoryContent.value.trim(),
    associations: splitLines(el.editAssociations.value),
    grounding: splitLines(el.editGrounding.value),
    artifacts: original.artifacts || [],
  };

  if (!replacement.content) {
    toast("Memory content cannot be empty", true);
    return;
  }

  try {
    const revised = await api(
      "/v1/admin/memory",
      {
        method: "PUT",
        body: JSON.stringify({ original, replacement }),
      },
      true,
    );
    toast("Durable memory revised and journaled");
    await Promise.all([
      refreshMemory(filters.mind, true),
      refreshMemory(filters.admin, true),
      refreshJournal(true),
      refreshStatus(),
    ]);
    openMemoryInspector(revised, "admin");
  } catch (error) {
    toast(error.message, true);
    if (error.status === 409) {
      await refresh();
      closeMemoryInspector();
    }
  }
}

function memoryQuery(config, offset = 0) {
  const params = new URLSearchParams({
    limit: String(state.memoryPageSizes[config.key]),
    offset: String(offset),
    order: config.sort.value,
  });

  const search = config.search.value.trim();
  const association = config.association.value.trim();
  const grounding = config.grounding.value.trim();

  if (search) params.set("search", search);
  if (config.memoryClass.value) params.set("memory_class", config.memoryClass.value);
  if (association) params.set("association", association);
  if (grounding) params.set("grounding", grounding);
  if (config.from.value) params.set("from", config.from.value);
  if (config.to.value) params.set("to", config.to.value);

  return `/v1/portal/memory?${params.toString()}`;
}

function renderMemoryList(config, sourceMode) {
  const page = state.memoryPages[config.key];
  config.list.innerHTML = "";
  config.count.textContent =
    `Showing ${page.items.length.toLocaleString()} of ${page.total.toLocaleString()} Memories`;
  config.loadMore.classList.toggle("hidden", !page.hasMore);
  config.loadMore.textContent = "Get More";

  if (!page.items.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = page.total
      ? "No durable memories match the current filters."
      : "No durable memories have been curated yet.";
    config.list.appendChild(empty);
    return;
  }

  for (const memory of page.items) {
    const item = document.createElement("article");
    item.className = "memory-item";
    item.tabIndex = 0;
    item.setAttribute("role", "button");
    item.setAttribute("aria-label", `Inspect ${memory.memory_class} memory`);
    item.addEventListener("click", () => openMemoryInspector(memory, sourceMode));
    item.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openMemoryInspector(memory, sourceMode);
      }
    });

    const meta = document.createElement("div");
    meta.className = "memory-meta";
    const klass = document.createElement("span");
    klass.textContent = displayLabel(memory.memory_class);
    const formed = document.createElement("span");
    formed.textContent = formatBrowserDateTime(memory.formed_at);
    meta.append(klass, formed);

    const content = document.createElement("div");
    content.className = "memory-content";
    content.textContent = memory.content;

    item.append(meta, content);
    config.list.appendChild(item);
  }
}

async function refreshMemory(config, reset = true) {
  try {
    const pageState = state.memoryPages[config.key];
    const offset = reset ? 0 : pageState.nextOffset;
    const page = await api(memoryQuery(config, offset));

    pageState.items = page.items;
    pageState.total = page.total;
    pageState.hasMore = page.has_more;
    pageState.nextOffset = page.next_offset ?? pageState.items.length;
    renderMemoryList(config, config.key);
  } catch (error) {
    toast(error.message, true);
  }
}

function scheduleMemoryRefresh(config) {
  clearTimeout(state.memoryFilterTimers[config.key]);
  state.memoryFilterTimers[config.key] = setTimeout(
    () => refreshMemory(config, true),
    250,
  );
}

function journalQuery(offset = 0) {
  const params = new URLSearchParams({
    limit: String(state.journalPageSize),
    offset: String(offset),
    order: el.journalSort.value,
  });

  const search = el.journalSearch.value.trim();
  if (search) params.set("search", search);
  if (el.journalKindFilter.value) params.set("kind", el.journalKindFilter.value);
  if (el.journalFrom.value) params.set("from", el.journalFrom.value);
  if (el.journalTo.value) params.set("to", el.journalTo.value);

  return `/v1/portal/journal?${params.toString()}`;
}

function renderJournalList() {
  if (!el.journalTimeline) return;
  el.journalTimeline.innerHTML = "";
  el.journalResultCount.textContent =
    `Showing ${state.journals.length.toLocaleString()} of ${state.journalTotal.toLocaleString()} Experiences`;
  el.loadMoreJournals.classList.toggle("hidden", !state.journalHasMore);
  el.loadMoreJournals.textContent = "Get More";

  if (!state.journals.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = state.journalTotal
      ? "No journal experiences match the current filters."
      : "No journal experiences have been recorded yet.";
    el.journalTimeline.appendChild(empty);
    return;
  }

  for (const entry of state.journals) {
    const item = document.createElement("article");
    item.className = "journal-entry";
    item.tabIndex = 0;
    item.setAttribute("role", "button");
    item.setAttribute("aria-label", `Inspect ${entry.title} journal experience`);
    item.addEventListener("click", () => openJournalInspector(entry));
    item.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openJournalInspector(entry);
      }
    });

    const meta = document.createElement("div");
    meta.className = "journal-entry-meta";
    const kind = document.createElement("span");
    kind.textContent = displayLabel(entry.kind);
    const occurred = document.createElement("span");
    occurred.textContent = formatBrowserDateTime(entry.occurred_at);
    meta.append(kind, occurred);

    const title = document.createElement("div");
    title.className = "journal-entry-title";
    title.textContent = entry.title || displayLabel(entry.kind);

    const preview = document.createElement("div");
    preview.className = "journal-entry-preview";
    preview.textContent = entry.preview || "";

    item.append(meta, title, preview);
    el.journalTimeline.appendChild(item);
  }
}

function addJournalBlock(label, content) {
  const block = document.createElement("div");
  block.className = "journal-block";
  const heading = document.createElement("span");
  heading.className = "journal-block-label";
  heading.textContent = label;
  const value = document.createElement("div");
  value.className = "journal-block-content";
  value.textContent = content || "—";
  block.append(heading, value);
  return block;
}

function formatResearchEvidence(observations) {
  if (!observations || !observations.length) return "None";
  return observations.map((observation, index) => {
    const interpretation = observation.semantic_interpretation;
    const meaning = interpretation
      ? `\nMeaning: ${interpretation.subject} · ${interpretation.attribute} = ${interpretation.value}${interpretation.scope?.label ? ` [${interpretation.scope.label}]` : ""}`
      : "";
    const appraisal = observation.appraisal
      ? `\n${formatEvidenceAppraisal(observation.appraisal)}`
      : "\nNot Appraised";
    const finding = observation.tension_finding
      ? `\nTension Finding: ${JSON.stringify(observation.tension_finding, null, 2)}`
      : "";
    return `${index + 1}. ${observation.response}${meaning}${appraisal}${finding}`;
  }).join("\n\n");
}

function renderJournalDetail(entry) {
  el.journalStructuredDetail.innerHTML = "";
  const experience = entry.experience || {};

  if (entry.kind === "interaction") {
    el.journalStructuredDetail.append(
      addJournalBlock("Human Input", experience.input?.content || ""),
      addJournalBlock("Conscious Response", experience.expression?.content || ""),
    );
    return;
  }

  if (entry.kind === "tension") {
    const values = experience.competing_values || {};
    const evidence = experience.evidence || {};
    const appraisals = experience.appraisals || {};
    const deliberation = experience.deliberation || null;
    const currentEvidence = experience.current_evidence || [];
    const diff = document.createElement("div");
    diff.className = "journal-diff";
    diff.append(
      addJournalBlock("Existing Value", String(values.existing ?? "")),
      addJournalBlock("Proposed Value", String(values.proposed ?? "")),
    );
    el.journalStructuredDetail.append(
      addJournalBlock(
        "Semantic Slot",
        [experience.subject, experience.attribute].filter(Boolean).join(" · "),
      ),
      addJournalBlock("Semantic Scope", experience.scope?.label || "Unscoped"),
      diff,
      addJournalBlock("Existing Evidence", evidence.existing || ""),
      addJournalBlock("Existing Appraisal", formatEvidenceAppraisal(appraisals.existing)),
      addJournalBlock("Proposed Evidence", evidence.proposed || ""),
      addJournalBlock("Proposed Appraisal", formatEvidenceAppraisal(appraisals.proposed)),
      addJournalBlock("Evidence Deliberation", formatEvidenceDeliberation(deliberation)),
      ...(experience.phase === "reassessment"
        ? [addJournalBlock("Current Evidence Used", formatResearchEvidence(currentEvidence))]
        : []),
      addJournalBlock("Phase", displayLabel(experience.phase || "detected")),
      addJournalBlock("Status", displayLabel(experience.status || "unresolved")),
    );
    return;
  }

  if (entry.kind === "belief_reframe") {
    el.journalStructuredDetail.append(
      addJournalBlock(
        "Semantic Slot",
        [experience.subject, experience.attribute].filter(Boolean).join(" · "),
      ),
      addJournalBlock("Relationship", displayLabel(experience.relationship || "")),
      addJournalBlock(
        "Existing Scoped Belief",
        `${String(experience.existing_value ?? "")} [${experience.existing_scope || "—"}]`,
      ),
      addJournalBlock(
        "Proposed Scoped Belief",
        `${String(experience.proposed_value ?? "")} [${experience.proposed_scope || "—"}]`,
      ),
      addJournalBlock(
        "Deliberation Revision",
        String(experience.deliberation_revision ?? ""),
      ),
      addJournalBlock("Evidence Basis", (experience.basis || []).join("\n")),
      addJournalBlock(
        "Existing Evidence Preserved",
        (experience.existing_evidence || []).join("\n"),
      ),
      addJournalBlock(
        "Proposed Evidence Preserved",
        (experience.proposed_evidence || []).join("\n"),
      ),
      addJournalBlock("Status", displayLabel(experience.status || "committed")),
    );
    return;
  }

  if (entry.kind === "belief_transition") {
    el.journalStructuredDetail.append(
      addJournalBlock(
        "Semantic Slot",
        [experience.subject, experience.attribute].filter(Boolean).join(" · "),
      ),
      addJournalBlock("Superseded Belief", String(experience.from_value ?? "")),
      addJournalBlock("Current Belief", String(experience.to_value ?? "")),
      addJournalBlock("Semantic Scope", experience.scope?.label || "Unscoped"),
      addJournalBlock(
        "Deliberation Revision",
        String(experience.deliberation_revision ?? ""),
      ),
      addJournalBlock(
        "Readiness Basis",
        (experience.readiness_basis || []).join("\n"),
      ),
      addJournalBlock(
        "Candidate Evidence Preserved",
        (experience.candidate_evidence || []).join("\n"),
      ),
      addJournalBlock(
        "Superseded Evidence Preserved",
        (experience.superseded_evidence || []).join("\n"),
      ),
      addJournalBlock("Status", displayLabel(experience.status || "committed")),
    );
    return;
  }

  if (entry.kind === "memory_revision") {
    const diff = document.createElement("div");
    diff.className = "journal-diff";
    diff.append(
      addJournalBlock("Before", experience.before?.content || JSON.stringify(experience.before || {}, null, 2)),
      addJournalBlock("After", experience.after?.content || JSON.stringify(experience.after || {}, null, 2)),
    );
    el.journalStructuredDetail.append(diff);

    if (experience.source || experience.channel) {
      el.journalStructuredDetail.append(
        addJournalBlock(
          "Revision Source",
          [experience.source, experience.channel].filter(Boolean).map(displayLabel).join(" · "),
        ),
      );
    }
    return;
  }

  if (entry.kind === "initialization") {
    el.journalStructuredDetail.append(
      addJournalBlock("Self Name", experience.self_name || ""),
      addJournalBlock(
        "Foundational Values",
        (experience.foundational_values || []).join("\n"),
      ),
    );
    return;
  }

  el.journalStructuredDetail.append(
    addJournalBlock("Experience", JSON.stringify(experience, null, 2)),
  );
}

async function openJournalInspector(summary) {
  try {
    const entry = await api("/v1/portal/journal/detail", {
      method: "POST",
      body: JSON.stringify({
        kind: summary.kind,
        occurred_at: summary.occurred_at,
      }),
    });
    state.activeJournal = entry;
    el.journalInspectorKind.textContent = displayLabel(entry.kind);
    el.journalInspectorOccurredAt.textContent = formatBrowserDateTime(entry.occurred_at);
    renderJournalDetail(entry);
    await renderJournalEvidence(entry);
    el.journalInspectorRaw.textContent = JSON.stringify(entry, null, 2);
    el.journalInspector.classList.remove("hidden");
    el.closeJournalInspector.focus();
  } catch (error) {
    toast(error.message, true);
  }
}

function findEvidenceReferences(value, found = [], seen = new Set()) {
  if (!value || typeof value !== "object" || seen.has(value)) return found;
  seen.add(value);
  if (typeof value.sha256 === "string" && /^[a-f0-9]{64}$/i.test(value.sha256)) {
    const capturedAt = value.captured_at || value.capturedAt;
    if (capturedAt) {
      const key = `${value.sha256}:${capturedAt}`;
      if (!found.some(item => `${item.sha256}:${item.captured_at}` === key)) {
        found.push({
          sha256: value.sha256,
          captured_at: capturedAt,
          modality: value.modality || value.media_type?.split("/")[0] || "sensory",
          source: value.source || "journal evidence",
          media_type: value.media_type || "",
          byte_length: value.byte_length || 0,
        });
      }
    }
  }
  for (const child of Object.values(value)) findEvidenceReferences(child, found, seen);
  return found;
}

async function renderJournalEvidence(entry) {
  el.journalEvidenceList.replaceChildren();
  const references = findEvidenceReferences(entry.experience || {});
  el.journalEvidenceDetail.classList.toggle("hidden", references.length === 0);
  for (const artifact of references) {
    const item = document.createElement("article");
    item.className = "journal-entry";
    const meta = document.createElement("div");
    meta.className = "journal-entry-meta";
    const kind = document.createElement("span");
    kind.textContent = `${artifact.modality} · ${artifact.source}`;
    const captured = document.createElement("span");
    captured.textContent = formatBrowserDateTime(artifact.captured_at);
    meta.append(kind, captured);
    const title = document.createElement("div");
    title.className = "journal-entry-title";
    title.textContent = artifact.media_type
      ? `${artifact.media_type} · ${Number(artifact.byte_length).toLocaleString()} bytes`
      : "Preserved media artifact";
    const hash = document.createElement("div");
    hash.className = "journal-entry-preview";
    hash.textContent = `SHA-256: ${artifact.sha256}`;
    item.append(meta, title, hash);
    const mediaUrl = evidenceMediaUrl(artifact);
    if (artifact.media_type.startsWith("image/") || artifact.modality === "vision") {
      const preview = document.createElement("img");
      preview.loading = "lazy";
      preview.alt = "Preserved sensory evidence from this journal record";
      preview.className = "evidence-preview";
      preview.src = mediaUrl;
      item.append(preview);
    } else if (artifact.media_type.startsWith("audio/") || artifact.modality === "audio") {
      const audio = document.createElement("audio");
      audio.controls = true;
      audio.preload = "none";
      audio.src = mediaUrl;
      audio.className = "evidence-audio";
      item.append(audio);
    }
    const actions = document.createElement("div");
    actions.className = "edit-actions";
    if (state.adminAuthorized) {
      const erase = document.createElement("button");
      erase.className = "danger-button";
      erase.type = "button";
      erase.textContent = "Erase Evidence";
      erase.addEventListener("click", async () => {
        if (!window.confirm("Permanently erase the media bytes for this journal record? The journal audit entry will remain.")) return;
        erase.disabled = true;
        try {
          const query = new URLSearchParams({ captured_at: artifact.captured_at });
          await api(`/v1/portal/evidence/${encodeURIComponent(artifact.sha256)}?${query}`, { method: "DELETE" }, true);
          toast("Evidence erased; journal history retained");
          await renderJournalEvidence(entry);
        } catch (error) {
          toast(`Could not erase evidence: ${error.message}`, true);
          erase.disabled = false;
        }
      });
      actions.append(erase);
    } else {
      const note = document.createElement("span");
      note.className = "muted-copy";
      note.textContent = "Administrator authorization is required to erase media.";
      actions.append(note);
    }
    item.append(actions);
    el.journalEvidenceList.append(item);
  }
}

function closeJournalInspector() {
  state.activeJournal = null;
  el.journalEvidenceDetail.classList.add("hidden");
  el.journalEvidenceList.replaceChildren();
  el.journalInspector.classList.add("hidden");
}

function clearJournalFilters() {
  el.journalSearch.value = "";
  el.journalKindFilter.value = "";
  el.journalFrom.value = "";
  el.journalTo.value = "";
  el.journalSort.value = "newest";
  refreshJournal(true);
}

async function refreshJournal(reset = true) {
  try {
    const offset = reset ? 0 : state.journalNextOffset;
    const page = await api(journalQuery(offset));

    state.journals = page.items;
    state.journalTotal = page.total;
    state.journalHasMore = page.has_more;
    state.journalNextOffset = page.next_offset ?? state.journals.length;
    renderJournalList();
  } catch (error) {
    toast(error.message, true);
  }
}

function scheduleJournalRefresh() {
  clearTimeout(state.journalFilterTimer);
  state.journalFilterTimer = setTimeout(() => refreshJournal(true), 250);
}

function clearFilters(config) {
  config.search.value = "";
  config.memoryClass.value = "";
  config.association.value = "";
  config.grounding.value = "";
  config.from.value = "";
  config.to.value = "";
  config.sort.value = "newest";
  refreshMemory(config, true);
}

async function logout() {
  try {
    await api("/v1/portal/logout", { method: "POST" });
  } catch (_) {
    // Redirect even if the server response is unavailable; protected requests
    // will require a fresh session on the next portal load.
  } finally {
    sessionStorage.removeItem("acm_admin_pin");
    location.replace("/portal");
  }
}

async function refreshStatus() {
  const status = await api("/v1/portal/status");
  renderStatus(status);
  return status;
}

async function refresh() {
  try {
    const admin = state.mode === "admin" && state.adminAuthorized;
    await Promise.all([
      refreshStatus(),
      refreshMemory(admin ? filters.admin : filters.mind, true),
      refreshJournal(true),
      ...(admin ? [
        refreshBodyFallbackSettings(),
        refreshHostBehaviors(),
        refreshTaskModelAssignments(),
        refreshTaskBehaviors(),
        refreshProviderEndpoints(),
        refreshMcpServers(),
        loadVoiceSettings(),
      ] : []),
    ]);
    el.initializeOverlay.classList.add("hidden");
  } catch (error) {
    if (error.status === 404) {
      el.connectionLabel.textContent = "Mind Not Initialized";
      el.continuityLabel.textContent = "Awaiting Genesis";
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

function bindFilterEvents(config) {
  for (const control of [config.search, config.association, config.grounding]) {
    control.addEventListener("input", () => scheduleMemoryRefresh(config));
  }
  for (const control of [
    config.memoryClass,
    config.from,
    config.to,
    config.sort,
  ]) {
    control.addEventListener("change", () => refreshMemory(config, true));
  }
}

el.mindTab.addEventListener("click", () => setMode("mind"));
el.adminTab.addEventListener("click", enterAdminMode);
el.logoutButton.addEventListener("click", logout);
if (el.refreshButton) el.refreshButton.addEventListener("click", refresh);
el.adminMemoryRefreshButton.addEventListener("click", () => refreshMemory(filters.admin, true));
el.adminRefreshButton.addEventListener("click", refresh);
if (el.saveBodyFallbackSetting) el.saveBodyFallbackSetting.addEventListener("click", saveBodyFallbackSettings);
el.journalRefreshButton.addEventListener("click", () => refreshJournal(true));
el.loadMoreJournals.addEventListener("click", () => refreshJournal(false));
el.journalPageSize.addEventListener("change", () => {
  state.journalPageSize = Number(el.journalPageSize.value) || 25;
  refreshJournal(true);
});
el.initializeForm.addEventListener("submit", initializeMind);
el.closeMemoryInspector.addEventListener("click", closeMemoryInspector);
el.memoryInspector.addEventListener("click", event => {
  if (event.target === el.memoryInspector) closeMemoryInspector();
});
el.editMemoryButton.addEventListener("click", beginMemoryEdit);
el.cancelMemoryEdit.addEventListener("click", cancelMemoryEdit);
el.memoryEditForm.addEventListener("submit", saveMemoryEdit);
el.clearMemoryFilters.addEventListener("click", () => clearFilters(filters.mind));
el.adminClearMemoryFilters.addEventListener("click", () => clearFilters(filters.admin));
el.loadMoreMemories.addEventListener("click", () => refreshMemory(filters.mind, false));
el.memoryPageSize.addEventListener("change", () => {
  state.memoryPageSizes.mind = Number(el.memoryPageSize.value) || 25;
  refreshMemory(filters.mind, true);
});
el.adminLoadMoreMemories.addEventListener("click", () => refreshMemory(filters.admin, false));
el.adminMemoryPageSize.addEventListener("change", () => {
  state.memoryPageSizes.admin = Number(el.adminMemoryPageSize.value) || 25;
  refreshMemory(filters.admin, true);
});
el.clearJournalFilters.addEventListener("click", clearJournalFilters);
el.journalSearch.addEventListener("input", scheduleJournalRefresh);
for (const control of [
  el.journalKindFilter,
  el.journalFrom,
  el.journalTo,
  el.journalSort,
]) {
  control.addEventListener("change", () => refreshJournal(true));
}
el.closeJournalInspector.addEventListener("click", closeJournalInspector);
el.journalInspector.addEventListener("click", event => {
  if (event.target === el.journalInspector) closeJournalInspector();
});
bindFilterEvents(filters.mind);
bindFilterEvents(filters.admin);

document.addEventListener("keydown", event => {
  if (event.key !== "Escape") return;
  if (!el.memoryInspector.classList.contains("hidden")) {
    closeMemoryInspector();
  }
  if (!el.journalInspector.classList.contains("hidden")) {
    closeJournalInspector();
  }
});

refresh();

if (el.addHostBehavior) el.addHostBehavior.addEventListener("click", addHostBehavior);
if (el.saveHostBehaviors) el.saveHostBehaviors.addEventListener("click", saveHostBehaviors);
if (el.taskProfileBack) el.taskProfileBack.addEventListener("click", closeTaskProfile);

async function refreshDiagnostics() {
  const context = document.getElementById("currentStateDiagnostics");
  const performance = document.getElementById("performanceDiagnostics");
  if (!state.adminAuthorized || !context || !performance) return;
  try {
    const result = await api("/v1/admin/diagnostics", {}, true);
    context.textContent = JSON.stringify(result.current_state, null, 2);
    const cognitive = document.getElementById("cognitiveStateSummary");
    if (cognitive) {
      cognitive.replaceChildren();
      const fields = result.current_state?.fields || {};
      const questions = [
        ["Who Am I?", "identity"], ["What Is My Mood?", "mood"],
        ["Where Am I?", "locality"], ["Who Is Present?", "who_is_present"],
        ["Who Is Speaking?", "who_is_speaking"],
        ["What Is the Current Context?", "current_context"],
      ];
      for (const [label, key] of questions) {
        const item = fields[key] || {};
        const row = document.createElement("div");
        row.className = "summary-row";
        const title = document.createElement("span");
        title.textContent = label;
        const detail = document.createElement("strong");
        const value = item.value;
        detail.textContent = value == null ? "Unknown" :
          typeof value === "string" ? value : JSON.stringify(value);
        detail.title = [item.status, item.source, item.observed_at].filter(Boolean).join(" | ");
        row.append(title, detail);
        cognitive.append(row);
      }
    }
    const samples = result.performance?.samples || [];
    const summary = document.getElementById("apiActivitySummary");
    const list = document.getElementById("apiActivityList");
    const filter = document.getElementById("apiActivityFilter");
    const errors = samples.filter(x => Number(x.status) >= 400);
    const average = samples.length ? (samples.reduce((sum, x) => sum + Number(x.duration_ms || 0), 0) / samples.length).toFixed(1) : "0";
    if (summary) summary.textContent = samples.length + " completed | " + errors.length + " errors | " + average + " ms avg | Pending/running: not measured";
    const show = filter?.value || "all";
    if (list) {
      list.replaceChildren();
      for (const x of samples.filter(x => show === "all" || (show === "errors" ? Number(x.status) >= 400 : Number(x.status) < 400))) {
        const detail = document.createElement("details");
        const header = document.createElement("summary");
        header.textContent = formatBrowserDateTime(x.time) + " | " + (x.status >= 400 ? "Error " : "Success ") + x.status + " | " + x.duration_ms + " ms | " + (x.operation || x.method + " " + x.route);
        const extra = document.createElement("pre");
        extra.className = "mcp-tool-output";
        extra.textContent = JSON.stringify({ source: x.source || "API", destination: x.destination || x.route, trace_id: x.trace_id || "Unavailable", operation: x.operation || x.method + " " + x.route, http_status: x.status, duration_ms: x.duration_ms }, null, 2);
        detail.append(header, extra);
        list.append(detail);
      }
      if (!list.childElementCount) list.textContent = "No matching requests.";
    }
    performance.textContent = "";
  } catch (error) {
    context.textContent = "Cannot load state: " + error.message;
    performance.textContent = "Cannot load timings: " + error.message;
  }
}
document.getElementById("refreshDiagnostics")?.addEventListener("click", refreshDiagnostics);
document.getElementById("apiActivityFilter")?.addEventListener("change", refreshDiagnostics);

const adminSectionIds = {
  mcp: "mcpSection",
  tasks: "tasksSection",
  behaviors: "behaviorsSection",
  skills: "skillsSection",
  memories: "memoriesSection",
  journals: "journalsSection",
  overview: "overviewSection",
  devices: "devicesSection",
  voice: "voiceSection",
};

function decorateAdminFormTitles() {
  for (const [name, id] of Object.entries(adminSectionIds)) {
    const source = document.querySelector(`[data-admin-section="${name}"] .admin-section-icon`);
    const section = document.getElementById(id);
    if (!source || !section) continue;
    const headings = [section.querySelector(".panel-heading")];
    // Individual task forms render their own task-specific icon instead of the menu icon.
    for (const heading of headings.filter(Boolean)) {
      if (heading.querySelector(":scope > .admin-form-icon")) continue;
      const icon = source.cloneNode(true);
      icon.classList.add("admin-form-icon");
      heading.prepend(icon);
    }
  }
}
decorateAdminFormTitles();

document.getElementById("portalReturnButton")?.addEventListener("click", event => {
  if (history.length > 1) { event.preventDefault(); history.back(); }
});
document.getElementById("continuityRefreshButton")?.addEventListener("click", refresh);

async function refreshTaskProfilesFromButton() {
  const button = el.refreshTaskProfiles;
  if (!button || button.disabled) return;
  const originalLabel = button.textContent;
  button.disabled = true;
  button.textContent = "Refreshing…";
  try {
    await Promise.all([
      refreshTaskModelAssignments(),
      refreshTaskBehaviors(),
      refreshProviderEndpoints(),
    ]);
    renderTaskProfiles();
    toast("Task profiles refreshed");
  } catch (error) {
    toast(`Could not refresh task profiles: ${error.message}`, true);
  } finally {
    button.disabled = false;
    button.textContent = originalLabel;
  }
}

async function refreshEvidence() {
  if (!el.evidenceList || !el.evidenceResultCount) return;
  el.evidenceResultCount.textContent = "Loading evidence…";
  try {
    const page = await api("/v1/portal/evidence", {}, true);
    el.evidenceList.innerHTML = "";
    el.evidenceResultCount.textContent = `${page.total.toLocaleString()} preserved artifact${page.total === 1 ? "" : "s"}`;
    if (!page.items.length) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "No sensory evidence artifacts are currently stored.";
      el.evidenceList.appendChild(empty);
      return;
    }
    for (const artifact of page.items) {
      const item = document.createElement("article");
      item.className = "journal-entry";
      const meta = document.createElement("div");
      meta.className = "journal-entry-meta";
      const kind = document.createElement("span");
      kind.textContent = `${artifact.modality || "sensory"} · ${artifact.source || "unknown source"}`;
      const captured = document.createElement("span");
      captured.textContent = formatBrowserDateTime(artifact.captured_at);
      meta.append(kind, captured);
      const title = document.createElement("div");
      title.className = "journal-entry-title";
      title.textContent = `${artifact.media_type || "unknown media"} · ${Number(artifact.byte_length || 0).toLocaleString()} bytes`;
      const hash = document.createElement("div");
      hash.className = "journal-entry-preview";
      hash.textContent = `SHA-256: ${artifact.sha256}`;
      item.append(meta, title, hash);
      if (artifact.media_type?.startsWith("image/")) {
        const preview = document.createElement("img");
        preview.loading = "lazy";
        preview.alt = `Preserved ${artifact.modality || "sensory"} evidence`;
        preview.className = "evidence-preview";
        preview.src = evidenceMediaUrl(artifact);
        item.appendChild(preview);
      } else if (artifact.media_type?.startsWith("audio/")) {
        const audio = document.createElement("audio");
        audio.controls = true;
        audio.preload = "none";
        audio.src = evidenceMediaUrl(artifact);
        audio.className = "evidence-audio";
        item.appendChild(audio);
      }
      const actions = document.createElement("div");
      actions.className = "edit-actions";
      const erase = document.createElement("button");
      erase.className = "danger-button";
      erase.type = "button";
      erase.textContent = "Erase Evidence";
      erase.addEventListener("click", async () => {
        const description = `${artifact.modality || "sensory"} evidence captured ${captured.textContent}`;
        if (!window.confirm(`Permanently erase this stored media artifact?\n\n${description}\n\nThe journal audit entry will remain.`)) return;
        erase.disabled = true;
        try {
          const query = new URLSearchParams({ captured_at: artifact.captured_at });
          await api(`/v1/portal/evidence/${encodeURIComponent(artifact.sha256)}?${query}`, { method: "DELETE" }, true);
          toast("Evidence erased");
          await refreshEvidence();
        } catch (error) {
          toast(`Could not erase evidence: ${error.message}`, true);
          erase.disabled = false;
        }
      });
      actions.appendChild(erase);
      item.appendChild(actions);
      el.evidenceList.appendChild(item);
    }
  } catch (error) {
    el.evidenceResultCount.textContent = "Evidence could not be loaded";
    toast(`Could not load evidence: ${error.message}`, true);
  }
}

function evidenceMediaUrl(artifact) {
  const query = new URLSearchParams({ captured_at: artifact.captured_at });
  return `/v1/evidence/${encodeURIComponent(artifact.sha256)}?${query}`;
}

function selectedMcpServer() {
  return state.mcpServerDraft || state.mcpServers.find(server => server.id === state.activeMcpServerId) || null;
}

function syncMcpServerForm() {
  const server = state.mcpServerDraft;
  if (!server) return selectedMcpServer();
  server.name = el.mcpServerName.value.trim();
  server.url = el.mcpServerUrl.value.trim();
  server.bearer_token = el.mcpServerToken.value;
  server.enabled = el.mcpServerEnabled.checked;
  updateMcpEditorState();
  return server;
}

function updateMcpEditorState() {
  const editing = !!state.mcpServerDraft;
  const saved = state.mcpServers.some(server => server.id === state.activeMcpServerId);
  const busy = state.integrationSaving;
  [el.mcpServerName, el.mcpServerUrl, el.mcpServerToken, el.mcpServerEnabled].forEach(input => {
    input.disabled = !editing || busy;
  });
  el.mcpServerSelect.disabled = editing || busy;
  el.mcpAddServer.disabled = editing || busy;
  el.mcpEditServer.disabled = !saved || editing || busy;
  el.mcpDeleteServer.disabled = !saved || editing || busy;
  el.mcpCancelEdit.disabled = !editing || busy;
  const server = state.mcpServerDraft;
  const valid = !!(server?.name && /^https?:\/\/\S+$/i.test(server?.url || ""));
  el.mcpDiscoverTools.disabled = !editing || busy || !valid;
  el.saveMcpServers.disabled = !editing || busy || !valid || JSON.stringify(server) === state.mcpEditBaseline;
  el.mcpRunTool.disabled = editing || busy || !saved;
}

function editMcpServer() {
  const server = selectedMcpServer();
  if (!server) return;
  state.mcpServerDraft = JSON.parse(JSON.stringify(server));
  state.mcpEditBaseline = JSON.stringify(state.mcpServerDraft);
  loadMcpServerIntoForm();
  el.mcpServerName.focus();
}

function cancelMcpEdit() {
  state.mcpServerDraft = null;
  state.mcpEditBaseline = "";
  if (!selectedMcpServer()) state.activeMcpServerId = state.mcpServers[0]?.id || null;
  renderMcpServerOptions();
  loadMcpServerIntoForm();
}

function renderMcpServerOptions() {
  el.mcpServerSelect.replaceChildren();
  const blank = document.createElement("option");
  blank.value = "";
  blank.textContent = "Choose an MCP server";
  el.mcpServerSelect.append(blank);
  const servers = [...state.mcpServers];
  if (state.mcpServerDraft && !servers.some(item => item.id === state.mcpServerDraft.id)) servers.push(state.mcpServerDraft);
  for (const server of servers) {
    const option = document.createElement("option");
    option.value = server.id;
    option.textContent = server.name || server.url || (server.id === state.activeMcpServerId ? "New MCP server" : "Unnamed MCP server");
    el.mcpServerSelect.append(option);
  }
  el.mcpServerSelect.value = state.activeMcpServerId || "";
}

function loadMcpServerIntoForm() {
  const server = selectedMcpServer();
  el.mcpServerName.value = server?.name || "";
  el.mcpServerUrl.value = server?.url || "";
  el.mcpServerToken.value = server?.bearer_token || "";
  el.mcpServerEnabled.checked = server ? server.enabled !== false : true;
  el.mcpServerStatus.textContent = server
    ? `${server.tools?.length || 0} discovered tool(s). ${state.mcpServerDraft ? "Save to apply server and tool changes." : "Choose Edit to change this server or its tools."}`
    : "Choose Add to configure an MCP server.";
  renderMcpTools();
  updateMcpEditorState();
}

function renderMcpTools() {
  const server = selectedMcpServer();
  el.mcpToolList.replaceChildren();
  el.mcpToolRunnerSelect.replaceChildren();
  const runnerPlaceholder = document.createElement("option");
  runnerPlaceholder.value = "";
  runnerPlaceholder.textContent = "Choose an enabled tool";
  el.mcpToolRunnerSelect.append(runnerPlaceholder);
  if (!server?.tools?.length) {
    const empty = document.createElement("p");
    empty.className = "record-empty";
    empty.textContent = "No tools discovered for this server yet.";
    el.mcpToolList.append(empty);
    return;
  }
  for (const tool of server.tools) {
    const row = document.createElement("div");
    row.className = "memory-card host-behavior-card";
    const details = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = tool.name;
    const description = document.createElement("p");
    description.className = "muted-copy";
    description.textContent = tool.description || "No description provided by server.";
    const schema = document.createElement("code");
    schema.className = "mcp-tool-schema";
    schema.textContent = JSON.stringify(tool.inputSchema || {}, null, 2);
    details.append(title, description, schema);
    const toggleLabel = document.createElement("label");
    toggleLabel.className = "host-behavior-enabled";
    const toggle = document.createElement("input");
    toggle.type = "checkbox";
    toggle.checked = tool.enabled !== false;
    toggle.disabled = !state.mcpServerDraft || state.integrationSaving;
    toggle.addEventListener("change", () => {
      tool.enabled = toggle.checked;
      renderMcpTools();
      updateMcpEditorState();
    });
    toggleLabel.append(toggle, document.createTextNode(" Enabled"));
    row.append(details, toggleLabel);
    el.mcpToolList.append(row);
    if (tool.enabled !== false) {
      const option = document.createElement("option");
      option.value = tool.name;
      option.textContent = tool.name;
      el.mcpToolRunnerSelect.append(option);
    }
  }
}

async function refreshMcpServers() {
  if (state.mcpServerDraft) return;
  try {
    const payload = await api("/v1/admin/mcp/servers", {}, true);
    state.mcpServers = payload.items || [];
    if (!state.mcpServers.some(server => server.id === state.activeMcpServerId)) {
      state.activeMcpServerId = state.mcpServers[0]?.id || null;
    }
    renderMcpServerOptions();
    loadMcpServerIntoForm();
  } catch (error) {
    toast(`Could not load MCP servers: ${error.message}`, true);
  }
}

function addMcpServer() {
  const server = {
    id: crypto.randomUUID(),
    name: "",
    url: "",
    bearer_token: "",
    enabled: true,
    tools: [],
  };
  state.mcpServerDraft = server;
  state.mcpEditBaseline = "";
  state.activeMcpServerId = server.id;
  renderMcpServerOptions();
  loadMcpServerIntoForm();
  el.mcpServerName.focus();
}

async function discoverMcpTools() {
  if (!state.mcpServerDraft) return;
  const server = syncMcpServerForm();
  if (!server) {
    addMcpServer();
    toast("Enter a server URL, then discover its tools", true);
    return;
  }
  if (!server.name || !server.url) {
    toast("Server name and URL are required", true);
    return;
  }
  el.mcpServerStatus.textContent = "Connecting and discovering tools…";
  el.mcpDiscoverTools.disabled = true;
  try {
    const payload = await api("/v1/admin/mcp/servers/discover", {
      method: "POST",
      body: JSON.stringify(server),
    }, true);
    server.tools = payload.items || [];
    renderMcpServerOptions();
    loadMcpServerIntoForm();
    el.mcpServerStatus.textContent = `Connected. Discovered ${server.tools.length} tool(s). Save to persist this configuration.`;
    toast(`Discovered ${server.tools.length} MCP tool(s)`);
  } catch (error) {
    el.mcpServerStatus.textContent = `Connection failed: ${error.message}`;
    toast(error.message, true);
  }
  finally { updateMcpEditorState(); }
}

async function saveMcpServers() {
  syncMcpServerForm();
  if (el.saveMcpServers.disabled) return;
  const server = state.mcpServerDraft;
  state.integrationSaving = true;
  updateMcpEditorState();
  try {
    const payload = await api("/v1/admin/mcp/servers", {
      method: "PUT",
      body: JSON.stringify({ items: state.mcpServers.filter(item => item.id !== server.id).concat(server) }),
    }, true);
    state.mcpServers = payload.items || [];
    state.mcpServerDraft = null;
    state.mcpEditBaseline = "";
    renderMcpServerOptions();
    loadMcpServerIntoForm();
    toast("MCP server and tool configuration saved");
  } catch (error) {
    toast(`Could not save MCP configuration: ${error.message}`, true);
  }
  finally {
    state.integrationSaving = false;
    updateMcpEditorState();
  }
}

async function removeMcpServer() {
  if (!state.activeMcpServerId || state.mcpServerDraft || state.integrationSaving) return;
  state.integrationSaving = true;
  updateMcpEditorState();
  try {
    const payload = await api("/v1/admin/mcp/servers", {
      method: "PUT",
      body: JSON.stringify({ items: state.mcpServers.filter(server => server.id !== state.activeMcpServerId) }),
    }, true);
    state.mcpServers = payload.items || [];
    state.activeMcpServerId = state.mcpServers[0]?.id || null;
    renderMcpServerOptions();
    loadMcpServerIntoForm();
    toast("Removed MCP server");
  } catch (error) { toast(error.message, true); }
  finally {
    state.integrationSaving = false;
    updateMcpEditorState();
  }
}

async function runMcpTool() {
  const server = syncMcpServerForm();
  const toolName = el.mcpToolRunnerSelect.value;
  if (!server || !toolName) {
    toast("Choose a server and an enabled tool", true);
    return;
  }
  let argumentsValue;
  try {
    argumentsValue = JSON.parse(el.mcpToolArguments.value || "{}");
    if (!argumentsValue || Array.isArray(argumentsValue) || typeof argumentsValue !== "object") {
      throw new Error("Arguments must be a JSON object");
    }
  } catch (error) {
    toast(`Invalid tool arguments: ${error.message}`, true);
    return;
  }
  el.mcpToolOutput.textContent = "Running tool…";
  try {
    const result = await api("/v1/admin/mcp/tools/call", {
      method: "POST",
      body: JSON.stringify({ server_id: server.id, tool_name: toolName, arguments: argumentsValue }),
    }, true);
    el.mcpToolOutput.textContent = JSON.stringify(result, null, 2);
    toast(`MCP tool ${toolName} completed`);
  } catch (error) {
    el.mcpToolOutput.textContent = error.message;
    toast(error.message, true);
  }
}

async function refreshIntegrations() {
  try { await Promise.all([refreshProviderEndpoints(), refreshMcpServers()]); }
  catch (error) { toast(`Could not refresh integrations: ${error.message}`, true); }
}

function showAdminSection(sectionName) {
  for (const [name, id] of Object.entries(adminSectionIds)) {
    const panel = document.getElementById(id);
    if (panel) panel.classList.toggle("hidden", name !== sectionName);
  }
  document.querySelectorAll("[data-admin-section]").forEach(button => {
    const active = button.dataset.adminSection === sectionName;
    button.classList.toggle("active", active);
    button.setAttribute("aria-current", active ? "page" : "false");
  });
  if (sectionName !== "tasks" && state.activeTaskProfile) closeTaskProfile();
  if (sectionName === "tasks") renderTaskProfiles();
  if (sectionName === "devices") refreshDeviceInventory();
  if (sectionName === "skills") refreshSkillDrafts();
  if (sectionName === "overview") refreshDiagnostics();
  if (sectionName === "mcp" && state.adminAuthorized) refreshIntegrations();
}

document.querySelectorAll("[data-admin-section]").forEach(button => {
  button.addEventListener("click", () => showAdminSection(button.dataset.adminSection));
});
if (el.refreshTaskProfiles) el.refreshTaskProfiles.addEventListener("click", refreshTaskProfilesFromButton);
if (el.refreshMcpServers) el.refreshMcpServers.addEventListener("click", refreshIntegrations);
if (el.mcpAddServer) el.mcpAddServer.addEventListener("click", addMcpServer);
if (el.mcpServerSelect) el.mcpServerSelect.addEventListener("change", () => {
  const selectedId = el.mcpServerSelect.value;
  if (state.mcpServerDraft) return;
  state.activeMcpServerId = selectedId || null;
  loadMcpServerIntoForm();
});
if (el.mcpEditServer) el.mcpEditServer.addEventListener("click", editMcpServer);
if (el.mcpCancelEdit) el.mcpCancelEdit.addEventListener("click", cancelMcpEdit);
[el.mcpServerName, el.mcpServerUrl, el.mcpServerToken, el.mcpServerEnabled].forEach(input => {
  if (input) input.addEventListener("input", syncMcpServerForm);
});
if (el.mcpDiscoverTools) el.mcpDiscoverTools.addEventListener("click", discoverMcpTools);
if (el.mcpDeleteServer) el.mcpDeleteServer.addEventListener("click", removeMcpServer);
if (el.saveMcpServers) el.saveMcpServers.addEventListener("click", saveMcpServers);
if (el.mcpRunTool) el.mcpRunTool.addEventListener("click", runMcpTool);
if (el.refreshDevicesButton) el.refreshDevicesButton.addEventListener("click", refreshDeviceInventory);
if (el.taskProfileEndpointSelect) el.taskProfileEndpointSelect.addEventListener("change", () => {
  if (state.endpointDraft) return;
  const value = el.taskProfileEndpointSelect.value;
  if (value.startsWith("preset:")) { addTaskProfileEndpointFromPreset(value.slice(7)); return; }
  state.activeEndpointId = value || null;
  state.activeEndpointOriginalName = selectedEndpoint()?.name || "";
  loadEndpointIntoForm();
});
if (el.taskProfileAddEndpoint) el.taskProfileAddEndpoint.addEventListener("click", addTaskProfileEndpoint);
if (el.endpointEditButton) el.endpointEditButton.addEventListener("click", editEndpoint);
if (el.endpointRemoveButton) el.endpointRemoveButton.addEventListener("click", removeEndpoint);
if (el.endpointCancelButton) el.endpointCancelButton.addEventListener("click", cancelEndpointEdit);
[el.taskProfileEndpointName, el.taskProfileProviderName, el.taskProfileBaseUrl, el.taskProfileApiKey, el.endpointModelId].forEach(input => {
  if (input) input.addEventListener("input", () => {
    syncEndpointDraft();
    if (input === el.endpointModelId) el.endpointModelSelect.value = input.value;
  });
});
if (el.endpointModelSelect) el.endpointModelSelect.addEventListener("change", () => {
  el.endpointModelId.value = el.endpointModelSelect.value;
  syncEndpointDraft();
});
el.saveProviderEndpoints.addEventListener("click", saveProviderEndpoints);
el.taskProviderSelect.addEventListener("change", () => {
  const assignment = state.taskModelAssignments.find(item => item.task === state.activeTaskProfile);
  if (!assignment) return;
  const endpoint = state.providerEndpoints.find(item => item.id === el.taskProviderSelect.value);
  const sameEndpoint = endpoint && (assignment.provider === endpoint.id || assignment.provider === endpoint.name);
  assignment.provider = endpoint?.id || el.taskProviderSelect.value;
  assignment.model = endpoint?.model || (sameEndpoint ? assignment.model : "")
    || (assignment.provider === "connected-host" ? "host-selected" : "");
  if (endpoint && !assignment.model) toast("Save a model for this endpoint in Endpoints, Servers & Tools first", true);
  el.taskProviderSelect.classList.toggle("endpoint-has-key", Boolean(endpoint?.has_api_key || endpoint?.api_key));
  updateTaskSaveState();
});
if (el.taskProfileDiscover) el.taskProfileDiscover.addEventListener("click", discoverTaskProfileModels);
if (el.saveTaskProfile) el.saveTaskProfile.addEventListener("click", saveTaskProfile);
if (el.taskProfileAddFallback) el.taskProfileAddFallback.addEventListener("click", () => {
  const assignment = state.taskModelAssignments.find(item => item.task === state.activeTaskProfile);
  if (!assignment) return;
  assignment.fallbacks = assignment.fallbacks || [];
  assignment.fallbacks.push({ provider: "", model: "" });
  renderFallbackSelectors();
  updateTaskSaveState();
});
if (el.taskProfileAddBehavior) el.taskProfileAddBehavior.addEventListener("click", () => {
  el.taskProfileBehaviorSelection?.querySelector("input:not(:disabled)")?.focus();
});
if (el.taskProfileVoiceReferenceId) el.taskProfileVoiceReferenceId.addEventListener("input", () => {
  const assignment = state.taskModelAssignments.find(item => item.task === state.activeTaskProfile);
  if (assignment) assignment.voice_reference_id = el.taskProfileVoiceReferenceId.value;
  updateTaskSaveState();
});
if (el.refreshVoiceSettings) el.refreshVoiceSettings.addEventListener("click", loadVoiceSettings);
if (el.saveVoiceSettings) el.saveVoiceSettings.addEventListener("click", saveVoiceSettings);
[el.voiceRate, el.voicePitch, el.voiceVolume].forEach((slider) => {
  if (slider) slider.addEventListener("input", updateVoiceSliderReadouts);
});

const BODY_DEVICE_STORAGE_KEYS = {
  videoinput: "aicognitive_mind.device.videoInput",
  audioinput: "aicognitive_mind.device.audioInput",
  audiooutput: "aicognitive_mind.device.audioOutput",
};

function selectedDeviceId(kind) {
  try { return localStorage.getItem(BODY_DEVICE_STORAGE_KEYS[kind]) || ""; }
  catch (_) { return ""; }
}

function saveSelectedDevice(kind, deviceId) {
  try {
    if (deviceId) localStorage.setItem(BODY_DEVICE_STORAGE_KEYS[kind], deviceId);
    else localStorage.removeItem(BODY_DEVICE_STORAGE_KEYS[kind]);
    renderDeviceSelectionSummary();
    toast(deviceId ? "Body device selection saved" : "Body will use the browser default device");
  } catch (error) {
    toast("Could not save device selection in this browser: " + error.message, true);
  }
}

function renderDeviceSelectionSummary() {
  if (!el.deviceSelectionSummary) return;
  const labels = [];
  for (const [kind, label] of [["videoinput", "Camera"], ["audioinput", "Microphone"], ["audiooutput", "Speaker"]]) {
    const id = selectedDeviceId(kind);
    const device = (state.deviceInventory || []).find(item => item.kind === kind && item.deviceId === id);
    labels.push(label + ": " + (device?.label || (id ? "Saved device (" + id.slice(0, 8) + "…)" : "Browser default")));
  }
  el.deviceSelectionSummary.textContent = labels.join(" · ");
}

async function refreshDeviceInventory() {
  el.devicePermissionStatus.textContent = "Querying browser device inventory…";
  el.deviceInventoryList.replaceChildren();
  if (!navigator.mediaDevices?.enumerateDevices) {
    el.devicePermissionStatus.textContent = "Device discovery is unavailable in this browser or context. Use a secure HTTPS page and a browser that supports MediaDevices.";
    return;
  }
  try {
    const [devices, cameraPermission, microphonePermission] = await Promise.all([
      navigator.mediaDevices.enumerateDevices(),
      navigator.permissions?.query ? navigator.permissions.query({ name: "camera" }).catch(() => null) : Promise.resolve(null),
      navigator.permissions?.query ? navigator.permissions.query({ name: "microphone" }).catch(() => null) : Promise.resolve(null),
    ]);
    state.deviceInventory = devices.filter(device => ["videoinput", "audioinput", "audiooutput"].includes(device.kind));
    const permissions = [
      `Camera permission: ${cameraPermission?.state || "not reported by browser"}`,
      `Microphone permission: ${microphonePermission?.state || "not reported by browser"}`,
    ];
    el.devicePermissionStatus.textContent = `${state.deviceInventory.length} device(s) discovered. ${permissions.join(" · ")}. Labels may be hidden until permission is granted.`;
    for (const [kind, heading] of [["videoinput", "Body camera"], ["audioinput", "Body microphone"], ["audiooutput", "Body speaker / audio output"]]) {
      const matches = state.deviceInventory.filter(device => device.kind === kind);
      const section = document.createElement("section");
      section.className = "device-inventory-group";
      const title = document.createElement("h4");
      title.textContent = heading;
      section.append(title);
      const pickerLabel = document.createElement("label");
      pickerLabel.className = "host-behavior-field";
      pickerLabel.append(document.createTextNode("Use for Body operation"));
      const picker = document.createElement("select");
      picker.setAttribute("aria-label", `Select ${heading.toLowerCase()}`);
      const defaultOption = document.createElement("option");
      defaultOption.value = "";
      defaultOption.textContent = "Browser default";
      picker.append(defaultOption);
      matches.forEach((device, index) => {
        if (!device.deviceId) return;
        const option = document.createElement("option");
        option.value = device.deviceId;
        const singular = kind === "videoinput" ? "Camera" : kind === "audioinput" ? "Microphone" : "Speaker";
        option.textContent = device.label.trim() || `${singular} ${index + 1} (label hidden)`;
        picker.append(option);
      });
      picker.value = selectedDeviceId(kind);
      if (![...picker.options].some(option => option.value === picker.value)) picker.value = "";
      picker.addEventListener("change", () => saveSelectedDevice(kind, picker.value));
      pickerLabel.append(picker);
      section.append(pickerLabel);
      if (!matches.length) {
        const empty = document.createElement("p");
        empty.className = "record-empty";
        empty.textContent = "No devices of this type were exposed to this browser.";
        section.append(empty);
      }
      if (kind === "audiooutput" && typeof HTMLMediaElement !== "undefined" && !("setSinkId" in HTMLMediaElement.prototype)) {
        const note = document.createElement("p");
        note.className = "record-empty";
        note.textContent = "This browser cannot route media-element playback to a selected speaker; its default output will be used.";
        section.append(note);
      }
      el.deviceInventoryList.append(section);
    }
    renderDeviceSelectionSummary();
  } catch (error) {
    el.devicePermissionStatus.textContent = `Device query failed: ${error.message}. Check browser permissions and reload the page.`;
    toast(`Could not query devices: ${error.message}`, true);
  }
}

if (navigator.mediaDevices?.addEventListener) {
  navigator.mediaDevices.addEventListener("devicechange", () => refreshDeviceInventory());
}

// Render the built-in task list immediately so the workspace remains navigable
// even if an admin configuration request fails or is slow.
renderTaskProfiles();
refresh();

let skillDraftSha = null;
async function refreshSkillDrafts() {
  const list = document.getElementById("skillsList");
  try {
    const data = await api("/v1/admin/skills", {}, true);
    list.replaceChildren(new Option("New skill", ""));
    for (const item of data.items) list.add(new Option(item.slug, item.slug));
    document.getElementById("skillsStatus").textContent = "Drafts loaded from GitHub.";
  } catch (error) { document.getElementById("skillsStatus").textContent = error.message; }
}
document.getElementById("skillsRefresh")?.addEventListener("click", refreshSkillDrafts);
document.getElementById("skillsList")?.addEventListener("change", async event => {
  const slug = event.target.value;
  skillDraftSha = null;
  document.getElementById("skillsSlug").value = slug;
  document.getElementById("skillsContent").value = "";
  if (!slug) return;
  try {
    const item = await api("/v1/admin/skills/" + encodeURIComponent(slug), {}, true);
    skillDraftSha = item.sha;
    document.getElementById("skillsContent").value = item.content;
  } catch (error) { document.getElementById("skillsStatus").textContent = error.message; }
});
function skillPayload() {
  return { slug: document.getElementById("skillsSlug").value.trim(), content: document.getElementById("skillsContent").value, sha: skillDraftSha };
}
document.getElementById("skillsValidate")?.addEventListener("click", async () => {
  const status = document.getElementById("skillsStatus");
  try {
    const result = await api("/v1/admin/skills/validate", {method:"POST",body:JSON.stringify(skillPayload())}, true);
    status.textContent = result.valid ? "SKILL.md validation passed." : result.errors.join("; ");
  } catch (error) { status.textContent = error.message; }
});
document.getElementById("skillsSave")?.addEventListener("click", async () => {
  const status = document.getElementById("skillsStatus");
  try {
    const payload = skillPayload();
    const result = await api("/v1/admin/skills/" + encodeURIComponent(payload.slug), {method:"PUT",body:JSON.stringify(payload)}, true);
    skillDraftSha = result.sha;
    status.textContent = "Saved draft to GitHub commit " + result.commit.slice(0,8) + ". Not published to ChatGPT.";
    await refreshSkillDrafts();
    document.getElementById("skillsList").value = payload.slug;
  } catch (error) { status.textContent = error.message; }
});
document.getElementById("skillsPrepare")?.addEventListener("click", async () => {
  const status = document.getElementById("skillsStatus");
  try {
    const payload = skillPayload();
    const check = await api("/v1/admin/skills/validate", {method:"POST",body:JSON.stringify(payload)}, true);
    if (!check.valid) { status.textContent = check.errors.join("; "); return; }
    const markdown = payload.content;
    const blob = new Blob([markdown], {type:"text/markdown"});
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = payload.slug + "-SKILL.md";
    anchor.click(); URL.revokeObjectURL(url);
    status.textContent = "Release file prepared. Install or update it in ChatGPT manually.";
  } catch (error) { status.textContent = error.message; }
});

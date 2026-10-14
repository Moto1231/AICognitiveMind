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
  deviceInventory: [],
  voiceSettingsRevision: 0,
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
  taskProfileEndpointPreset: document.getElementById("taskProfileEndpointPreset"),
  taskProfileAddPreset: document.getElementById("taskProfileAddPreset"),
  taskProfileAddEndpoint: document.getElementById("taskProfileAddEndpoint"),
  taskProfileEndpointName: document.getElementById("taskProfileEndpointName"),
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
    title.addEventListener("input", () => { behavior.name = title.value; });
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
    instruction.addEventListener("input", () => { behavior.instruction = instruction.value; });
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
    priority.addEventListener("change", () => { behavior.priority = Number(priority.value); });
    priorityField.append(priority);
    fields.append(nameField, priorityField, instructionField);
    const enabled = document.createElement("input");
    enabled.type = "checkbox";
    enabled.checked = behavior.enabled;
    enabled.disabled = behavior.protected;
    enabled.setAttribute("aria-label", "Enable behavior");
    enabled.addEventListener("change", () => { behavior.enabled = enabled.checked; });
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
}

async function refreshHostBehaviors() {
  const payload = await api("/v1/admin/host-behaviors", {}, true);
  state.hostBehaviors = payload.items;
  renderHostBehaviors();
}

function addHostBehavior() {
  const id = "behavior-" + Date.now();
  state.hostBehaviors.push({
    id,
    name: "New Behavior",
    instruction: "Describe the host behavior.",
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
    renderHostBehaviors();
    toast("Host behaviors saved");
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
    const title = document.createElement("strong");
    title.textContent = taskModelLabels[task] || displayLabel(task);
    const detail = document.createElement("span");
    detail.textContent = endpoint
      ? [endpoint.name || "Unnamed endpoint", assignment.model || "No model selected"].join(" · ")
      : (assignment.provider || assignment.model)
        ? [assignment.provider || "No endpoint", assignment.model || "No model selected"].join(" · ")
        : "Endpoint and model not configured";
    const behaviorStatus = document.createElement("small");
    behaviorStatus.textContent = behavior.enabled === false
      ? "Behavior layer disabled"
      : behavior.instructions
        ? "Behavior configured"
        : "Behavior instructions not configured";
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
  for (const endpoint of state.providerEndpoints) {
    const option = document.createElement("option");
    option.value = endpoint.id;
    option.textContent = endpoint.name || endpoint.base_url || "Unnamed endpoint";
    select.append(option);
  }
  select.value = state.activeEndpointId || "";
}

function modelCapabilityLabel(model, capabilityMap) {
  const capabilities = capabilityMap?.[model];
  return capabilities?.length ? `${model} · ${capabilities.join(" · ")}` : `${model} · Capabilities unknown`;
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
    row.className = "task-fallback-row task-model-fields";
    const providerLabel = document.createElement("label");
    providerLabel.className = "host-behavior-field";
    providerLabel.textContent = "Fallback " + (index + 1) + " provider";
    const provider = document.createElement("select");
    provider.setAttribute("aria-label", "Fallback " + (index + 1) + " provider");
    fillSelect(provider, state.providerEndpoints.map(item => item.name), fallback.provider, "Choose endpoint");
    provider.addEventListener("change", () => {
      fallback.provider = provider.value;
      fallback.model = "";
      renderFallbackSelectors();
    });
    providerLabel.append(provider);
    const modelLabel = document.createElement("label");
    modelLabel.className = "host-behavior-field";
    modelLabel.textContent = "Fallback " + (index + 1) + " model";
    const model = document.createElement("input");
    model.type = "text";
    model.maxLength = 160;
    model.placeholder = "Model ID";
    model.value = fallback.model || "";
    model.setAttribute("aria-label", "Fallback " + (index + 1) + " model");
    model.addEventListener("input", () => { fallback.model = model.value.trim(); });
    modelLabel.append(model);
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "secondary-button";
    remove.textContent = "Remove";
    remove.setAttribute("aria-label", "Remove fallback " + (index + 1));
    remove.addEventListener("click", () => {
      assignment.fallbacks.splice(index, 1);
      renderFallbackSelectors();
    });
    row.append(providerLabel, modelLabel, remove);
    el.taskProfileFallbackList.append(row);
  });
}

function loadEndpointIntoForm() {
  const { endpoint } = activeProfileRecords();
  el.taskProfileEndpointName.value = endpoint?.name || "";
  el.taskProfileBaseUrl.value = endpoint?.base_url || "";
  el.taskProfileApiKey.value = endpoint?.api_key || "";
  const selectedModel = el.taskProfileModel.value;
  fillSelect(el.taskProfileModel, endpoint?.models || [], selectedModel, "Discover models or choose a model", endpoint?.model_capabilities || {});
  renderFallbackSelectors();
}

function openTaskProfile(task) {
  state.activeTaskProfile = task;
  let assignment = task === "reasoning" ? null : state.taskModelAssignments.find(item => item.task === task);
  if (!assignment && task !== "reasoning") {
    assignment = { task, provider: "", model: "", fallbacks: [], voice_reference_id: "", notes: "" };
    state.taskModelAssignments.push(assignment);
  }
  let behavior = state.taskBehaviors.find(item => item.task === task);
  if (!behavior) {
    behavior = { task, instructions: "", enabled: true, revision: 1 };
    state.taskBehaviors.push(behavior);
  }
  const endpoint = assignment && state.providerEndpoints.find(item =>
    item.name === assignment.provider || item.id === assignment.provider
  );
  state.activeEndpointId = endpoint?.id || state.providerEndpoints[0]?.id || null;
  state.activeEndpointOriginalName = state.providerEndpoints.find(item => item.id === state.activeEndpointId)?.name || "";
  if (state.activeEndpointId && assignment && !assignment.provider) {
    assignment.provider = state.providerEndpoints.find(item => item.id === state.activeEndpointId)?.name || "";
  }

  el.taskProfileEndpointSection.classList.toggle("hidden", task === "reasoning");
  el.taskProfileAssignmentSection.classList.toggle("hidden", task === "reasoning");
  const isAudioVoice = task === "audio_voice";
  el.taskProfileStandardModelField.classList.toggle("hidden", isAudioVoice);
  el.taskProfileVoiceModelField.classList.toggle("hidden", !isAudioVoice);
  el.taskProfileVoiceReferenceField.classList.toggle("hidden", !isAudioVoice);
  el.taskProfileTitle.textContent = taskModelLabels[task] || displayLabel(task);
  el.taskProfileRevision.textContent = "Revision: " + (behavior.revision || 1);
  // Populate the editor from the selected task's own behavior profile.
  // Without this, switching tasks leaves the previous task's instructions in
  // the form and saving can copy those instructions into another task.
  el.taskProfileFoundation.value = state.taskFoundations[task] || "";
  el.taskProfileBehaviorName.value = behavior.name || (taskModelLabels[task] || displayLabel(task));
  el.taskProfileInstructions.value = behavior.instructions || "";
  el.taskProfileEnabled.checked = behavior.enabled !== false;
  renderTaskProfileEndpointOptions();
  fillSelect(
    el.taskProfileModel,
    selectedEndpoint()?.models || [],
    isAudioVoice ? "" : (assignment?.model || ""),
    "Discover models or choose a model",
  );
  el.taskProfileVoiceModel.value = assignment?.model || "s2.1-pro-free";
  el.taskProfileVoiceReferenceId.value = assignment?.voice_reference_id || "";
  renderFallbackSelectors();
  loadEndpointIntoForm();
  renderFallbackSelectors();
  el.taskProfileOverview.classList.add("hidden");
  el.taskProfileList.classList.add("hidden");
  el.taskProfileEditor.classList.remove("hidden");
}

function closeTaskProfile() {
  state.activeTaskProfile = null;
  el.taskProfileEditor.classList.add("hidden");
  el.taskProfileOverview.classList.remove("hidden");
  el.taskProfileList.classList.remove("hidden");
  renderTaskProfiles();
}

function selectedEndpoint() {
  return state.providerEndpoints.find(item => item.id === state.activeEndpointId) || null;
}

async function refreshProviderEndpoints() {
  const payload = await api("/v1/admin/provider-endpoints", {}, true);
  state.providerEndpoints = payload.items || [];
  if (state.activeTaskProfile) {
    renderTaskProfileEndpointOptions();
    loadEndpointIntoForm();
  }
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

async function saveTaskProfile() {
  const task = state.activeTaskProfile;
  if (!task) return;
  try {
    const endpoint = task === "reasoning" ? null : selectedEndpoint();
    if (endpoint) {
      const previousName = state.activeEndpointOriginalName || endpoint.name;
      const nextName = el.taskProfileEndpointName.value.trim();
      endpoint.name = nextName;
      endpoint.base_url = el.taskProfileBaseUrl.value.trim();
      endpoint.api_key = el.taskProfileApiKey.value;
      if (!endpoint.name || !endpoint.base_url) {
        toast("Endpoint name and base URL are required", true);
        return;
      }
      if (previousName && previousName !== nextName) {
        for (const item of state.taskModelAssignments) {
          if (item.provider === previousName) item.provider = nextName;
          for (const fallback of (item.fallbacks || [])) {
            if (fallback.provider === previousName) fallback.provider = nextName;
          }
        }
      }
      state.activeEndpointOriginalName = nextName;
    }

    const assignment = state.taskModelAssignments.find(item => item.task === task);
    if (task !== "reasoning" && assignment) {
      assignment.provider = endpoint?.name || "";
      assignment.model = task === "audio_voice" ? el.taskProfileVoiceModel.value.trim() : el.taskProfileModel.value.trim();
      assignment.fallbacks = (assignment.fallbacks || []).filter(item => item.provider && item.model);
      assignment.voice_reference_id = task === "audio_voice" ? el.taskProfileVoiceReferenceId.value.trim() : (assignment.voice_reference_id || "");
    }

    const behavior = state.taskBehaviors.find(item => item.task === task);
    behavior.name = el.taskProfileBehaviorName.value.trim() || (taskModelLabels[task] || displayLabel(task));
    behavior.instructions = el.taskProfileInstructions.value;
    behavior.enabled = el.taskProfileEnabled.checked;

    if (task !== "reasoning" && state.providerEndpoints.length) {
      const endpointPayload = await api("/v1/admin/provider-endpoints", {
        method: "PUT",
        body: JSON.stringify({ items: state.providerEndpoints }),
      }, true);
      state.providerEndpoints = endpointPayload.items || [];
    }
    if (task !== "reasoning") {
      const assignmentPayload = await api("/v1/admin/task-model-assignments", {
        method: "PUT",
        body: JSON.stringify({ items: state.taskModelAssignments }),
      }, true);
      state.taskModelAssignments = assignmentPayload.items || [];
    }
    const behaviorPayload = await api("/v1/admin/task-behaviors", {
      method: "PUT",
      body: JSON.stringify({ items: state.taskBehaviors }),
    }, true);
    state.taskBehaviors = behaviorPayload.items || [];
    state.taskFoundations = behaviorPayload.foundations || state.taskFoundations;
    toast(`Saved ${taskModelLabels[task] || displayLabel(task)} task profile`);
    renderTaskProfiles();
    openTaskProfile(task);
  } catch (error) {
    toast(error.message, true);
  }
}

async function discoverTaskProfileModels() {
  const endpoint = selectedEndpoint();
  if (!endpoint) {
    toast("Choose or add an endpoint first", true);
    return;
  }
  endpoint.name = el.taskProfileEndpointName.value.trim();
  endpoint.base_url = el.taskProfileBaseUrl.value.trim();
  endpoint.api_key = el.taskProfileApiKey.value;
  try {
    const payload = await api("/v1/admin/provider-endpoints/discover", {
      method: "POST",
      body: JSON.stringify(endpoint),
    }, true);
    endpoint.models = payload.models || [];
    endpoint.model_capabilities = payload.model_capabilities || {};
    renderTaskProfileEndpointOptions();
    loadEndpointIntoForm();
    toast(`Discovered ${endpoint.models.length} model(s)`);
  } catch (error) {
    toast(error.message, true);
  }
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
function addTaskProfileEndpointFromPreset() {
  const presetId = el.taskProfileEndpointPreset?.value;
  const preset = COMMON_ENDPOINT_PRESETS.find(item => item.id === presetId);
  if (!preset) {
    toast("Choose an endpoint preset first", true);
    return;
  }
  const endpoint = {
    id: crypto.randomUUID(),
    name: preset.name,
    base_url: preset.base_url,
    api_key: "",
    models: [],
    model_capabilities: {},
  };
  state.providerEndpoints.push(endpoint);
  state.activeEndpointId = endpoint.id;
  state.activeEndpointOriginalName = "";
  renderTaskProfileEndpointOptions();
  loadEndpointIntoForm();
  if (el.taskProfileEndpointPreset) el.taskProfileEndpointPreset.value = "";
  el.taskProfileApiKey.focus();
  toast(`Added ${preset.name}. Add credentials if required, then discover models.`);
}

function addTaskProfileEndpoint() {
  const endpoint = {
    id: crypto.randomUUID(),
    name: "",
    base_url: "",
    api_key: "",
    models: [],
    model_capabilities: {},
  };
  state.providerEndpoints.push(endpoint);
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

  el.connectionLabel.textContent = `${integration.protocol} · Mind Online`;
  el.mindName.textContent = mind.identity.self_name;
  el.continuityLabel.textContent = "Persistent";
  el.selfName.textContent = mind.identity.self_name;
  el.developmentState.textContent = displayLabel(mind.developmental_state);
  el.createdAt.textContent = new Date(mind.created_at).toLocaleString();
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
  el.adminCreatedAt.textContent = new Date(mind.created_at).toLocaleString();
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
  el.inspectorFormedAt.textContent = new Date(memory.formed_at).toLocaleString();
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
    formed.textContent = new Date(memory.formed_at).toLocaleString();
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
    occurred.textContent = new Date(entry.occurred_at).toLocaleString();
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
    el.journalInspectorOccurredAt.textContent = new Date(entry.occurred_at).toLocaleString();
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
    captured.textContent = new Date(artifact.captured_at).toLocaleString();
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
      ...(admin ? [refreshBodyFallbackSettings()] : []),
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
el.refreshButton.addEventListener("click", refresh);
el.adminMemoryRefreshButton.addEventListener("click", () => refreshMemory(filters.admin, true));
el.adminRefreshButton.addEventListener("click", () => Promise.all([
  refreshStatus(),
  refreshMemory(filters.admin, true),
  refreshJournal(true),
  refreshBodyFallbackSettings(),
]));
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

const adminSectionIds = {
  mcp: "mcpSection",
  tasks: "tasksSection",
  behaviors: "behaviorsSection",
  memories: "memoriesSection",
  journals: "journalsSection",
  overview: "overviewSection",
  devices: "devicesSection",
  voice: "voiceSection",
};

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
      captured.textContent = new Date(artifact.captured_at).toLocaleString();
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
  return state.mcpServers.find(server => server.id === state.activeMcpServerId) || null;
}

function syncMcpServerForm() {
  const server = selectedMcpServer();
  if (!server) return null;
  server.name = el.mcpServerName.value.trim();
  server.url = el.mcpServerUrl.value.trim();
  server.bearer_token = el.mcpServerToken.value;
  server.enabled = el.mcpServerEnabled.checked;
  return server;
}

function renderMcpServerOptions() {
  el.mcpServerSelect.replaceChildren();
  const blank = document.createElement("option");
  blank.value = "";
  blank.textContent = "Add a new server";
  el.mcpServerSelect.append(blank);
  for (const server of state.mcpServers) {
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
    ? `${server.tools?.length || 0} discovered tool(s). Save after changing server or tool settings.`
    : "Add a server URL, then discover its tools.";
  renderMcpTools();
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
    toggle.addEventListener("change", () => {
      tool.enabled = toggle.checked;
      renderMcpTools();
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
  syncMcpServerForm();
  const server = {
    id: crypto.randomUUID(),
    name: "",
    url: "",
    bearer_token: "",
    enabled: true,
    tools: [],
  };
  state.mcpServers.push(server);
  state.activeMcpServerId = server.id;
  renderMcpServerOptions();
  loadMcpServerIntoForm();
  el.mcpServerName.focus();
}

async function discoverMcpTools() {
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
}

async function saveMcpServers() {
  syncMcpServerForm();
  try {
    const payload = await api("/v1/admin/mcp/servers", {
      method: "PUT",
      body: JSON.stringify({ items: state.mcpServers }),
    }, true);
    state.mcpServers = payload.items || [];
    renderMcpServerOptions();
    loadMcpServerIntoForm();
    toast("MCP server and tool configuration saved");
  } catch (error) {
    toast(`Could not save MCP configuration: ${error.message}`, true);
  }
}

async function removeMcpServer() {
  if (!state.activeMcpServerId) return;
  state.mcpServers = state.mcpServers.filter(server => server.id !== state.activeMcpServerId);
  state.activeMcpServerId = state.mcpServers[0]?.id || null;
  renderMcpServerOptions();
  loadMcpServerIntoForm();
  await saveMcpServers();
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
  if (sectionName === "mcp" && state.adminAuthorized) refreshMcpServers();
}

document.querySelectorAll("[data-admin-section]").forEach(button => {
  button.addEventListener("click", () => showAdminSection(button.dataset.adminSection));
});
if (el.refreshTaskProfiles) el.refreshTaskProfiles.addEventListener("click", refreshTaskProfilesFromButton);
if (el.refreshMcpServers) el.refreshMcpServers.addEventListener("click", refreshMcpServers);
if (el.mcpAddServer) el.mcpAddServer.addEventListener("click", addMcpServer);
if (el.mcpServerSelect) el.mcpServerSelect.addEventListener("change", () => {
  const selectedId = el.mcpServerSelect.value;
  if (!selectedId) {
    addMcpServer();
    return;
  }
  syncMcpServerForm();
  state.activeMcpServerId = selectedId;
  loadMcpServerIntoForm();
});
if (el.mcpDiscoverTools) el.mcpDiscoverTools.addEventListener("click", discoverMcpTools);
if (el.mcpDeleteServer) el.mcpDeleteServer.addEventListener("click", removeMcpServer);
if (el.saveMcpServers) el.saveMcpServers.addEventListener("click", saveMcpServers);
if (el.mcpRunTool) el.mcpRunTool.addEventListener("click", runMcpTool);
if (el.refreshDevicesButton) el.refreshDevicesButton.addEventListener("click", refreshDeviceInventory);
if (el.taskProfileEndpointSelect) el.taskProfileEndpointSelect.addEventListener("change", () => {
  state.activeEndpointId = el.taskProfileEndpointSelect.value || null;
  state.activeEndpointOriginalName = selectedEndpoint()?.name || "";
  el.taskProfileModel.value = "";
  loadEndpointIntoForm();
});
if (el.taskProfileAddEndpoint) el.taskProfileAddEndpoint.addEventListener("click", addTaskProfileEndpoint);
if (el.taskProfileAddPreset) el.taskProfileAddPreset.addEventListener("click", addTaskProfileEndpointFromPreset);
if (el.taskProfileDiscover) el.taskProfileDiscover.addEventListener("click", discoverTaskProfileModels);
if (el.saveTaskProfile) el.saveTaskProfile.addEventListener("click", saveTaskProfile);
if (el.taskProfileAddFallback) el.taskProfileAddFallback.addEventListener("click", () => {
  const assignment = state.taskModelAssignments.find(item => item.task === state.activeTaskProfile);
  if (!assignment) return;
  assignment.fallbacks = assignment.fallbacks || [];
  assignment.fallbacks.push({ provider: "", model: "" });
  renderFallbackSelectors();
});
if (el.taskProfileAddBehavior) el.taskProfileAddBehavior.addEventListener("click", () => {
  el.taskProfileEnabled.checked = true;
  el.taskProfileBehaviorName.focus();
  toast("Behavior editor ready. Save the task profile to keep your changes.");
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

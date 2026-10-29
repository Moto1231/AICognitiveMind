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
  hostBehaviorDraft: null,
  hostBehaviorRevision: null,
  hostBehaviorSaving: false,
  activeHostBehaviorId: null,
  hostBehaviorQuery: "",
  cognitiveConfiguration: null,
  cognitiveDraft: null,
  cognitiveSaving: false,
  breakerSettings: null,
  breakerDraft: null,
  breakerSaving: false,
  breakerLoadRevision: 0,
  foundationIdentity: null,
  taskModelAssignments: [],
  taskBehaviors: [],
  taskSkills: [],
  providerEndpoints: [],
  providerEndpointRevision: null,
  mcpServers: [],
  activeMcpServerId: null,
  activeTaskProfile: null,
  activeTaskFallback: 0,
  taskFallbackTask: null,
  activeEndpointId: null,
  activeEndpointOriginalName: "",
  endpointDraft: null,
  endpointEditBaseline: "",
  endpointDiscovering: false,
  endpointProbing: false,
  endpointProbe: null,
  providerSetupDraft: null,
  mcpServerDraft: null,
  mcpEditBaseline: "",
  mcpToolsServerId: "",
  mcpToolsQuery: "",
  activeMcpToolKey: "",
  mcpToolsDraft: null,
  mcpToolsError: "",
  mcpToolsSaving: false,
  mcpToolsDiscovering: false,
  mcpToolsDiscoveryRevision: 0,
  mcpToolsRefreshRevision: 0,
  mcpToolRunRevision: 0,
  mcpToolRunning: false,
  integrationSaving: false,
  deviceInventory: [],
  voiceSettingsRevision: 0,
  voiceSettingsLoaded: false,
  voiceSettingsBusy: false,
  voiceSettingsBaseline: null,
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
  taskProviderRotation: document.getElementById("taskProviderRotation"),
  saveProviderEndpoints: document.getElementById("saveProviderEndpoints"),
  taskProfileOverview: document.getElementById("taskProfileOverview"),
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
  mcpToolsServerFilter: document.getElementById("mcpToolsServerFilter"),
  mcpToolsSearch: document.getElementById("mcpToolsSearch"),
  mcpToolList: document.getElementById("mcpToolList"),
  mcpToolCount: document.getElementById("mcpToolCount"),
  mcpToolDetail: document.getElementById("mcpToolDetail"),
  mcpToolName: document.getElementById("mcpToolName"),
  mcpToolServerName: document.getElementById("mcpToolServerName"),
  mcpToolDescription: document.getElementById("mcpToolDescription"),
  mcpToolSchema: document.getElementById("mcpToolSchema"),
  mcpToolEnabled: document.getElementById("mcpToolEnabled"),
  mcpToolStatus: document.getElementById("mcpToolStatus"),
  mcpEditTools: document.getElementById("mcpEditTools"),
  saveMcpTools: document.getElementById("saveMcpTools"),
  mcpCancelTools: document.getElementById("mcpCancelTools"),
  mcpToolArguments: document.getElementById("mcpToolArguments"),
  mcpRunTool: document.getElementById("mcpRunTool"),
  mcpToolOutput: document.getElementById("mcpToolOutput"),
  saveMcpServers: document.getElementById("saveMcpServers"),
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
  hostBehaviorSearch: document.getElementById("hostBehaviorSearch"),
  hostBehaviorSelect: document.getElementById("hostBehaviorSelect"),
  hostBehaviorSummary: document.getElementById("hostBehaviorSummary"),
  addHostBehavior: document.getElementById("addHostBehavior"),
  saveHostBehaviors: document.getElementById("saveHostBehaviors"),
  editHostBehaviors: document.getElementById("editHostBehaviors"),
  cancelHostBehaviors: document.getElementById("cancelHostBehaviors"),
  taskProfileList: document.getElementById("taskProfileList"),
  taskProfileEditor: document.getElementById("taskProfileEditor"),
  taskProfileTitle: document.getElementById("taskProfileTitle"),
  taskProfileBack: document.getElementById("taskProfileBack"),
  taskProfileEndpointSection: document.getElementById("taskProfileEndpointSection"),
  taskProfileEndpointSelect: document.getElementById("taskProfileEndpointSelect"),
  taskProfileAddEndpoint: document.getElementById("taskProfileAddEndpoint"),
  prepareProviderConnections: document.getElementById("prepareProviderConnections"),
  providerSetupPanel: document.getElementById("providerSetupPanel"),
  providerSetupList: document.getElementById("providerSetupList"),
  saveProviderConnections: document.getElementById("saveProviderConnections"),
  cancelProviderConnections: document.getElementById("cancelProviderConnections"),
  endpointTemplateField: document.getElementById("endpointTemplateField"),
  endpointTemplateSelect: document.getElementById("endpointTemplateSelect"),
  endpointApiKeyVisibility: document.getElementById("endpointApiKeyVisibility"),
  endpointApiKeyHelp: document.getElementById("endpointApiKeyHelp"),
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
  endpointProbeButton: document.getElementById("endpointProbeButton"),
  taskProfileAssignmentSection: document.getElementById("taskProfileAssignmentSection"),
  taskProfileModel: document.getElementById("taskProfileModel"),
  taskProfileModels: document.getElementById("taskProfileModels"),
  taskProfileStandardModelField: document.getElementById("taskProfileStandardModelField"),
  taskProfileVoiceModelField: document.getElementById("taskProfileVoiceModelField"),
  taskProfileVoiceModel: document.getElementById("taskProfileVoiceModel"),
  taskProfileVoiceReferenceField: document.getElementById("taskProfileVoiceReferenceField"),
  taskProfileVoiceReferenceId: document.getElementById("taskProfileVoiceReferenceId"),
  taskProfileFallbackList: document.getElementById("taskProfileFallbackList"),
  taskProfileFallbackEditor: document.getElementById("taskProfileFallbackEditor"),
  taskProfileFallbackEndpoint: document.getElementById("taskProfileFallbackEndpoint"),
  taskProfileFallbackModel: document.getElementById("taskProfileFallbackModel"),
  taskProfileFallbackUp: document.getElementById("taskProfileFallbackUp"),
  taskProfileFallbackDown: document.getElementById("taskProfileFallbackDown"),
  taskProfileFallbackRemove: document.getElementById("taskProfileFallbackRemove"),
  taskProfileAddFallback: document.getElementById("taskProfileAddFallback"),
  taskProfileSkillSelection: document.getElementById("taskProfileSkillSelection"),
  taskProfileSkillSelect: document.getElementById("taskProfileSkillSelect"),
  taskProfileAddSkill: document.getElementById("taskProfileAddSkill"),
  taskProfileAddBehavior: document.getElementById("taskProfileAddBehavior"),
  voiceRate: document.getElementById("voiceRate"),
  voiceRateValue: document.getElementById("voiceRateValue"),
  voicePitch: document.getElementById("voicePitch"),
  voicePitchValue: document.getElementById("voicePitchValue"),
  voiceVolume: document.getElementById("voiceVolume"),
  voiceVolumeValue: document.getElementById("voiceVolumeValue"),
  voiceName: document.getElementById("voiceName"),
  voiceSettingsRevision: document.getElementById("voiceSettingsRevision"),
  voiceSettingsStatus: document.getElementById("voiceSettingsStatus"),
  saveVoiceSettings: document.getElementById("saveVoiceSettings"),
  cancelVoiceSettings: document.getElementById("cancelVoiceSettings"),
  taskProfileBehaviorSelection: document.getElementById("taskProfileBehaviorSelection"),
  taskProfileBehaviorName: document.getElementById("taskProfileBehaviorName"),
  taskProfileInstructions: document.getElementById("taskProfileInstructions"),
  taskProfileEnabled: document.getElementById("taskProfileEnabled"),
  taskProfileRevision: document.getElementById("taskProfileRevision"),
  saveTaskProfile: document.getElementById("saveTaskProfile"),
  saveTaskEndpoints: document.getElementById("saveTaskEndpoints"),
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
  if (mode === "mind" && typeof discardDeviceSelectionChanges === "function") discardDeviceSelectionChanges();
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
  const items = state.hostBehaviorDraft || state.hostBehaviors;
  const query = (state.hostBehaviorQuery || "").trim().toLocaleLowerCase();
  const matches = items.filter(behavior => !query || `${behavior.name}\n${behavior.instruction}`.toLocaleLowerCase().includes(query));
  if (!matches.some(behavior => behavior.id === state.activeHostBehaviorId)) {
    state.activeHostBehaviorId = matches[0]?.id || null;
  }
  state.hostBehaviorMatchCount = matches.length;
  if (el.hostBehaviorSearch) {
    el.hostBehaviorSearch.value = state.hostBehaviorQuery || "";
    el.hostBehaviorSearch.disabled = state.hostBehaviorSaving;
  }
  if (el.hostBehaviorSelect) {
    el.hostBehaviorSelect.replaceChildren();
    if (!matches.length) {
      const emptyOption = document.createElement("option");
      emptyOption.value = "";
      emptyOption.textContent = items.length ? "No matching behaviors" : "No behaviors yet";
      el.hostBehaviorSelect.append(emptyOption);
    }
    for (const behavior of matches) {
      const option = document.createElement("option");
      option.value = behavior.id;
      option.textContent = behavior.name || "Unnamed behavior";
      el.hostBehaviorSelect.append(option);
    }
    el.hostBehaviorSelect.value = state.activeHostBehaviorId || "";
    el.hostBehaviorSelect.disabled = state.hostBehaviorSaving || !matches.length;
  }
  const editing = Boolean(state.hostBehaviorDraft) && !state.hostBehaviorSaving;
  const selected = matches.find(behavior => behavior.id === state.activeHostBehaviorId);
  if (!selected) {
    const empty = document.createElement("p");
    empty.className = "record-empty";
    empty.textContent = items.length ? "No behaviors match this search. Clear the search to browse the library." : "No behaviors yet. Add a behavior to start.";
    el.hostBehaviorList.append(empty);
  }
  for (const behavior of selected ? [selected] : []) {
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
    title.readOnly = !editing;
    title.setAttribute("aria-label", "Behavior name");
    title.addEventListener("input", () => { if (!editing) return; behavior.name = title.value; updateBehaviorSaveState(); });
    nameField.append(title);
    const instructionField = document.createElement("label");
    instructionField.className = "host-behavior-field host-behavior-instruction";
    instructionField.append(document.createTextNode("Instruction"));
    const instruction = document.createElement("textarea");
    instruction.rows = 5;
    instruction.maxLength = 4000;
    instruction.value = behavior.instruction;
    instruction.readOnly = !editing;
    instruction.setAttribute("aria-label", "Instruction");
    instruction.addEventListener("input", () => { if (!editing) return; behavior.instruction = instruction.value; updateBehaviorSaveState(); });
    instructionField.append(instruction);
    const priorityField = document.createElement("label");
    priorityField.className = "host-behavior-field host-behavior-priority";
    priorityField.append(document.createTextNode("Priority"));
    const priority = document.createElement("input");
    priority.type = "number";
    priority.min = "0";
    priority.max = "10000";
    priority.value = behavior.priority;
    priority.disabled = !editing;
    priority.setAttribute("aria-label", "Priority");
    priority.addEventListener("change", () => { if (!editing) return; behavior.priority = Number(priority.value); updateBehaviorSaveState(); });
    priorityField.append(priority);
    fields.append(nameField, priorityField, instructionField);
    const enabled = document.createElement("input");
    enabled.type = "checkbox";
    enabled.checked = behavior.enabled;
    enabled.disabled = !editing;
    enabled.setAttribute("aria-label", "Enable behavior");
    enabled.addEventListener("change", () => { if (!editing) return; behavior.enabled = enabled.checked; updateBehaviorSaveState(); });
    const label = document.createElement("label");
    label.className = "host-behavior-enabled";
    label.append(enabled, document.createTextNode(" Enabled"));
    const flags = [];
    for (const [key, text] of [["required", "Required"], ["protected", "Protected"]]) {
      const flag = document.createElement("input");
      flag.type = "checkbox";
      flag.checked = behavior[key] === true;
      flag.disabled = !editing;
      flag.setAttribute("aria-label", text + " behavior");
      flag.addEventListener("change", () => { if (!editing) return; behavior[key] = flag.checked; updateBehaviorSaveState(); });
      const flagLabel = document.createElement("label");
      flagLabel.className = "host-behavior-enabled";
      flagLabel.append(flag, document.createTextNode(" " + text));
      flags.push(flagLabel);
    }
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "secondary-button";
    remove.textContent = "Remove";
    remove.disabled = !editing;
    remove.addEventListener("click", () => {
      if (!state.hostBehaviorDraft || state.hostBehaviorSaving) return;
      state.hostBehaviorDraft = state.hostBehaviorDraft.filter(item => item.id !== behavior.id);
      state.activeHostBehaviorId = null;
      renderHostBehaviors();
    });
    const controls = document.createElement("div");
    controls.className = "host-behavior-controls";
    controls.append(label, ...flags, remove);
    row.append(fields, controls);
    el.hostBehaviorList.append(row);
  }
  updateBehaviorSaveState();
}

function updateBehaviorSaveState() {
  const editing = Boolean(state.hostBehaviorDraft);
  const items = state.hostBehaviorDraft || state.hostBehaviors;
  const dirty = editing && JSON.stringify(state.hostBehaviorDraft) !== state.hostBehaviorSnapshot;
  const invalid = editing && state.hostBehaviorDraft.some(item => !item.name.trim() || !item.instruction.trim()
    || !Number.isInteger(item.priority) || item.priority < 0 || item.priority > 10000);
  if (el.saveHostBehaviors) el.saveHostBehaviors.disabled =
    !editing || state.hostBehaviorSaving || !dirty || invalid;
  if (el.editHostBehaviors) el.editHostBehaviors.disabled = !Number.isInteger(state.hostBehaviorRevision) || editing || state.hostBehaviorSaving;
  if (el.cancelHostBehaviors) el.cancelHostBehaviors.disabled = !editing || state.hostBehaviorSaving;
  if (el.addHostBehavior) el.addHostBehavior.disabled = !Number.isInteger(state.hostBehaviorRevision) || state.hostBehaviorSaving;
  if (el.hostBehaviorSelect) {
    const selected = items.find(item => item.id === state.activeHostBehaviorId);
    const option = [...el.hostBehaviorSelect.options].find(item => item.value === state.activeHostBehaviorId);
    if (selected && option) option.textContent = selected.name || "Unnamed behavior";
  }
  if (el.hostBehaviorSummary) {
    const count = state.hostBehaviorMatchCount ?? items.length;
    const mode = state.hostBehaviorSaving ? "Saving…" : editing ? dirty ? "Unsaved changes" : "Editing · No changes" : "Read-only";
    el.hostBehaviorSummary.textContent = `${items.length} behavior${items.length === 1 ? "" : "s"} · ${count} match${count === 1 ? "" : "es"} · ${mode}${invalid ? " · Complete all draft fields before saving." : ""}`;
  }
}

async function refreshHostBehaviors() {
  if (state.hostBehaviorDraft || state.hostBehaviorSaving) return;
  const revision = state.hostBehaviorLoadRevision = (state.hostBehaviorLoadRevision || 0) + 1;
  const payload = await api("/v1/admin/host-behaviors", {}, true);
  if (revision !== state.hostBehaviorLoadRevision || state.hostBehaviorDraft || state.hostBehaviorSaving) return;
  state.hostBehaviors = payload.items;
  state.hostBehaviorRevision = payload.revision;
  state.hostBehaviorSnapshot = JSON.stringify(state.hostBehaviors);
  renderHostBehaviors();
}

function editHostBehaviors() {
  if (!Number.isInteger(state.hostBehaviorRevision) || state.hostBehaviorDraft || state.hostBehaviorSaving) return;
  state.hostBehaviorLoadRevision = (state.hostBehaviorLoadRevision || 0) + 1;
  state.hostBehaviorDraft = JSON.parse(JSON.stringify(state.hostBehaviors));
  renderHostBehaviors();
}

function cancelHostBehaviorEdit() {
  if (state.hostBehaviorSaving) return;
  state.hostBehaviorDraft = null;
  renderHostBehaviors();
}

function addHostBehavior() {
  if (!Number.isInteger(state.hostBehaviorRevision) || state.hostBehaviorSaving) return;
  if (!state.hostBehaviorDraft) editHostBehaviors();
  const id = "behavior-" + Date.now() + "-" + state.hostBehaviorDraft.length;
  state.hostBehaviorDraft.push({
    id,
    name: "New Behavior",
    instruction: "Describe the behavior.",
    enabled: true,
    priority: 100,
    protected: false,
  });
  state.hostBehaviorQuery = "";
  state.activeHostBehaviorId = id;
  renderHostBehaviors();
}

async function saveHostBehaviors() {
  updateBehaviorSaveState();
  if (el.saveHostBehaviors.disabled) return;
  state.hostBehaviorSaving = true;
  renderHostBehaviors();
  try {
    const payload = await api("/v1/admin/host-behaviors", {
      method: "PUT",
      body: JSON.stringify({ items: state.hostBehaviorDraft, expected_revision: state.hostBehaviorRevision }),
    }, true);
    state.hostBehaviors = payload.items;
    state.hostBehaviorRevision = payload.revision;
    state.hostBehaviorDraft = null;
    state.hostBehaviorSnapshot = JSON.stringify(state.hostBehaviors);
    renderHostBehaviors();
    await refreshTaskModelAssignments();
    toast("Behaviors saved");
  } catch (error) {
    toast(error.message, true);
  } finally { state.hostBehaviorSaving = false; renderHostBehaviors(); }
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
    const selectionStatus = document.createElement("small");
    const behaviorIds = selectedTaskBehaviorIds(task, assignment);
    const skillCount = requiredTaskSkills(task).length + selectedTaskSkillIds(assignment).length;
    selectionStatus.textContent = `${skillCount} skill${skillCount === 1 ? "" : "s"} · ${behaviorIds.length} behavior${behaviorIds.length === 1 ? "" : "s"}`;
    card.append(title, detail, selectionStatus);
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
  const templateId = el.endpointTemplateSelect.value;
  el.endpointTemplateSelect.replaceChildren(new Option("Blank endpoint", ""));
  for (const endpoint of state.providerEndpoints) {
    el.endpointTemplateSelect.append(new Option(endpoint.name || endpoint.base_url, endpoint.id));
  }
  el.endpointTemplateSelect.value = templateId;
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
    option.textContent += endpoint.has_api_key || endpoint.api_key ? " · Key loaded" : " · Needs API key";
    if (!endpoint.model) option.textContent += " · Needs model";
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
  return capabilities?.length ? `${model} · ${capabilities.join(" · ")}` : `${model} · Capabilities not supplied; compatibility unverified`;
}

function capabilityDocumentationSource(source) {
  if (typeof source !== "string") return null;
  const includesProviderMetadata = source.startsWith("provider_metadata+");
  const value = includesProviderMetadata ? source.slice("provider_metadata+".length) : source;
  try {
    const url = new URL(value);
    if (url.protocol !== "https:" || url.username || url.password || url.port || url.search) return null;
    const paths = {
      "developers.openai.com": /^\/api\/docs\/models\//,
      "ai.google.dev": /^\/gemini-api\/docs(?:\/|$)/,
      "docs.mistral.ai": /^\/(?:models|studio|capabilities|resources)(?:\/|$)/,
      "openrouter.ai": /^\/(?:docs(?:\/|$)|[a-z0-9_.-]+\/[a-z0-9_.:-]+\/?$)/i,
      "inference-docs.cerebras.ai": /^\/(?:models|capabilities|resources)(?:\/|$)/,
      "docs.sambanova.ai": /^\/(?:docs|cloud)(?:\/|$)/,
      "sambanova.ai": /^\/blog\//,
      "www.sambanova.ai": /^\/blog\//,
      "console.groq.com": /^\/docs(?:\/|$)/,
      "docs.together.ai": /^\/docs(?:\/|$)/,
    };
    return paths[url.hostname]?.test(url.pathname) ? { url: url.href, includesProviderMetadata } : null;
  } catch {
    return null;
  }
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

function taskProviderEndpoint(provider) {
  const selected = String(provider || "").trim().toLowerCase();
  if (!selected) return null;
  return state.providerEndpoints.find(endpoint => [endpoint.id, endpoint.name, endpoint.base_url]
    .some(value => String(value || "").trim().toLowerCase() === selected)) || null;
}

function taskEndpointOptions(select, selected, task = state.activeTaskProfile) {
  select.replaceChildren(new Option(task === "fallback" ? "None (remove fallback)" : "None (default routing)", ""));
  if (task === "reasoning") select.append(new Option("Connected reasoning host", "connected-host"));
  for (const endpoint of state.providerEndpoints) {
    const option = new Option(endpoint.name || "Unnamed endpoint", endpoint.id);
    option.dataset.hasKey = endpoint.has_api_key || Boolean(endpoint.api_key) ? "true" : "false";
    if (option.dataset.hasKey === "true") option.style.color = "var(--success)";
    select.append(option);
  }
  const endpoint = taskProviderEndpoint(selected);
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

function selectedTaskSkillIds(assignment) {
  return Array.isArray(assignment?.skill_ids) ? [...assignment.skill_ids] : [];
}

function requiredTaskSkills(task) {
  return state.taskSkills.filter(skill => Array.isArray(skill.required_tasks) && skill.required_tasks.includes(task));
}

function optionalTaskSkills() {
  return state.taskSkills.filter(skill => !skill.required && !(skill.required_tasks || []).length);
}

function renderTaskSkillSelection() {
  if (!el.taskProfileSkillSelection || !el.taskProfileSkillSelect) return;
  const assignment = state.taskModelAssignments.find(item => item.task === state.activeTaskProfile);
  const selectedIds = selectedTaskSkillIds(assignment);
  const catalog = new Map(state.taskSkills.map(skill => [skill.slug, skill]));
  const required = requiredTaskSkills(state.activeTaskProfile);
  el.taskProfileSkillSelection.replaceChildren();

  function appendSkill(skill, index = -1) {
    const row = document.createElement("div");
    row.className = "task-skill-option";
    const text = document.createElement("div");
    const title = document.createElement("strong");
    const isRequired = index < 0;
    title.textContent = `${skill.name}${isRequired ? " · Required" : ""}${!skill.enabled ? " · Disabled in library" : ""}`;
    const detail = document.createElement("small");
    detail.textContent = skill.slug;
    text.append(title, detail);
    row.append(text);
    if (!isRequired) {
      const actions = document.createElement("div");
      actions.className = "edit-actions task-skill-actions";
      const up = document.createElement("button");
      up.type = "button"; up.className = "secondary-button"; up.textContent = "Up";
      up.setAttribute("aria-label", `Move ${skill.name} up`); up.disabled = index === 0;
      up.addEventListener("click", () => moveTaskSkill(index, -1));
      const down = document.createElement("button");
      down.type = "button"; down.className = "secondary-button"; down.textContent = "Down";
      down.setAttribute("aria-label", `Move ${skill.name} down`); down.disabled = index === selectedIds.length - 1;
      down.addEventListener("click", () => moveTaskSkill(index, 1));
      const remove = document.createElement("button");
      remove.type = "button"; remove.className = "secondary-button"; remove.textContent = "Remove";
      remove.setAttribute("aria-label", `Remove ${skill.name}`);
      remove.addEventListener("click", () => removeTaskSkill(index));
      actions.append(up, down, remove);
      row.append(actions);
    }
    el.taskProfileSkillSelection.append(row);
  }

  required.forEach(skill => appendSkill(skill));
  selectedIds.forEach((slug, index) => {
    const skill = catalog.get(slug);
    if (skill) appendSkill(skill, index);
  });
  if (!required.length && !selectedIds.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "No task skills are available.";
    el.taskProfileSkillSelection.append(empty);
  }

  const selected = new Set(selectedIds);
  el.taskProfileSkillSelect.replaceChildren(new Option("Choose a skill", ""));
  for (const skill of optionalTaskSkills().filter(item => !selected.has(item.slug))) {
    el.taskProfileSkillSelect.append(new Option(
      `${skill.name}${skill.enabled ? "" : " · Disabled in library"}`,
      skill.slug,
    ));
  }
  el.taskProfileSkillSelect.value = "";
  el.taskProfileSkillSelect.disabled = !assignment || el.taskProfileSkillSelect.options.length === 1;
  if (el.taskProfileAddSkill) el.taskProfileAddSkill.disabled = el.taskProfileSkillSelect.disabled;
}

function addTaskSkill() {
  const assignment = state.taskModelAssignments.find(item => item.task === state.activeTaskProfile);
  const slug = el.taskProfileSkillSelect?.value;
  if (!assignment || !slug || selectedTaskSkillIds(assignment).includes(slug)) return;
  assignment.skill_ids = [...selectedTaskSkillIds(assignment), slug];
  renderTaskSkillSelection();
  updateTaskSaveState();
}

function moveTaskSkill(index, direction) {
  const assignment = state.taskModelAssignments.find(item => item.task === state.activeTaskProfile);
  const ids = selectedTaskSkillIds(assignment);
  const target = index + direction;
  if (!assignment || target < 0 || target >= ids.length) return;
  [ids[index], ids[target]] = [ids[target], ids[index]];
  assignment.skill_ids = ids;
  renderTaskSkillSelection();
  updateTaskSaveState();
}

function removeTaskSkill(index) {
  const assignment = state.taskModelAssignments.find(item => item.task === state.activeTaskProfile);
  if (!assignment) return;
  assignment.skill_ids = selectedTaskSkillIds(assignment).filter((_, itemIndex) => itemIndex !== index);
  renderTaskSkillSelection();
  updateTaskSaveState();
}

function taskProfileConfiguration() {
  const assignment = state.taskModelAssignments.find(item => item.task === state.activeTaskProfile);
  return JSON.stringify(assignment || {});
}

function syncTaskProviderRotation() {
  const assignment = state.taskModelAssignments.find(item => item.task === state.activeTaskProfile);
  if (!assignment) return;
  assignment.provider_rotation = el.taskProviderRotation.value;
  updateTaskSaveState();
}

function updateTaskSaveState() {
  if (!el.saveTaskProfile) return;
  const assignment = state.taskModelAssignments.find(item => item.task === state.activeTaskProfile);
  const endpoint = state.providerEndpoints.find(item => item.id === assignment?.provider || item.name === assignment?.provider);
  const invalidPrimary = assignment?.provider && assignment.provider !== "connected-host"
    && !endpoint?.model && !assignment.model;
  const invalidFallback = assignment?.fallbacks?.some(item => !item.provider || !item.model);
  // Save must become actionable for every changed selection. Validate on click,
  // rather than silently disabling the control when an endpoint lacks a model.
  const disabled = state.taskProfileSaving || !assignment
    || taskProfileConfiguration() === state.taskProfileSnapshot;
  el.saveTaskProfile.disabled = disabled;
  if (el.saveTaskEndpoints) el.saveTaskEndpoints.disabled = disabled;
}

function renderTaskBehaviorSelection() {
  const container = el.taskProfileBehaviorSelection;
  if (!container) return;
  const assignment = state.taskModelAssignments.find(item => item.task === state.activeTaskProfile);
  const selected = new Set(selectedTaskBehaviorIds(state.activeTaskProfile, assignment));
  const catalog = taskBehaviorCatalog();
  container.replaceChildren();
  if (!catalog.length) container.textContent = "Add and save behaviors on the Behaviors form first.";
  for (const behavior of catalog) {
    const label = document.createElement("label");
    label.className = "task-behavior-option";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = selected.has(behavior.id);
    checkbox.disabled = false;
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) selected.add(behavior.id); else selected.delete(behavior.id);
      assignment.behavior_ids = [...selected];
      updateTaskSaveState();
    });
    const text = document.createElement("span");
    const title = document.createElement("strong");
    title.textContent = behavior.name + (!behavior.enabled ? " · Disabled in library" : "");
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
  const busy = state.taskProfileSaving === true;
  if (state.taskFallbackTask !== state.activeTaskProfile) state.activeTaskFallback = 0;
  state.taskFallbackTask = state.activeTaskProfile;
  state.activeTaskFallback = Math.max(0, Math.min(state.activeTaskFallback || 0, fallbacks.length - 1));
  el.taskProfileFallbackList.replaceChildren();
  el.taskProfileFallbackList.disabled = busy || !fallbacks.length;
  el.taskProfileFallbackList.size = Math.min(5, Math.max(1, fallbacks.length));
  el.taskProfileAddFallback.disabled = busy || !assignment;
  if (el.taskProfileBack) el.taskProfileBack.disabled = busy;
  el.taskProfileFallbackEditor.classList.toggle("hidden", !fallbacks.length);
  if (!fallbacks.length) {
    el.taskProfileFallbackList.append(new Option("No fallbacks", ""));
  }
  fallbacks.forEach((fallback, index) => {
    const endpoint = taskProviderEndpoint(fallback.provider);
    const name = endpoint?.name || fallback.provider || "New fallback";
    const model = endpoint?.model || fallback.model || "Model not set";
    const option = new Option(`${index + 1}. ${name} · ${model}`, String(index));
    option.classList.toggle("endpoint-has-key", Boolean(endpoint?.has_api_key || endpoint?.api_key));
    el.taskProfileFallbackList.append(option);
  });
  el.taskProfileFallbackList.value = fallbacks.length ? String(state.activeTaskFallback) : "";
  const selected = fallbacks[state.activeTaskFallback];
  taskEndpointOptions(el.taskProfileFallbackEndpoint, selected?.provider || "", "fallback");
  el.taskProfileFallbackEndpoint.disabled = busy || !selected;
  const endpoint = taskProviderEndpoint(selected?.provider);
  el.taskProfileFallbackModel.textContent = selected ? endpoint?.model || selected.model || "Model not set" : "";
  el.taskProfileFallbackUp.disabled = busy || !selected || state.activeTaskFallback === 0;
  el.taskProfileFallbackDown.disabled = busy || !selected || state.activeTaskFallback === fallbacks.length - 1;
  el.taskProfileFallbackRemove.disabled = busy || !selected;
}

function selectTaskFallback() {
  if (state.taskProfileSaving) return;
  const index = Number(el.taskProfileFallbackList.value);
  if (!Number.isInteger(index)) return;
  state.activeTaskFallback = index;
  renderFallbackSelectors();
}

function addTaskFallback() {
  if (state.taskProfileSaving) return;
  const assignment = state.taskModelAssignments.find(item => item.task === state.activeTaskProfile);
  if (!assignment) return;
  assignment.fallbacks = assignment.fallbacks || [];
  assignment.fallbacks.push({ provider: "", model: "" });
  state.taskFallbackTask = state.activeTaskProfile;
  state.activeTaskFallback = assignment.fallbacks.length - 1;
  renderFallbackSelectors();
  el.taskProfileFallbackEndpoint.focus();
  updateTaskSaveState();
}

function removeTaskFallback() {
  if (state.taskProfileSaving) return;
  const assignment = state.taskModelAssignments.find(item => item.task === state.activeTaskProfile);
  if (!assignment?.fallbacks?.[state.activeTaskFallback]) return;
  assignment.fallbacks.splice(state.activeTaskFallback, 1);
  renderFallbackSelectors();
  updateTaskSaveState();
}

function moveTaskFallback(offset) {
  if (state.taskProfileSaving) return;
  const assignment = state.taskModelAssignments.find(item => item.task === state.activeTaskProfile);
  const index = state.activeTaskFallback;
  const target = index + offset;
  if (!assignment?.fallbacks?.[index] || !assignment.fallbacks[target]) return;
  const [fallback] = assignment.fallbacks.splice(index, 1);
  assignment.fallbacks.splice(target, 0, fallback);
  state.activeTaskFallback = target;
  renderFallbackSelectors();
  updateTaskSaveState();
}

function changeTaskFallbackEndpoint() {
  if (state.taskProfileSaving) return;
  const assignment = state.taskModelAssignments.find(item => item.task === state.activeTaskProfile);
  const fallback = assignment?.fallbacks?.[state.activeTaskFallback];
  if (!fallback) return;
  const provider = el.taskProfileFallbackEndpoint.value;
  if (!provider) { removeTaskFallback(); return; }
  const endpoint = taskProviderEndpoint(provider);
  const sameEndpoint = endpoint && taskProviderEndpoint(fallback.provider) === endpoint;
  fallback.provider = endpoint?.id || provider;
  fallback.model = endpoint?.model || (sameEndpoint ? fallback.model : "");
  if (endpoint && !fallback.model) toast("Save a model for this endpoint in Endpoints & MCP Servers first", true);
  renderFallbackSelectors();
  updateTaskSaveState();
}

function loadEndpointIntoForm() {
  const endpoint = state.endpointDraft || selectedEndpoint();
  el.taskProfileEndpointName.value = endpoint?.name || "";
  el.taskProfileProviderName.value = endpoint?.provider_name || "";
  el.taskProfileBaseUrl.value = endpoint?.base_url || "";
  el.taskProfileApiKey.value = endpoint?.api_key || "";
  resetEndpointApiKeyVisibility();
  el.endpointModelId.value = endpoint?.model || "";
  fillSelect(el.endpointModelSelect, endpoint?.models || [], endpoint?.model || "", "Choose a discovered model", endpoint?.model_capabilities || {});
  renderEndpointModelStatus(endpoint);
  updateEndpointEditorState();
}

function resetEndpointApiKeyVisibility() {
  el.taskProfileApiKey.classList.add("is-masked");
  el.endpointApiKeyVisibility.textContent = "Show API key";
  el.endpointApiKeyHelp.textContent = "Visually hidden. Use Show API key to read the value.";
}

function toggleEndpointApiKeyVisibility() {
  if (el.taskProfileApiKey.disabled) return;
  const masked = el.endpointApiKeyVisibility.textContent === "Show API key";
  el.taskProfileApiKey.classList.toggle("is-masked", !masked);
  el.endpointApiKeyVisibility.textContent = masked ? "Hide API key" : "Show API key";
  el.endpointApiKeyHelp.textContent = masked
    ? "API key is visible. Use Hide API key to conceal the value."
    : "Visually hidden. Use Show API key to read the value.";
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
  const documentation = capabilityDocumentationSource(source);
  el.endpointModelStatus.textContent = model
    ? `${model}${capabilities.length ? " · " + capabilities.join(" · ") : " · Capabilities not supplied; compatibility unverified"}`
    : `${endpoint.models?.length || 0} discovered models`;
  if (!endpoint.has_api_key && !endpoint.api_key) el.endpointModelStatus.append(document.createTextNode(" · Needs API key"));
  if (!model) el.endpointModelStatus.append(document.createTextNode(" · Needs model selection"));
  const probe = state.endpointProbe;
  if (probe?.endpointId === endpoint.id && probe.model === model && probe.baseUrl === endpoint.base_url) {
    el.endpointModelStatus.append(document.createTextNode(" · " + probe.message));
  } else {
    el.endpointModelStatus.append(document.createTextNode(" · Tool calling has not been tested"));
  }
  if (source === "provider_metadata") {
    el.endpointModelStatus.append(document.createTextNode(" · Provider metadata"));
  } else if (capabilities.length && documentation) {
    const link = document.createElement("a");
    link.href = documentation.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = documentation.includesProviderMetadata
      ? "Provider metadata + documented capabilities (not tested)"
      : "Documented capabilities (not tested)";
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
  state.endpointProbe = null;
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
  const busy = Boolean(state.integrationSaving || state.endpointDiscovering || state.endpointProbing);
  const preparing = Boolean(state.providerSetupDraft);
  const revisionKnown = Number.isInteger(state.providerEndpointRevision);
  const endpoint = state.endpointDraft || saved;
  const adding = editing && !state.providerEndpoints.some(item => item.id === state.endpointDraft.id);
  [el.taskProfileEndpointName, el.taskProfileProviderName, el.taskProfileBaseUrl, el.taskProfileApiKey,
    el.endpointModelSelect, el.endpointModelId].forEach(input => { input.disabled = !editing || busy; });
  el.taskProfileEndpointSelect.disabled = editing || busy || preparing || !revisionKnown;
  el.taskProfileAddEndpoint.disabled = editing || busy || preparing || !revisionKnown;
  if (el.prepareProviderConnections) el.prepareProviderConnections.disabled = editing || busy || preparing;
  el.endpointTemplateField.classList.toggle("hidden", !adding);
  el.endpointTemplateSelect.disabled = !adding || busy;
  el.endpointApiKeyVisibility.disabled = !editing || busy;
  el.endpointEditButton.disabled = !saved || editing || busy || preparing;
  el.endpointRemoveButton.disabled = !saved || editing || busy || preparing || !revisionKnown;
  el.endpointCancelButton.disabled = !editing || busy;
  el.taskProfileDiscover.disabled = busy || preparing || !/^https?:\/\/\S+$/i.test(endpoint?.base_url || "");
  el.taskProfileDiscover.textContent = state.endpointDiscovering ? "Discovering…" : "Discover Models";
  if (el.endpointProbeButton) {
    el.endpointProbeButton.disabled = busy || preparing || !endpoint?.model || !/^https?:\/\/\S+$/i.test(endpoint?.base_url || "");
    el.endpointProbeButton.textContent = state.endpointProbing ? "Testing tool calling…" : "Test tool calling";
  }
  if (el.saveProviderConnections) el.saveProviderConnections.disabled = busy || !state.providerSetupDraft?.length;
  if (el.cancelProviderConnections) el.cancelProviderConnections.disabled = busy || !preparing;
  el.saveProviderEndpoints.disabled = !editing || busy || !revisionKnown || !endpointFormIsValid(state.endpointDraft)
    || JSON.stringify(state.endpointDraft) === state.endpointEditBaseline;
}

function editEndpoint() {
  const endpoint = selectedEndpoint();
  if (!endpoint) return;
  state.providerEndpointLoadRevision = (state.providerEndpointLoadRevision || 0) + 1;
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
  if (state.taskProfileSaving && task !== state.activeTaskProfile) return;
  if (state.activeTaskProfile && state.activeTaskProfile !== task) discardTaskProfileChanges();
  state.activeTaskProfile = task;
  let assignment = state.taskModelAssignments.find(item => item.task === task);
  if (!assignment) {
    assignment = { task, provider: "", model: "", fallbacks: [], provider_rotation: "ordered", behavior_ids: null, skill_ids: [], voice_reference_id: "", notes: "" };
    state.taskModelAssignments.push(assignment);
  }
  const behavior = state.taskBehaviors.find(item => item.task === task) || {};
  taskEndpointOptions(el.taskProviderSelect, assignment.provider, task);
  if (el.taskProviderRotation) el.taskProviderRotation.value = assignment.provider_rotation || "ordered";
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
  el.taskProfileInstructions.value = behavior.instructions || "";
  el.taskProfileEnabled.checked = behavior.enabled !== false;
  el.taskProfileVoiceReferenceId.value = assignment.voice_reference_id || "";
  renderTaskBehaviorSelection();
  renderTaskSkillSelection();
  renderFallbackSelectors();
  state.taskProfileSnapshot = taskProfileConfiguration();
  updateTaskSaveState();
  el.taskProfileOverview.classList.add("hidden");
  el.taskProfileList.classList.add("hidden");
  el.taskProfileEditor.classList.remove("hidden");
}

function closeTaskProfile() {
  if (state.taskProfileSaving) return;
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
  if (state.endpointDraft || state.endpointProbing || state.integrationSaving) return;
  const revision = state.providerEndpointLoadRevision = (state.providerEndpointLoadRevision || 0) + 1;
  const payload = await api("/v1/admin/provider-endpoints", {}, true);
  if (revision !== state.providerEndpointLoadRevision || state.endpointDraft || state.endpointProbing || state.integrationSaving) return;
  state.providerEndpoints = payload.items || [];
  state.providerEndpointRevision = payload.revision ?? 0;
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
  state.taskSkills = payload.skills || [];
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
      method: "PUT", body: JSON.stringify({ items, expected_revision: state.providerEndpointRevision }),
    }, true);
    state.providerEndpoints = payload.items || [];
    state.providerEndpointRevision = payload.revision ?? state.providerEndpointRevision;
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
  } catch (error) { toast(error.status === 409 ? "Connections changed. Your draft is preserved. Cancel, refresh and review the latest connections before editing again." : error.message, true); }
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
      body: JSON.stringify({ items: state.providerEndpoints.filter(item => item.id !== endpoint.id), expected_revision: state.providerEndpointRevision }),
    }, true);
    state.providerEndpoints = payload.items || [];
    state.providerEndpointRevision = payload.revision ?? state.providerEndpointRevision;
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
  } catch (error) { toast(error.status === 409 ? "Connections changed. Refresh and review the latest connections before removing an endpoint." : error.message, true); }
  finally {
    state.integrationSaving = false;
    updateEndpointEditorState();
  }
}

async function saveTaskProfile() {
  const task = state.activeTaskProfile;
  if (!task || el.saveTaskProfile.disabled) return;
  const selectedAssignment = state.taskModelAssignments.find(item => item.task === task);
  const selectedEndpoint = state.providerEndpoints.find(item =>
    item.id === selectedAssignment?.provider || item.name === selectedAssignment?.provider);
  if (selectedAssignment?.provider && selectedAssignment.provider !== "connected-host"
      && !selectedEndpoint?.model && !selectedAssignment.model) {
    toast("Select an endpoint with a saved model before saving this task.", true);
    return;
  }
  if (selectedAssignment?.fallbacks?.some(item => !item.provider || !item.model)) {
    toast("Complete or remove unfinished fallback endpoints before saving.", true);
    return;
  }
  state.taskProfileSaving = true;
  el.saveTaskProfile.disabled = true;
  renderFallbackSelectors();
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
  finally { state.taskProfileSaving = false; renderFallbackSelectors(); updateTaskSaveState(); }
}

async function discoverTaskProfileModels() {
  if (state.integrationSaving || state.endpointDiscovering || state.endpointProbing || state.providerSetupDraft) return;
  if (!state.endpointDraft && selectedEndpoint()) editEndpoint();
  syncEndpointDraft();
  const endpoint = state.endpointDraft;
  if (!endpoint || !/^https?:\/\/\S+$/i.test(endpoint.base_url || "")) {
    toast("Enter a valid endpoint Base URL before discovering models", true);
    return;
  }
  state.endpointDiscovering = true;
  updateEndpointEditorState();
  updateMcpEditorState();
  try {
    const payload = await api("/v1/admin/provider-endpoints/discover", {
      method: "POST",
      body: JSON.stringify({ ...endpoint, name: endpoint.name || "Model discovery" }),
    }, true);
    endpoint.models = payload.models || [];
    endpoint.model_capabilities = payload.model_capabilities || {};
    endpoint.model_capability_sources = payload.model_capability_sources || {};
    endpoint.model_capability_exclusions = payload.model_capability_exclusions || {};
    if (!endpoint.model && endpoint.models.length === 1) endpoint.model = endpoint.models[0];
    renderTaskProfileEndpointOptions();
    loadEndpointIntoForm();
    toast(`Discovered ${endpoint.models.length} model(s)`);
  } catch (error) {
    toast(error.message, true);
  }
  finally {
    state.endpointDiscovering = false;
    updateEndpointEditorState();
    updateMcpEditorState();
  }
}

async function probeEndpointToolCalling() {
  if (state.integrationSaving || state.endpointDiscovering || state.endpointProbing || state.providerSetupDraft) return;
  if (state.endpointDraft) syncEndpointDraft();
  const endpoint = state.endpointDraft || selectedEndpoint();
  if (!endpoint?.model || !/^https?:\/\/\S+$/i.test(endpoint?.base_url || "")) {
    toast("Choose a provider and model before testing tool calling", true);
    return;
  }
  const requestBody = JSON.stringify(endpoint);
  const isCurrent = () => JSON.stringify(state.endpointDraft || selectedEndpoint()) === requestBody;
  state.endpointProbing = true;
  updateEndpointEditorState();
  updateMcpEditorState();
  try {
    const result = await api("/v1/admin/provider-endpoints/probe", {
      method: "POST", body: requestBody,
    }, true);
    if (!isCurrent()) return;
    state.endpointProbe = {
      endpointId: endpoint.id, model: endpoint.model, baseUrl: endpoint.base_url,
      message: result.tool_calling_verified ? "Tool calling verified in current test" : (result.message || "Tool calling test failed"),
    };
    toast(state.endpointProbe.message, !result.tool_calling_verified);
  } catch (error) {
    if (!isCurrent()) return;
    state.endpointProbe = { endpointId: endpoint.id, model: endpoint.model, baseUrl: endpoint.base_url, message: "Tool calling test failed: " + error.message };
    toast(error.message, true);
  } finally {
    state.endpointProbing = false;
    renderEndpointModelStatus(state.endpointDraft || selectedEndpoint());
    updateEndpointEditorState();
    updateMcpEditorState();
  }
}

const COMMON_ENDPOINT_PRESETS = [
  { id: "openai", name: "OpenAI", base_url: "https://api.openai.com/v1" },
  { id: "openrouter", name: "OpenRouter", base_url: "https://openrouter.ai/api/v1" },
  { id: "google-gemini", name: "Google Gemini (OpenAI-compatible)", base_url: "https://generativelanguage.googleapis.com/v1beta/openai" },
  { id: "groq", name: "Groq", base_url: "https://api.groq.com/openai/v1" },
  { id: "together", name: "Together AI", base_url: "https://api.together.ai/v1" },
  { id: "fireworks", name: "Fireworks AI", base_url: "https://api.fireworks.ai/inference/v1" },
  { id: "deepseek", name: "DeepSeek", base_url: "https://api.deepseek.com" },
  { id: "mistral", name: "Mistral AI", base_url: "https://api.mistral.ai/v1" },
  { id: "cerebras", name: "Cerebras", base_url: "https://api.cerebras.ai/v1" },
  { id: "sambanova", name: "SambaNova", base_url: "https://api.sambanova.ai/v1" },
  { id: "ollama", name: "Ollama (local)", base_url: "http://localhost:11434/v1" },
  { id: "lm-studio", name: "LM Studio (local)", base_url: "http://localhost:1234/v1" },
  { id: "vllm", name: "vLLM (local/self-hosted)", base_url: "http://localhost:8000/v1" },
  { id: "localai", name: "LocalAI (local/self-hosted)", base_url: "http://localhost:8080/v1" },
];

function prepareProviderConnections() {
  if (state.endpointDraft || state.providerSetupDraft || state.integrationSaving || state.endpointDiscovering || state.endpointProbing) return;
  const providers = ["cerebras", "google-gemini", "openrouter", "sambanova", "together"];
  const baseUrls = new Set(state.providerEndpoints.map(item => item.base_url.replace(/\/$/, "")));
  state.providerSetupDraft = COMMON_ENDPOINT_PRESETS.filter(item => providers.includes(item.id) && !baseUrls.has(item.base_url))
    .map(preset => ({ id: crypto.randomUUID(), name: preset.name, provider_name: preset.name,
      base_url: preset.base_url, api_key: "", model: "", models: [], model_capabilities: {}, model_capability_sources: {}, model_capability_exclusions: {} }));
  if (!state.providerSetupDraft.length) {
    state.providerSetupDraft = null;
    toast("All five provider profiles are already present. Edit each connection to finish its setup.");
    return;
  }
  el.providerSetupList.replaceChildren();
  for (const endpoint of state.providerSetupDraft) {
    const row = document.createElement("p");
    row.className = "record-empty";
    row.textContent = `${endpoint.name} · Needs API key · Needs model · Tool calling has not been tested`;
    el.providerSetupList.append(row);
  }
  el.providerSetupPanel.classList.remove("hidden");
  updateEndpointEditorState();
}

function cancelProviderConnections() {
  if (state.integrationSaving) return;
  state.providerSetupDraft = null;
  el.providerSetupPanel.classList.add("hidden");
  el.providerSetupList.replaceChildren();
  updateEndpointEditorState();
}

async function saveProviderConnections() {
  if (!state.providerSetupDraft?.length || state.integrationSaving || state.endpointDraft) return;
  state.integrationSaving = true;
  updateEndpointEditorState();
  updateMcpEditorState();
  try {
    const latest = await api("/v1/admin/provider-endpoints", {}, true);
    const existing = latest.items || [];
    const baseUrls = new Set(existing.map(item => item.base_url.replace(/\/$/, "")));
    const additions = state.providerSetupDraft.filter(item => !baseUrls.has(item.base_url));
    const payload = additions.length ? await api("/v1/admin/provider-endpoints", {
      method: "PUT", body: JSON.stringify({ items: existing.concat(additions), expected_revision: latest.revision ?? 0 }),
    }, true) : latest;
    state.providerEndpoints = payload.items || [];
    state.providerEndpointRevision = payload.revision ?? latest.revision ?? 0;
    state.activeEndpointId = additions[0]?.id || state.activeEndpointId;
    state.providerSetupDraft = null;
    el.providerSetupPanel.classList.add("hidden");
    el.providerSetupList.replaceChildren();
    renderTaskProfileEndpointOptions();
    loadEndpointIntoForm();
    renderTaskProfiles();
    toast(`Saved ${additions.length} new connection profile(s). Add keys, choose models and test tool calling before assigning tasks.`);
  } catch (error) {
    toast(error.message, true);
  } finally {
    state.integrationSaving = false;
    updateEndpointEditorState();
    updateMcpEditorState();
  }
}

function addTaskProfileEndpointFromPreset(presetId) {
  const preset = COMMON_ENDPOINT_PRESETS.find(item => item.id === presetId);
  if (!preset) {
    toast("Choose an endpoint preset first", true);
    return;
  }
  state.providerEndpointLoadRevision = (state.providerEndpointLoadRevision || 0) + 1;
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
    model_capability_exclusions: {},
  };
  state.endpointDraft = endpoint;
  state.endpointEditBaseline = "";
  state.activeEndpointId = endpoint.id;
  state.activeEndpointOriginalName = "";
  el.endpointTemplateSelect.value = "";
  renderTaskProfileEndpointOptions();
  loadEndpointIntoForm();

  el.taskProfileApiKey.focus();
  toast(`Added ${preset.name}. Add credentials if required, then discover models.`);
}

function addTaskProfileEndpoint() {
  state.providerEndpointLoadRevision = (state.providerEndpointLoadRevision || 0) + 1;
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
    model_capability_exclusions: {},
  };
  state.endpointDraft = endpoint;
  state.endpointEditBaseline = "";
  state.activeEndpointId = endpoint.id;
  state.activeEndpointOriginalName = "";
  el.endpointTemplateSelect.value = "";
  renderTaskProfileEndpointOptions();
  loadEndpointIntoForm();
  el.taskProfileEndpointName.focus();
}

function applyEndpointTemplate() {
  if (!state.endpointDraft || state.integrationSaving || state.endpointDiscovering
    || state.providerEndpoints.some(item => item.id === state.endpointDraft.id)) return;
  const source = state.providerEndpoints.find(item => item.id === el.endpointTemplateSelect.value);
  const id = state.endpointDraft.id;
  state.endpointDraft = source ? {
    ...JSON.parse(JSON.stringify(source)), id,
    name: source.name.slice(0, 115) + " copy", model: "",
  } : {
    id, name: "", provider_name: "", base_url: "", api_key: "", model: "", models: [],
    model_capabilities: {}, model_capability_sources: {}, model_capability_exclusions: {},
  };
  renderTaskProfileEndpointOptions();
  loadEndpointIntoForm();
  el.taskProfileEndpointName.focus();
}

function updateVoiceSliderReadouts() {
  if (el.voiceRateValue) el.voiceRateValue.value = Number(el.voiceRate.value).toFixed(2);
  if (el.voicePitchValue) el.voicePitchValue.value = Number(el.voicePitch.value).toFixed(2);
  if (el.voiceVolumeValue) el.voiceVolumeValue.value = Number(el.voiceVolume.value).toFixed(2);
}

function normalizeVoiceSettings(settings = {}) {
  return {
    rate: Number(settings.rate ?? 1),
    pitch: Number(settings.pitch ?? 1),
    volume: Number(settings.volume ?? 1),
    voiceName: String(settings.voiceName ?? ""),
  };
}

function readVoiceSettingsForm() {
  return normalizeVoiceSettings({
    rate: el.voiceRate?.value,
    pitch: el.voicePitch?.value,
    volume: el.voiceVolume?.value,
    voiceName: el.voiceName?.value.trim(),
  });
}

function applyVoiceSettingsForm(settings) {
  const normalized = normalizeVoiceSettings(settings);
  if (el.voiceRate) el.voiceRate.value = String(normalized.rate);
  if (el.voicePitch) el.voicePitch.value = String(normalized.pitch);
  if (el.voiceVolume) el.voiceVolume.value = String(normalized.volume);
  if (el.voiceName) el.voiceName.value = normalized.voiceName;
  updateVoiceSliderReadouts();
}

function voiceSettingsDirty() {
  if (!state.voiceSettingsBaseline) return false;
  return JSON.stringify(readVoiceSettingsForm()) !== JSON.stringify(state.voiceSettingsBaseline);
}

function bodySettingsAvailable() {
  return state.adminAuthorized && state.status?.administration?.body_settings_available === true;
}

function bodyFallbackSettingsAvailable() {
  return state.adminAuthorized && state.status?.administration?.body_fallback_settings_available === true;
}

function renderBodySettingsAvailability() {
  const available = bodySettingsAvailable();
  if (!available) {
    state.voiceSettingsLoaded = false;
    state.voiceSettingsRevision = 0;
    state.voiceSettingsBaseline = null;
    for (const name of ["voiceRate", "voicePitch", "voiceVolume"]) {
      if (el[name]) el[name].value = "1";
    }
    if (el.voiceName) el.voiceName.value = "";
    updateVoiceSliderReadouts();
    if (el.voiceSettingsRevision) el.voiceSettingsRevision.textContent = "";
    const message = state.status?.administration?.body_settings_available === false
      ? "Unavailable for this account." : "Voice settings unavailable.";
    if (el.voiceSettingsStatus) el.voiceSettingsStatus.textContent = message;
    if (el.bodyFallbackEnabled) el.bodyFallbackEnabled.checked = false;
    if (el.bodyFallbackSource) el.bodyFallbackSource.textContent = message;
  }
  const enabled = available && state.voiceSettingsLoaded && !state.voiceSettingsBusy;
  for (const name of ["voiceRate", "voicePitch", "voiceVolume", "voiceName"]) {
    if (el[name]) el[name].disabled = !enabled;
  }
  const dirty = enabled && voiceSettingsDirty();
  if (el.saveVoiceSettings) el.saveVoiceSettings.disabled = !dirty;
  if (el.cancelVoiceSettings) el.cancelVoiceSettings.disabled = !dirty;
  if (el.bodyFallbackEnabled) el.bodyFallbackEnabled.disabled = !bodyFallbackSettingsAvailable();
  if (el.saveBodyFallbackSetting) el.saveBodyFallbackSetting.disabled = !bodyFallbackSettingsAvailable();
}

async function loadVoiceSettings() {
  const revision = state.voiceSettingsLoadRevision = (state.voiceSettingsLoadRevision || 0) + 1;
  if (!bodySettingsAvailable()) {
    renderBodySettingsAvailability();
    return;
  }
  state.voiceSettingsLoaded = false;
  state.voiceSettingsBusy = true;
  renderBodySettingsAvailability();
  if (el.voiceSettingsStatus) el.voiceSettingsStatus.textContent = "Loading voice settings…";
  try {
    const settings = await api("/v1/admin/body/voice/settings", {}, true);
    if (revision !== state.voiceSettingsLoadRevision || !bodySettingsAvailable()) return;
    state.voiceSettingsRevision = Number(settings.revision || 0);
    state.voiceSettingsBaseline = normalizeVoiceSettings(settings);
    applyVoiceSettingsForm(state.voiceSettingsBaseline);
    state.voiceSettingsLoaded = true;
    if (el.voiceSettingsRevision) el.voiceSettingsRevision.textContent = "Revision: " + state.voiceSettingsRevision;
    if (el.voiceSettingsStatus) el.voiceSettingsStatus.textContent = "";
  } catch (error) {
    if (revision !== state.voiceSettingsLoadRevision || !bodySettingsAvailable()) return;
    if (el.voiceSettingsStatus) el.voiceSettingsStatus.textContent = error.message;
    toast("Could not load voice settings: " + error.message, true);
  } finally {
    if (revision === state.voiceSettingsLoadRevision) {
      state.voiceSettingsBusy = false;
      renderBodySettingsAvailability();
    }
  }
}

async function saveVoiceSettings() {
  if (!bodySettingsAvailable() || !state.voiceSettingsLoaded || state.voiceSettingsBusy || !voiceSettingsDirty()) {
    renderBodySettingsAvailability();
    return;
  }
  const draft = readVoiceSettingsForm();
  state.voiceSettingsBusy = true;
  renderBodySettingsAvailability();
  try {
    const settings = await api("/v1/admin/body/voice/settings", {
      method: "POST",
      body: JSON.stringify({
        expected_revision: state.voiceSettingsRevision,
        rate: draft.rate,
        pitch: draft.pitch,
        volume: draft.volume,
        voice_name: draft.voiceName,
      }),
    }, true);
    if (!bodySettingsAvailable()) return;
    state.voiceSettingsRevision = Number(settings.revision || 0);
    state.voiceSettingsBaseline = normalizeVoiceSettings({ ...draft, ...settings });
    applyVoiceSettingsForm(state.voiceSettingsBaseline);
    if (el.voiceSettingsRevision) el.voiceSettingsRevision.textContent = "Revision: " + state.voiceSettingsRevision;
    if (el.voiceSettingsStatus) el.voiceSettingsStatus.textContent = "";
    toast("Voice settings saved");
  } catch (error) {
    if (!bodySettingsAvailable()) return;
    if (el.voiceSettingsStatus) el.voiceSettingsStatus.textContent = error.message;
    toast("Could not save voice settings: " + error.message, true);
  } finally {
    state.voiceSettingsBusy = false;
    renderBodySettingsAvailability();
  }
}

function cancelVoiceSettings() {
  if (!bodySettingsAvailable() || !state.voiceSettingsLoaded || state.voiceSettingsBusy || !state.voiceSettingsBaseline) {
    renderBodySettingsAvailability();
    return;
  }
  applyVoiceSettingsForm(state.voiceSettingsBaseline);
  if (el.voiceSettingsStatus) el.voiceSettingsStatus.textContent = "Changes cancelled.";
  renderBodySettingsAvailability();
}

async function refreshBodyFallbackSettings() {
  if (!bodyFallbackSettingsAvailable() || !el.bodyFallbackEnabled) return;
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
  if (!bodyFallbackSettingsAvailable() || !el.bodyFallbackEnabled) return;
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
    await refreshStatus();
    const allowed = await validateAdmin();
    if (!allowed) return;
    setMode("admin");
    await Promise.all([
      refreshDiagnostics(),
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
  renderBodySettingsAvailability();
  const mind = status.mind;
  const integration = status.integration;
  const selfName = typeof mind.identity.self_name === "string" && mind.identity.self_name.trim()
    ? mind.identity.self_name : "Self-name not set";

  el.connectionLabel.textContent = "MCP - Axiom Online";
  el.mindName.textContent = selfName;
  el.continuityLabel.textContent = "Persistent";
  el.selfName.textContent = selfName;
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
  el.adminMindName.textContent = selfName;
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
    await refreshStatus();
    const admin = state.mode === "admin" && state.adminAuthorized;
    await Promise.all([
      refreshMemory(admin ? filters.admin : filters.mind, true),
      refreshJournal(true),
      ...(admin ? [
        refreshDiagnostics(),
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
el.adminRefreshButton.addEventListener("click", refreshAdmin);
if (el.saveBodyFallbackSetting) el.saveBodyFallbackSetting.addEventListener("click", saveBodyFallbackSettings);
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
if (el.editHostBehaviors) el.editHostBehaviors.addEventListener("click", editHostBehaviors);
if (el.cancelHostBehaviors) el.cancelHostBehaviors.addEventListener("click", cancelHostBehaviorEdit);
if (el.hostBehaviorSearch) el.hostBehaviorSearch.addEventListener("input", () => {
  if (state.hostBehaviorSaving) return;
  state.hostBehaviorQuery = el.hostBehaviorSearch.value;
  renderHostBehaviors();
});
if (el.hostBehaviorSelect) el.hostBehaviorSelect.addEventListener("change", () => {
  if (state.hostBehaviorSaving) return;
  state.activeHostBehaviorId = el.hostBehaviorSelect.value;
  renderHostBehaviors();
});
if (el.taskProfileBack) el.taskProfileBack.addEventListener("click", closeTaskProfile);

let diagnosticsRevision = 0;
function formatCurrentIdentity(value) {
  if (value == null) return "Unknown";
  if (typeof value !== "object" || Array.isArray(value)) {
    return typeof value === "string" ? value : JSON.stringify(value);
  }
  const name = typeof value.self_name === "string" ? value.self_name.trim() : "";
  const parts = ["Persistent cognitive Mind", name ? "self-name: " + name : "self-name not set"];
  if (typeof value.pronouns === "string" && value.pronouns.trim()) parts.push("pronouns: " + value.pronouns);
  if (typeof value.developmental_state === "string" && value.developmental_state.trim()) {
    parts.push("developmental state: " + displayLabel(value.developmental_state));
  }
  return parts.join("; ");
}

async function refreshDiagnostics() {
  const context = document.getElementById("currentStateDiagnostics");
  const performance = document.getElementById("performanceDiagnostics");
  if (!state.adminAuthorized || !context || !performance) return;
  const revision = ++diagnosticsRevision;
  try {
    const result = await api("/v1/admin/diagnostics", {}, true);
    if (revision !== diagnosticsRevision) return;
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
        detail.textContent = key === "identity" ? formatCurrentIdentity(value) : value == null ? "Unknown" :
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
    if (revision !== diagnosticsRevision) return;
    context.textContent = "Cannot load state: " + error.message;
    performance.textContent = "Cannot load timings: " + error.message;
    const cognitive = document.getElementById("cognitiveStateSummary");
    if (cognitive) {
      cognitive.replaceChildren();
      cognitive.textContent = "Cannot load current state: " + error.message;
    }
    const summary = document.getElementById("apiActivitySummary");
    if (summary) summary.textContent = "API activity unavailable.";
    const list = document.getElementById("apiActivityList");
    if (list) {
      list.replaceChildren();
      list.textContent = "Cannot load API activity: " + error.message;
    }
  }
}
document.getElementById("apiActivityFilter")?.addEventListener("change", refreshDiagnostics);

const adminSectionIds = {
  mcp: "mcpSection",
  tools: "toolsSection",
  tasks: "tasksSection",
  behaviors: "behaviorsSection",
  skills: "skillsSection",
  memories: "memoriesSection",
  journals: "journalsSection",
  overview: "overviewSection",
  foundations: "foundationsSection",
  breaker: "breakerSection",
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

async function refreshAdmin() {
  const updates = [refresh()];
  if (document.getElementById("foundationsSection")?.classList.contains("hidden") === false) updates.push(refreshFoundations());
  if (typeof refreshBreakerSettings === "function" && document.getElementById("breakerSection")?.classList.contains("hidden") === false) updates.push(refreshBreakerSettings());
  if (document.getElementById("skillsSection")?.classList.contains("hidden") === false) {
    updates.push(refreshSkillDrafts());
  }
  if (document.getElementById("devicesSection")?.classList.contains("hidden") === false) {
    updates.push(refreshDeviceInventory());
  }
  await Promise.all(updates);
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
  const busy = Boolean(state.integrationSaving || state.endpointDiscovering || state.endpointProbing || state.mcpToolsSaving || state.mcpToolsDiscovering);
  [el.mcpServerName, el.mcpServerUrl, el.mcpServerToken, el.mcpServerEnabled].forEach(input => {
    input.disabled = !editing || busy;
  });
  el.mcpServerSelect.disabled = editing || busy;
  el.mcpAddServer.disabled = editing || busy;
  el.mcpEditServer.disabled = !saved || editing || busy;
  el.mcpDeleteServer.disabled = !saved || editing || busy;
  el.mcpCancelEdit.disabled = !editing || busy;
  const server = selectedMcpServer();
  const valid = !!(server?.name && /^https?:\/\/\S+$/i.test(server?.url || ""));
  el.saveMcpServers.disabled = !editing || busy || !valid || JSON.stringify(server) === state.mcpEditBaseline;
  updateMcpToolsState();
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
  el.mcpServerStatus.textContent = state.mcpServerDraft ? "Unsaved changes" : "";
  updateMcpEditorState();
}

function mcpToolKey(serverId, toolName) {
  return JSON.stringify([serverId, toolName]);
}

function mcpToolEntries() {
  return state.mcpServers.flatMap(server => {
    const tools = state.mcpToolsDraft?.serverId === server.id ? state.mcpToolsDraft.tools : server.tools;
    return (tools || []).map(tool => ({ server, tool, key: mcpToolKey(server.id, tool.name) }));
  });
}

function selectedMcpTool() {
  return mcpToolEntries().find(entry => entry.key === state.activeMcpToolKey) || null;
}

function mcpToolsTargetServer() {
  const id = state.mcpToolsDraft?.serverId || state.mcpToolsServerId || selectedMcpTool()?.server.id;
  return state.mcpServers.find(server => server.id === id) || null;
}

function invalidateMcpToolRun() {
  state.mcpToolRunRevision = (state.mcpToolRunRevision || 0) + 1;
  state.mcpToolRunning = false;
  el.mcpToolArguments.value = "{}";
  el.mcpToolOutput.textContent = "";
}

function selectMcpTool(key) {
  if (state.activeMcpToolKey !== key) invalidateMcpToolRun();
  state.activeMcpToolKey = key;
  el.mcpToolList.value = key;
  renderMcpToolDetail();
}

function renderMcpTools() {
  if (!el.mcpToolList) return;
  el.mcpToolsServerFilter.replaceChildren(new Option("All servers", ""));
  for (const server of state.mcpServers) el.mcpToolsServerFilter.append(new Option(server.name, server.id));
  if (state.mcpToolsDraft && !state.mcpServers.some(server => server.id === state.mcpToolsDraft.serverId)) {
    el.mcpToolsServerFilter.append(new Option("Unavailable server", state.mcpToolsDraft.serverId));
  } else if (!state.mcpServers.some(server => server.id === state.mcpToolsServerId)) {
    state.mcpToolsServerId = "";
  }
  el.mcpToolsServerFilter.value = state.mcpToolsServerId || "";
  el.mcpToolsSearch.value = state.mcpToolsQuery || "";
  const query = (state.mcpToolsQuery || "").trim().toLowerCase();
  const entries = mcpToolEntries().filter(({ server, tool }) =>
    (!state.mcpToolsServerId || server.id === state.mcpToolsServerId)
    && (!query || `${tool.name} ${tool.description || ""} ${server.name}`.toLowerCase().includes(query)))
    .sort((a, b) => a.tool.name.localeCompare(b.tool.name) || a.server.name.localeCompare(b.server.name));
  el.mcpToolList.replaceChildren();
  for (const { server, tool, key } of entries) {
    const status = server.enabled === false ? "Server disabled" : tool.enabled === false ? "Disabled" : "Enabled";
    el.mcpToolList.append(new Option(`${tool.name} · ${server.name} · ${status}`, key));
  }
  el.mcpToolCount.textContent = String(entries.length);
  const nextKey = entries.some(entry => entry.key === state.activeMcpToolKey) ? state.activeMcpToolKey : entries[0]?.key || "";
  el.mcpToolList.value = nextKey;
  selectMcpTool(nextKey);
}

function renderMcpToolDetail() {
  const entry = selectedMcpTool();
  el.mcpToolDetail.classList.toggle("hidden", !entry);
  el.mcpToolName.textContent = entry?.tool.name || "";
  el.mcpToolServerName.textContent = entry?.server.name || "";
  el.mcpToolDescription.textContent = entry?.tool.description || "";
  el.mcpToolDescription.classList.toggle("hidden", !entry?.tool.description);
  el.mcpToolSchema.textContent = entry ? JSON.stringify(entry.tool.inputSchema || {}, null, 2) : "";
  el.mcpToolEnabled.checked = !!entry && entry.tool.enabled !== false;
  updateMcpToolsState();
}

function mcpToolArgumentsValid() {
  try {
    const value = JSON.parse(el.mcpToolArguments.value || "{}");
    return !!value && typeof value === "object" && !Array.isArray(value);
  } catch (_) { return false; }
}

function updateMcpToolsState() {
  if (!el.mcpToolList) return;
  const editing = !!state.mcpToolsDraft;
  const busy = Boolean(state.integrationSaving || state.endpointDiscovering || state.endpointProbing || state.mcpToolsSaving || state.mcpToolsDiscovering);
  const target = mcpToolsTargetServer();
  const entry = selectedMcpTool();
  const dirty = editing && JSON.stringify(state.mcpToolsDraft.tools) !== state.mcpToolsDraft.baseline;
  el.mcpToolsServerFilter.disabled = editing || state.mcpToolsSaving;
  el.mcpEditTools.disabled = editing || busy || !target;
  el.mcpDiscoverTools.disabled = busy || !target || !!state.mcpServerDraft;
  el.mcpCancelTools.disabled = !editing || state.mcpToolsSaving;
  el.saveMcpTools.disabled = !dirty || busy || !target || !!state.mcpServerDraft;
  el.mcpToolEnabled.disabled = !editing || busy || !entry || entry.server.id !== state.mcpToolsDraft.serverId;
  const runnable = !!entry && entry.server.enabled !== false && entry.tool.enabled !== false && !editing && !state.mcpServerDraft && !busy;
  el.mcpToolArguments.disabled = !runnable || state.mcpToolRunning;
  el.mcpRunTool.disabled = !runnable || state.mcpToolRunning || !mcpToolArgumentsValid();
  el.mcpToolStatus.textContent = state.mcpToolsError || (state.mcpToolsSaving ? "Saving tools…"
    : state.mcpToolsDiscovering ? "Discovering tools…"
    : editing && !target ? "Server unavailable"
    : dirty ? "Unsaved changes"
    : entry?.server.enabled === false ? "Server disabled"
    : entry?.tool.enabled === false ? "Tool disabled"
    : runnable && !mcpToolArgumentsValid() ? "Arguments must be a JSON object"
    : !el.mcpToolList.children.length ? "No matching tools" : "");
}

function editMcpTools() {
  if (state.mcpToolsDraft || state.mcpToolsSaving || state.integrationSaving || state.mcpToolsDiscovering) return;
  const server = mcpToolsTargetServer();
  if (!server) return;
  invalidateMcpToolRun();
  state.mcpToolsDraft = {
    serverId: server.id,
    tools: JSON.parse(JSON.stringify(server.tools || [])),
    baseline: JSON.stringify(server.tools || []),
    connection: JSON.stringify([server.url, server.bearer_token || ""]),
  };
  state.mcpToolsServerId = server.id;
  state.mcpToolsError = "";
  renderMcpTools();
}

function cancelMcpTools() {
  if (state.mcpToolsSaving) return;
  state.mcpToolsDiscoveryRevision = (state.mcpToolsDiscoveryRevision || 0) + 1;
  state.mcpToolsDiscovering = false;
  state.mcpToolsDraft = null;
  state.mcpToolsError = "";
  invalidateMcpToolRun();
  renderMcpTools();
  updateMcpEditorState();
}

async function refreshMcpServers() {
  if (state.integrationSaving || state.mcpToolsSaving) return;
  const revision = state.mcpToolsRefreshRevision = (state.mcpToolsRefreshRevision || 0) + 1;
  try {
    const payload = await api("/v1/admin/mcp/servers", {}, true);
    if (revision !== state.mcpToolsRefreshRevision) return;
    invalidateMcpToolRun();
    state.mcpServers = payload.items || [];
    if (!state.mcpServerDraft && !state.mcpServers.some(server => server.id === state.activeMcpServerId)) {
      state.activeMcpServerId = state.mcpServers[0]?.id || null;
    }
    renderMcpServerOptions();
    loadMcpServerIntoForm();
    renderMcpTools();
  } catch (error) {
    if (revision === state.mcpToolsRefreshRevision) toast(`Could not load MCP servers: ${error.message}`, true);
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
  updateMcpToolsState();
  if (el.mcpDiscoverTools.disabled) return;
  if (!state.mcpToolsDraft) editMcpTools();
  const draft = state.mcpToolsDraft;
  const server = mcpToolsTargetServer();
  if (!draft || !server) return;
  const revision = state.mcpToolsDiscoveryRevision = (state.mcpToolsDiscoveryRevision || 0) + 1;
  state.mcpToolsDiscovering = true;
  state.mcpToolsError = "";
  updateMcpEditorState();
  try {
    const payload = await api("/v1/admin/mcp/servers/discover", {
      method: "POST", body: JSON.stringify({ ...server, tools: draft.tools }),
    }, true);
    if (revision !== state.mcpToolsDiscoveryRevision || state.mcpToolsDraft !== draft) return;
    if (payload.server_id !== server.id) throw new Error("Discovery returned a different server");
    draft.tools = payload.items || [];
    renderMcpTools();
    toast(`Discovered ${draft.tools.length} tool(s)`);
  } catch (error) {
    if (revision !== state.mcpToolsDiscoveryRevision || state.mcpToolsDraft !== draft) return;
    state.mcpToolsError = `Discovery failed: ${error.message}`;
    toast(state.mcpToolsError, true);
  } finally {
    if (revision === state.mcpToolsDiscoveryRevision) {
      state.mcpToolsDiscovering = false;
      updateMcpEditorState();
    }
  }
}

async function saveMcpTools() {
  updateMcpToolsState();
  if (el.saveMcpTools.disabled) return;
  const draft = state.mcpToolsDraft;
  state.mcpToolsSaving = true;
  state.mcpToolsError = "";
  state.mcpToolsRefreshRevision = (state.mcpToolsRefreshRevision || 0) + 1;
  updateMcpEditorState();
  try {
    const latest = await api("/v1/admin/mcp/servers", {}, true);
    const servers = latest.items || [];
    state.mcpServers = servers;
    renderMcpServerOptions();
    loadMcpServerIntoForm();
    renderMcpTools();
    const server = servers.find(item => item.id === draft.serverId);
    if (!server) throw new Error("Server was removed. Cancel to reload.");
    if (JSON.stringify([server.url, server.bearer_token || ""]) !== draft.connection
        || JSON.stringify(server.tools || []) !== draft.baseline) {
      throw new Error("Saved server or tools changed. Cancel to reload.");
    }
    const payload = await api("/v1/admin/mcp/servers", {
      method: "PUT",
      body: JSON.stringify({ items: servers.map(item => item.id === draft.serverId ? { ...item, tools: draft.tools } : item) }),
    }, true);
    state.mcpServers = payload.items || [];
    state.mcpToolsDraft = null;
    renderMcpServerOptions();
    loadMcpServerIntoForm();
    renderMcpTools();
    toast("Tools saved");
  } catch (error) {
    state.mcpToolsError = error.message;
    toast(`Could not save tools: ${error.message}`, true);
  } finally {
    state.mcpToolsSaving = false;
    state.mcpToolsRefreshRevision = (state.mcpToolsRefreshRevision || 0) + 1;
    updateMcpEditorState();
  }
}

async function saveMcpServers() {
  syncMcpServerForm();
  if (el.saveMcpServers.disabled) return;
  const server = state.mcpServerDraft;
  const wasSaved = state.mcpServers.some(item => item.id === server.id);
  state.integrationSaving = true;
  state.mcpToolsRefreshRevision = (state.mcpToolsRefreshRevision || 0) + 1;
  updateMcpEditorState();
  try {
    const latest = await api("/v1/admin/mcp/servers", {}, true);
    const servers = latest.items || [];
    const saved = servers.find(item => item.id === server.id);
    if (wasSaved && !saved) throw new Error("Server was removed. Cancel to reload.");
    const changed = { ...(saved || server), name: server.name, url: server.url,
      bearer_token: server.bearer_token, enabled: server.enabled };
    const payload = await api("/v1/admin/mcp/servers", {
      method: "PUT",
      body: JSON.stringify({ items: saved ? servers.map(item => item.id === server.id ? changed : item) : servers.concat(changed) }),
    }, true);
    state.mcpServers = payload.items || [];
    state.mcpServerDraft = null;
    state.mcpEditBaseline = "";
    renderMcpServerOptions();
    loadMcpServerIntoForm();
    renderMcpTools();
    toast("MCP server saved");
  } catch (error) {
    toast(`Could not save MCP configuration: ${error.message}`, true);
  }
  finally {
    state.integrationSaving = false;
    state.mcpToolsRefreshRevision = (state.mcpToolsRefreshRevision || 0) + 1;
    updateMcpEditorState();
  }
}

async function removeMcpServer() {
  if (!state.activeMcpServerId || state.mcpServerDraft || state.integrationSaving || state.mcpToolsSaving || state.mcpToolsDiscovering) return;
  const serverId = state.activeMcpServerId;
  state.integrationSaving = true;
  state.mcpToolsRefreshRevision = (state.mcpToolsRefreshRevision || 0) + 1;
  updateMcpEditorState();
  try {
    const latest = await api("/v1/admin/mcp/servers", {}, true);
    const payload = await api("/v1/admin/mcp/servers", {
      method: "PUT",
      body: JSON.stringify({ items: (latest.items || []).filter(server => server.id !== serverId) }),
    }, true);
    state.mcpServers = payload.items || [];
    state.activeMcpServerId = state.mcpServers[0]?.id || null;
    renderMcpServerOptions();
    loadMcpServerIntoForm();
    invalidateMcpToolRun();
    renderMcpTools();
    toast("Removed MCP server");
  } catch (error) { toast(error.message, true); }
  finally {
    state.integrationSaving = false;
    state.mcpToolsRefreshRevision = (state.mcpToolsRefreshRevision || 0) + 1;
    updateMcpEditorState();
  }
}

async function runMcpTool() {
  updateMcpToolsState();
  if (el.mcpRunTool.disabled) return;
  const entry = selectedMcpTool();
  if (!entry || entry.server.enabled === false || entry.tool.enabled === false || state.mcpToolsDraft) return;
  const argumentsValue = JSON.parse(el.mcpToolArguments.value || "{}");
  const key = entry.key;
  const revision = state.mcpToolRunRevision = (state.mcpToolRunRevision || 0) + 1;
  state.mcpToolRunning = true;
  el.mcpToolOutput.textContent = "Running tool…";
  updateMcpToolsState();
  try {
    const result = await api("/v1/admin/mcp/tools/call", {
      method: "POST",
      body: JSON.stringify({ server_id: entry.server.id, tool_name: entry.tool.name, arguments: argumentsValue }),
    }, true);
    if (revision !== state.mcpToolRunRevision || key !== state.activeMcpToolKey) return;
    el.mcpToolOutput.textContent = JSON.stringify(result, null, 2);
  } catch (error) {
    if (revision !== state.mcpToolRunRevision || key !== state.activeMcpToolKey) return;
    el.mcpToolOutput.textContent = error.message;
  } finally {
    if (revision === state.mcpToolRunRevision) {
      state.mcpToolRunning = false;
      updateMcpToolsState();
    }
  }
}

async function refreshIntegrations() {
  try { await Promise.all([refreshProviderEndpoints(), refreshMcpServers()]); }
  catch (error) { toast(`Could not refresh integrations: ${error.message}`, true); }
}

function showAdminSection(sectionName) {
  if (sectionName !== "devices" && typeof discardDeviceSelectionChanges === "function") discardDeviceSelectionChanges();
  if (sectionName !== "mcp" && state.providerSetupDraft) cancelProviderConnections();
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
  if (sectionName === "foundations") refreshFoundations();
  if (sectionName === "breaker") refreshBreakerSettings();
  if (sectionName === "overview") refreshDiagnostics();
  if (sectionName === "mcp" && state.adminAuthorized) refreshIntegrations();
  if (sectionName === "tools") {
    renderMcpTools();
    if (state.adminAuthorized) refreshMcpServers();
  }
}

document.querySelectorAll("[data-admin-section]").forEach(button => {
  button.addEventListener("click", () => showAdminSection(button.dataset.adminSection));
});
document.querySelectorAll("[data-admin-back]").forEach(button => {
  button.addEventListener("click", () => showAdminSection("overview"));
});
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
if (el.mcpEditTools) el.mcpEditTools.addEventListener("click", editMcpTools);
if (el.mcpCancelTools) el.mcpCancelTools.addEventListener("click", cancelMcpTools);
if (el.saveMcpTools) el.saveMcpTools.addEventListener("click", saveMcpTools);
if (el.mcpToolsServerFilter) el.mcpToolsServerFilter.addEventListener("change", () => {
  if (state.mcpToolsDraft || state.mcpToolsSaving) return;
  state.mcpToolsServerId = el.mcpToolsServerFilter.value;
  state.mcpToolsError = "";
  renderMcpTools();
});
if (el.mcpToolsSearch) el.mcpToolsSearch.addEventListener("input", () => {
  state.mcpToolsQuery = el.mcpToolsSearch.value;
  renderMcpTools();
});
if (el.mcpToolList) el.mcpToolList.addEventListener("change", () => selectMcpTool(el.mcpToolList.value));
if (el.mcpToolArguments) el.mcpToolArguments.addEventListener("input", updateMcpToolsState);
if (el.mcpToolEnabled) el.mcpToolEnabled.addEventListener("change", () => {
  const entry = selectedMcpTool();
  if (el.mcpToolEnabled.disabled || !state.mcpToolsDraft || entry?.server.id !== state.mcpToolsDraft.serverId) return;
  entry.tool.enabled = el.mcpToolEnabled.checked;
  state.mcpToolsError = "";
  renderMcpTools();
});
if (el.taskProfileEndpointSelect) el.taskProfileEndpointSelect.addEventListener("change", () => {
  if (state.endpointDraft) return;
  const value = el.taskProfileEndpointSelect.value;
  if (value.startsWith("preset:")) { addTaskProfileEndpointFromPreset(value.slice(7)); return; }
  state.activeEndpointId = value || null;
  state.activeEndpointOriginalName = selectedEndpoint()?.name || "";
  loadEndpointIntoForm();
});
if (el.taskProfileAddEndpoint) el.taskProfileAddEndpoint.addEventListener("click", addTaskProfileEndpoint);
if (el.prepareProviderConnections) el.prepareProviderConnections.addEventListener("click", prepareProviderConnections);
if (el.saveProviderConnections) el.saveProviderConnections.addEventListener("click", saveProviderConnections);
if (el.cancelProviderConnections) el.cancelProviderConnections.addEventListener("click", cancelProviderConnections);
if (el.endpointTemplateSelect) el.endpointTemplateSelect.addEventListener("change", applyEndpointTemplate);
if (el.endpointApiKeyVisibility) el.endpointApiKeyVisibility.addEventListener("click", toggleEndpointApiKeyVisibility);
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
  if (endpoint && !assignment.model) toast("Save a model for this endpoint in Endpoints & MCP Servers first", true);
  el.taskProviderSelect.classList.toggle("endpoint-has-key", Boolean(endpoint?.has_api_key || endpoint?.api_key));
  updateTaskSaveState();
});
if (el.taskProfileDiscover) el.taskProfileDiscover.addEventListener("click", discoverTaskProfileModels);
if (el.endpointProbeButton) el.endpointProbeButton.addEventListener("click", probeEndpointToolCalling);
if (el.taskProviderRotation) el.taskProviderRotation.addEventListener("change", syncTaskProviderRotation);
if (el.saveTaskProfile) el.saveTaskProfile.addEventListener("click", saveTaskProfile);
if (el.saveTaskEndpoints) el.saveTaskEndpoints.addEventListener("click", saveTaskProfile);
if (el.taskProfileAddFallback) el.taskProfileAddFallback.addEventListener("click", addTaskFallback);
if (el.taskProfileFallbackList) el.taskProfileFallbackList.addEventListener("change", selectTaskFallback);
if (el.taskProfileFallbackEndpoint) el.taskProfileFallbackEndpoint.addEventListener("change", changeTaskFallbackEndpoint);
if (el.taskProfileFallbackUp) el.taskProfileFallbackUp.addEventListener("click", () => moveTaskFallback(-1));
if (el.taskProfileFallbackDown) el.taskProfileFallbackDown.addEventListener("click", () => moveTaskFallback(1));
if (el.taskProfileFallbackRemove) el.taskProfileFallbackRemove.addEventListener("click", removeTaskFallback);
if (el.taskProfileAddSkill) el.taskProfileAddSkill.addEventListener("click", addTaskSkill);
if (el.taskProfileAddBehavior) el.taskProfileAddBehavior.addEventListener("click", () => {
  el.taskProfileBehaviorSelection?.querySelector("input:not(:disabled)")?.focus();
});
if (el.taskProfileVoiceReferenceId) el.taskProfileVoiceReferenceId.addEventListener("input", () => {
  const assignment = state.taskModelAssignments.find(item => item.task === state.activeTaskProfile);
  if (assignment) assignment.voice_reference_id = el.taskProfileVoiceReferenceId.value;
  updateTaskSaveState();
});
if (el.saveVoiceSettings) el.saveVoiceSettings.addEventListener("click", saveVoiceSettings);
if (el.cancelVoiceSettings) el.cancelVoiceSettings.addEventListener("click", cancelVoiceSettings);
[el.voiceRate, el.voicePitch, el.voiceVolume].forEach((slider) => {
  if (slider) slider.addEventListener("input", () => {
    updateVoiceSliderReadouts();
    renderBodySettingsAvailability();
  });
});
if (el.voiceName) el.voiceName.addEventListener("input", renderBodySettingsAvailability);

const BODY_DEVICE_STORAGE_KEYS = {
  videoinput: "aicognitive_mind.device.videoInput",
  audioinput: "aicognitive_mind.device.audioInput",
  audiooutput: "aicognitive_mind.device.audioOutput",
};
let deviceSelectionDraft = null;
let deviceSelectionBaseline = null;
let deviceSelectionError = "";
let deviceInventoryRequest = 0;

function readDeviceSelections() {
  return Object.fromEntries(Object.entries(BODY_DEVICE_STORAGE_KEYS)
    .map(([kind, key]) => [kind, localStorage.getItem(key)]));
}

function ensureDeviceSelectionDraft() {
  if (deviceSelectionDraft) return true;
  try {
    deviceSelectionBaseline = readDeviceSelections();
    deviceSelectionDraft = Object.fromEntries(Object.entries(deviceSelectionBaseline)
      .map(([kind, value]) => [kind, value || ""]));
    deviceSelectionError = "";
    return true;
  } catch (error) {
    deviceSelectionError = "Could not read device preferences in this browser: " + error.message;
    return false;
  }
}

function selectedDeviceId(kind) {
  try { return localStorage.getItem(BODY_DEVICE_STORAGE_KEYS[kind]) || ""; }
  catch (_) { return ""; }
}

function deviceSelectionIsDirty() {
  return Boolean(deviceSelectionDraft) && Object.keys(BODY_DEVICE_STORAGE_KEYS)
    .some(kind => deviceSelectionDraft[kind] !== (deviceSelectionBaseline[kind] || ""));
}

function updateDeviceSelectionState() {
  const dirty = deviceSelectionIsDirty();
  const valid = Boolean(deviceSelectionDraft) && Object.keys(BODY_DEVICE_STORAGE_KEYS).every(kind => {
    const value = deviceSelectionDraft[kind];
    return value === "" || value === (deviceSelectionBaseline[kind] || "")
      || (state.deviceInventory || []).some(device => device.kind === kind && device.deviceId === value);
  });
  const save = document.getElementById("saveDeviceSelections");
  const cancel = document.getElementById("cancelDeviceSelections");
  const status = document.getElementById("deviceSelectionStatus");
  if (save) save.disabled = !dirty || !valid;
  if (cancel) cancel.disabled = !dirty && !deviceSelectionError;
  if (status) status.textContent = deviceSelectionError || (dirty
    ? (valid ? "Unsaved changes."
      : "A selected device is no longer available. Choose an available device or Cancel.")
    : "");
}

function saveSelectedDevice(kind, deviceId) {
  if (!Object.hasOwn(BODY_DEVICE_STORAGE_KEYS, kind) || !ensureDeviceSelectionDraft()) return;
  deviceSelectionDraft[kind] = deviceId;
  deviceSelectionError = "";
  updateDeviceSelectionState();
}

function saveDeviceSelections() {
  updateDeviceSelectionState();
  if (document.getElementById("saveDeviceSelections")?.disabled || !deviceSelectionDraft) return;
  let before;
  try {
    before = readDeviceSelections();
    if (Object.keys(BODY_DEVICE_STORAGE_KEYS).some(kind => before[kind] !== deviceSelectionBaseline[kind])) {
      deviceSelectionError = "Saved device preferences changed while you were editing. Cancel to reload them before trying again.";
      updateDeviceSelectionState();
      return;
    }
    for (const [kind, key] of Object.entries(BODY_DEVICE_STORAGE_KEYS)) {
      if (deviceSelectionDraft[kind] === (before[kind] || "")) continue;
      if (deviceSelectionDraft[kind]) localStorage.setItem(key, deviceSelectionDraft[kind]);
      else localStorage.removeItem(key);
    }
    deviceSelectionBaseline = readDeviceSelections();
    deviceSelectionDraft = Object.fromEntries(Object.entries(deviceSelectionBaseline)
      .map(([kind, value]) => [kind, value || ""]));
    deviceSelectionError = "";
    renderDeviceSelectionSummary();
    updateDeviceSelectionState();
    toast("Body device choices saved in this browser");
  } catch (error) {
    let restored = Boolean(before);
    if (before) {
      for (const [kind, key] of Object.entries(BODY_DEVICE_STORAGE_KEYS)) {
        try {
          if (localStorage.getItem(key) === before[kind]) continue;
          if (before[kind] === null) localStorage.removeItem(key);
          else localStorage.setItem(key, before[kind]);
        } catch (_) { restored = false; }
      }
    }
    deviceSelectionError = "Could not save device preferences: " + error.message
      + (restored ? ". Previous choices were restored; your draft is still available."
        : ". Some preferences may have changed; Cancel reloads saved values. Your draft has been kept.");
    renderDeviceSelectionSummary();
    updateDeviceSelectionState();
    toast(deviceSelectionError, true);
  }
}

function cancelDeviceSelectionEdit() {
  deviceSelectionDraft = null;
  deviceSelectionBaseline = null;
  deviceSelectionError = "";
  ensureDeviceSelectionDraft();
  renderDeviceInventory();
  renderDeviceSelectionSummary();
  updateDeviceSelectionState();
}

function discardDeviceSelectionChanges() {
  deviceInventoryRequest += 1;
  deviceSelectionDraft = null;
  deviceSelectionBaseline = null;
  deviceSelectionError = "";
}

function renderDeviceSelectionSummary() {
  if (!el.deviceSelectionSummary) return;
  let saved;
  try { saved = readDeviceSelections(); }
  catch (_) {
    el.deviceSelectionSummary.textContent = "Saved device preferences could not be read in this browser.";
    return;
  }
  const labels = [];
  for (const [kind, label] of [["videoinput", "Camera"], ["audioinput", "Microphone"], ["audiooutput", "Speaker"]]) {
    const id = saved[kind] || "";
    const device = (state.deviceInventory || []).find(item => item.kind === kind && item.deviceId === id);
    labels.push(label + ": " + (device?.label || (id ? "Saved device (" + id.slice(0, 8) + "…)" : "Browser default")));
  }
  el.deviceSelectionSummary.textContent = "Saved for this browser — " + labels.join(" · ");
}

function renderDeviceInventory() {
  el.deviceInventoryList.replaceChildren();
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
      picker.dataset.deviceKind = kind;
      picker.setAttribute("aria-label", `Select ${heading.toLowerCase()}`);
      picker.disabled = !deviceSelectionDraft;
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
      const value = deviceSelectionDraft?.[kind] || "";
      if (value && !matches.some(device => device.deviceId === value)) {
        const unavailable = document.createElement("option");
        unavailable.value = value;
        unavailable.textContent = `${value === (deviceSelectionBaseline?.[kind] || "") ? "Saved" : "Selected"} device (${value.slice(0, 8)}…, unavailable)`;
        picker.append(unavailable);
      }
      picker.value = value;
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
}

async function refreshDeviceInventory() {
  const request = ++deviceInventoryRequest;
  if (deviceSelectionDraft && !deviceSelectionError && !deviceSelectionIsDirty()) {
    deviceSelectionDraft = null;
    deviceSelectionBaseline = null;
  }
  ensureDeviceSelectionDraft();
  renderDeviceInventory();
  renderDeviceSelectionSummary();
  updateDeviceSelectionState();
  el.devicePermissionStatus.textContent = "Querying browser device inventory…";
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
    if (request !== deviceInventoryRequest) return;
    state.deviceInventory = devices.filter(device => ["videoinput", "audioinput", "audiooutput"].includes(device.kind));
    const permissions = [
      `Camera permission: ${cameraPermission?.state || "not reported by browser"}`,
      `Microphone permission: ${microphonePermission?.state || "not reported by browser"}`,
    ];
    el.devicePermissionStatus.textContent = `${state.deviceInventory.length} device(s) discovered. ${permissions.join(" · ")}. Labels may be hidden until permission is granted.`;
    renderDeviceInventory();
    renderDeviceSelectionSummary();
    updateDeviceSelectionState();
  } catch (error) {
    if (request !== deviceInventoryRequest) return;
    el.devicePermissionStatus.textContent = `Device query failed: ${error.message}. Check browser permissions and reload the page.`;
    toast(`Could not query devices: ${error.message}`, true);
  }
}

document.getElementById("saveDeviceSelections")?.addEventListener("click", saveDeviceSelections);
document.getElementById("cancelDeviceSelections")?.addEventListener("click", cancelDeviceSelectionEdit);

if (navigator.mediaDevices?.addEventListener) {
  navigator.mediaDevices.addEventListener("devicechange", () => refreshDeviceInventory());
}

// Render the built-in task list immediately so the workspace remains navigable
// even if an admin configuration request fails or is slow.
renderTaskProfiles();
refresh();

function foundationIdentityText(value) {
  if (value === null || value === undefined || value === "") return "Unknown";
  if (Array.isArray(value)) return value.length ? value.map(foundationIdentityText).join("\n") : "None recorded";
  if (typeof value === "object") {
    return Object.entries(value).map(([key, detail]) => `${displayLabel(key)}: ${foundationIdentityText(detail)}`).join("\n") || "None recorded";
  }
  return String(value);
}

function renderIdentityConfiguration() {
  const value = state.foundationIdentity;
  const identity = value?.identity || {};
  const fields = {
    SelfName: value ? identity.self_name || "Not selected" : "Unknown",
    Pronouns: identity.pronouns,
    Development: value?.developmental_state,
    Values: identity.foundational_values,
    Commitments: identity.commitments,
    Relationships: identity.relationships,
  };
  for (const [name, detail] of Object.entries(fields)) {
    const output = document.getElementById("foundation" + name);
    if (output) output.textContent = foundationIdentityText(detail);
  }
}

async function refreshIdentityConfiguration() {
  const revision = state.identityConfigurationLoadRevision = (state.identityConfigurationLoadRevision || 0) + 1;
  const status = document.getElementById("foundationStatus");
  if (status) status.textContent = "Loading identity…";
  try {
    const result = await api("/v1/admin/identity", {}, true);
    if (revision !== state.identityConfigurationLoadRevision) return;
    state.foundationIdentity = result;
    renderIdentityConfiguration();
    if (status) status.textContent = "Identity loaded.";
  } catch (error) {
    if (revision !== state.identityConfigurationLoadRevision) return;
    state.foundationIdentity = null;
    renderIdentityConfiguration();
    if (status) status.textContent = error.message;
  }
}

function renderStartupConfiguration() {
  const value = state.cognitiveDraft || state.cognitiveConfiguration;
  document.getElementById("foundationContract").value = value?.base_contract ?? "";
  document.getElementById("foundationStartup").value = value?.startup_instructions ?? "";
  updateStartupEditorState();
}

function updateStartupEditorState() {
  const editing = Boolean(state.cognitiveDraft);
  const busy = state.cognitiveSaving === true;
  const payload = {
    base_contract: document.getElementById("foundationContract").value,
    startup_instructions: document.getElementById("foundationStartup").value,
  };
  for (const id of ["foundationContract", "foundationStartup"]) document.getElementById(id).readOnly = !editing || busy;
  document.getElementById("startupEdit").disabled = !state.cognitiveConfiguration || editing || busy;
  document.getElementById("startupCancel").disabled = !editing || busy;
  document.getElementById("startupSave").disabled = !editing || busy || JSON.stringify(payload) === state.cognitiveDraft?.baseline;
}

async function refreshStartupConfiguration() {
  if (state.cognitiveDraft || state.cognitiveSaving) return;
  const revision = state.startupConfigurationLoadRevision = (state.startupConfigurationLoadRevision || 0) + 1;
  try {
    const result = await api("/v1/admin/cognitive-configuration", {}, true);
    if (revision !== state.startupConfigurationLoadRevision || state.cognitiveDraft || state.cognitiveSaving) return;
    state.cognitiveConfiguration = result;
    renderStartupConfiguration();
    document.getElementById("startupStatus").textContent = "";
  } catch (error) {
    if (revision === state.startupConfigurationLoadRevision && !state.cognitiveDraft && !state.cognitiveSaving) document.getElementById("startupStatus").textContent = error.message;
  }
}

function editStartupConfiguration() {
  if (!state.cognitiveConfiguration || state.cognitiveDraft || state.cognitiveSaving) return;
  state.startupConfigurationLoadRevision = (state.startupConfigurationLoadRevision || 0) + 1;
  const { base_contract, startup_instructions, revision } = state.cognitiveConfiguration;
  state.cognitiveDraft = { base_contract, startup_instructions, revision, baseline: JSON.stringify({ base_contract, startup_instructions }) };
  renderStartupConfiguration();
  document.getElementById("startupStatus").textContent = "Editing startup configuration.";
}

function cancelStartupConfiguration() {
  if (state.cognitiveSaving) return;
  state.cognitiveDraft = null;
  renderStartupConfiguration();
  document.getElementById("startupStatus").textContent = "Changes cancelled.";
}

async function saveStartupConfiguration() {
  updateStartupEditorState();
  if (document.getElementById("startupSave").disabled) return;
  const payload = {
    expected_revision: state.cognitiveDraft.revision,
    base_contract: document.getElementById("foundationContract").value,
    startup_instructions: document.getElementById("foundationStartup").value,
  };
  state.cognitiveSaving = true;
  updateStartupEditorState();
  try {
    state.cognitiveConfiguration = await api("/v1/admin/cognitive-configuration", { method: "PUT", body: JSON.stringify(payload) }, true);
    state.cognitiveDraft = null;
    renderStartupConfiguration();
    document.getElementById("startupStatus").textContent = "Startup configuration saved for this Mind.";
  } catch (error) { document.getElementById("startupStatus").textContent = error.message; }
  finally { state.cognitiveSaving = false; updateStartupEditorState(); }
}

async function refreshFoundations() {
  await Promise.all([refreshIdentityConfiguration(), refreshStartupConfiguration()]);
}

const breakerFieldIds = {
  consecutive_failure_limit: "breakerConsecutiveLimit",
  rolling_failure_limit: "breakerRollingLimit",
  rolling_window_size: "breakerRollingWindow",
  provider_request_timeout_seconds: "breakerProviderTimeout",
  steward_assessment_timeout_seconds: "breakerAssessmentTimeout",
  rate_limit_retry_wait_cap_seconds: "breakerRetryWaitCap",
};

function breakerFormPayload() {
  return Object.fromEntries(Object.entries(breakerFieldIds).map(([key, id]) => [
    key, Number(document.getElementById(id).value),
  ]));
}

function breakerFormValid(payload = breakerFormPayload()) {
  const integerFields = [
    "consecutive_failure_limit", "rolling_failure_limit", "rolling_window_size",
  ];
  if (!Object.values(payload).every(Number.isFinite)) return false;
  if (!integerFields.every(key => Number.isInteger(payload[key]))) return false;
  if (payload.consecutive_failure_limit < 1 || payload.consecutive_failure_limit > 20) return false;
  if (payload.rolling_window_size < 20 || payload.rolling_window_size > 500) return false;
  if (payload.rolling_failure_limit < payload.consecutive_failure_limit || payload.rolling_failure_limit > payload.rolling_window_size) return false;
  if (payload.provider_request_timeout_seconds < 1 || payload.provider_request_timeout_seconds > 120) return false;
  if (payload.steward_assessment_timeout_seconds < 5 || payload.steward_assessment_timeout_seconds > 300) return false;
  return payload.rate_limit_retry_wait_cap_seconds >= 0 && payload.rate_limit_retry_wait_cap_seconds <= 120;
}

function renderBreakerSettings() {
  const value = state.breakerDraft || state.breakerSettings;
  for (const [key, id] of Object.entries(breakerFieldIds)) {
    document.getElementById(id).value = value?.[key] ?? "";
  }
  const health = state.breakerSettings?.health || {};
  document.getElementById("breakerHealthStatus").textContent = displayLabel(health.status || "unavailable");
  document.getElementById("breakerHealthConsecutive").textContent = Number.isInteger(health.consecutive_failures)
    ? `${health.consecutive_failures} / ${state.breakerSettings?.consecutive_failure_limit ?? "—"}` : "—";
  document.getElementById("breakerHealthRolling").textContent = Number.isInteger(health.rolling_failures)
    ? `${health.rolling_failures} / ${state.breakerSettings?.rolling_failure_limit ?? "—"} in ${health.rolling_sample_size ?? 0} of ${state.breakerSettings?.rolling_window_size ?? "—"}` : "—";
  document.getElementById("breakerHealthLastFailure").textContent = health.last_failure_class || "None";
  updateBreakerEditorState();
}

function updateBreakerEditorState() {
  const editing = Boolean(state.breakerDraft);
  const busy = state.breakerSaving === true;
  const payload = breakerFormPayload();
  for (const id of Object.values(breakerFieldIds)) {
    document.getElementById(id).readOnly = !editing || busy;
  }
  document.getElementById("breakerEdit").disabled = !state.breakerSettings || editing || busy;
  document.getElementById("breakerCancel").disabled = !editing || busy;
  document.getElementById("breakerSave").disabled = !editing || busy
    || !breakerFormValid(payload) || JSON.stringify(payload) === state.breakerDraft?.baseline;
}

async function refreshBreakerSettings() {
  if (state.breakerDraft || state.breakerSaving) return;
  const revision = state.breakerLoadRevision = (state.breakerLoadRevision || 0) + 1;
  const status = document.getElementById("breakerSettingsStatus");
  if (status) status.textContent = "Loading The Breaker settings…";
  try {
    const result = await api("/v1/admin/continuity-settings", {}, true);
    if (revision !== state.breakerLoadRevision || state.breakerDraft || state.breakerSaving) return;
    state.breakerSettings = result;
    renderBreakerSettings();
    if (status) status.textContent = "";
  } catch (error) {
    if (revision === state.breakerLoadRevision && !state.breakerDraft && !state.breakerSaving && status) status.textContent = error.message;
  }
}

function editBreakerSettings() {
  if (!state.breakerSettings || state.breakerDraft || state.breakerSaving) return;
  state.breakerLoadRevision = (state.breakerLoadRevision || 0) + 1;
  const values = Object.fromEntries(Object.keys(breakerFieldIds).map(key => [key, state.breakerSettings[key]]));
  state.breakerDraft = { ...values, revision: state.breakerSettings.revision, baseline: JSON.stringify(values) };
  renderBreakerSettings();
  document.getElementById("breakerSettingsStatus").textContent = "Editing The Breaker settings.";
}

function cancelBreakerSettings() {
  if (state.breakerSaving) return;
  state.breakerDraft = null;
  renderBreakerSettings();
  document.getElementById("breakerSettingsStatus").textContent = "Changes cancelled.";
}

async function saveBreakerSettings() {
  updateBreakerEditorState();
  if (document.getElementById("breakerSave").disabled) return;
  const payload = { expected_revision: state.breakerDraft.revision, ...breakerFormPayload() };
  state.breakerSaving = true;
  updateBreakerEditorState();
  try {
    state.breakerSettings = await api("/v1/admin/continuity-settings", {
      method: "PUT", body: JSON.stringify(payload),
    }, true);
    state.breakerDraft = null;
    renderBreakerSettings();
    document.getElementById("breakerSettingsStatus").textContent = "The Breaker settings were saved for this Mind.";
  } catch (error) {
    document.getElementById("breakerSettingsStatus").textContent = error.message;
  } finally {
    state.breakerSaving = false;
    updateBreakerEditorState();
  }
}

for (const id of ["foundationContract", "foundationStartup"]) document.getElementById(id)?.addEventListener("input", updateStartupEditorState);
document.getElementById("startupEdit")?.addEventListener("click", editStartupConfiguration);
document.getElementById("startupCancel")?.addEventListener("click", cancelStartupConfiguration);
document.getElementById("startupSave")?.addEventListener("click", saveStartupConfiguration);
for (const id of Object.values(breakerFieldIds)) document.getElementById(id)?.addEventListener("input", updateBreakerEditorState);
document.getElementById("breakerEdit")?.addEventListener("click", editBreakerSettings);
document.getElementById("breakerCancel")?.addEventListener("click", cancelBreakerSettings);
document.getElementById("breakerSave")?.addEventListener("click", saveBreakerSettings);
let skillDraftSha = null;
let skillCatalog = [];
let skillDraftsAvailable = false;
let skillLoadFailed = false;
let skillLoadRevision = 0;
let skillSavedItem = null;
let skillSelectionKind = "mind";
let skillEditing = false;
let skillSaving = false;
let skillFormBaseline = "";
function skillPayload() {
  const payload = {
    slug: document.getElementById("skillsSlug").value.trim(),
    content: document.getElementById("skillsContent").value,
  };
  if (skillSelectionKind === "github") return { ...payload, sha: skillDraftSha };
  return {
    ...payload,
    name: document.getElementById("skillsName").value.trim(),
    enabled: document.getElementById("skillsEnabled").checked,
    required: document.getElementById("skillsRequired").checked,
    protected: document.getElementById("skillsProtected").checked,
    required_tasks: skillSavedItem?.required_tasks || [],
    revision: skillSavedItem?.revision ?? 0,
  };
}
function updateSkillEditorState() {
  const payload = skillPayload();
  const mind = skillSelectionKind === "mind";
  const locked = !skillEditing || skillLoadFailed || skillSaving || (!mind && !skillDraftsAvailable);
  document.getElementById("skillsSlug").readOnly = locked || Boolean(skillSavedItem);
  document.getElementById("skillsContent").readOnly = locked;
  document.getElementById("skillsName").readOnly = locked;
  const taskRequired = Boolean(skillSavedItem?.required_tasks?.length);
  for (const id of ["skillsEnabled", "skillsRequired", "skillsProtected"]) document.getElementById(id).disabled = locked || taskRequired;
  document.getElementById("skillsNameField").classList.toggle("hidden", !mind);
  document.getElementById("skillsConfigurationFlags").classList.toggle("hidden", !mind);
  document.getElementById("skillsList").disabled = skillEditing || skillSaving;
  document.getElementById("skillsEdit").disabled = !skillSavedItem || skillEditing || skillSaving || skillLoadFailed;
  document.getElementById("skillsCancel").disabled = !skillEditing || skillSaving;
  const valid = /^[a-z0-9][a-z0-9-]{0,63}$/.test(payload.slug) && (mind ? payload.name : payload.content.trim());
  document.getElementById("skillsSave").disabled = locked || !valid || JSON.stringify(payload) === skillFormBaseline;
  document.getElementById("skillsSave").textContent = mind ? "Save Mind Skill" : "Save Draft to GitHub";
  document.getElementById("skillsValidate").disabled = skillLoadFailed || skillSaving || !payload.slug || !payload.content.trim();
  document.getElementById("skillsPrepare").disabled = skillLoadFailed || skillSaving || !payload.slug || !payload.content.trim();
}
function fillSkillForm(item) {
  document.getElementById("skillsSlug").value = item?.slug || "";
  document.getElementById("skillsContent").value = item?.content || "";
  document.getElementById("skillsName").value = item?.name || "";
  document.getElementById("skillsEnabled").checked = item?.enabled !== false;
  document.getElementById("skillsRequired").checked = item?.required === true;
  document.getElementById("skillsProtected").checked = item?.protected === true;
}
async function loadSkillSelection(value) {
  const revision = ++skillLoadRevision;
  skillDraftSha = null;
  skillLoadFailed = false;
  skillSavedItem = null;
  const selected = skillCatalog.find(item => item.selection === value);
  skillSelectionKind = selected?.kind || (value === "new:github" ? "github" : "mind");
  skillEditing = !selected;
  fillSkillForm(null);
  document.getElementById("skillsSource").textContent = skillSelectionKind === "mind"
    ? "Mind configuration. Enabled skills marked Load at startup are applied to this Mind's interactions."
    : "GitHub draft. Saving a draft does not change this Mind or publish to ChatGPT.";
  updateSkillEditorState();
  if (!selected) { skillFormBaseline = ""; return; }
  try {
    const item = selected.kind === "mind" ? selected : await api("/v1/admin/skills/" + encodeURIComponent(selected.slug) + "?source=github_draft", {}, true);
    if (revision !== skillLoadRevision) return;
    skillSavedItem = JSON.parse(JSON.stringify({ ...selected, ...item }));
    skillDraftSha = item.sha ?? null;
    fillSkillForm(skillSavedItem);
    skillFormBaseline = JSON.stringify(skillPayload());
  } catch (error) {
    if (revision !== skillLoadRevision) return;
    skillLoadFailed = true;
    document.getElementById("skillsStatus").textContent = error.message;
  }
  updateSkillEditorState();
}
async function refreshSkillDrafts() {
  if (skillEditing || skillSaving) return;
  const revision = ++skillLoadRevision;
  const list = document.getElementById("skillsList");
  try {
    const [configuration, data] = await Promise.all([
      api("/v1/admin/skill-configurations", {}, true), api("/v1/admin/skills", {}, true),
    ]);
    if (revision !== skillLoadRevision || skillEditing || skillSaving) return;
    const previous = list.value;
    skillCatalog = [
      ...configuration.items.map(item => ({ ...item, kind: "mind", selection: "mind:" + item.slug })),
      ...data.items.filter(item => !configuration.items.some(config => config.slug === item.slug && item.source !== "github_draft" && !item.path?.startsWith("skills/drafts/")))
        .map(item => ({ ...item, kind: "github", selection: "github:" + item.slug })),
    ];
    skillDraftsAvailable = data.drafts_available !== false;
    const newDraft = new Option("New GitHub draft", "new:github");
    newDraft.disabled = !skillDraftsAvailable;
    list.replaceChildren(new Option("New Mind skill", "new:mind"), newDraft);
    for (const item of skillCatalog) list.add(new Option((item.name || item.slug) + (item.kind === "mind" ? " · Mind" : " · GitHub draft"), item.selection));
    list.value = skillCatalog.some(item => item.selection === previous) ? previous : skillCatalog[0]?.selection || "new:mind";
    const message = skillDraftsAvailable ? "Mind skills and GitHub drafts loaded."
      : "Mind skills available. Custom drafts unavailable: " + (data.drafts_error || "Draft access is unavailable.");
    document.getElementById("skillsStatus").textContent = message;
    await loadSkillSelection(list.value);
  } catch (error) {
    if (revision !== skillLoadRevision || skillEditing || skillSaving) return;
    skillLoadFailed = true;
    updateSkillEditorState();
    document.getElementById("skillsStatus").textContent = error.message;
  }
}
document.getElementById("skillsList")?.addEventListener("change", event => loadSkillSelection(event.target.value));
for (const id of ["skillsSlug", "skillsContent", "skillsName", "skillsEnabled", "skillsRequired", "skillsProtected"]) {
  document.getElementById(id)?.addEventListener("input", updateSkillEditorState);
  document.getElementById(id)?.addEventListener("change", updateSkillEditorState);
}
document.getElementById("skillsEdit")?.addEventListener("click", () => {
  if (!skillSavedItem || skillSaving || skillLoadFailed) return;
  skillLoadRevision += 1;
  skillEditing = true;
  updateSkillEditorState();
});
document.getElementById("skillsCancel")?.addEventListener("click", async () => {
  if (skillSaving) return;
  skillEditing = false;
  if (skillSavedItem) {
    fillSkillForm(skillSavedItem);
    skillDraftSha = skillSavedItem.sha ?? null;
    skillFormBaseline = JSON.stringify(skillPayload());
    updateSkillEditorState();
  } else await loadSkillSelection(skillCatalog[0]?.selection || "new:mind");
});
document.getElementById("skillsValidate")?.addEventListener("click", async () => {
  const status = document.getElementById("skillsStatus");
  try {
    const result = await api("/v1/admin/skills/validate", {method:"POST",body:JSON.stringify(skillPayload())}, true);
    status.textContent = result.valid ? "SKILL.md validation passed." : result.errors.join("; ");
  } catch (error) { status.textContent = error.message; }
});
document.getElementById("skillsSave")?.addEventListener("click", async () => {
  const status = document.getElementById("skillsStatus");
  updateSkillEditorState();
  if (document.getElementById("skillsSave").disabled) return;
  const payload = skillPayload();
  const kind = skillSelectionKind;
  skillSaving = true;
  updateSkillEditorState();
  try {
    const url = kind === "mind" ? "/v1/admin/skill-configurations/" : "/v1/admin/skills/";
    const result = await api(url + encodeURIComponent(payload.slug) + (kind === "github" ? "?source=github_draft" : ""), {method:"PUT",body:JSON.stringify(payload)}, true);
    skillEditing = false;
    skillSaving = false;
    document.getElementById("skillsList").value = kind + ":" + payload.slug;
    await refreshSkillDrafts();
    if (skillCatalog.some(item => item.selection === kind + ":" + payload.slug)) {
      document.getElementById("skillsList").value = kind + ":" + payload.slug;
      await loadSkillSelection(kind + ":" + payload.slug);
    }
    status.textContent = kind === "mind" ? "Skill configuration saved for this Mind."
      : "Saved draft to GitHub commit " + result.commit.slice(0,8) + ". Not published to ChatGPT.";
  } catch (error) { status.textContent = error.message; }
  finally { skillSaving = false; updateSkillEditorState(); }
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

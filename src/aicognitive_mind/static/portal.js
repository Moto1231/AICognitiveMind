const state = {
  status: null,
  memoryPages: {
    mind: { items: [], total: 0, hasMore: false, nextOffset: 0 },
    admin: { items: [], total: 0, hasMore: false, nextOffset: 0 },
  },
  memoryPageSize: 25,
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
};

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
  memorySearch: document.getElementById("memorySearch"),
  memoryClassFilter: document.getElementById("memoryClassFilter"),
  associationFilter: document.getElementById("associationFilter"),
  groundingFilter: document.getElementById("groundingFilter"),
  formedFrom: document.getElementById("formedFrom"),
  formedTo: document.getElementById("formedTo"),
  memorySort: document.getElementById("memorySort"),
  clearMemoryFilters: document.getElementById("clearMemoryFilters"),
  memoryResultCount: document.getElementById("memoryResultCount"),
  loadMoreMemories: document.getElementById("loadMoreMemories"),
  refreshButton: document.getElementById("refreshButton"),
  adminRefreshButton: document.getElementById("adminRefreshButton"),
  protocolValue: document.getElementById("protocolValue"),
  reasoningOwner: document.getElementById("reasoningOwner"),
  identityOwner: document.getElementById("identityOwner"),
  memoryOwner: document.getElementById("memoryOwner"),
  adminMindName: document.getElementById("adminMindName"),
  adminMemoryCount: document.getElementById("adminMemoryCount"),
  adminJournalCount: document.getElementById("adminJournalCount"),
  adminAuthorizationState: document.getElementById("adminAuthorizationState"),
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
  adminLoadMoreMemories: document.getElementById("adminLoadMoreMemories"),
  journalRefreshButton: document.getElementById("journalRefreshButton"),
  journalSearch: document.getElementById("journalSearch"),
  journalKindFilter: document.getElementById("journalKindFilter"),
  journalFrom: document.getElementById("journalFrom"),
  journalTo: document.getElementById("journalTo"),
  journalSort: document.getElementById("journalSort"),
  clearJournalFilters: document.getElementById("clearJournalFilters"),
  journalResultCount: document.getElementById("journalResultCount"),
  journalTimeline: document.getElementById("journalTimeline"),
  loadMoreJournals: document.getElementById("loadMoreJournals"),
  journalInspector: document.getElementById("journalInspector"),
  closeJournalInspector: document.getElementById("closeJournalInspector"),
  journalInspectorKind: document.getElementById("journalInspectorKind"),
  journalInspectorOccurredAt: document.getElementById("journalInspectorOccurredAt"),
  journalStructuredDetail: document.getElementById("journalStructuredDetail"),
  journalInspectorRaw: document.getElementById("journalInspectorRaw"),
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
    const detail = payload && typeof payload === "object" && payload.detail
      ? payload.detail
      : `Request failed (${response.status})`;
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
    el.adminAuthorizationState.textContent = pinRequired ? "Authorized" : "Local Admin";
    return true;
  } catch (error) {
    state.adminAuthorized = false;
    if (error.status === 401) {
      sessionStorage.removeItem("acm_admin_pin");
      state.adminPin = "";
      el.adminAuthorizationState.textContent = "Authorization Required";
      toast("Administrator authorization was not accepted", true);
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
    await Promise.all([
      refreshMemory(filters.admin, true),
      refreshJournal(true),
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

  el.protocolValue.textContent = integration.protocol;
  el.reasoningOwner.textContent = integration.reasoning_owner;
  el.identityOwner.textContent = integration.identity_owner;
  el.memoryOwner.textContent = integration.memory_owner;
  el.adminMindName.textContent = mind.identity.self_name;
  el.adminMemoryCount.textContent = Number(status.durable_memory_count).toLocaleString();
  el.adminJournalCount.textContent = Number(status.journal_experience_count).toLocaleString();

  if (!state.adminAuthorized) {
    el.adminAuthorizationState.textContent = status.administration?.pin_required
      ? "PIN Required"
      : "Local Admin";
  }

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
      return `${index + 1}. ${item.response_excerpt} [${meaning.subject || "?"} · ${meaning.attribute || "?"} = ${meaning.value ?? "?"}]`;
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
    limit: String(state.memoryPageSize),
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

    if (reset) {
      pageState.items = page.items;
    } else {
      pageState.items.push(...page.items);
    }
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
    preview.textContent = entry.preview || "Open to inspect the exact journal record.";

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
      ? `\nMeaning: ${interpretation.subject} · ${interpretation.attribute} = ${interpretation.value}`
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
    el.journalInspectorRaw.textContent = JSON.stringify(entry, null, 2);
    el.journalInspector.classList.remove("hidden");
    el.closeJournalInspector.focus();
  } catch (error) {
    toast(error.message, true);
  }
}

function closeJournalInspector() {
  state.activeJournal = null;
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

    if (reset) {
      state.journals = page.items;
    } else {
      state.journals.push(...page.items);
    }
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

async function refreshStatus() {
  const status = await api("/v1/portal/status");
  renderStatus(status);
  return status;
}

async function refresh() {
  try {
    await Promise.all([
      refreshStatus(),
      refreshMemory(filters.mind, true),
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
el.refreshButton.addEventListener("click", () => Promise.all([
  refreshStatus(),
  refreshMemory(filters.mind, true),
]));
el.adminRefreshButton.addEventListener("click", () => Promise.all([
  refreshStatus(),
  refreshMemory(filters.admin, true),
  refreshJournal(true),
]));
el.journalRefreshButton.addEventListener("click", () => refreshJournal(true));
el.loadMoreJournals.addEventListener("click", () => refreshJournal(false));
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
el.adminLoadMoreMemories.addEventListener("click", () => refreshMemory(filters.admin, false));
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

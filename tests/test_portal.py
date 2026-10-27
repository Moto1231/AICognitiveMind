import unittest
from html.parser import HTMLParser
from types import SimpleNamespace

from starlette.requests import Request

from aicognitive_mind.api import (
    STATIC_DIR,
    AdminMemoryRevisionRequest,
    _journal_summary,
    app,
    revise_memory,
)
from aicognitive_mind.domain import (
    CognitiveActor,
    DurableMemory,
    JournalEntry,
    JournalKind,
    MemoryArtifact,
    MemoryClass,
)
from aicognitive_mind.storage import InMemoryJournalStore, InMemoryMemoryStore


class PortalPageMap(HTMLParser):
    """Locate controls by their actual Administration page, including duplicates."""

    def __init__(self, markup: str) -> None:
        super().__init__()
        self.articles = []
        self.elements = {}
        self.duplicate_ids = set()
        self.page_controls = {}
        self.navigation = {}
        self.active_navigation = None
        self.feed(markup)

    def handle_starttag(self, tag, attrs) -> None:
        attributes = dict(attrs)
        if tag == "article":
            self.articles.append(attributes.get("id"))
        page = self.articles[-1] if self.articles else None
        if page:
            self.page_controls.setdefault(page, []).append((tag, attributes))
        element_id = attributes.get("id")
        if element_id:
            if element_id in self.elements:
                self.duplicate_ids.add(element_id)
            self.elements[element_id] = (tag, attributes, page)
        if tag == "button" and "data-admin-section" in attributes:
            self.active_navigation = attributes["data-admin-section"]
            self.navigation[self.active_navigation] = {"attributes": attributes, "text": ""}

    def handle_data(self, data) -> None:
        if self.active_navigation:
            self.navigation[self.active_navigation]["text"] += data

    def handle_endtag(self, tag) -> None:
        if tag == "article":
            self.articles.pop()
        if tag == "button":
            self.active_navigation = None


class PortalTests(unittest.TestCase):
    def test_all_portal_icons_share_one_transparent_neon_component(self) -> None:
        markup = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        stylesheet = (STATIC_DIR / "portal.css").read_text(encoding="utf-8")
        button_icons = (STATIC_DIR / "button_icons.js").read_text(encoding="utf-8")

        sections = {
            "overview": "overview", "foundations": "foundations", "breaker": "breaker",
            "behaviors": "behaviors",
            "devices": "devices", "voice": "voice", "tasks": "tasks", "mcp": "mcp",
            "tools": "tools", "skills": "skills", "memories": "memories", "journals": "journals",
        }
        for section, icon in sections.items():
            button = markup.split(f'data-admin-section="{section}"', 1)[1].split("</button>", 1)[0]
            with self.subTest(section=section):
                self.assertIn('<svg class="admin-line-icon"', button)
                self.assertIn(f'<use href="#admin-icon-{icon}"/>', button)
                self.assertNotIn("<img", button)
                self.assertNotIn("#8cdfe9", button)
                self.assertNotIn("style=", button)

        top_menu = {
            "mindTab": "home",
            "adminTab": "administration",
            'href="/body/live"': "live",
            "portalReturnButton": "return",
            "logoutButton": "logout",
        }
        for control, icon in top_menu.items():
            control_markup = markup.split(control, 1)[1].split("</", 1)[0]
            with self.subTest(top_menu_control=control):
                self.assertIn('class="axiom-line-icon top-menu-icon"', control_markup)
                self.assertIn(f'<use href="#menu-icon-{icon}"/>', control_markup)
                self.assertNotIn("<img", control_markup)

        brand = markup.split('class="brand-logo axiom-icon-art"', 1)[1].split("</svg>", 1)[0]
        self.assertIn('href="/static/axiom-logo.png"', brand)
        self.assertIn('filter="url(#axiom-brand-cutout)"', brand)
        self.assertNotIn('<img class="brand-logo"', markup)
        self.assertIn('<feFlood class="axiom-brand-palette"', markup)

        self.assertIn("--icon-line-color: #83dffe", stylesheet)
        self.assertIn("--icon-line-glow: rgba(70,182,255,.65)", stylesheet)
        self.assertIn("--icon-line-stroke: 1.4", stylesheet)
        self.assertIn(".axiom-icon-definitions,", stylesheet)
        self.assertIn(".admin-icon-definitions {", stylesheet)
        self.assertIn(".axiom-icon-art,", stylesheet)
        self.assertIn(".axiom-line-icon,", stylesheet)
        self.assertIn(".admin-line-icon {", stylesheet)
        icon_styles = stylesheet.rsplit(".axiom-line-icon,\n.admin-line-icon {", 1)[1].split("}", 1)[0]
        self.assertIn("fill: none", icon_styles)
        self.assertIn("stroke-width: var(--icon-line-stroke)", icon_styles)
        self.assertIn("background: transparent", stylesheet)
        self.assertIn("filter: drop-shadow(0 0 3px var(--icon-line-glow))", stylesheet)
        self.assertIn(".top-menu-icon { width: 28px; height: 28px;", stylesheet)
        self.assertIn(".brand-logo { width: 144px; height: 106px; }", stylesheet)
        self.assertNotIn("admin-section-icon-mcp", stylesheet)
        self.assertNotIn("skills-line-icon", stylesheet)
        self.assertFalse(list(STATIC_DIR.glob("admin-*.svg")))
        self.assertIn("color: var(--icon-line-color, #83dffe)", button_icons)
        self.assertIn("var(--icon-line-glow, rgba(70,182,255,.65))", button_icons)
        self.assertIn("var(--icon-line-stroke, 1.4)", button_icons)
        self.assertNotIn("const halo =", button_icons)
        self.assertNotIn("const light =", button_icons)

    def test_tools_are_reachable_on_their_own_page_and_connection_controls_stay_separate(self) -> None:
        pages = PortalPageMap((STATIC_DIR / "index.html").read_text(encoding="utf-8"))
        script = (STATIC_DIR / "portal.js").read_text(encoding="utf-8")

        self.assertFalse(pages.duplicate_ids, f"Duplicate DOM controls: {pages.duplicate_ids}")
        self.assertEqual(pages.navigation["tools"]["text"].strip(), "Tools")
        self.assertEqual(pages.navigation["tools"]["attributes"]["type"], "button")
        self.assertIn("Endpoints", pages.navigation["mcp"]["text"])
        self.assertIn("MCP", pages.navigation["mcp"]["text"])
        self.assertNotIn("Tools", pages.navigation["mcp"]["text"])
        self.assertRegex(script, r'\btools:\s*"toolsSection"')

        for element_id in (
            "mcpToolsServerFilter", "mcpToolsSearch", "mcpToolList", "mcpToolDetail",
            "mcpToolName", "mcpToolServerName", "mcpToolDescription", "mcpToolSchema",
            "mcpToolEnabled", "mcpToolStatus", "mcpDiscoverTools", "mcpEditTools",
            "saveMcpTools", "mcpCancelTools", "mcpToolArguments", "mcpRunTool", "mcpToolOutput",
        ):
            with self.subTest(tool_control=element_id):
                self.assertEqual(pages.elements[element_id][2], "toolsSection")
        self.assertNotIn("mcpToolRunnerSelect", pages.elements)

        for element_id in (
            "taskProfileEndpointSelect", "taskProfileAddEndpoint", "endpointModelSelect",
            "endpointModelId", "endpointEditButton", "endpointRemoveButton", "saveProviderEndpoints",
            "mcpServerSelect", "mcpServerName", "mcpServerUrl", "mcpServerToken",
            "mcpServerEnabled", "mcpAddServer", "mcpEditServer", "mcpDeleteServer",
            "mcpCancelEdit", "saveMcpServers",
        ):
            with self.subTest(connection_control=element_id):
                self.assertEqual(pages.elements[element_id][2], "mcpSection")

        for page in ("toolsSection", "mcpSection"):
            back_controls = [attrs for tag, attrs in pages.page_controls[page]
                             if tag == "button" and "data-admin-back" in attrs]
            self.assertEqual(len(back_controls), 1)
            self.assertEqual(back_controls[0]["aria-label"], "Back to System Overview")

    def test_tools_page_exposes_search_selection_and_a_locked_runner(self) -> None:
        pages = PortalPageMap((STATIC_DIR / "index.html").read_text(encoding="utf-8"))

        self.assertEqual(pages.elements["mcpToolsServerFilter"][0], "select")
        self.assertEqual(pages.elements["mcpToolsSearch"][1]["type"], "search")
        self.assertEqual(pages.elements["mcpToolList"][0], "select")
        self.assertGreater(int(pages.elements["mcpToolList"][1]["size"]), 1)
        self.assertTrue(pages.elements["mcpToolList"][1].get("aria-label"))
        self.assertEqual(pages.elements["mcpToolArguments"][0], "textarea")
        self.assertEqual(pages.elements["mcpToolEnabled"][1]["type"], "checkbox")
        for element_id in ("mcpToolEnabled", "mcpRunTool", "saveMcpTools", "mcpCancelTools"):
            with self.subTest(element_id=element_id):
                self.assertIn("disabled", pages.elements[element_id][1])
        self.assertEqual(pages.elements["mcpToolOutput"][1]["aria-live"], "polite")

    def test_foundations_keeps_identity_read_only_and_restores_the_startup_editor(self) -> None:
        class Foundations(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self.active = False
                self.fields = {}
                self.controls = []

            def handle_starttag(self, tag, attrs) -> None:
                attributes = dict(attrs)
                if tag == "article":
                    self.active = attributes.get("id") == "foundationsSection"
                if not self.active:
                    return
                if attributes.get("id"):
                    self.fields[attributes["id"]] = (tag, attributes)
                if tag in ("input", "textarea", "select", "button"):
                    self.controls.append((tag, attributes))

            def handle_endtag(self, tag) -> None:
                if tag == "article":
                    self.active = False

        foundations = Foundations()
        foundations.feed((STATIC_DIR / "index.html").read_text(encoding="utf-8"))
        for name in ("SelfName", "Pronouns", "Development", "Values", "Commitments", "Relationships"):
            with self.subTest(name=name):
                self.assertEqual(foundations.fields["foundation" + name][0], "dd")
        self.assertEqual(len(foundations.controls), 6)
        tag, back = foundations.controls[0]
        self.assertEqual(tag, "button")
        self.assertIn("data-admin-back", back)
        self.assertEqual(back["aria-label"], "Back to System Overview")
        self.assertEqual(foundations.fields["foundationStatus"][1]["role"], "status")
        for name in ("foundationContract", "foundationStartup"):
            self.assertEqual(foundations.fields[name][0], "textarea")
            self.assertIn("readonly", foundations.fields[name][1])
        for name in ("startupEdit", "startupSave", "startupCancel"):
            self.assertEqual(foundations.fields[name][0], "button")
            self.assertIn("disabled", foundations.fields[name][1])
        for name in ("foundationEdit", "foundationSave", "foundationCancel"):
            self.assertNotIn(name, foundations.fields)
        self.assertEqual(foundations.fields["startupStatus"][1]["role"], "status")

    def test_breaker_has_its_own_locked_revisioned_parameters_form(self) -> None:
        pages = PortalPageMap((STATIC_DIR / "index.html").read_text(encoding="utf-8"))
        script = (STATIC_DIR / "portal.js").read_text(encoding="utf-8")

        self.assertEqual(pages.navigation["breaker"]["text"].strip(), "The Breaker")
        self.assertRegex(script, r'\bbreaker:\s*"breakerSection"')
        field_ids = (
            "breakerConsecutiveLimit", "breakerRollingLimit", "breakerRollingWindow",
            "breakerProviderTimeout", "breakerAssessmentTimeout", "breakerRetryWaitCap",
        )
        for field_id in field_ids:
            with self.subTest(field_id=field_id):
                tag, attributes, page = pages.elements[field_id]
                self.assertEqual((tag, page), ("input", "breakerSection"))
                self.assertEqual(attributes["type"], "number")
                self.assertIn("readonly", attributes)
        for control_id in ("breakerEdit", "breakerSave", "breakerCancel"):
            self.assertIn("disabled", pages.elements[control_id][1])
        back_controls = [
            attrs for tag, attrs in pages.page_controls["breakerSection"]
            if tag == "button" and "data-admin-back" in attrs
        ]
        self.assertEqual(len(back_controls), 1)
        self.assertEqual(back_controls[0]["aria-label"], "Back to System Overview")
        self.assertEqual(pages.elements["breakerSettingsStatus"][1]["role"], "status")

    def test_endpoint_api_key_is_an_accessible_masked_text_input(self) -> None:
        class Controls(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self.by_id = {}

            def handle_starttag(self, tag, attrs) -> None:
                attributes = dict(attrs)
                if attributes.get("id"):
                    self.by_id[attributes["id"]] = attributes

        controls = Controls()
        controls.feed((STATIC_DIR / "index.html").read_text(encoding="utf-8"))
        field = controls.by_id["taskProfileApiKey"]
        reveal = controls.by_id["endpointApiKeyVisibility"]
        self.assertEqual(field["type"], "text")
        self.assertEqual(field["autocomplete"], "off")
        self.assertEqual(field["autocapitalize"], "off")
        self.assertEqual(field["spellcheck"], "false")
        self.assertIn("is-masked", field["class"].split())
        self.assertIn(field["aria-describedby"], controls.by_id)
        self.assertEqual(reveal["type"], "button")
        self.assertEqual(reveal["aria-controls"], "taskProfileApiKey")
        self.assertNotIn("aria-pressed", reveal)

    def test_admin_save_buttons_use_consistent_label_and_mcp_add_starts_new_record(self) -> None:
        markup = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        script = (STATIC_DIR / "portal.js").read_text(encoding="utf-8")

        for element_id in ("saveHostBehaviors", "saveTaskProfile", "saveMcpServers", "saveMcpTools", "saveVoiceSettings"):
            with self.subTest(element_id=element_id):
                self.assertRegex(markup, rf'id="{element_id}"[^>]*class="primary-button"[^>]*>Save</button>')

        self.assertIn("function editMcpServer()", script)
        self.assertIn("function addMcpServer()", script)
        self.assertIn('name: "",\n    url: "",\n    bearer_token: "",', script)

    def test_task_profile_controls_are_bound_and_renderable(self) -> None:
        markup = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        script = (STATIC_DIR / "portal.js").read_text(encoding="utf-8")
        profile_ids = (
            "taskProfileList",
            "taskProfileEditor",
            "taskProfileTitle",
            "taskProfileBack",
            "taskProfileEndpointSection",
            "taskProfileEndpointSelect",
            "taskProfileAddEndpoint",
            "taskProfileEndpointName",
            "taskProfileBaseUrl",
            "taskProfileApiKey",
            "taskProfileDiscover",
            "taskProfileAssignmentSection",
            "taskProfileModel",
            "taskProfileStandardModelField",
            "taskProfileVoiceModelField",
            "taskProfileVoiceModel",
            "taskProfileVoiceReferenceField",
            "taskProfileVoiceReferenceId",
            "taskProfileFallbackList",
            "taskProfileAddFallback",
            "taskProfileFoundation",
            "taskFoundationEdit",
            "taskFoundationSave",
            "taskFoundationCancel",
            "taskProfileBehaviorName",
            "taskProfileInstructions",
            "taskProfileEnabled",
            "saveTaskProfile",
            "voiceRate",
            "voicePitch",
            "voiceVolume",
            "voiceName",
        )
        for element_id in profile_ids:
            with self.subTest(element_id=element_id):
                self.assertIn(f'id="{element_id}"', markup)
                self.assertIn(
                    f'{element_id}: document.getElementById("{element_id}")',
                    script,
                )
        self.assertIn("function renderTaskProfiles()", script)
        self.assertIn("renderTaskProfiles();", script)
        self.assertRegex(markup, r'<textarea id="taskProfileFoundation"[^>]*readonly')
        self.assertIn("el.taskProfileInstructions.value = behavior.instructions || \"\";", script)
        self.assertIn("el.taskProfileEnabled.checked = behavior.enabled !== false;", script)
        self.assertIn('audio_voice: "Audio/Voice"', script)
        self.assertIn("assignment.fallbacks.push({ provider: \"\", model: \"\" })", script)
        self.assertIn('id="taskProfileFallbackList"', markup)
        self.assertIn('id="voiceRate"', markup)
        self.assertNotIn('id="fishAudioApiKey"', markup)

    def test_portal_assets_are_packaged_and_routes_are_registered(self) -> None:
        index = STATIC_DIR / "index.html"
        stylesheet = STATIC_DIR / "portal.css"
        script = STATIC_DIR / "portal.js"

        self.assertTrue(index.is_file())
        self.assertTrue(stylesheet.is_file())
        self.assertTrue(script.is_file())

        markup = index.read_text(encoding="utf-8")
        stylesheet = (STATIC_DIR / "portal.css").read_text(encoding="utf-8")
        self.assertIn("Administration", markup)
        self.assertRegex(markup, r'/static/portal\.css\?v=[\w-]+')
        self.assertIn("admin-section-nav", stylesheet)
        self.assertIn("linear-gradient(135deg, rgba(15,27,46,.96)", stylesheet)
        self.assertNotIn('content: "Inspect exact record', stylesheet)
        self.assertIn("outline: 2px solid var(--accent)", stylesheet)
        self.assertIn("MCP", markup)
        self.assertIn("MEMORY INSPECTOR", markup)
        self.assertIn("Raw Record Returned by the Mind", markup)
        self.assertIn("Steward Artifacts", markup)

        script_text = script.read_text(encoding="utf-8")
        self.assertIn("JSON.stringify(memory, null, 2)", script_text)
        self.assertIn("memory.grounding", script_text)
        self.assertIn("memory.associations", script_text)
        self.assertIn("renderMemoryArtifacts", script_text)
        self.assertIn("formatEvidenceAppraisal", script_text)
        self.assertIn("formatEvidenceDeliberation", script_text)
        self.assertIn("formatResolutionReadiness", script_text)
        self.assertIn("Resolution Readiness:", script_text)
        self.assertIn("Retained Research Evidence:", script_text)
        self.assertIn("Candidate Side:", script_text)
        self.assertIn("formatResearchEvidence", script_text)
        self.assertIn("Current Evidence Used", script_text)
        self.assertIn("Revision:", script_text)
        self.assertIn("Trigger:", script_text)
        self.assertIn("Evidence Deliberation", script_text)
        self.assertIn("Investigation Questions:", script_text)
        self.assertIn("Confidence:", script_text)
        self.assertIn("Weight:", script_text)
        self.assertIn("Existing Appraisal", script_text)
        self.assertIn("Proposed Appraisal", script_text)
        self.assertIn("artifacts: original.artifacts || []", script_text)
        self.assertIn("adminMemorySearch", script_text)
        self.assertIn("saveMemoryEdit", script_text)
        self.assertIn("memoryQuery", script_text)
        self.assertIn("refreshMemory", script_text)
        self.assertIn("memoryPageSize: 25", script_text)
        self.assertIn("loadMoreMemories", script_text)
        self.assertNotIn("function memoryMatches", script_text)
        self.assertIn("<h3>History</h3>", markup)
        self.assertIn("JOURNAL INSPECTOR", markup)
        self.assertIn("renderJournalList", script_text)
        self.assertIn("openJournalInspector", script_text)
        self.assertIn('entry.kind === "tension"', script_text)
        self.assertIn('entry.kind === "belief_transition"', script_text)
        self.assertIn('entry.kind === "belief_reframe"', script_text)
        self.assertIn("Superseded Belief", script_text)
        self.assertIn("Existing Scoped Belief", script_text)
        self.assertIn("Proposed Scoped Belief", script_text)
        self.assertIn('value="belief_transition">Belief Transition', markup)
        self.assertIn('value="belief_reframe">Belief Reframe', markup)
        self.assertIn("Current Belief", script_text)
        self.assertIn("Existing Value", script_text)
        self.assertIn("Semantic Scope", script_text)
        self.assertIn("Proposed Value", script_text)
        self.assertIn("loadMoreJournals", script_text)
        self.assertIn("journalPageSize: 25", script_text)

        paths = {route.path for route in app.routes if hasattr(route, "path")}
        self.assertIn("/", paths)
        self.assertIn("/v1/portal/status", paths)
        self.assertIn("/v1/portal/memory", paths)
        self.assertIn("/v1/admin/status", paths)
        self.assertIn("/v1/admin/memory", paths)
        self.assertIn("/v1/portal/journal", paths)
        self.assertIn("/v1/portal/journal/detail", paths)

        schema = app.openapi()
        journal_parameters = schema["paths"]["/v1/portal/journal"]["get"]["parameters"]
        journal_limit = next(
            parameter for parameter in journal_parameters if parameter["name"] == "limit"
        )
        self.assertEqual(journal_limit["schema"]["default"], 25)
        self.assertEqual(journal_limit["schema"]["maximum"], 100)

        memory_parameters = schema["paths"]["/v1/portal/memory"]["get"]["parameters"]
        memory_limit = next(
            parameter for parameter in memory_parameters if parameter["name"] == "limit"
        )
        self.assertEqual(memory_limit["schema"]["default"], 25)
        self.assertEqual(memory_limit["schema"]["maximum"], 100)
        memory_parameter_names = {parameter["name"] for parameter in memory_parameters}
        self.assertTrue(
            {
                "search",
                "memory_class",
                "association",
                "grounding",
                "from",
                "to",
                "order",
            }.issubset(memory_parameter_names)
        )

    def test_interaction_journal_summary_is_compact(self) -> None:
        entry = JournalEntry(
            kind=JournalKind.INTERACTION,
            experience={
                "input": {"content": "When is my birthday?"},
                "expression": {"content": "Your birthday is February 7."},
                "memory_steward": {"large": {"nested": "trace"}},
            },
        )

        summary = _journal_summary(entry)

        self.assertEqual(summary["title"], "Interaction")
        self.assertEqual(summary["preview"], "When is my birthday?")
        self.assertIn("February 7", summary["search_text"])
        self.assertNotIn("memory_steward", summary)


    def test_tension_journal_summary_exposes_competing_values(self) -> None:
        entry = JournalEntry(
            kind=JournalKind.TENSION,
            experience={
                "source": "conscious_memory_steward",
                "status": "unresolved",
                "subject": "current_human",
                "attribute": "birthday",
                "competing_values": {
                    "existing": "February 7",
                    "proposed": "February 8",
                },
                "evidence": {
                    "existing": "The user's birthday is February 7.",
                    "proposed": "The user's birthday is February 8.",
                },
                "deliberation": {
                    "existing_support_count": 1,
                    "proposed_support_count": 1,
                    "provenance_relationship": "unknown",
                    "existing_provenance_depth": 0,
                    "proposed_provenance_depth": 0,
                    "appraisal_gaps": [
                        "existing evidence has no appraisal",
                        "proposed evidence has no appraisal",
                    ],
                    "context_observations": [],
                    "investigation_questions": [
                        "Establish enough provenance to compare the competing evidence responsibly."
                    ],
                },
            },
        )

        summary = _journal_summary(entry)

        self.assertEqual(summary["title"], "Semantic Tension")
        self.assertIn("February 7", summary["preview"])
        self.assertIn("February 8", summary["preview"])
        self.assertIn("birthday", summary["search_text"])
        self.assertIn("The user's birthday is February 8.", summary["search_text"])
        self.assertIn("Establish enough provenance", summary["search_text"])
        self.assertIn("unknown", summary["search_text"])

    def test_tension_reassessment_summary_and_search_include_current_evidence(self) -> None:
        entry = JournalEntry(
            kind=JournalKind.TENSION,
            experience={
                "source": "conscious_memory_steward",
                "phase": "reassessment",
                "status": "unresolved",
                "subject": "deployment",
                "attribute": "date",
                "competing_values": {
                    "existing": "October 1",
                    "proposed": "October 8",
                },
                "evidence": {
                    "existing": "The deployment date is October 1.",
                    "proposed": "The deployment date is October 8.",
                },
                "current_evidence": [
                    {
                        "query": "release calendar",
                        "response": "The release board independently lists October 8.",
                        "articles": [],
                        "appraisal": {
                            "confidence": 0.9,
                            "weight": 0.55,
                            "provenance": [
                                {
                                    "source": "release board",
                                    "context": "current release calendar",
                                    "condition": "published",
                                }
                            ],
                            "basis": [],
                        },
                        "semantic_interpretation": {
                            "subject": "deployment",
                            "attribute": "date",
                            "value": "October 8",
                        },
                        "tension_finding": {
                            "subject": "deployment",
                            "attribute": "date",
                            "existing_value": "October 1",
                            "proposed_value": "October 8",
                            "provenance_independence": "verified_independent",
                            "temporal_relationship": "same_timeframe",
                            "contextual_relationship": "same_context",
                            "basis": ["release board is independently maintained"],
                        },
                    }
                ],
                "deliberation": {
                    "subject": "deployment",
                    "attribute": "date",
                    "existing_value": "October 1",
                    "proposed_value": "October 8",
                    "revision": 2,
                    "trigger": "current_evidence_reassessment",
                    "current_evidence_considered": 1,
                    "current_existing_support_count": 0,
                    "current_proposed_support_count": 1,
                    "existing_support_count": 1,
                    "proposed_support_count": 2,
                    "provenance_relationship": "no_overlap_observed",
                    "existing_provenance_depth": 1,
                    "proposed_provenance_depth": 1,
                    "appraisal_gaps": [],
                    "context_observations": [],
                    "investigation_questions": [
                        "Seek independent corroboration for the existing value."
                    ],
                    "resolution_readiness": {
                        "status": "candidate_ready",
                        "candidate_side": "proposed",
                        "candidate_value": "October 8",
                        "existing": {
                            "value": "October 1",
                            "support_count": 1,
                            "appraised_support_count": 1,
                            "distinct_immediate_sources": 1,
                            "confidence_floor": 0.55,
                            "confidence_ceiling": 0.55,
                            "weight_floor": 0.4,
                            "weight_ceiling": 0.4,
                        },
                        "proposed": {
                            "value": "October 8",
                            "support_count": 2,
                            "appraised_support_count": 2,
                            "distinct_immediate_sources": 2,
                            "confidence_floor": 0.8,
                            "confidence_ceiling": 0.9,
                            "weight_floor": 0.7,
                            "weight_ceiling": 0.75,
                        },
                        "blockers": [],
                        "basis": [
                            "Candidate evidence has independent corroboration."
                        ],
                    },
                },
            },
        )

        summary = _journal_summary(entry)

        self.assertEqual(summary["title"], "Tension Reassessment")
        self.assertIn("release board", summary["search_text"])
        self.assertIn("current_evidence_reassessment", summary["search_text"])
        self.assertIn("candidate_ready", summary["search_text"])
        self.assertIn("proposed", summary["search_text"])
        self.assertIn("verified_independent", summary["search_text"])
        self.assertIn("October 8", summary["preview"])

    def test_scoped_tension_summary_exposes_scope(self) -> None:
        entry = JournalEntry(
            kind=JournalKind.TENSION,
            experience={
                "phase": "detected",
                "status": "unresolved",
                "subject": "invoice",
                "attribute": "approval_route",
                "scope": {"kind": "contextual", "label": "Customer A"},
                "competing_values": {
                    "existing": "Alpha",
                    "proposed": "Gamma",
                },
                "evidence": {
                    "existing": "Customer A uses Alpha.",
                    "proposed": "Customer A uses Gamma.",
                },
                "deliberation": {
                    "subject": "invoice",
                    "attribute": "approval_route",
                    "scope": {"kind": "contextual", "label": "Customer A"},
                    "existing_value": "Alpha",
                    "proposed_value": "Gamma",
                    "existing_support_count": 1,
                    "proposed_support_count": 1,
                    "provenance_relationship": "unknown",
                    "existing_provenance_depth": 0,
                    "proposed_provenance_depth": 0,
                    "appraisal_gaps": [
                        "existing evidence has incomplete appraisal",
                        "proposed evidence has incomplete appraisal",
                    ],
                    "context_observations": [],
                    "investigation_questions": [],
                },
            },
        )

        summary = _journal_summary(entry)

        self.assertEqual(summary["title"], "Semantic Tension")
        self.assertIn("Customer A", summary["preview"])
        self.assertIn("Customer A", summary["search_text"])

    def test_belief_transition_summary_exposes_current_and_superseded_values(self) -> None:
        entry = JournalEntry(
            kind=JournalKind.BELIEF_TRANSITION,
            experience={
                "source": "conscious_memory_steward",
                "subject": "deployment",
                "attribute": "date",
                "from_value": "October 1",
                "to_value": "October 8",
                "deliberation_revision": 2,
                "readiness_basis": [
                    "Candidate evidence is independently corroborated."
                ],
                "candidate_evidence": [
                    "The deployment date is October 8."
                ],
                "superseded_evidence": [
                    "The deployment date is October 1."
                ],
                "status": "committed",
            },
        )

        summary = _journal_summary(entry)

        self.assertEqual(summary["title"], "Belief Transition")
        self.assertIn("October 1", summary["preview"])
        self.assertIn("October 8", summary["preview"])
        self.assertIn("deployment", summary["search_text"])
        self.assertIn("independently corroborated", summary["search_text"])
        self.assertIn("committed", summary["search_text"])

    def test_belief_reframe_summary_exposes_scoped_values(self) -> None:
        entry = JournalEntry(
            kind=JournalKind.BELIEF_REFRAME,
            experience={
                "source": "conscious_memory_steward",
                "status": "committed",
                "subject": "service",
                "attribute": "owner",
                "relationship": "temporal",
                "existing_value": "Alice",
                "existing_scope": "before September 1",
                "proposed_value": "Bob",
                "proposed_scope": "on or after September 1",
                "deliberation_revision": 2,
                "basis": ["The ownership record establishes the effective-date change."],
                "existing_evidence": ["The service owner is Alice."],
                "proposed_evidence": ["The service owner is Bob."],
            },
        )

        summary = _journal_summary(entry)

        self.assertEqual(summary["title"], "Belief Reframe")
        self.assertIn("Alice [before September 1]", summary["preview"])
        self.assertIn("Bob [on or after September 1]", summary["preview"])
        self.assertIn("temporal", summary["search_text"])
        self.assertIn("ownership record", summary["search_text"])
        self.assertIn("committed", summary["search_text"])

    def test_memory_revision_summary_exposes_before_and_after_text(self) -> None:
        entry = JournalEntry(
            kind=JournalKind.MEMORY_REVISION,
            experience={
                "source": "human_administrator",
                "before": {"content": "The User's birthday is February 7."},
                "after": {"content": "Will's birthday is February 7."},
            },
        )

        summary = _journal_summary(entry)

        self.assertEqual(summary["title"], "Memory Revision")
        self.assertEqual(summary["preview"], "Will's birthday is February 7.")
        self.assertIn("The User's birthday", summary["search_text"])


class PortalAdministrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_admin_revision_preserves_steward_artifacts(self) -> None:
        memory_store = InMemoryMemoryStore()
        journal_store = InMemoryJournalStore()
        artifact = MemoryArtifact(
            kind="semantic_interpretation",
            payload={"attribute": "birthday", "value": "February 7"},
        )
        original = DurableMemory(
            memory_class=MemoryClass.SEMANTIC,
            content="The user's birthday is February 7.",
            associations=("birthday",),
            grounding=("direct-user-statement",),
            artifacts=(artifact,),
        )
        await memory_store.remember(
            original,
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )

        replacement = original.model_copy(
            update={
                "content": "The user's birthday is February 8.",
                "artifacts": (),
            }
        )
        request = Request(
            {
                "type": "http",
                "method": "PUT",
                "path": "/v1/admin/memory",
                "headers": [],
                "app": SimpleNamespace(
                    state=SimpleNamespace(
                        memory_store=memory_store,
                        journal_store=journal_store,
                    )
                ),
            }
        )

        revised = await revise_memory(
            AdminMemoryRevisionRequest(
                original=original,
                replacement=replacement,
            ),
            request,
        )

        self.assertEqual(revised.content, "The user's birthday is February 8.")
        self.assertEqual(revised.artifacts, (artifact,))
        stored = await memory_store.read()
        self.assertEqual(stored[0].artifacts, (artifact,))
        journal = await journal_store.read()
        self.assertEqual(journal[-1].kind, JournalKind.MEMORY_REVISION)



if __name__ == "__main__":
    unittest.main()

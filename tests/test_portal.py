import unittest
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


class PortalTests(unittest.TestCase):
    def test_portal_assets_are_packaged_and_routes_are_registered(self) -> None:
        index = STATIC_DIR / "index.html"
        stylesheet = STATIC_DIR / "portal.css"
        script = STATIC_DIR / "portal.js"

        self.assertTrue(index.is_file())
        self.assertTrue(stylesheet.is_file())
        self.assertTrue(script.is_file())

        markup = index.read_text(encoding="utf-8")
        self.assertIn("Administration", markup)
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
        self.assertIn("Journal Timeline", markup)
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

        paths = {route.path for route in app.routes}
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

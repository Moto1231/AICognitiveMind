"""Administrator settings and GitHub drafts retain separate save paths."""

import base64
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request

from aicognitive_mind import api
from aicognitive_mind.core_skills import REQUIRED_SKILLS, load_required_skill
from aicognitive_mind.effective_skills import EffectiveSkillRegistry
from aicognitive_mind.host_runtime import RuntimeRecords


DRAFT = "---\nname: custom\ndescription: A custom draft.\n---\n\nKeep the custom workflow.\n"


class AdminSkillTests(unittest.IsolatedAsyncioTestCase):
    def request(self, *, tenant=False, query=""):
        request = Request({"type": "http", "app": api.app, "headers": [], "query_string": query.encode()})
        if tenant:
            request.state.tenant_storage = object()
        return request

    def setUp(self):
        self.settings = patch("aicognitive_mind.api.get_settings", return_value=SimpleNamespace(admin_pin=""))
        self.settings.start()
        self.addCleanup(self.settings.stop)
        self.records = RuntimeRecords(SimpleNamespace())
        self.runtime = patch("aicognitive_mind.api._request_runtime", return_value=SimpleNamespace(runtime_records=self.records))
        self.runtime.start()
        self.addCleanup(self.runtime.stop)

    async def test_core_catalog_is_available_when_github_is_unavailable_or_missing(self):
        for code in (503, 404):
            with self.subTest(code=code), patch("aicognitive_mind.api._skill_github_call", side_effect=HTTPException(
                status_code=code, detail="Synthetic GitHub unavailable",
            )):
                result = await api.list_admin_skills(self.request())
            self.assertEqual({item["slug"] for item in result["items"]}, {*REQUIRED_SKILLS, "memory-steward"})
            self.assertTrue(all(not item["read_only"] for item in result["items"]))
            self.assertTrue(all("content" not in item for item in result["items"]))
            self.assertEqual(result["drafts_available"], code == 404)
            self.assertEqual(bool(result["drafts_error"]), code != 404)

    async def test_root_catalog_preserves_custom_drafts_even_when_names_match_packaged_skills(self):
        with patch("aicognitive_mind.api._skill_github_call", return_value=[
            {"type": "dir", "name": "custom", "path": "skills/drafts/custom"},
            {"type": "dir", "name": REQUIRED_SKILLS[0], "path": "old/core/draft"},
            {"type": "file", "name": "README.md", "path": "skills/drafts/README.md"},
        ]):
            result = await api.list_admin_skills(self.request())
        self.assertEqual([item["slug"] for item in result["items"]], [*REQUIRED_SKILLS, "memory-steward", "custom", REQUIRED_SKILLS[0]])
        self.assertEqual(result["items"][-2], {
            "slug": "custom", "path": "skills/drafts/custom", "required": False, "read_only": False, "source": "github_draft",
        })
        self.assertTrue(result["drafts_available"])

    async def test_core_reads_previews_and_account_catalog_never_contact_github(self):
        with patch("aicognitive_mind.api._skill_github_call", side_effect=AssertionError("No shared GitHub access")) as github:
            result = await api.list_admin_skills(self.request(tenant=True))
            self.assertFalse(result["drafts_available"])
            self.assertEqual({item["slug"] for item in result["items"]}, {*REQUIRED_SKILLS, "memory-steward"})
            for slug in REQUIRED_SKILLS:
                item = await api.get_admin_skill(slug, self.request(tenant=True))
                self.assertEqual(item["content"], load_required_skill(slug))
                self.assertTrue(item["required"] and not item["read_only"])
                self.assertIsNone(item["sha"])
                preview = await api.prepare_admin_skill(slug, self.request(tenant=True))
                self.assertEqual(preview.body.decode(), item["content"])
                self.assertIn(slug + "-SKILL.md", preview.headers["content-disposition"])
            github.assert_not_called()

    async def test_administrator_can_save_formerly_required_skill_without_github_and_preview_saved_text(self):
        with patch("aicognitive_mind.api._skill_github_call") as github:
            for slug in REQUIRED_SKILLS:
                saved = await api.save_admin_skill(slug, api.SkillDraftPayload(
                    slug=slug, content="Administrator instructions", name="Renamed", revision=0,
                    enabled=False, required=False, protected=False,
                ), self.request(tenant=True))
                self.assertEqual(saved["revision"], 1)
                self.assertFalse(saved["required"] or saved["protected"] or saved["enabled"])
                preview = await api.prepare_admin_skill(slug, self.request(tenant=True))
                self.assertEqual(preview.body.decode(), "Administrator instructions")
                with self.assertRaises(HTTPException) as error:
                    await api.save_admin_skill(slug, api.SkillDraftPayload(slug=slug, content="Stale", revision=0), self.request())
                self.assertEqual(error.exception.status_code, 409)
            github.assert_not_called()

    async def test_custom_draft_read_save_and_prepare_retain_existing_workflow(self):
        stored = {"sha": "old-revision", "content": base64.b64encode(DRAFT.encode()).decode()}
        with patch("aicognitive_mind.api._skill_github_call", side_effect=[
            stored, {"content": {"sha": "new-revision"}, "commit": {"sha": "commit-id"}}, stored,
        ]) as github:
            loaded = await api.get_admin_skill("custom", self.request())
            self.assertEqual(loaded, {"slug": "custom", "sha": "old-revision", "content": DRAFT, "source": "github_draft"})
            saved = await api.save_admin_skill("custom", api.SkillDraftPayload(
                slug="custom", content=DRAFT, sha="old-revision",
            ), self.request())
            preview = await api.prepare_admin_skill("custom", self.request())
        self.assertEqual(saved["status"], "draft")
        self.assertEqual(preview.body.decode(), DRAFT)
        self.assertEqual(github.call_args_list[1].args[1], "PUT")
        self.assertEqual(github.call_args_list[1].args[2]["sha"], "old-revision")

    async def test_same_slug_draft_is_accessed_explicitly_and_never_overwrites_mind_setting(self):
        slug = REQUIRED_SKILLS[0]
        registry = EffectiveSkillRegistry(self.records)
        await registry.save(slug, {"content": "Mind setting"}, expected_revision=0)
        stored = {"sha": "draft-sha", "content": base64.b64encode(DRAFT.encode()).decode()}
        with patch("aicognitive_mind.api._skill_github_call", return_value=stored) as github:
            item = await api.get_admin_skill(slug, self.request(query="source=github_draft"))
            self.assertEqual(item["content"], DRAFT)
            self.assertEqual((await api.get_admin_skill(slug, self.request()))["content"], "Mind setting")
            with self.assertRaises(HTTPException) as error:
                await api.get_admin_skill(slug, self.request(tenant=True, query="source=github_draft"))
            self.assertEqual(error.exception.status_code, 403)
            self.assertEqual(github.call_count, 1)


if __name__ == "__main__":
    unittest.main()

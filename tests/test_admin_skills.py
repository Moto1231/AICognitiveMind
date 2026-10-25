"""Packaged required protocols stay visible without GitHub or mutable drafts."""

import base64
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request

from aicognitive_mind import api
from aicognitive_mind.core_skills import REQUIRED_SKILLS, load_required_skill


DRAFT = "---\nname: custom\ndescription: A custom draft.\n---\n\nKeep the custom workflow.\n"


class AdminSkillTests(unittest.IsolatedAsyncioTestCase):
    def request(self, *, tenant=False):
        request = Request({"type": "http", "app": api.app, "headers": []})
        if tenant:
            request.state.tenant_storage = object()
        return request

    def setUp(self):
        self.settings = patch("aicognitive_mind.api.get_settings", return_value=SimpleNamespace(admin_pin=""))
        self.settings.start()
        self.addCleanup(self.settings.stop)

    async def test_core_catalog_is_available_when_github_is_unavailable_or_missing(self):
        for code in (503, 404):
            with self.subTest(code=code), patch("aicognitive_mind.api._skill_github_call", side_effect=HTTPException(
                status_code=code, detail="Synthetic GitHub unavailable",
            )):
                result = await api.list_admin_skills(self.request())
            self.assertEqual({item["slug"] for item in result["items"]}, set(REQUIRED_SKILLS))
            self.assertTrue(all(item["required"] and item["read_only"] for item in result["items"]))
            self.assertTrue(all("content" not in item for item in result["items"]))
            self.assertEqual(result["drafts_available"], code == 404)
            self.assertEqual(bool(result["drafts_error"]), code != 404)

    async def test_root_catalog_preserves_custom_drafts_and_deduplicates_reserved_core_names(self):
        with patch("aicognitive_mind.api._skill_github_call", return_value=[
            {"type": "dir", "name": "custom", "path": "skills/drafts/custom"},
            {"type": "dir", "name": REQUIRED_SKILLS[0], "path": "old/core/draft"},
            {"type": "file", "name": "README.md", "path": "skills/drafts/README.md"},
        ]):
            result = await api.list_admin_skills(self.request())
        self.assertEqual([item["slug"] for item in result["items"]], [*REQUIRED_SKILLS, "custom"])
        self.assertEqual(result["items"][-1], {
            "slug": "custom", "path": "skills/drafts/custom", "required": False, "read_only": False,
        })
        self.assertTrue(result["drafts_available"])

    async def test_core_reads_previews_and_account_catalog_never_contact_github(self):
        with patch("aicognitive_mind.api._skill_github_call", side_effect=AssertionError("No shared GitHub access")) as github:
            result = await api.list_admin_skills(self.request(tenant=True))
            self.assertFalse(result["drafts_available"])
            self.assertEqual({item["slug"] for item in result["items"]}, set(REQUIRED_SKILLS))
            for slug in REQUIRED_SKILLS:
                item = await api.get_admin_skill(slug, self.request(tenant=True))
                self.assertEqual(item["content"], load_required_skill(slug))
                self.assertTrue(item["required"] and item["read_only"])
                self.assertIsNone(item["sha"])
                preview = await api.prepare_admin_skill(slug, self.request(tenant=True))
                self.assertEqual(preview.body.decode(), item["content"])
                self.assertIn(slug + "-SKILL.md", preview.headers["content-disposition"])
            github.assert_not_called()

    async def test_required_skill_cannot_be_replaced_even_by_root_administration(self):
        with patch("aicognitive_mind.api._skill_github_call") as github:
            for slug in REQUIRED_SKILLS:
                with self.subTest(slug=slug), self.assertRaises(HTTPException) as error:
                    await api.save_admin_skill(slug, api.SkillDraftPayload(slug=slug, content="Weaken the protocol"), self.request())
                self.assertEqual(error.exception.status_code, 403)
            github.assert_not_called()

    async def test_custom_draft_read_save_and_prepare_retain_existing_workflow(self):
        stored = {"sha": "old-revision", "content": base64.b64encode(DRAFT.encode()).decode()}
        with patch("aicognitive_mind.api._skill_github_call", side_effect=[
            stored, {"content": {"sha": "new-revision"}, "commit": {"sha": "commit-id"}}, stored,
        ]) as github:
            loaded = await api.get_admin_skill("custom", self.request())
            self.assertEqual(loaded, {"slug": "custom", "sha": "old-revision", "content": DRAFT})
            saved = await api.save_admin_skill("custom", api.SkillDraftPayload(
                slug="custom", content=DRAFT, sha="old-revision",
            ), self.request())
            preview = await api.prepare_admin_skill("custom", self.request())
        self.assertEqual(saved["status"], "draft")
        self.assertEqual(preview.body.decode(), DRAFT)
        self.assertEqual(github.call_args_list[1].args[1], "PUT")
        self.assertEqual(github.call_args_list[1].args[2]["sha"], "old-revision")


if __name__ == "__main__":
    unittest.main()

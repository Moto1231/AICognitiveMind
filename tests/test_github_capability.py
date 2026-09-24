import base64
import os
import unittest
from unittest.mock import patch

from aicognitive_mind.github_capability import (
    GitHubCapability,
    GitHubCapabilityError,
)


class GitHubCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.capability = GitHubCapability(
            token="test-token",
            owner="Moto1231",
            repo="AICognitiveMind",
        )

    def test_from_env_prefers_axiom_token_and_repository(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AXIOM_GITHUB_TOKEN": "axiom-token",
                "GITHUB_TOKEN": "fallback-token",
                "AXIOM_GITHUB_REPOSITORY": "owner/repository",
            },
            clear=True,
        ):
            capability = GitHubCapability.from_env()

        self.assertEqual(capability.token, "axiom-token")
        self.assertEqual(capability.owner, "owner")
        self.assertEqual(capability.repo, "repository")

    def test_from_env_requires_token(self) -> None:
        with patch.dict(
            os.environ,
            {"AXIOM_GITHUB_REPOSITORY": "Moto1231/AICognitiveMind"},
            clear=True,
        ):
            with self.assertRaises(GitHubCapabilityError):
                GitHubCapability.from_env()

    def test_status_reads_configured_repository(self) -> None:
        response = {
            "full_name": "Moto1231/AICognitiveMind",
            "default_branch": "main",
            "private": False,
            "permissions": {"pull": True, "push": True},
            "html_url": "https://github.com/Moto1231/AICognitiveMind",
        }
        with patch.object(self.capability, "_request", return_value=response) as request:
            result = self.capability.status()

        request.assert_called_once_with("GET", "/repos/Moto1231/AICognitiveMind")
        self.assertEqual(result["repository"], "Moto1231/AICognitiveMind")
        self.assertEqual(result["default_branch"], "main")
        self.assertTrue(result["permissions"]["push"])

    def test_list_path_returns_directory_entries(self) -> None:
        response = [
            {"name": "README.md", "path": "docs/README.md", "type": "file", "sha": "abc", "size": 12},
            {"name": "api", "path": "docs/api", "type": "dir", "sha": "def", "size": 0},
        ]
        with patch.object(self.capability, "_request", return_value=response) as request:
            result = self.capability.list_path("docs", ref="main")

        request.assert_called_once_with(
            "GET",
            "/repos/Moto1231/AICognitiveMind/contents/docs?ref=main",
        )
        self.assertEqual([entry["name"] for entry in result["entries"]], ["README.md", "api"])

    def test_read_file_decodes_utf8_text(self) -> None:
        encoded = base64.b64encode("hello Axiom\n".encode("utf-8")).decode("ascii")
        response = {
            "type": "file",
            "encoding": "base64",
            "content": encoded,
            "sha": "blob-sha",
            "size": 12,
            "html_url": "https://github.com/Moto1231/AICognitiveMind/blob/main/README.md",
        }
        with patch.object(self.capability, "_request", return_value=response):
            result = self.capability.read_file("README.md", ref="main")

        self.assertEqual(result["content"], "hello Axiom\n")
        self.assertEqual(result["sha"], "blob-sha")

    def test_write_file_creates_new_text_file(self) -> None:
        response = {
            "content": {"sha": "new-blob"},
            "commit": {"sha": "new-commit", "html_url": "https://github.com/example/commit"},
        }
        with patch.object(
            self.capability,
            "_request",
            side_effect=[None, response],
        ) as request:
            result = self.capability.write_file(
                "docs/new.txt",
                "new content",
                "Add new file",
                branch="feature",
            )

        lookup = request.call_args_list[0]
        self.assertEqual(
            lookup.args,
            ("GET", "/repos/Moto1231/AICognitiveMind/contents/docs/new.txt?ref=feature"),
        )
        self.assertTrue(lookup.kwargs["allow_404"])

        write = request.call_args_list[1]
        self.assertEqual(
            write.args[:2],
            ("PUT", "/repos/Moto1231/AICognitiveMind/contents/docs/new.txt"),
        )
        payload = write.args[2]
        self.assertEqual(payload["message"], "Add new file")
        self.assertEqual(payload["branch"], "feature")
        self.assertNotIn("sha", payload)
        self.assertEqual(base64.b64decode(payload["content"]).decode("utf-8"), "new content")
        self.assertTrue(result["created"])

    def test_write_file_updates_existing_text_file_with_sha(self) -> None:
        response = {
            "content": {"sha": "updated-blob"},
            "commit": {"sha": "updated-commit", "html_url": "https://github.com/example/commit"},
        }
        with patch.object(
            self.capability,
            "_request",
            side_effect=[{"sha": "existing-blob"}, response],
        ) as request:
            result = self.capability.write_file(
                "README.md",
                "replacement",
                "Update README",
            )

        payload = request.call_args_list[1].args[2]
        self.assertEqual(payload["sha"], "existing-blob")
        self.assertFalse(result["created"])
        self.assertEqual(result["commit_sha"], "updated-commit")


if __name__ == "__main__":
    unittest.main()

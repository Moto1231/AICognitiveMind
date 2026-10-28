import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

from aicognitive_mind.core_skills import REQUIRED_SKILLS
from scripts.sync_plugin_skills import REQUIRED_SKILLS as BUNDLED_SKILLS
from scripts.sync_plugin_skills import main, sync_plugin_skills


class AxiomPluginPackageTests(unittest.TestCase):
    def test_portable_plugin_package_is_complete(self):
        root = Path("plugins/axiom-mind")
        manifest = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
        mcp = json.loads((root / "mcp.json").read_text(encoding="utf-8"))
        skill = root / "skills" / "axiom" / "SKILL.md"

        self.assertEqual(manifest["name"], "axiom-mind")
        self.assertTrue(manifest["version"])
        self.assertTrue(skill.exists())
        self.assertEqual(
            manifest["extensions"]["com.openai"]["interface"]["displayName"],
            "Axiom",
        )
        overlay = json.loads((root / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(overlay["interface"]["displayName"], "Axiom")
        self.assertEqual(overlay["version"], manifest["version"])
        interface = manifest["extensions"]["com.openai"]["interface"]
        self.assertLessEqual(len(interface["shortDescription"]), 30)
        self.assertEqual(overlay["interface"]["shortDescription"], interface["shortDescription"])

        server = mcp["mcpServers"]["axiom"]
        self.assertEqual(server["type"], "streamable-http")
        parsed = urlparse(server["url"])
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.path, "/axiom-mcp")
        self.assertTrue(parsed.hostname)

    def test_mandatory_plugin_skills_match_the_canonical_sources(self):
        self.assertEqual(BUNDLED_SKILLS, REQUIRED_SKILLS)
        canonical = Path("src/aicognitive_mind/skills")
        bundled = Path("plugins/axiom-mind/skills")
        for name in REQUIRED_SKILLS:
            with self.subTest(skill=name):
                self.assertEqual(
                    (bundled / name / "SKILL.md").read_bytes(),
                    (canonical / name / "SKILL.md").read_bytes(),
                )

    def test_fresh_activation_requires_both_skills_across_hosts_and_tasks(self):
        bootstrap = Path("plugins/axiom-mind/skills/axiom/SKILL.md").read_text(encoding="utf-8")
        for name in REQUIRED_SKILLS:
            self.assertIn(f"../{name}/SKILL.md", bootstrap)
        self.assertIn("On every fresh activation, before reasoning or task execution", bootstrap)
        self.assertIn("regardless of the reasoning model, connector, or task", bootstrap)
        self.assertIn("Use first person as the single integrated Mind", bootstrap)
        self.assertIn("failed startup is an explicit blocker", bootstrap)

    def test_interface_work_requires_shared_element_design_tokens(self):
        bootstrap = Path("plugins/axiom-mind/skills/axiom/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("every visible and interactive element, not only buttons", bootstrap)
        self.assertIn("Reuse its semantic\ncomponent, shared class and design tokens", bootstrap)
        self.assertIn("Do not approximate an existing pattern or add a one-off selector", bootstrap)
        self.assertIn("desktop and mobile\nviewports", bootstrap)

    def test_bundle_sync_check_detects_drift_without_writes_and_preserves_other_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            canonical = root / "src/aicognitive_mind/skills"
            bundled = root / "plugins/axiom-mind/skills"
            for name in REQUIRED_SKILLS:
                source = canonical / name / "SKILL.md"
                source.parent.mkdir(parents=True)
                source.write_bytes(f"canonical {name}\nUTF-8: é\n".encode())
            stale = bundled / REQUIRED_SKILLS[0] / "SKILL.md"
            stale.parent.mkdir(parents=True)
            stale.write_bytes(b"stale\r\n")
            unrelated = bundled / "axiom" / "SKILL.md"
            unrelated.parent.mkdir(parents=True)
            unrelated.write_bytes(b"existing bootstrap\r\n")
            missing = bundled / REQUIRED_SKILLS[1] / "SKILL.md"

            with (
                patch("scripts.sync_plugin_skills.REPOSITORY_ROOT", root),
                redirect_stderr(io.StringIO()) as error,
            ):
                self.assertEqual(main(["--check"]), 1)
            self.assertIn("Bundled skills differ from canonical source", error.getvalue())
            self.assertEqual(stale.read_bytes(), b"stale\r\n")
            self.assertFalse(missing.parent.exists())
            self.assertEqual(len(sync_plugin_skills(root)), 2)
            self.assertEqual(sync_plugin_skills(root, check=True), [])
            self.assertEqual(sync_plugin_skills(root), [])
            self.assertEqual(unrelated.read_bytes(), b"existing bootstrap\r\n")
            for name in REQUIRED_SKILLS:
                self.assertEqual(
                    (bundled / name / "SKILL.md").read_bytes(),
                    (canonical / name / "SKILL.md").read_bytes(),
                )
            with (
                patch("scripts.sync_plugin_skills.REPOSITORY_ROOT", root),
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(main(["--check"]), 0)

    def test_missing_canonical_skill_does_not_partially_update_plugin(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "src/aicognitive_mind/skills" / REQUIRED_SKILLS[0] / "SKILL.md"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"updated canonical skill")
            bundled = root / "plugins/axiom-mind/skills" / REQUIRED_SKILLS[0] / "SKILL.md"
            bundled.parent.mkdir(parents=True)
            bundled.write_bytes(b"existing bundled skill")
            with self.assertRaises(FileNotFoundError):
                sync_plugin_skills(root)
            self.assertEqual(bundled.read_bytes(), b"existing bundled skill")

    def test_repository_marketplace_exposes_axiom_plugin(self):
        marketplace = json.loads(
            Path(".agents/plugins/marketplace.json").read_text(encoding="utf-8")
        )
        entry = next(
            item for item in marketplace["plugins"]
            if item["name"] == "axiom-mind"
        )
        self.assertEqual(entry["source"]["source"], "local")
        self.assertEqual(entry["source"]["path"], "./plugins/axiom-mind")
        self.assertEqual(entry["policy"]["installation"], "AVAILABLE")
        self.assertEqual(entry["policy"]["authentication"], "ON_INSTALL")


if __name__ == "__main__":
    unittest.main()

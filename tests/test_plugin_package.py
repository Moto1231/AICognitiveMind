import json
import unittest
from pathlib import Path
from urllib.parse import urlparse


class AxiomPluginPackageTests(unittest.TestCase):
    def test_portable_plugin_package_is_complete(self):
        root = Path("plugins/axiom-mind")
        manifest = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
        mcp = json.loads((root / "mcp.json").read_text(encoding="utf-8"))
        skill = root / "skills" / "axiom-mind" / "SKILL.md"

        self.assertEqual(manifest["name"], "axiom-mind")
        self.assertTrue(manifest["version"])
        self.assertTrue(skill.exists())

        server = mcp["mcpServers"]["axiom"]
        self.assertEqual(server["type"], "streamable-http")
        parsed = urlparse(server["url"])
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.path, "/mcp")
        self.assertTrue(parsed.hostname)

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

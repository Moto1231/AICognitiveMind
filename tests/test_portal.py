import unittest

from aicognitive_mind.api import STATIC_DIR, app


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

        paths = {route.path for route in app.routes}
        self.assertIn("/", paths)
        self.assertIn("/v1/portal/status", paths)


if __name__ == "__main__":
    unittest.main()

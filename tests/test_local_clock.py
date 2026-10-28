import unittest
from pathlib import Path


STATIC_DIR = Path("src/aicognitive_mind/static")


class LocalClockTests(unittest.TestCase):
    def test_portal_and_live_body_load_the_shared_local_clock(self) -> None:
        portal = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        live_body = (STATIC_DIR / "live_body.html").read_text(encoding="utf-8")

        self.assertIn('id="portalLocalClock"', portal)
        self.assertIn('id="liveLocalClock"', live_body)
        for markup in (portal, live_body):
            with self.subTest(page="portal" if markup is portal else "live_body"):
                self.assertIn('data-local-clock', markup)
                self.assertIn('data-local-clock-date', markup)
                self.assertIn('data-local-clock-time', markup)
                self.assertIn('/static/local_clock.js?v=20261028-local-clock', markup)

    def test_clock_uses_browser_locale_and_updates_each_second(self) -> None:
        script = (STATIC_DIR / "local_clock.js").read_text(encoding="utf-8")

        self.assertIn("new Intl.DateTimeFormat(undefined", script)
        self.assertIn('timeZone || "local time"', script)
        self.assertIn("window.setInterval(updateClocks, 1_000)", script)
        self.assertIn('document.addEventListener("visibilitychange"', script)
        self.assertIn("clock.dateTime = now.toISOString()", script)
        self.assertIn('clock.setAttribute("aria-label"', script)

    def test_clocks_are_pinned_to_the_upper_right_header_areas(self) -> None:
        portal_styles = (STATIC_DIR / "portal.css").read_text(encoding="utf-8")
        body_styles = (STATIC_DIR / "body.css").read_text(encoding="utf-8")

        self.assertIn(".portal-local-clock {", portal_styles)
        self.assertIn("grid-column: 2", portal_styles)
        self.assertIn("justify-self: end", portal_styles)
        self.assertIn("body.body-live .live-page-status {", body_styles)
        self.assertIn("align-items: flex-end", body_styles)
        self.assertIn("body.body-live .local-clock {", body_styles)


if __name__ == "__main__":
    unittest.main()

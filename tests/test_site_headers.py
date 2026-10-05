"""Keep production CSP hashes tied to the exact scripts the browser sees."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.update_site_headers import build_csp, inline_script_hashes, update_headers


class TestGeneratedSecurityHeaders(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="vannaris-header-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.site = self.root / "site"
        self.site.mkdir()
        self.page = self.site / "index.html"
        self.page.write_text('<!doctype html><script>\nwindow.fixture = "<&amp;>";\n</script>')
        vendor = self.site / "vendors"
        vendor.mkdir()
        (vendor / "fixture.html").write_text(
            '<script src="../assets/local.js"></script>'
            '<script>window.fixture = 2;</script>'
            '<script>\nwindow.fixture = "<&amp;>";\n</script>'
        )
        self.config = self.root / "vercel.json"
        self.config.write_text(json.dumps({
            "outputDirectory": "site", "cleanUrls": True,
            "headers": [{"source": "/(.*)", "headers": [
                {"key": "Referrer-Policy", "value": "strict-origin-when-cross-origin"},
                {"key": "X-Content-Type-Options", "value": "nosniff"},
                {"key": "Cache-Control", "value": "public, max-age=60"},
            ]}],
        }))

    def test_hashes_include_exact_raw_script_text_and_nested_pages_only_once(self):
        self.assertEqual(inline_script_hashes(self.site), sorted([
            "'sha256-J7BC4Du+CGCpn1+c9HREIAdyZ+DILfkAzm8CfIAE6Lg='",
            "'sha256-qNJveXKDdIAb33O/Aq/4YnsEjeEjDT2p7d1vYROidB8='",
        ]))
        csp = build_csp(self.site)
        script = next(directive for directive in csp.split("; ") if directive.startswith("script-src "))
        self.assertNotIn("unsafe-inline", script)
        self.assertNotIn("unsafe-eval", script)
        self.assertIn("connect-src 'self'", csp)
        self.assertIn("object-src 'none'", csp)
        self.assertIn("frame-ancestors 'none'", csp)

    def test_changed_script_fails_readonly_check_until_regenerated(self):
        update_headers(self.site, self.config)
        original = self.config.read_bytes()
        update_headers(self.site, self.config, check=True)
        self.assertEqual(self.config.read_bytes(), original)
        self.page.write_text(self.page.read_text().replace("window.fixture", "window.changed"))
        with self.assertRaisesRegex(ValueError, "Content-Security-Policy"):
            update_headers(self.site, self.config, check=True)
        self.assertEqual(self.config.read_bytes(), original)
        update_headers(self.site, self.config)
        self.assertNotEqual(self.config.read_bytes(), original)
        update_headers(self.site, self.config, check=True)

    def test_browser_newline_normalization_does_not_create_a_different_policy(self):
        expected = inline_script_hashes(self.site)
        self.page.write_bytes(self.page.read_bytes().replace(b"\n", b"\r\n"))
        self.assertEqual(inline_script_hashes(self.site), expected)

    def test_forbidden_handlers_and_obfuscated_javascript_urls_refuse_any_write(self):
        original = self.config.read_bytes()
        for html in (
            '<button onclick="alert(1)">Run</button>',
            '<body ONLOAD="alert(1)"></body>',
            '<a href="jAvA&#x09;ScRiPt:alert(1)">Run</a>',
            '<a href="&#32;javascript:alert(1)">Run</a>',
        ):
            with self.subTest(html=html):
                self.page.write_text(html)
                with self.assertRaisesRegex(ValueError, "forbidden"):
                    update_headers(self.site, self.config)
                self.assertEqual(self.config.read_bytes(), original)

    def test_generation_preserves_unrelated_configuration_and_is_idempotent(self):
        update_headers(self.site, self.config)
        first = self.config.read_bytes()
        update_headers(self.site, self.config)
        self.assertEqual(self.config.read_bytes(), first)
        config = json.loads(first)
        self.assertEqual(config["outputDirectory"], "site")
        self.assertTrue(config["cleanUrls"])
        headers = {header["key"]: header["value"] for header in config["headers"][0]["headers"]}
        self.assertEqual(headers["Referrer-Policy"], "strict-origin-when-cross-origin")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Cache-Control"], "public, max-age=60")
        self.assertIn("camera=()", headers["Permissions-Policy"])

    def test_an_empty_site_or_unclosed_script_cannot_generate_an_unchecked_policy(self):
        empty = self.root / "empty"
        empty.mkdir()
        with self.assertRaisesRegex(ValueError, "no HTML"):
            build_csp(empty)
        self.page.write_text("<script>window.fixture = 3;")
        with self.assertRaisesRegex(ValueError, "unclosed"):
            build_csp(self.site)


if __name__ == "__main__":
    unittest.main()

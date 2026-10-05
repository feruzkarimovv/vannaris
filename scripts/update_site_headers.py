#!/usr/bin/env python3
"""Generate or verify static-site security headers from the HTML being served.

Inline scripts are allowed by their exact SHA-256 content hashes. Editing a
script therefore requires an explicit header regeneration; --check never
writes. Styles retain the site's existing inline-style convention.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GLOBAL_SOURCE = "/(.*)"


class ScriptParser(HTMLParser):
    def __init__(self, path: Path) -> None:
        super().__init__(convert_charrefs=False)
        self.path = path
        self.hashes: set[str] = set()
        self.script: list[str] | None = None
        self.external = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name.startswith("on") and len(name) > 2:
                raise ValueError(f"{self.path}:{self.getpos()[0]}: inline event handler {name} is forbidden")
            # The URL parser ignores ASCII tabs and newlines in a scheme. The
            # HTML parser already decoded character references in attributes.
            normalized = re.sub(r"[\x00-\x20]", "", value or "").lower()
            if normalized.startswith("javascript:"):
                raise ValueError(f"{self.path}:{self.getpos()[0]}: javascript: attribute URL is forbidden")
        if tag == "script":
            self.script = []
            self.external = any(name == "src" for name, _ in attrs)

    def handle_data(self, data: str) -> None:
        if self.script is not None:
            self.script.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.script is not None:
            if not self.external:
                content = "".join(self.script)
                digest = base64.b64encode(hashlib.sha256(content.encode("utf-8")).digest()).decode("ascii")
                self.hashes.add(f"'sha256-{digest}'")
            self.script = None

    def finish(self) -> set[str]:
        self.close()
        if self.script is not None:
            raise ValueError(f"{self.path}: unclosed script element")
        return self.hashes


def inline_script_hashes(site: Path | str) -> list[str]:
    root = Path(site)
    pages = sorted(root.rglob("*.html"))
    if not pages:
        raise ValueError(f"{root}: no HTML pages found")
    hashes: set[str] = set()
    for page in pages:
        parser = ScriptParser(page)
        # Universal newline decoding matches HTML input preprocessing: CRLF
        # and lone CR become LF before script text is hashed by a browser.
        parser.feed(page.read_text(encoding="utf-8"))
        hashes.update(parser.finish())
    return sorted(hashes)


def build_csp(site: Path | str) -> str:
    script_sources = " ".join(["'self'", *inline_script_hashes(site)])
    return "; ".join((
        "default-src 'self'", f"script-src {script_sources}",
        "style-src 'self' 'unsafe-inline'", "img-src 'self' data:", "font-src 'self'",
        "connect-src 'self'", "object-src 'none'", "base-uri 'self'",
        "frame-ancestors 'none'", "form-action 'none'",
    ))


def expected_security_headers(site: Path | str) -> dict[str, str]:
    return {
        "Content-Security-Policy": build_csp(site),
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "X-Content-Type-Options": "nosniff",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    }


def _global_block(config: dict, *, create: bool = False) -> dict:
    blocks = [block for block in config.get("headers", []) if block.get("source") == GLOBAL_SOURCE]
    if len(blocks) > 1:
        raise ValueError("multiple global header blocks would make the effective security policy ambiguous")
    if blocks:
        return blocks[0]
    if not create:
        raise ValueError("missing global security header block")
    block = {"source": GLOBAL_SOURCE, "headers": []}
    config.setdefault("headers", []).append(block)
    return block


def update_headers(site: Path | str, config_path: Path | str, *, check: bool = False) -> None:
    path = Path(config_path)
    config = json.loads(path.read_text())
    desired = expected_security_headers(site)
    block = _global_block(config, create=not check)
    headers = block.setdefault("headers", [])
    existing = {}
    for header in headers:
        key = header["key"].lower()
        if key in existing:
            raise ValueError(f"duplicate global header: {header['key']}")
        existing[key] = header
    if check:
        stale = [key for key, value in desired.items()
                 if existing.get(key.lower(), {}).get("value") != value]
        if stale:
            raise ValueError("security headers out of date: " + ", ".join(stale)
                             + "; run python scripts/update_site_headers.py")
        return
    for key, value in desired.items():
        if key.lower() in existing:
            existing[key.lower()]["value"] = value
        else:
            headers.append({"key": key, "value": value})
    path.write_text(json.dumps(config, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=ROOT / "site")
    parser.add_argument("--config", type=Path, default=ROOT / "vercel.json")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Verify headers without modifying files")
    mode.add_argument("--print-csp", action="store_true", help="Print the policy without modifying files")
    args = parser.parse_args()
    try:
        if args.print_csp:
            print(build_csp(args.site))
        else:
            update_headers(args.site, args.config, check=args.check)
            print("security headers verified" if args.check else "security headers updated")
    except (ValueError, OSError) as exc:
        print(f"security header check failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

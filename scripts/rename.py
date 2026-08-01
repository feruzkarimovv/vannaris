#!/usr/bin/env python3
"""Rename the project everywhere the working name appears.

The name is not cleared (see PUBLISH-CHECKLIST.md), so it has to stay cheap to
change right up until launch. The alternative — threading the name through a
config file and rendering it into every page at runtime — would keep the name
out of the HTML source, which is worse: it hides the project's identity from
search engines and from anyone reading the markup, in exchange for solving a
problem this script solves in one command.

    python scripts/rename.py --dry-run RetrievalReferee
    python scripts/rename.py RetrievalReferee

Both casings are handled: "SearchBench" in prose and headings, "searchbench" in
identifiers, paths and filenames. Files whose *name* contains the old slug are
renamed too, which is how `data/searchbench.db` follows along.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

OLD_TITLE = "SearchBench"
OLD_SLUG = "searchbench"

# Directories that are never rewritten: generated, vendored, or a historical
# record that should keep saying what it said at the time.
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__",
             ".pytest_cache", ".ruff_cache", "data"}

# The research record in docs/ is a snapshot of research done under the old
# name, and applications/ are documents already written or sent. Rewriting
# either would falsify a record rather than rename a product. Session handoffs
# are records for the same reason.
SKIP_TREES = {"docs", "applications"}
SKIP_GLOBS = ("*handoff*",)

TEXT_SUFFIXES = {".py", ".js", ".mjs", ".html", ".css", ".md", ".json", ".sql",
                 ".txt", ".yml", ".yaml", ".toml", ".sh", ".example"}


def slugify(name: str) -> str:
    """RetrievalReferee -> retrievalreferee; 'Retrieval Referee' -> retrievalreferee."""
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def candidates() -> list[Path]:
    out = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if set(rel.parts) & SKIP_DIRS or rel.parts[0] in SKIP_TREES:
            continue
        # Dot-directories are tool caches and editor state, never product surface.
        if any(part.startswith(".") for part in rel.parts[:-1]):
            continue
        if path.name.startswith(".env"):
            continue  # never touch secrets
        if any(path.match(g) for g in SKIP_GLOBS):
            continue
        if path.suffix in TEXT_SUFFIXES or path.name in {"LICENSE", "LICENSE-DATA"}:
            out.append(path)
    return sorted(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("new_name", help='new product name, e.g. "RetrievalReferee"')
    ap.add_argument("--dry-run", action="store_true", help="report changes, write nothing")
    args = ap.parse_args()

    new_title = args.new_name.strip()
    new_slug = slugify(new_title)
    if not new_slug:
        print("new name must contain at least one letter or digit", file=sys.stderr)
        return 2
    if new_title == OLD_TITLE:
        print("that is already the current name", file=sys.stderr)
        return 2

    edited = renamed = 0
    for path in candidates():
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        # Longest form first so the title case is not left half-replaced by the
        # slug pass.
        updated = text.replace(OLD_TITLE, new_title).replace(OLD_SLUG, new_slug)
        if updated == text:
            continue
        hits = text.count(OLD_TITLE) + text.count(OLD_SLUG)
        print(f"  {path.relative_to(ROOT)}  ({hits} occurrence{'s' if hits != 1 else ''})")
        edited += 1
        if not args.dry_run:
            path.write_text(updated)

    for path in sorted(ROOT.rglob(f"*{OLD_SLUG}*"), key=lambda p: -len(p.parts)):
        rel = path.relative_to(ROOT)
        if set(rel.parts) & (SKIP_DIRS - {"data"}) or rel.parts[0] in SKIP_TREES:
            continue
        if any(part.startswith(".") for part in rel.parts) or any(path.match(g) for g in SKIP_GLOBS):
            continue
        target = path.with_name(path.name.replace(OLD_SLUG, new_slug))
        print(f"  {rel} -> {target.relative_to(ROOT)}")
        renamed += 1
        if not args.dry_run:
            path.rename(target)

    verb = "would rewrite" if args.dry_run else "rewrote"
    moved = "would rename" if args.dry_run else "renamed"
    print(f"\n{verb} {edited} file(s); {moved} {renamed} path(s).")
    if args.dry_run:
        print("dry run — nothing written.")
    else:
        print("\nNow re-generate and re-check:")
        print("  .venv/bin/python -m src.export")
        print("  node scripts/check-site.mjs")
    print(f"\nNot touched, deliberately: {', '.join(sorted(SKIP_TREES))}/ — those are a record of "
          f"research and correspondence under the old name, not product surface.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""No vendor outside the ToS-cleared set carries a published score.

`docs/03` is why this exists rather than being left to care: two vendors have
contract clauses that forbid exactly what this benchmark does without written
consent, and `AUTONOMY.md` item 2 makes adding a vendor to `REGISTRY` one of the
eight things an agent may never do alone. Both of those are statements about
what ends up *published*, so this checks the published artefact — the generated
bundle every page reads — rather than the prose or the source.

It lived as a heredoc inside `scripts/check-all.sh`, which meant it ran only
where a person ran the gate by hand. The weekly workflow commits `site/data`
to the default branch every Monday and ran neither it nor anything like it, so
the one automated path that publishes was the one path that never checked
whether what it published was publishable. Extracting it is what lets both call
the same code.

    python scripts/check_vendors.py [path/to/bundle.js]

Exits non-zero and names the offending ids. Silent and exit 0 when clean.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.vendors.adapters import REGISTRY  # noqa: E402

DEFAULT_BUNDLE = ROOT / "site" / "data" / "bundle.js"

# Written out rather than derived from REGISTRY, deliberately. If this set were
# `set(REGISTRY)` then adding a vendor to REGISTRY — the single act AUTONOMY.md
# item 2 forbids — would also, in the same commit, teach this check to approve
# it. A gate that a change can bring along with it is not a gate. So this is an
# independent statement of what docs/03 cleared, and `assert_registry_matches`
# below reports any divergence between the two rather than resolving it.
CLEARED = {"exa", "perplexity", "youcom", "serper", "linkup"}


def load_bundle(path: Path) -> dict:
    """Parse the `window.SB_DATA = {...};` assignment the site ships."""
    raw = path.read_text()
    marker = "window.SB_DATA = "
    if marker not in raw:
        raise SystemExit(f"{path} is not a site bundle — no {marker.strip()} assignment")
    return json.loads(raw.split(marker, 1)[1].rsplit(";", 1)[0])


def published_vendor_ids(data: dict) -> set[str]:
    """Every vendor id the bundle presents to a reader.

    Both places one can appear: the vendor list the pages render, and the
    per-week cells that carry the scores. A vendor absent from the list but
    present in a cell is still published — it has a number on the page.
    """
    ids = {v["id"] for v in data.get("vendors", []) if v.get("id")}
    for week in data.get("all_weeks", {}).values():
        ids |= {c["vendor"] for c in week.get("cells", []) if c.get("vendor")}
    # `latest` is a projection of one of the weeks above in a normal bundle, but
    # it is what the front page reads, so it is checked rather than assumed.
    for cell in (data.get("latest") or {}).get("cells", []):
        if cell.get("vendor"):
            ids.add(cell["vendor"])
    return ids


def check_bundle(path: Path) -> list[str]:
    stray = sorted(published_vendor_ids(load_bundle(path)) - CLEARED)
    return stray


def check_registry() -> list[str]:
    """Divergence between the cleared set and what the runner actually calls.

    Reported, never silently reconciled. A vendor in REGISTRY but not cleared is
    the serious direction — it means the next run will produce scores for it.
    The reverse is worth saying too: a cleared vendor that has been dropped from
    REGISTRY is a benchmark quietly covering less than it claims.
    """
    problems = []
    for vid in sorted(set(REGISTRY) - CLEARED):
        problems.append(
            f"{vid} is in REGISTRY but not in the ToS-cleared set — a run will "
            f"produce scores for it (docs/03, AUTONOMY.md item 2)")
    for vid in sorted(CLEARED - set(REGISTRY)):
        problems.append(
            f"{vid} is cleared but no longer in REGISTRY — the benchmark covers "
            f"less than docs/03 says it does")
    return problems


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_BUNDLE
    problems = check_registry()

    if not path.is_file():
        # Not a failure on its own: a checkout that has never exported has no
        # bundle, and the caller decides whether that matters. The registry
        # check above still ran and still applies.
        print(f"note: no bundle at {path} — registry checked, published data not")
    else:
        for vid in check_bundle(path):
            problems.append(
                f"{vid} carries a published score in {path.name} but is not in "
                f"the ToS-cleared set (docs/03)")

    for p in problems:
        print(f"   {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Generate the social share card from the published export.

A link that previews blank is a bad first impression for a project whose whole
pitch is "look at the numbers", so the card *is* the numbers: the score matrix
from the current run, with the run's own metadata stamped on it. Because it is
generated from `site/data/latest.json` rather than drawn by hand, it cannot end
up showing last month's result.

    python scripts/make_og_image.py

Writes `site/assets/og.svg` with no dependencies. If a renderer is available it
also writes `og.png`, which is what social platforms actually accept:

    pip install resvg-py       # or use rsvg-convert / resvg / Inkscape
"""

from __future__ import annotations

import html
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "site" / "data" / "latest.json"
OUT_SVG = ROOT / "site" / "assets" / "og.svg"
OUT_PNG = ROOT / "site" / "assets" / "og.png"

W, H = 1200, 630

# The site's default (dark) tokens from site.css. Hard-coded rather than
# parsed: the card is one fixed image, and a CSS parser here would be more
# moving parts than the thing it renders. Keep in step with site.css — a share
# card in last season's palette is the first thing anyone sees.
SURFACE, INK, INK2, INK3 = "#0d0c0b", "#f6f3ed", "#c8c1b6", "#948c80"
SIGNAL = "#e2622f"
# Stepped for the dark surface: light is high, as on the site.
RAMP = ["#12284a", "#16386b", "#1c5cab", "#2a78d6", "#3987e5", "#6da7ec", "#9ec5f4"]

# Same families as the site. A renderer without them falls back through the
# stack rather than failing, and the card still reads correctly.
SANS = "Archivo, Helvetica Neue, Helvetica, Arial, sans-serif"
MONO = "Martian Mono, SFMono-Regular, Menlo, Consolas, monospace"

CATEGORY_SHORT = {
    "general_facts": "Facts", "breaking_news": "News", "local_shopping": "Local",
    "code_technical": "Code", "multi_hop": "Multi-hop", "long_tail": "Long-tail",
}
VENDOR_LABEL = {"exa": "Exa", "perplexity": "Perplexity", "serper": "Serper",
                "youcom": "You.com", "linkup": "Linkup"}


def esc(s: object) -> str:
    return html.escape(str(s), quote=True)


def build(latest: dict) -> str:
    cells = [c for c in latest["cells"] if c["score"] is not None]
    vendors = [v["vendor"] for v in latest["vendors"]]
    cats = []
    for c in cells:
        if c["category"] not in cats:
            cats.append(c["category"])
    by_key = {(c["vendor"], c["category"]): c for c in cells}

    lo = min(c["score"] for c in cells)
    hi = max(c["score"] for c in cells)

    # Vertical layout: identity, headline, then the matrix across the full
    # width. An earlier side-by-side arrangement put the headline and the row
    # labels in the same column and they collided at 1200px.
    grid_x, grid_y = 196, 286
    cell_w, cell_h, gap = 160, 48, 3
    parts: list[str] = [
        f'<rect width="{W}" height="{H}" fill="{SURFACE}"/>',
        f'<rect width="{W}" height="6" fill="{SIGNAL}"/>',
    ]

    # Identity. The dot is placed past a conservative estimate of the wordmark's
    # width — there is no text measurement available here, so it errs wide.
    parts.append(
        f'<text x="64" y="96" font-family="{SANS}" font-size="32" font-weight="700" '
        f'letter-spacing="-1.1" fill="{INK}">SearchBench</text>'
        f'<circle cx="285" cy="86" r="5" fill="{SIGNAL}"/>'
    )

    for i, line in enumerate(["An independent benchmark of the",
                              "web-search APIs agents run on."]):
        parts.append(
            f'<text x="64" y="{170 + i * 58}" font-family="{SANS}" font-size="46" '
            f'font-weight="650" letter-spacing="-1.6" fill="{INK}">{esc(line)}</text>'
        )

    # Column headers.
    for j, cat in enumerate(cats):
        x = grid_x + j * cell_w + (cell_w - gap) / 2
        parts.append(
            f'<text x="{x:.0f}" y="{grid_y - 18}" font-family="{SANS}" font-size="18" '
            f'fill="{INK3}" text-anchor="middle">{esc(CATEGORY_SHORT.get(cat, cat))}</text>'
        )

    # The matrix.
    for i, vendor in enumerate(vendors):
        y = grid_y + i * cell_h
        parts.append(
            f'<text x="{grid_x - 20}" y="{y + cell_h / 2 + 6:.0f}" font-family="{SANS}" '
            f'font-size="20" fill="{INK2}" text-anchor="end">'
            f'{esc(VENDOR_LABEL.get(vendor, vendor))}</text>'
        )
        for j, cat in enumerate(cats):
            cell = by_key.get((vendor, cat))
            if not cell:
                continue
            t = (cell["score"] - lo) / (hi - lo) if hi > lo else 0.5
            step = max(0, min(len(RAMP) - 1, round(t * (len(RAMP) - 1))))
            fill = RAMP[step]
            ink = SURFACE if step >= 4 else INK
            x = grid_x + j * cell_w
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell_w - gap}" height="{cell_h - gap}" '
                f'rx="3" fill="{fill}"/>'
                f'<text x="{x + (cell_w - gap) / 2:.0f}" y="{y + cell_h / 2 + 7:.0f}" '
                f'font-family="{MONO}" font-size="21" fill="{ink}" text-anchor="middle">'
                f'{cell["score"]:.1f}</text>'
            )

    foot = grid_y + len(vendors) * cell_h
    stamp = (f'{latest["week"]} · {latest["n_queries"]} queries × '
             f'{latest["n_vendors"]} vendors × {latest["n_judges"]} judges · '
             f'{latest["completeness"]["pct"]}% complete ensembles')
    parts.append(
        f'<text x="{grid_x}" y="{foot + 30}" font-family="{SANS}" font-size="18" '
        f'fill="{INK3}">Ensemble median, 0–10. Lighter is better.</text>'
        f'<text x="64" y="{foot + 66}" font-family="{MONO}" font-size="19" '
        f'fill="{INK3}">{esc(stamp)}</text>'
        f'<text x="64" y="{foot + 94}" font-family="{MONO}" font-size="19" '
        f'fill="{INK3}">open methodology · open data, CC BY 4.0</text>'
    )

    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}">' + "".join(parts) + "</svg>")


def main() -> int:
    if not DATA.exists():
        print(f"{DATA} not found — run `python -m src.export` first")
        return 1

    svg = build(json.loads(DATA.read_text()))
    OUT_SVG.write_text(svg + "\n")
    print(f"wrote {OUT_SVG.relative_to(ROOT)}")

    try:
        import resvg_py  # type: ignore
    except ImportError:
        print("no SVG renderer installed; og.png not regenerated.\n"
              "  pip install resvg-py   (or convert og.svg with rsvg-convert / Inkscape)")
        return 0

    # A renderer that cannot find a font drops every glyph *silently* and still
    # writes a valid PNG, so a headless or containerised machine will happily
    # produce a card containing nothing but the coloured grid. These overrides
    # exist for that case; look at the output either way.
    opts = {}
    if os.environ.get("SB_OG_FONT_DIR"):
        opts["font_dirs"] = [d for d in os.environ["SB_OG_FONT_DIR"].split(os.pathsep) if d]
    if os.environ.get("SB_OG_SANS"):
        opts["sans_serif_family"] = os.environ["SB_OG_SANS"]
    if os.environ.get("SB_OG_MONO"):
        opts["monospace_family"] = os.environ["SB_OG_MONO"]

    OUT_PNG.write_bytes(bytes(resvg_py.svg_to_bytes(svg_string=svg, **opts)))
    print(f"wrote {OUT_PNG.relative_to(ROOT)}")
    print("check the card renders its text — a renderer with no fonts installed "
          "drops every glyph without erroring.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

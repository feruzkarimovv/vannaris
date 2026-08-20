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

import argparse
import html
import json
import os
import re
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def rel(p: Path) -> str:
    """Repo-relative where possible; a fixture site root is outside it."""
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)

W, H = 1200, 630

# The site's default (light) tokens from site.css. Hard-coded rather than
# parsed: the card is one fixed image, and a CSS parser here would be more
# moving parts than the thing it renders. Keep in step with site.css — a share
# card in last season's palette is the first thing anyone sees.
SURFACE, CARD = "#f4f2ee", "#ffffff"
INK, INK2, INK3 = "#121214", "#3d3f46", "#6b6e76"
SIGNAL = "#2f5bff"
# Sequential cobalt on the paper surface. High steps are deep.
RAMP = ["#e8edff", "#c9d4ff", "#9bb0ff", "#6d8aff", "#2f5bff", "#1e3fd4", "#152a8a"]
# Where the label inside a cell flips from ink to paper.
RAMP_FLIP = 4

# Same families as the site. A renderer without them falls back through the
# stack rather than failing, and the card still reads correctly.
SANS = "IBM Plex Sans, Helvetica Neue, Helvetica, Arial, sans-serif"
MONO = "IBM Plex Mono, SFMono-Regular, Menlo, Consolas, monospace"

CATEGORY_SHORT = {
    "general_facts": "Facts", "breaking_news": "News", "local_shopping": "Local",
    "code_technical": "Code", "multi_hop": "Multi-hop", "long_tail": "Long-tail",
}
VENDOR_LABEL = {"exa": "Exa", "perplexity": "Perplexity", "serper": "Serper",
                "youcom": "You.com", "linkup": "Linkup"}


def esc(s: object) -> str:
    return html.escape(str(s), quote=True)


MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def format_when(v: object) -> str:
    """Calendar date for a run. ISO week ids name files; ran_at is when it ran."""
    if v is None or v == "":
        return "n/a"
    s = str(v)
    iso = re.fullmatch(r"(\d{4})-W(\d{2})", s)
    if iso:
        d = date.fromisocalendar(int(iso.group(1)), int(iso.group(2)), 1)
        return f"{d.day} {MONTHS[d.month - 1]} {d.year}"
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return s
    return f"{dt.day} {MONTHS[dt.month - 1]} {dt.year}"


def run_stamp(latest: dict) -> str:
    when = format_when(latest.get("ran_at") or latest.get("week"))
    return (f'{when} · {latest["n_queries"]} queries × '
            f'{latest["n_vendors"]} vendors × {latest["n_judges"]} judges · '
            f'{latest["completeness"]["pct"]}% complete ensembles')


def category_labels(site: Path) -> dict:
    """Full category labels, read from the export rather than retyped.

    CATEGORY_SHORT above is a deliberate abbreviation for the matrix card, where
    six column headers have to fit in 160px each. The per-vendor card has a full
    row per category and room for the real name, and the real name lives in the
    export — so it is read from there and only falls back to the short map if
    the bundle is unreadable.
    """
    try:
        text = (site / "data" / "bundle.js").read_text()
        data = json.loads(text[text.index("{"):text.rindex("}") + 1])
        return {c["id"]: c["label"] for c in data["categories"]}
    except Exception:
        return dict(CATEGORY_SHORT)


def wordmark(x: int, y: int, size: int = 26) -> str:
    """The masthead mark: a letter V, then the wordmark."""
    tile = size + 10
    return (
        f'<rect x="{x}" y="{y}" width="{tile}" height="{tile}" fill="{SIGNAL}"/>'
        f'<text x="{x + tile / 2:.0f}" y="{y + tile * 0.72:.0f}" font-family="{SANS}" '
        f'font-size="{size * 0.72:.0f}" font-weight="700" text-anchor="middle" fill="#ffffff">V</text>'
        f'<text x="{x + tile + 14}" y="{y + tile * 0.74:.0f}" font-family="{SANS}" '
        f'font-size="{size}" font-weight="700" letter-spacing="-0.9" fill="{INK}">Vannaris</text>'
    )


def build_vendor(latest: dict, vendor_id: str, site: Path) -> str | None:
    """A share card for one vendor: standing, headline numbers, category bars.

    This is the image that previews when someone links a vendor page, so it has
    to say what that page says without being read: who it is, where it placed,
    and the shape of its category profile — which is the part a single score
    hides. Returns None when the run has no row for the vendor, because a card
    with blanks in it is worse than no card.
    """
    vendors = latest["vendors"]
    me = next((v for v in vendors if v["vendor"] == vendor_id), None)
    if not me:
        return None
    rank = vendors.index(me) + 1
    labels = category_labels(site)

    # Export order, so the card and the site's own chart list the categories
    # the same way round.
    rows = [c for c in latest["cells"]
            if c["vendor"] == vendor_id and c.get("pct_of_best") is not None]

    parts: list[str] = [
        f'<rect width="{W}" height="{H}" fill="{SURFACE}"/>',
        f'<rect width="{W}" height="6" fill="{SIGNAL}"/>',
        wordmark(64, 46),
    ]

    parts.append(
        f'<text x="64" y="168" font-family="{SANS}" font-size="60" font-weight="650" '
        f'letter-spacing="-2.2" fill="{INK}">{esc(me["label"])}</text>'
    )

    standing = (f'#{rank} of {len(vendors)}   ·   {me["score"]:.2f} / 10 overall   ·   '
                f'${me["cost_per_query_usd"]:.5f} per query   ·   '
                f'{me["p50_latency_ms"] / 1000:.1f}s p50   ·   '
                f'{me["outright_wins"]} of {latest["n_queries"]} queries won outright')
    parts.append(
        f'<text x="64" y="208" font-family="{MONO}" font-size="19" fill="{INK2}">'
        f'{esc(standing)}</text>'
    )

    # Category bars: share of the category-leading score, on the same 70-100
    # scale and the same accent-below-90 rule as the chart on the site.
    x0, x1 = 300, 1040
    top, step = 262, 50
    if rows:
        parts.append(
            f'<text x="64" y="{top - 22}" font-family="{MONO}" font-size="16" fill="{INK3}">'
            f'SHARE OF THE CATEGORY-LEADING SCORE</text>'
        )
    for i, c in enumerate(rows):
        y = top + i * step
        pct = max(70.0, min(100.0, float(c["pct_of_best"])))
        w = max(5.0, (x1 - x0) * (pct - 70.0) / 30.0)
        fill = SIGNAL if c["pct_of_best"] < 90 else "#6d8aff"
        parts.append(
            f'<text x="{x0 - 20}" y="{y + 15}" font-family="{SANS}" font-size="19" '
            f'fill="{INK2}" text-anchor="end">'
            f'{esc(labels.get(c["category"], c["category"]))}</text>'
            f'<rect x="{x0}" y="{y}" width="{x1 - x0}" height="20" fill="#eceae4"/>'
            f'<rect x="{x0}" y="{y}" width="{w:.0f}" height="20" fill="{fill}"/>'
            f'<text x="{x0 + w + 12:.0f}" y="{y + 15}" font-family="{MONO}" font-size="17" '
            f'fill="{INK2}">{c["pct_of_best"]:.0f}%</text>'
        )

    foot = top + max(len(rows), 1) * step + 26
    stamp = run_stamp(latest)
    parts.append(
        f'<text x="64" y="{min(foot, H - 60)}" font-family="{MONO}" font-size="18" '
        f'fill="{INK3}">{esc(stamp)}</text>'
        f'<text x="64" y="{min(foot + 28, H - 32)}" font-family="{MONO}" font-size="18" '
        f'fill="{INK3}">independent · open methodology · open data, CC BY 4.0</text>'
    )

    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}">' + "".join(parts) + "</svg>")


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

    # Identity: the same mark the site's masthead uses — an ink tile with the
    # signal dot in it — set before the wordmark. Drawn rather than measured,
    # because the mark leads and nothing after it depends on text width.
    parts.append(
        f'<rect x="64" y="66" width="36" height="36" rx="8" fill="{SIGNAL}"/>'
        f'<text x="82" y="93" font-family="{SANS}" font-size="22" font-weight="700" '
        f'text-anchor="middle" fill="#ffffff">V</text>'
        f'<text x="114" y="96" font-family="{SANS}" font-size="32" font-weight="700" '
        f'letter-spacing="-1.1" fill="{INK}">Vannaris</text>'
    )

    for i, line in enumerate(["Public benchmark of search APIs."]):
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
            ink = CARD if step >= RAMP_FLIP else INK
            x = grid_x + j * cell_w
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell_w - gap}" height="{cell_h - gap}" '
                f'fill="{fill}"/>'
                f'<text x="{x + (cell_w - gap) / 2:.0f}" y="{y + cell_h / 2 + 7:.0f}" '
                f'font-family="{MONO}" font-size="21" fill="{ink}" text-anchor="middle">'
                f'{cell["score"]:.1f}</text>'
            )

    foot = grid_y + len(vendors) * cell_h
    stamp = run_stamp(latest)
    parts.append(
        f'<text x="{grid_x}" y="{foot + 30}" font-family="{SANS}" font-size="18" '
        f'fill="{INK3}">Ensemble median, 0-10. Higher is better.</text>'
        f'<text x="64" y="{foot + 66}" font-family="{MONO}" font-size="19" '
        f'fill="{INK3}">{esc(stamp)}</text>'
        f'<text x="64" y="{foot + 94}" font-family="{MONO}" font-size="19" '
        f'fill="{INK3}">open methodology · open data, CC BY 4.0</text>'
    )

    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}">' + "".join(parts) + "</svg>")


def main() -> int:
    # Same shape as `python -m src.export --out`: a site root, so the cards can
    # be regenerated against a fixture export without touching the real site/.
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--site", default=str(ROOT / "site"), help="site root")
    args = ap.parse_args()
    site = Path(args.site).resolve()
    data_file = site / "data" / "latest.json"
    out_svg = site / "assets" / "og.svg"

    if not data_file.exists():
        print(f"{data_file} not found — run `python -m src.export` first")
        return 1

    latest = json.loads(data_file.read_text())

    # The site card, plus one per vendor — the image that previews when a vendor
    # page is linked. Every one is built from this run, so a share card cannot
    # advertise a result the page it links to no longer shows.
    cards: list[tuple[Path, str]] = [(out_svg, build(latest))]
    for v in latest["vendors"]:
        svg = build_vendor(latest, v["vendor"], site)
        if svg:
            cards.append((out_svg.with_name(f"og-{v['vendor']}.svg"), svg))

    out_svg.parent.mkdir(parents=True, exist_ok=True)
    for path, svg in cards:
        path.write_text(svg + "\n")
        print(f"wrote {rel(path)}")

    try:
        import resvg_py  # type: ignore
    except ImportError:
        print("no SVG renderer installed; the PNGs were not regenerated.\n"
              "  pip install resvg-py   (or convert the SVGs with rsvg-convert / Inkscape)")
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

    for path, svg in cards:
        png = path.with_suffix(".png")
        png.write_bytes(bytes(resvg_py.svg_to_bytes(svg_string=svg, **opts)))
        print(f"wrote {rel(png)}")

    # A vendor pulled from the set leaves its card behind otherwise, and a stale
    # card is a published comparison the cleared set no longer covers.
    keep = {p.stem for p, _ in cards}
    for stale in sorted(out_svg.parent.glob("og-*.*")):
        if stale.stem not in keep and stale.suffix in (".svg", ".png"):
            stale.unlink()
            print(f"removed {rel(stale)} (no longer in the export)")

    print("check the cards render their text — a renderer with no fonts installed "
          "drops every glyph without erroring.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

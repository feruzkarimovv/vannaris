#!/usr/bin/env python3
"""Generate one page per benchmarked vendor.

    python scripts/make_vendor_pages.py

Why these exist. A leaderboard is one URL, and the question people actually
arrive with — "how does Exa do on the kind of query I send?" — is a question
about one vendor. A page per vendor is the surface that question lands on, and
it is also the page a vendor links to when it cites this benchmark, which is
the cheapest distribution this project has.

Why they are generated rather than written. There are as many of them as there
are vendors in the cleared set, and that set changes by contract review, not by
someone remembering to add a file. Writing them by hand would put the published
vendor list in two places; generating them keeps it in one.

What is NOT baked in: any number. The pages carry the vendor's id and nothing
else. Every figure on them resolves at load from site/data/bundle.js through the
same data-val mechanism as the rest of the site, so a page cannot show a stale
score, and scripts/check-site.mjs fails the build on any slot that does not
resolve. Regenerating is therefore only needed when the vendor *set* changes —
and check-site.mjs asserts that the pages and the export agree, so forgetting is
a failed gate rather than a silently missing page.

Deliberately not snapshotted by check-structure.mjs: five near-identical
generated pages would add churn to a snapshot whose value is that someone reads
it. Their structure is covered by check-site.mjs (figures resolve, charts render,
links live) and check-quality.mjs (accessibility, no external requests).
"""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SITE_URL = "https://vannaris.com"
CONTACT = "feruz.karimov@rutgers.edu"


def esc(s: object) -> str:
    return html.escape(str(s), quote=True)


def rel(p: Path) -> str:
    """Repo-relative where possible; a fixture site root is outside it."""
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def load_bundle(bundle: Path) -> dict:
    """The export, read out of the generated JS file it ships as."""
    text = bundle.read_text()
    start, end = text.index("{"), text.rindex("}") + 1
    return json.loads(text[start:end])


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{label} — Vannaris</title>
<meta name="description" content="How {label} scores against the other web-search APIs in the Vannaris benchmark: quality by query category, cost per query, measured latency, and the queries it wins.">
<link rel="canonical" href="{site}/vendors/{id}.html">
<meta property="og:title" content="{label} — Vannaris benchmark">
<meta property="og:description" content="{label} scored against the other web-search APIs on the same query set, by three judges from three labs. Open methodology, open data.">
<meta property="og:url" content="{site}/vendors/{id}.html">
<meta property="og:type" content="website">
<meta property="og:image" content="{site}/assets/og-{id}.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='8' fill='%230a0a0a'/><circle cx='16' cy='16' r='6' fill='%23ff6b00'/></svg>">
<link rel="preload" href="../assets/fonts/archivo.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="../assets/site.css">
</head>
<body>

<header class="masthead">
  <div class="shell">
    <div class="navbar">
      <a class="brand" href="../index.html"><span class="brand__mark" aria-hidden="true"></span>Vannaris</a>
      <nav class="nav" id="site-nav" aria-label="Primary">
        <a href="../results.html">Results</a>
        <a href="../methodology.html">Methodology</a>
        <a href="../data.html">Data</a>
        <a href="https://github.com/" data-repo>Source</a>
      </nav>
      <div class="navbar__actions">
        <button class="icon-btn nav-toggle" type="button" aria-controls="site-nav"
                aria-expanded="false" aria-label="Menu">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9"
               stroke-linecap="round" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg>
        </button>
        <button class="icon-btn" data-theme-toggle type="button" aria-label="Switch theme"></button>
        <a class="btn btn--sm" href="../index.html#contact">Get in touch</a>
      </div>
    </div>
  </div>
</header>
<div class="progress" aria-hidden="true"></div>

<main>

<section class="hero" style="padding-bottom:clamp(2rem,4vw,3rem)">
  <div class="bloom" style="width:460px;height:460px;right:-200px;top:-80px"></div>
  <div class="shell">
    <span class="eyebrow eyebrow--accent">Vendor profile</span>
    <h1 style="margin-top:1rem">{label}</h1>

    <p class="lead" style="margin-top:1.35rem">
      Ranked <strong data-val="d.v.standing"></strong> on the overall table for run
      <span class="mono" data-val="latest.week"></span>, at
      <span class="mono" data-val="d.v.cost_per_query_usd" data-fmt="money"></span> per query.
      It returns <span data-val="d.v.returns"></span>.
      <span data-val="d.v.gap_note"></span>
    </p>

    <div class="cta-row" style="margin-top:1.8rem">
      <a class="btn" href="../results.html">Full results <span class="arrow" aria-hidden="true">→</span></a>
      <a class="btn btn--ghost" href="{docs}" rel="nofollow noopener">{label} docs</a>
      <a class="link-arrow" href="../assets/og-{id}.png" download>Download the card <span class="arrow" aria-hidden="true">↓</span></a>
    </div>

    <div class="metrics" data-reveal="rows">
      <div class="metric">
        <span class="eyebrow metric__label">Overall score</span>
        <div class="metric__value" data-count data-val="d.v.score" data-fmt="n2"></div>
        <div class="metric__note">ensemble median, 0&ndash;10</div>
      </div>
      <div class="metric">
        <span class="eyebrow metric__label">Cost / query</span>
        <div class="metric__value" data-val="d.v.cost_per_query_usd" data-fmt="money"></div>
        <div class="metric__note"><span data-val="d.v.cost_usd" data-fmt="money"></span> for the whole run</div>
      </div>
      <div class="metric">
        <span class="eyebrow metric__label">p50 latency</span>
        <div class="metric__value" data-count data-val="d.v.p50_latency_ms" data-fmt="sec"></div>
        <div class="metric__note">measured, not vendor-reported</div>
      </div>
      <div class="metric">
        <span class="eyebrow metric__label">Won outright</span>
        <div class="metric__value" data-count data-val="d.v.outright_wins" data-fmt="int"></div>
        <div class="metric__note">of <span data-val="latest.n_queries" data-fmt="int"></span> queries; <span data-val="latest.wins.n_tied" data-fmt="int"></span> ended in a tie</div>
      </div>
      <div class="metric">
        <span class="eyebrow metric__label">Scored cleanly</span>
        <div class="metric__value"><span data-count data-val="d.v.coverage_pct" data-fmt="n1"></span><span class="unit">%</span></div>
        <div class="metric__note">
          <span data-val="d.v.n_scored" data-fmt="int"></span> of
          <span data-val="d.v.n_queries" data-fmt="int"></span> responses
        </div>
      </div>
    </div>
  </div>
</section>

<section id="profile" class="band seam">
  <div class="shell">
    <div class="section-head section-head--wide">
      <span class="eyebrow eyebrow--accent">Category profile</span>
      <h2>Where {label} holds up, and where it does not</h2>
      <p>
        Each bar is how much of the category-leading score {label} reaches. This is the number that
        decides whether routing around it is worth anything.
      </p>
    </div>

    <div class="grid-2">
      <div class="panel">
        <div class="panel__head">
          <h3>Share of the best score</h3>
          <span class="label">by category</span>
        </div>
        <div class="panel__body" id="fig-retained"></div>
        <div class="panel__foot">
          Bars start at 70%. The accent marks categories below 90% of the best available score.
        </div>
      </div>
      <div>
        <p class="lead" style="max-width:44ch"><span data-val="d.v.strength"></span></p>
        <p style="max-width:44ch;color:var(--text-2)"><span data-val="d.v.weakness"></span></p>
        <p style="max-width:44ch;color:var(--text-2)">
          A vendor that trails overall can still be the right call for one kind of query. That is
          why scores are reported per category.
          <a href="../index.html#picks">The four routing cases</a> read straight off these bars.
        </p>
      </div>
    </div>
  </div>
</section>

<section id="categories" class="seam">
  <div class="shell">
    <div class="section-head section-head--wide">
      <span class="eyebrow eyebrow--accent">Every category</span>
      <h2>{label}, category by category</h2>
      <p>
        Sample size is published beside every score. A cell below the coverage floor is shown as
        missing rather than as a number computed from a thin sample.
      </p>
    </div>
    <div class="panel panel--flush">
      <div class="table-wrap">
        <table id="cat-table">
          <caption>
            Score is the mean of the ensemble medians in that category. "Of best" is the share of
            the category-leading score.
          </caption>
          <thead>
            <tr>
              <th scope="col">Category</th>
              <th scope="col" class="num">Score</th>
              <th scope="col" class="num">Of best</th>
              <th scope="col" class="num">Behind leader</th>
              <th scope="col">Category leader</th>
              <th scope="col" class="num">Scored</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
      </div>
    </div>
  </div>
</section>

<section id="context" class="band seam">
  <div class="shell">
    <div class="section-head section-head--wide">
      <span class="eyebrow eyebrow--accent">In context</span>
      <h2>Against the rest of the set</h2>
      <p>The same table as the results page, with {label} marked.</p>
    </div>
    <div class="panel panel--flush">
      <div class="table-wrap">
        <table id="context-table">
          <thead>
            <tr>
              <th scope="col">Vendor</th>
              <th scope="col" class="num">Score</th>
              <th scope="col" class="num">Cost / query</th>
              <th scope="col" class="num">p50 latency</th>
              <th scope="col" class="num">Won outright</th>
              <th scope="col" class="num">Among best</th>
              <th scope="col">Returns</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
      </div>
    </div>
  </div>
</section>

<section id="caveats" class="seam">
  <div class="shell">
    <div class="section-head section-head--wide">
      <span class="eyebrow eyebrow--accent">Scope</span>
      <h2>Known limits</h2>
    </div>
    <div class="callout" style="max-width:76ch">
      <span class="eyebrow">Read this</span>
      <p>
        <span data-val="d.weeks"></span> <span data-val="d.weeks_plural"></span> of data. Scores
        carry roughly <span class="mono" data-val="latest.judging.mean_disagreement" data-fmt="n2"></span>
        points of judge-to-judge disagreement and the judge families differ by
        <span class="mono" data-val="latest.judging.family_spread" data-fmt="n2"></span> points on
        the same responses. Neither the score nor the whole ranking is firm: drop any one judge
        family and the top
        <span class="mono" data-val="latest.robustness.stable_prefix_leave_one_out" data-fmt="int"></span>
        of <span class="mono" data-val="latest.robustness.n_vendors" data-fmt="int"></span> places
        hold, but scored by a single family alone even first place moves.
        There is no human-labelled calibration set yet.
        <a href="../index.html#limits">The full list of limitations</a>.
      </p>
    </div>
    <p class="note" style="margin-top:1.4rem;max-width:76ch">
      One configuration is measured. If it misrepresents {label} — wrong tier, depth or parameters —
      corrections get a <a href="../methodology.html#changelog">changelog entry</a>, not a silent
      edit. <a href="mailto:{contact}">Report it</a>, or
      <a href="../data.html">recompute it from the export</a>.
    </p>
  </div>
</section>

</main>

<footer class="foot">
  <div class="shell foot__row">
    <div>
      <a class="brand" href="../index.html"><span class="brand__mark" aria-hidden="true"></span>Vannaris</a>
      <p style="margin:0;max-width:42ch">
        Independent benchmark of web-search APIs.<br>
        Data CC BY 4.0 · code MIT · not affiliated with any vendor listed.
      </p>
    </div>
    <div>
      <p class="foot__links" style="margin:0 0 0.8rem">
        <a href="../index.html">Overview</a>
        <a href="../results.html">Results</a>
        <a href="../methodology.html">Methodology</a>
        <a href="mailto:{contact}">Contact</a>
      </p>
      <p class="mono note" style="margin:0">
        run <span data-val="latest.week"></span>
      </p>
    </div>
  </div>
</footer>

<script>window.SB_VENDOR = "{id}";</script>
<script src="../data/bundle.js"></script>
<script>
/* Per-vendor page wiring. The vendor is named once, above; everything below
   reads it from there, so this file is identical for every vendor. */
window.SBPage = {{
  init: function () {{ this.categories(); this.context(); this.redraw(); }},

  redraw: function () {{
    var el = document.getElementById("fig-retained");
    if (!el) return;
    el.innerHTML = "";
    var panel = el.closest(".panel");
    var toggle = panel && panel.querySelector(".view-toggle");
    if (toggle) toggle.remove();
    window.SBCharts.retained(panel, window.SB_VENDOR);
  }},

  categories: function () {{
    var D = window.SB_DATA, h = window.SBCharts.helpers;
    var body = document.querySelector("#cat-table tbody");
    // Leader per category, so "behind leader" names who, not just how far. A
    // gap with no name attached is a number nobody can act on.
    var leaders = {{}};
    D.latest.cells.forEach(function (c) {{
      if (c.score == null) return;
      if (!leaders[c.category] || c.score > leaders[c.category].score) leaders[c.category] = c;
    }});
    D.categories.forEach(function (cat) {{
      var c = D.latest.cells.filter(function (x) {{
        return x.vendor === window.SB_VENDOR && x.category === cat.id;
      }})[0];
      var tr = document.createElement("tr");
      function td(text, cls) {{
        var e = document.createElement("td");
        if (cls) e.className = cls;
        e.textContent = text;
        return e;
      }}
      tr.appendChild(td(cat.label));
      if (!c || c.score == null) {{
        // Below the coverage floor: published as missing, which is the point.
        var gap = td("not published", "");
        gap.colSpan = 5;
        gap.className = "note";
        tr.appendChild(gap);
        body.appendChild(tr);
        return;
      }}
      var lead = leaders[cat.id];
      var isLead = lead && lead.vendor === window.SB_VENDOR;
      tr.appendChild(td(h.fmt(c.score), isLead ? "num best" : "num"));
      tr.appendChild(td(c.pct_of_best == null ? "—" : c.pct_of_best.toFixed(0) + "%", "num"));
      tr.appendChild(td(c.delta_from_best == null || c.delta_from_best === 0
        ? "—" : "−" + c.delta_from_best.toFixed(2), "num"));
      tr.appendChild(td(isLead ? "this vendor" : (lead ? h.vendorLabel[lead.vendor] : "—")));
      tr.appendChild(td(c.n_scored + " / " + c.n_queries, "num"));
      body.appendChild(tr);
    }});
  }},

  context: function () {{
    var D = window.SB_DATA, h = window.SBCharts.helpers;
    var modes = {{ ranked_results: "ranked results", both: "answer + ranked results",
                  synthesized_answer: "synthesized answer" }};
    var body = document.querySelector("#context-table tbody");
    var scores = D.latest.vendors.map(function (v) {{ return v.score; }});
    var lo = Math.min.apply(null, scores), hi = Math.max.apply(null, scores);
    var span = function (v) {{ return 14 + 86 * (hi > lo ? (v - lo) / (hi - lo) : 1); }};
    D.latest.vendors.forEach(function (v, i) {{
      var me = v.vendor === window.SB_VENDOR;
      var tr = document.createElement("tr");
      function td(text, cls) {{
        var e = document.createElement("td");
        if (cls) e.className = cls;
        e.textContent = text;
        return e;
      }}
      var name = document.createElement("td");
      name.innerHTML = '<span class="rank">' + String(i + 1).padStart(2, "0") + "</span>";
      var label = document.createElement("span");
      label.className = "vendor-name";
      label.textContent = v.label;
      if (me) {{
        name.appendChild(label);
        var tag = document.createElement("span");
        tag.className = "tag tag--accent";
        tag.textContent = "this page";
        tag.style.marginLeft = "0.55em";
        name.appendChild(tag);
      }} else {{
        var a = document.createElement("a");
        a.href = v.vendor + ".html";
        a.className = "vendor-name";
        a.textContent = v.label;
        name.appendChild(a);
      }}
      tr.appendChild(name);
      var sc = td(h.fmt(v.score), me ? "num meter best" : "num meter");
      sc.style.setProperty("--pct", span(v.score).toFixed(1));
      tr.appendChild(sc);
      tr.appendChild(td("$" + v.cost_per_query_usd.toFixed(5), "num"));
      tr.appendChild(td(v.p50_latency_ms.toLocaleString() + " ms", "num"));
      tr.appendChild(td(v.outright_wins, "num"));
      tr.appendChild(td(v.shared_best, "num"));
      tr.appendChild(td(modes[v.response_mode] || v.response_mode));
      body.appendChild(tr);
    }});
  }}
}};
</script>
<script src="../assets/charts.js"></script>
<script src="../assets/site.js"></script>
</body>
</html>
"""


def main() -> int:
    # Same shape as `python -m src.export --out`: a site root, so the whole
    # publish pipeline can be run against a generated fixture without touching
    # the real site/. That is how the pages get tested under a data state the
    # live export does not currently show.
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--site", default=str(ROOT / "site"), help="site root")
    args = ap.parse_args()
    site = Path(args.site).resolve()
    bundle = site / "data" / "bundle.js"
    out_dir = site / "vendors"

    if not bundle.exists():
        print(f"{bundle} not found — run `python -m src.export` first")
        return 1

    data = load_bundle(bundle)
    # Keyed on the vendors in the *published run*, not on the registry. The two
    # coincide on a healthy week and diverge on a degraded one — a vendor whose
    # calls all failed is in the cleared set but has no row to build a page
    # from, and a page of blanks about a vendor is worse than no page. The
    # registry is still where the docs link and the configuration note come
    # from, looked up by id.
    meta = {str(v["id"]): v for v in (data.get("vendors") or [])}
    vendors = (data.get("latest") or {}).get("vendors") or []
    if not vendors:
        print("the published run lists no vendors; nothing to generate")
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    wanted: set[str] = set()

    for v in vendors:
        vid = str(v["vendor"])
        reg = meta.get(vid, {})
        # The id becomes a filename and a JS string literal. The registry is
        # ours and these are already slugs, but generating a page from a value
        # without checking it is how a generator becomes an injection point.
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", vid):
            print(f"refusing to generate a page for a non-slug vendor id: {vid!r}")
            return 1
        page = PAGE.format(
            id=vid,
            label=esc(v.get("label") or reg.get("label") or vid),
            docs=esc(reg.get("docs") or "../methodology.html#vendors"),
            site=SITE_URL,
            contact=CONTACT,
        )
        path = out_dir / f"{vid}.html"
        path.write_text(page)
        wanted.add(path.name)
        print(f"wrote {rel(path)}")

    # A vendor pulled from the set must lose its page, or the site keeps
    # publishing a comparison the cleared set no longer covers.
    for stale in sorted(out_dir.glob("*.html")):
        if stale.name not in wanted:
            stale.unlink()
            print(f"removed {rel(stale)} (no longer in the export)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

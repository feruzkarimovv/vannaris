/* Charts.
 *
 * Every figure here is drawn from window.SB_DATA, which src/export.py
 * generates from the database. Nothing on this page is hand-entered, so a
 * number cannot drift away from the run that produced it.
 *
 * Three rules the drawing code follows, from the project's dataviz guidance:
 *   - quantity is carried by ONE blue sequential ramp; identity, where it is
 *     needed, is carried by direct labels rather than a second colour scale;
 *   - the vermilion signal colour is emphasis only — it marks the one series
 *     a chart is about, and never means "series 2";
 *   - every chart has a table equivalent behind a toggle, built from the same
 *     rows the SVG is built from, so the two cannot disagree.
 */
(function () {
  "use strict";

  var SVG = "http://www.w3.org/2000/svg";
  var D = window.SB_DATA;
  if (!D || !D.latest) return;

  var CATS = D.categories;
  var catLabel = {};
  CATS.forEach(function (c) { catLabel[c.id] = c.label; });
  var vendorLabel = {};
  D.vendors.forEach(function (v) { vendorLabel[v.id] = v.label; });

  /* --------------------------------------------------------------- helpers */
  function n(tag, attrs, text) {
    var e = document.createElementNS(SVG, tag);
    for (var k in attrs) if (attrs[k] != null) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  }
  function h(tag, attrs, children) {
    var e = document.createElement(tag);
    for (var k in attrs || {}) {
      if (k === "class") e.className = attrs[k];
      else if (k === "text") e.textContent = attrs[k];
      else if (attrs[k] != null) e.setAttribute(k, attrs[k]);
    }
    (children || []).forEach(function (c) { e.appendChild(c); });
    return e;
  }
  /* Marks are filled with a resolved colour rather than `var(--x)`, so that an
   * exported SVG carries its own colours. The fallbacks matter: an environment
   * that does not resolve custom properties through getComputedStyle would
   * otherwise hand back an empty string, and every mark would silently render
   * black. */
  var FALLBACK = {
    "--d100": "#cde2fb", "--d200": "#9ec5f4", "--d300": "#6da7ec", "--d400": "#3987e5",
    "--d500": "#256abf", "--d600": "#184f95", "--d700": "#0d366b",
    "--signal": "#d1521c", "--muted-mark": "#cfcec9", "--surface": "#fcfcfb"
  };
  /* Tokens resolve against the element the chart is being drawn into, not the
   * document root. A chart inside the ink band therefore picks up that band's
   * dark-surface steps without knowing it is in a dark band at all. */
  var CTX = null;
  function css(name) {
    var v = "";
    try {
      v = getComputedStyle(CTX || document.documentElement).getPropertyValue(name).trim();
    } catch (e) { /* fall through */ }
    return v || FALLBACK[name] || "currentColor";
  }
  function fmt(v, dp) {
    return v == null ? "—" : Number(v).toFixed(dp == null ? 2 : dp);
  }
  function money(v) {
    if (v == null) return "—";
    return v < 0.01 ? "$" + v.toFixed(4) : "$" + v.toFixed(2);
  }

  /* Sequential ramp, light→dark. Steps come from the CSS custom properties so
   * light and dark mode each use their own validated column. */
  function ramp(t) {
    var steps = ["--d100", "--d200", "--d300", "--d400", "--d500", "--d600", "--d700"];
    var i = Math.max(0, Math.min(steps.length - 1, Math.round(t * (steps.length - 1))));
    return { hex: css(steps[i]), step: i };
  }
  /* Ink or paper on top of a ramp fill, picked by how dark the step is so a
   * label inside a cell always clears contrast. */
  function onRamp(step) {
    // Light unless the page is explicitly stamped dark: the OS preference does
    // not decide this site's theme.
    var dark = document.documentElement.getAttribute("data-theme") === "dark";
    // On the dark ramp the light steps are the high scores, so the polarity of
    // the label colour inverts with it.
    if (dark) return step >= 4 ? "#0e0e10" : "#f6f6f3";
    return step >= 3 ? "#fbfbf9" : "#121210";
  }

  /* ------------------------------------------------------------- tooltip */
  var tip = h("div", { class: "tooltip", role: "status", "aria-live": "polite" });
  document.body.appendChild(tip);
  var tipTimer;

  function showTip(evt, html) {
    tip.innerHTML = html;
    tip.setAttribute("data-show", "");
    moveTip(evt);
    clearTimeout(tipTimer);
  }
  function moveTip(evt) {
    var pad = 14;
    var x = (evt.clientX != null ? evt.clientX : 0) + pad;
    var y = (evt.clientY != null ? evt.clientY : 0) + pad;
    var r = tip.getBoundingClientRect();
    if (x + r.width > window.innerWidth - 8) x = window.innerWidth - r.width - 8;
    if (y + r.height > window.innerHeight - 8) y = evt.clientY - r.height - pad;
    tip.style.left = Math.max(8, x) + "px";
    tip.style.top = Math.max(8, y) + "px";
  }
  function hideTip() { tip.removeAttribute("data-show"); }

  /* A hit target sits over every mark: marks are thin by design, and a 4px
   * bar is not a usable pointer or focus target. */
  function hit(g, box, label, html) {
    var r = n("rect", {
      x: box.x, y: box.y, width: Math.max(box.w, 1), height: Math.max(box.h, 1),
      class: "hit", tabindex: "0", role: "img", "aria-label": label
    });
    r.addEventListener("mouseenter", function (e) { showTip(e, html); });
    r.addEventListener("mousemove", moveTip);
    r.addEventListener("mouseleave", hideTip);
    r.addEventListener("focus", function () {
      var b = r.getBoundingClientRect();
      showTip({ clientX: b.left + b.width / 2, clientY: b.top }, html);
    });
    r.addEventListener("blur", hideTip);
    g.appendChild(r);
    return r;
  }

  function tipRows(title, rows) {
    return "<b>" + title + "</b>" + rows.map(function (r) {
      return '<div class="t-row"><span>' + r[0] + "</span><span>" + r[1] + "</span></div>";
    }).join("");
  }

  /* --------------------------------------------------- figure + table view */
  function figure(host, spec) {
    // spec: { svg, table: {head:[], rows:[[]], numeric:[bool] }, legend }
    var chart = h("div", { class: "chart" });
    if (spec.animate !== false) chart.setAttribute("data-animate", "");
    chart.appendChild(spec.svg);
    if (spec.legend) chart.appendChild(spec.legend);

    var tableWrap = h("div", { class: "table-wrap", hidden: "" });
    var table = h("table");
    var thead = h("thead");
    thead.appendChild(h("tr", {}, spec.table.head.map(function (t, i) {
      return h("th", { class: spec.table.numeric[i] ? "num" : "", scope: "col", text: t });
    })));
    var tbody = h("tbody");
    spec.table.rows.forEach(function (r) {
      tbody.appendChild(h("tr", {}, r.map(function (c, i) {
        return h("td", { class: spec.table.numeric[i] ? "num" : "", text: c == null ? "—" : String(c) });
      })));
    });
    table.appendChild(thead); table.appendChild(tbody);
    tableWrap.appendChild(table);

    var bChart = h("button", { type: "button", text: "chart", "aria-pressed": "true" });
    var bTable = h("button", { type: "button", text: "table", "aria-pressed": "false" });
    var toggle = h("div", { class: "view-toggle", role: "group", "aria-label": "View as" }, [bChart, bTable]);
    function set(showChart) {
      chart.hidden = !showChart;
      tableWrap.hidden = showChart;
      bChart.setAttribute("aria-pressed", String(showChart));
      bTable.setAttribute("aria-pressed", String(!showChart));
    }
    bChart.addEventListener("click", function () { set(true); });
    bTable.addEventListener("click", function () { set(false); });

    var head = host.querySelector(".panel__head");
    if (head) head.appendChild(toggle);
    var body = host.querySelector(".panel__body") || host;
    body.appendChild(chart);
    body.appendChild(tableWrap);
  }

  /* ============================================================== heatmap */
  /* Vendor × category quality. A grid of magnitudes is the one job a
   * sequential ramp is unambiguously right for, and it sidesteps needing five
   * categorical hues for five vendors. */
  function heatmap(host, opts) {
    opts = opts || {};
    CTX = host;
    var cells = D.latest.cells;
    var vendors = D.latest.vendors.map(function (v) { return v.vendor; });
    var byKey = {};
    cells.forEach(function (c) { byKey[c.vendor + "|" + c.category] = c; });

    var scores = cells.map(function (c) { return c.score; }).filter(function (s) { return s != null; });
    var lo = Math.floor(Math.min.apply(null, scores) * 2) / 2;
    var hi = Math.ceil(Math.max.apply(null, scores) * 2) / 2;

    // Header labels wrap to at most two lines, and the block is bottom-aligned
    // to a fixed baseline above the grid so a two-line label can never grow
    // down into the first row of cells.
    var wrapped = CATS.map(function (c) {
      var words = c.label.split(" ");
      if (words.length < 3) return words;
      return [words[0], words.slice(1).join(" ")];
    });

    var padL = 96, padT = 52, cellH = 42, gap = 2, lineH = 13;
    var cols = CATS.length;
    var W = 760, cellW = (W - padL) / cols;
    var H = padT + vendors.length * cellH + 8;

    var svg = n("svg", { viewBox: "0 0 " + W + " " + H, role: "group",
      "aria-label": "Quality score by vendor and category, 0 to 10" });

    CATS.forEach(function (c, i) {
      var x = padL + i * cellW + (cellW - gap) / 2;
      var lines = wrapped[i];
      var firstBaseline = padT - 14 - (lines.length - 1) * lineH;
      var t = n("text", { x: x, y: firstBaseline, class: "mark-name", "text-anchor": "middle" });
      lines.forEach(function (word, wi) {
        t.appendChild(n("tspan", { x: x, dy: wi === 0 ? 0 : lineH }, word));
      });
      svg.appendChild(t);
    });

    vendors.forEach(function (v, r) {
      var y = padT + r * cellH;
      svg.appendChild(n("text", {
        x: padL - 12, y: y + cellH / 2 + 4, class: "mark-name", "text-anchor": "end"
      }, vendorLabel[v] || v));

      CATS.forEach(function (c, i) {
        var cell = byKey[v + "|" + c.id];
        var x = padL + i * cellW;
        if (!cell || cell.score == null) {
          svg.appendChild(n("rect", { x: x, y: y, width: cellW - gap, height: cellH - gap,
            fill: "var(--surface-2)", stroke: "var(--line)", "stroke-dasharray": "2 2" }));
          return;
        }
        var t = (cell.score - lo) / (hi - lo);
        var fill = ramp(t);
        svg.appendChild(n("rect", { x: x, y: y, width: cellW - gap, height: cellH - gap,
          fill: fill.hex, rx: 2, class: "cell-in", style: "--i:" + (r * CATS.length + i) }));
        svg.appendChild(n("text", {
          x: x + (cellW - gap) / 2, y: y + cellH / 2 + 4, class: "cell-label",
          "text-anchor": "middle", fill: onRamp(fill.step)
        }, fmt(cell.score)));

        hit(svg, { x: x, y: y, w: cellW - gap, h: cellH - gap },
          (vendorLabel[v] || v) + ", " + c.label + ": " + fmt(cell.score) + " out of 10",
          tipRows((vendorLabel[v] || v) + " · " + c.label, [
            ["score", fmt(cell.score) + " / 10"],
            ["gap to best", cell.delta_from_best ? "−" + fmt(cell.delta_from_best) : "best"],
            ["p50 latency", cell.p50_latency_ms + " ms"],
            ["queries scored", cell.n_scored + " / " + cell.n_queries]
          ]));
      });
    });

    var lgSteps = [0, 0.25, 0.5, 0.75, 1].map(function (t) { return ramp(t).hex; });
    var legend = h("div", { class: "legend" }, [
      h("span", { class: "legend__item" }, [
        h("span", { text: fmt(lo, 1) }),
        h("span", { class: "legend__ramp" }, lgSteps.map(function (c) {
          return h("i", { style: "background:" + c });
        })),
        h("span", { text: fmt(hi, 1) + " · ensemble median, 0–10" })
      ])
    ]);

    var rows = [];
    vendors.forEach(function (v) {
      CATS.forEach(function (c) {
        var cell = byKey[v + "|" + c.id];
        if (cell) rows.push([vendorLabel[v] || v, c.label, fmt(cell.score),
          cell.n_scored + "/" + cell.n_queries, cell.p50_latency_ms]);
      });
    });

    figure(host, {
      svg: svg, legend: opts.legend === false ? null : legend,
      table: { head: ["Vendor", "Category", "Score", "Scored", "p50 ms"],
               numeric: [false, false, true, true, true], rows: rows }
    });
  }

  /* ========================================================= cost vs score */
  /* The headline finding. Log x because the cost spread is 23×; identity is
   * carried by direct labels, and the one highlighted point is the argument. */
  function costQuality(host) {
    CTX = host;
    var vs = D.latest.vendors.filter(function (v) { return v.score != null && v.cost_per_query_usd; });
    var W = 720, H = 380, padL = 52, padR = 24, padT = 24, padB = 54;

    var costs = vs.map(function (v) { return v.cost_per_query_usd; });
    var x0 = Math.log10(Math.min.apply(null, costs)) - 0.25;
    var x1 = Math.log10(Math.max.apply(null, costs)) + 0.25;
    var scores = vs.map(function (v) { return v.score; });
    var y0 = Math.floor(Math.min.apply(null, scores) * 2) / 2 - 0.25;
    var y1 = Math.ceil(Math.max.apply(null, scores) * 2) / 2 + 0.25;

    var X = function (c) { return padL + (Math.log10(c) - x0) / (x1 - x0) * (W - padL - padR); };
    var Y = function (s) { return H - padB - (s - y0) / (y1 - y0) * (H - padT - padB); };

    var svg = n("svg", { viewBox: "0 0 " + W + " " + H, role: "group",
      "aria-label": "Cost per query against quality score, by vendor" });

    for (var s = Math.ceil(y0 * 2) / 2; s <= y1; s += 0.5) {
      if (Math.abs(s * 2 % 2) > 0.01) continue;
      svg.appendChild(n("line", { x1: padL, x2: W - padR, y1: Y(s), y2: Y(s), class: "grid-line" }));
      svg.appendChild(n("text", { x: padL - 8, y: Y(s) + 3.5, class: "tick", "text-anchor": "end" }, s.toFixed(0)));
    }
    [0.0003, 0.001, 0.003, 0.01].forEach(function (c) {
      if (Math.log10(c) < x0 || Math.log10(c) > x1) return;
      svg.appendChild(n("text", { x: X(c), y: H - padB + 18, class: "tick", "text-anchor": "middle" },
        "$" + c.toFixed(4).replace(/0+$/, "").replace(/\.$/, "")));
    });
    svg.appendChild(n("line", { x1: padL, x2: W - padR, y1: H - padB, y2: H - padB,
      class: "grid-line", style: "stroke: var(--line-strong)" }));
    svg.appendChild(n("text", { x: (padL + W - padR) / 2, y: H - 8, class: "axis-title",
      "text-anchor": "middle" }, "cost per query (log scale)"));
    svg.appendChild(n("text", { x: 12, y: padT + 4, class: "axis-title" }, "score"));

    var cheapest = vs.reduce(function (a, b) { return a.cost_per_query_usd <= b.cost_per_query_usd ? a : b; });

    // Vendors that price identically land on the same x, and their labels then
    // sit on top of each other. Rather than nudge labels away from their marks,
    // a colliding label flips to the underside of its own point.
    var placed = [];
    function labelY(cx, cy) {
      var above = { x: cx, y: cy - 14 };
      var clash = placed.some(function (p) {
        return Math.abs(p.x - above.x) < 64 && Math.abs(p.y - above.y) < 26;
      });
      var spot = clash ? { x: cx, y: cy + 20 } : above;
      placed.push(spot);
      return spot.y;
    }

    vs.forEach(function (v) {
      var isSignal = v.vendor === cheapest.vendor;
      var colour = isSignal ? css("--signal") : css("--d400");
      var cx = X(v.cost_per_query_usd), cy = Y(v.score);
      svg.appendChild(n("circle", { cx: cx, cy: cy, r: 6.5, fill: colour,
        stroke: css("--surface"), "stroke-width": 2 }));
      svg.appendChild(n("text", {
        x: cx, y: labelY(cx, cy), "text-anchor": "middle",
        class: "mark-label" + (isSignal ? " mark-label--strong" : "")
      }, v.label));
      hit(svg, { x: cx - 16, y: cy - 16, w: 32, h: 32 },
        v.label + ": " + money(v.cost_per_query_usd) + " per query, score " + fmt(v.score),
        tipRows(v.label, [
          ["score", fmt(v.score) + " / 10"],
          ["cost / query", money(v.cost_per_query_usd)],
          ["p50 latency", v.p50_latency_ms + " ms"],
          ["queries won", v.wins + " of 150"]
        ]));
    });

    var legend = h("div", { class: "legend" }, [
      h("span", { class: "legend__item" }, [
        h("span", { class: "legend__swatch", style: "background:" + css("--signal") }),
        h("span", { text: cheapest.label + " — cheapest per query" })
      ]),
      h("span", { class: "legend__item" }, [
        h("span", { class: "legend__swatch", style: "background:" + css("--d400") }),
        h("span", { text: "other vendors" })
      ])
    ]);

    figure(host, {
      svg: svg, legend: legend,
      table: {
        head: ["Vendor", "Score", "Cost / query", "p50 ms", "Queries won"],
        numeric: [false, true, true, true, true],
        rows: vs.map(function (v) {
          return [v.label, fmt(v.score), "$" + v.cost_per_query_usd.toFixed(5), v.p50_latency_ms, v.wins];
        })
      }
    });
  }

  /* ============================================================== latency */
  function latency(host) {
    CTX = host;
    var vs = D.latest.vendors.slice().sort(function (a, b) { return a.p50_latency_ms - b.p50_latency_ms; });
    var W = 560, rowH = 34, padL = 92, padR = 62, padT = 8;
    var H = padT + vs.length * rowH + 26;
    var max = Math.max.apply(null, vs.map(function (v) { return v.p50_latency_ms; }));
    var scale = function (v) { return (v / (max * 1.02)) * (W - padL - padR); };

    var svg = n("svg", { viewBox: "0 0 " + W + " " + H, role: "group",
      "aria-label": "Median response latency by vendor" });

    vs.forEach(function (v, i) {
      var y = padT + i * rowH, barH = 14;
      svg.appendChild(n("text", { x: padL - 12, y: y + barH / 2 + 4, class: "mark-name",
        "text-anchor": "end" }, v.label));
      var w = scale(v.p50_latency_ms);
      // 4px rounded data-end, square at the baseline.
      var d = "M" + padL + " " + y + " H" + (padL + w - 4) +
              " a4 4 0 0 1 4 4 v" + (barH - 8) + " a4 4 0 0 1 -4 4 H" + padL + " Z";
      svg.appendChild(n("path", { d: d, fill: css("--d400"), class: "bar-in", style: "--i:" + i }));
      svg.appendChild(n("text", { x: padL + w + 8, y: y + barH / 2 + 4, class: "mark-label" },
        v.p50_latency_ms.toLocaleString() + " ms"));
      hit(svg, { x: padL, y: y - 4, w: W - padL - padR, h: rowH - 4 },
        v.label + ": " + v.p50_latency_ms + " milliseconds median",
        tipRows(v.label, [["p50 latency", v.p50_latency_ms + " ms"], ["score", fmt(v.score)]]));
    });
    svg.appendChild(n("text", { x: padL, y: H - 6, class: "axis-title" },
      "median across 150 queries · lower is better"));

    figure(host, {
      svg: svg, legend: null,
      table: { head: ["Vendor", "p50 latency (ms)", "Score"], numeric: [false, true, true],
               rows: vs.map(function (v) { return [v.label, v.p50_latency_ms, fmt(v.score)]; }) }
    });
  }

  /* ====================================================== quality retained */
  /* Emphasis, not categorical: the story is which two categories fall off the
   * cliff, so those two are in the signal colour and the rest recede. */
  function retained(host, vendorId) {
    CTX = host;
    var cells = D.latest.cells.filter(function (c) { return c.vendor === vendorId && c.pct_of_best != null; });
    var order = CATS.map(function (c) { return c.id; });
    cells.sort(function (a, b) { return b.pct_of_best - a.pct_of_best; });

    var W = 620, rowH = 34, padL = 136, padR = 56, padT = 8;
    var H = padT + cells.length * rowH + 26;
    var lo = 70; // axis floor: the interesting range is 80–100, not 0–100
    var scale = function (p) { return Math.max(0, (p - lo) / (100 - lo)) * (W - padL - padR); };
    var CLIFF = 90;

    var svg = n("svg", { viewBox: "0 0 " + W + " " + H, role: "group",
      "aria-label": "Share of the best available score reached by " + (vendorLabel[vendorId] || vendorId) });

    // The floor is a tick like any other, so the truncated axis is stated by
    // the scale itself rather than by a note sitting on top of the tick row.
    [lo, 80, 90, 100].forEach(function (p) {
      var x = padL + scale(p);
      svg.appendChild(n("line", { x1: x, x2: x, y1: padT - 2, y2: padT + cells.length * rowH - 6,
        class: "grid-line" }));
      svg.appendChild(n("text", { x: x, y: H - 10, class: "tick", "text-anchor": "middle" }, p + "%"));
    });

    cells.forEach(function (c, i) {
      var y = padT + i * rowH, barH = 14;
      var below = c.pct_of_best < CLIFF;
      svg.appendChild(n("text", { x: padL - 12, y: y + barH / 2 + 4, class: "mark-name",
        "text-anchor": "end" }, catLabel[c.category]));
      var w = Math.max(scale(c.pct_of_best), 3);
      var d = "M" + padL + " " + y + " H" + (padL + w - 4) +
              " a4 4 0 0 1 4 4 v" + (barH - 8) + " a4 4 0 0 1 -4 4 H" + padL + " Z";
      svg.appendChild(n("path", { d: d, fill: below ? css("--signal") : css("--muted-mark"),
        class: "bar-in", style: "--i:" + i }));
      svg.appendChild(n("text", {
        x: padL + w + 8, y: y + barH / 2 + 4,
        class: "mark-label" + (below ? " mark-label--strong" : "")
      }, c.pct_of_best.toFixed(0) + "%"));
      hit(svg, { x: padL, y: y - 4, w: W - padL - padR, h: rowH - 4 },
        catLabel[c.category] + ": " + c.pct_of_best.toFixed(0) + " percent of the best score",
        tipRows(catLabel[c.category], [
          ["share of best", c.pct_of_best.toFixed(1) + "%"],
          [(vendorLabel[vendorId] || vendorId) + " score", fmt(c.score)],
          ["gap", "−" + fmt(c.delta_from_best) + " pts"]
        ]));
    });
    var legend = h("div", { class: "legend" }, [
      h("span", { class: "legend__item" }, [
        h("span", { class: "legend__swatch", style: "background:" + css("--signal") }),
        h("span", { text: "below 90% of the best score — escalate here" })
      ]),
      h("span", { class: "legend__item" }, [
        h("span", { class: "legend__swatch", style: "background:" + css("--muted-mark") }),
        h("span", { text: "90% or above — the cheap vendor is good enough" })
      ])
    ]);

    figure(host, {
      svg: svg, legend: legend,
      table: {
        head: ["Category", "% of best", "Score", "Gap"],
        numeric: [false, true, true, true],
        rows: cells.map(function (c) {
          return [catLabel[c.category], c.pct_of_best.toFixed(1) + "%", fmt(c.score), "−" + fmt(c.delta_from_best)];
        })
      }
    });
  }

  /* ================================================================ judges */
  function judges(host) {
    CTX = host;
    var js = D.latest.judging.judges.filter(function (j) { return j.mean != null; });
    var W = 560, rowH = 36, padL = 92, padR = 58, padT = 8;
    var H = padT + js.length * rowH + 26;
    var lo = 7, hi = 9.4;
    var scale = function (v) { return Math.max(0, (v - lo) / (hi - lo)) * (W - padL - padR); };

    var svg = n("svg", { viewBox: "0 0 " + W + " " + H, role: "group",
      "aria-label": "Mean score awarded by each judge family" });

    // Truncated axis, stated by its own floor tick rather than a note that
    // would sit on top of the tick row.
    [lo, 8, 9].forEach(function (v) {
      var x = padL + scale(v);
      svg.appendChild(n("line", { x1: x, x2: x, y1: padT - 2, y2: padT + js.length * rowH - 8, class: "grid-line" }));
      svg.appendChild(n("text", { x: x, y: H - 10, class: "tick", "text-anchor": "middle" }, String(v)));
    });

    js.forEach(function (j, i) {
      var y = padT + i * rowH, barH = 14;
      svg.appendChild(n("text", { x: padL - 12, y: y + barH / 2 + 4, class: "mark-name",
        "text-anchor": "end" }, j.family));
      var w = Math.max(scale(j.mean), 3);
      var d = "M" + padL + " " + y + " H" + (padL + w - 4) +
              " a4 4 0 0 1 4 4 v" + (barH - 8) + " a4 4 0 0 1 -4 4 H" + padL + " Z";
      svg.appendChild(n("path", { d: d, fill: css("--d400"), class: "bar-in", style: "--i:" + i }));
      svg.appendChild(n("text", { x: padL + w + 8, y: y + barH / 2 + 4, class: "mark-label" }, fmt(j.mean)));
      hit(svg, { x: padL, y: y - 4, w: W - padL - padR, h: rowH - 6 },
        j.family + " judge mean score " + fmt(j.mean),
        tipRows(j.family, [["model", j.model], ["mean score", fmt(j.mean)],
          ["responses scored", j.n], ["coverage", (j.coverage * 100).toFixed(1) + "%"]]));
    });

    figure(host, {
      svg: svg, legend: null,
      table: { head: ["Judge family", "Model", "Mean score", "Responses", "Coverage"],
               numeric: [false, false, true, true, true],
               rows: js.map(function (j) {
                 return [j.family, j.model, fmt(j.mean), j.n, (j.coverage * 100).toFixed(1) + "%"];
               }) }
    });
  }

  /* ====================================================== score distribution */
  /* Where each vendor's queries actually land, as an ordered share.
   *
   * A jittered dot strip was the first attempt and was wrong: the ensemble
   * median of three near-integer scores is itself near-integer, so the dots
   * stacked into vertical stripes and read as an artefact rather than as a
   * distribution. An ordered-scale share is the right form for that data, and
   * it makes the published limitation — almost everything lands in the top
   * three bands — visible at a glance instead of merely asserted. */
  function distribution(host) {
    CTX = host;
    var X = window.SB_DETAIL;
    if (!X) return;

    var BANDS = [
      { lo: 0, hi: 6, label: "under 6", step: "--d300" },
      { lo: 6, hi: 7, label: "6–7", step: "--d400" },
      { lo: 7, hi: 8, label: "7–8", step: "--d500" },
      { lo: 8, hi: 9, label: "8–9", step: "--d600" },
      { lo: 9, hi: 10.01, label: "9–10", step: "--d700" }
    ];

    var byVendor = {};
    X.rows.forEach(function (r) {
      if (r.m == null) return;
      (byVendor[r.v] = byVendor[r.v] || []).push(r.m);
    });
    var vendors = D.latest.vendors.map(function (v) { return v.vendor; })
      .filter(function (v) { return byVendor[v] && byVendor[v].length; });

    var W = 700, rowH = 46, padL = 104, padR = 54, padT = 10, barH = 22, gap = 2;
    var H = padT + vendors.length * rowH + 30;
    var track = W - padL - padR;

    var svg = n("svg", { viewBox: "0 0 " + W + " " + H, role: "group",
      "aria-label": "Share of each vendor's queries falling in each score band" });

    var shares = {};
    vendors.forEach(function (v, i) {
      var vals = byVendor[v];
      var counts = BANDS.map(function (b) {
        return vals.filter(function (x) { return x >= b.lo && x < b.hi; }).length;
      });
      shares[v] = counts;

      var y = padT + i * rowH;
      svg.appendChild(n("text", { x: padL - 14, y: y + barH / 2 + 4, class: "mark-name",
        "text-anchor": "end" }, vendorLabel[v] || v));

      var x = padL;
      counts.forEach(function (c, bi) {
        if (!c) return;
        var w = (c / vals.length) * track;
        // 2px surface gap between segments: white does the separating, not a
        // stroke, so no segment carries ink that is not data.
        svg.appendChild(n("rect", {
          x: x, y: y, width: Math.max(w - gap, 1), height: barH,
          fill: css(BANDS[bi].step), rx: 1,
          class: "bar-in", style: "--i:" + i
        }));
        hit(svg, { x: x, y: y, w: Math.max(w - gap, 1), h: barH },
          (vendorLabel[v] || v) + ", " + BANDS[bi].label + ": " + c + " queries",
          tipRows((vendorLabel[v] || v) + " · " + BANDS[bi].label, [
            ["queries", c],
            ["share", (100 * c / vals.length).toFixed(1) + "%"]
          ]));
        x += w;
      });

      // One direct label per row: the share in the top band, which is the
      // number the chart exists to show.
      var topShare = 100 * counts[counts.length - 1] / vals.length;
      svg.appendChild(n("text", { x: padL + track + 10, y: y + barH / 2 + 4,
        class: "mark-label" }, topShare.toFixed(0) + "%"));
    });

    svg.appendChild(n("text", { x: padL, y: H - 8, class: "axis-title" },
      "share of scored queries · label is the 9–10 band"));

    var legend = h("div", { class: "legend" }, BANDS.map(function (b) {
      return h("span", { class: "legend__item" }, [
        h("span", { class: "legend__swatch", style: "background:" + css(b.step) }),
        h("span", { text: b.label })
      ]);
    }));

    figure(host, {
      svg: svg, legend: legend,
      table: {
        head: ["Vendor"].concat(BANDS.map(function (b) { return b.label; })).concat(["Scored"]),
        numeric: [false, true, true, true, true, true, true],
        rows: vendors.map(function (v) {
          var total = byVendor[v].length;
          return [vendorLabel[v] || v].concat(shares[v].map(function (c) {
            return c + " (" + (100 * c / total).toFixed(0) + "%)";
          })).concat([total]);
        })
      }
    });
  }

  /* ================================================== judge disagreement */
  /* How far apart the three judges were on the same response, bucketed. The
   * headline "mean disagreement 1.77" is a summary of this shape, and the
   * shape is the more honest object: the tail past 3 points is where the
   * ensemble is doing real work. */
  function disagreement(host) {
    CTX = host;
    var X = window.SB_DETAIL;
    if (!X) return;

    var BUCKETS = [[0, 1], [1, 2], [2, 3], [3, 4], [4, 10]];
    var counts = BUCKETS.map(function () { return 0; });
    var total = 0;
    X.rows.forEach(function (r) {
      var vals = r.s.filter(function (v) { return v != null; });
      if (vals.length < 2) return;
      var spread = Math.max.apply(null, vals) - Math.min.apply(null, vals);
      total++;
      for (var i = 0; i < BUCKETS.length; i++) {
        if (spread >= BUCKETS[i][0] && (spread < BUCKETS[i][1] || i === BUCKETS.length - 1)) {
          counts[i]++; break;
        }
      }
    });

    var W = 620, padL = 74, padR = 46, padT = 14, colW = (W - padL - padR) / BUCKETS.length;
    var H = 250, base = H - 46;
    var max = Math.max.apply(null, counts) || 1;

    var svg = n("svg", { viewBox: "0 0 " + W + " " + H, role: "group",
      "aria-label": "How far apart the three judges were, by number of responses" });

    [0, 0.5, 1].forEach(function (f) {
      var y = base - f * (base - padT);
      svg.appendChild(n("line", { x1: padL - 8, x2: W - padR, y1: y, y2: y, class: "grid-line" }));
      svg.appendChild(n("text", { x: padL - 14, y: y + 3.5, class: "tick", "text-anchor": "end" },
        Math.round(f * max).toLocaleString()));
    });

    var LABELS = ["under 1", "1–2", "2–3", "3–4", "4+"];
    counts.forEach(function (c, i) {
      var barW = Math.min(colW - 14, 52);
      var x = padL + i * colW + (colW - barW) / 2;
      var hgt = (c / max) * (base - padT);
      var over3 = i >= 3;
      // Columns: 4px rounded cap, square at the baseline.
      var d = "M" + x + " " + base + " V" + (base - hgt + 4) +
              " a4 4 0 0 1 4 -4 h" + (barW - 8) + " a4 4 0 0 1 4 4 V" + base + " Z";
      svg.appendChild(n("path", { d: d, fill: over3 ? css("--signal") : css("--d400"),
        class: "bar-in", style: "--i:" + i }));
      svg.appendChild(n("text", { x: x + barW / 2, y: base - hgt - 8,
        class: "mark-label" + (over3 ? " mark-label--strong" : ""), "text-anchor": "middle" },
        c.toLocaleString()));
      svg.appendChild(n("text", { x: x + barW / 2, y: base + 18, class: "tick",
        "text-anchor": "middle" }, LABELS[i]));

      hit(svg, { x: padL + i * colW, y: padT, w: colW, h: base - padT + 20 },
        LABELS[i] + " points apart: " + c + " responses",
        tipRows(LABELS[i] + " points apart", [
          ["responses", c.toLocaleString()],
          ["share", (100 * c / total).toFixed(1) + "%"]
        ]));
    });

    svg.appendChild(n("line", { x1: padL - 8, x2: W - padR, y1: base, y2: base,
      class: "grid-line", stroke: css("--muted-mark") }));
    svg.appendChild(n("text", { x: padL, y: H - 8, class: "axis-title" },
      "points between the highest and lowest judge"));

    var legend = h("div", { class: "legend" }, [
      h("span", { class: "legend__item" }, [
        h("span", { class: "legend__swatch", style: "background:" + css("--signal") }),
        h("span", { text: "more than 3 points apart on the same response" })
      ])
    ]);

    figure(host, {
      svg: svg, legend: legend,
      table: {
        head: ["Judges apart by", "Responses", "Share"],
        numeric: [false, true, true],
        rows: counts.map(function (c, i) {
          return [LABELS[i] + " points", c.toLocaleString(), (100 * c / total).toFixed(1) + "%"];
        })
      }
    });
  }

  window.SBCharts = {
    heatmap: heatmap, costQuality: costQuality, latency: latency,
    retained: retained, judges: judges,
    distribution: distribution, disagreement: disagreement,
    helpers: { fmt: fmt, money: money, catLabel: catLabel, vendorLabel: vendorLabel, h: h }
  };
})();

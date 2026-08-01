/* Page furniture, and the rule that no number on this site is typed by hand.
 *
 * Any element carrying data-val="<path>" has its text replaced with that value
 * from window.SB_DATA (or from the small set of derived figures below). If the
 * export changes, the prose changes with it; if a figure is missing, the
 * element says so loudly rather than silently keeping stale copy. The point is
 * that a claim on the landing page and a cell in the table cannot drift apart.
 */
(function () {
  "use strict";

  document.documentElement.classList.add("js");

  /* matchMedia is missing in some non-browser DOM implementations (the site
   * smoke test runs in one). Guarding is cheaper than a crash that takes the
   * whole page's data-filling with it. */
  function media(query) {
    return typeof window.matchMedia === "function" && window.matchMedia(query).matches;
  }
  window.SBMedia = media;

  /* ------------------------------------------------------------- theme */
  var stored = null;
  try { stored = localStorage.getItem("sb-theme"); } catch (e) { /* private mode */ }
  if (stored === "dark" || stored === "light") {
    document.documentElement.setAttribute("data-theme", stored);
  }

  function wireTheme() {
    var btn = document.querySelector("[data-theme-toggle]");
    if (!btn) return;
    // Dark is the unconditional default now, not a response to the OS setting,
    // so the only thing that can make the page light is an explicit stamp.
    // Reading prefers-color-scheme here would make the button offer "dark" on a
    // page that is already dark.
    function current() {
      return document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
    }
    function paint() {
      var mode = current();
      btn.setAttribute("aria-label", "Switch to " + (mode === "dark" ? "light" : "dark") + " theme");
      btn.textContent = mode === "dark" ? "light" : "dark";
    }
    btn.addEventListener("click", function () {
      var next = current() === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try { localStorage.setItem("sb-theme", next); } catch (e) { /* ignore */ }
      paint();
      // Charts read their colours from CSS custom properties at draw time, so
      // they are rebuilt rather than left in the previous mode's palette.
      if (window.SBPage && window.SBPage.redraw) window.SBPage.redraw();
      scan();
    });
    paint();
  }

  /* --------------------------------------------------------------- values */
  var D = window.SB_DATA;

  function derived() {
    if (!D || !D.latest) return {};
    var vs = D.latest.vendors;
    var withCost = vs.filter(function (v) { return v.cost_per_query_usd; });
    var cheap = withCost.reduce(function (a, b) { return a.cost_per_query_usd <= b.cost_per_query_usd ? a : b; });
    var top = vs[0];
    var cells = D.latest.cells.filter(function (c) { return c.vendor === cheap.vendor && c.pct_of_best != null; });
    var weak = cells.filter(function (c) { return c.pct_of_best < 90; })
                    .sort(function (a, b) { return a.pct_of_best - b.pct_of_best; });
    var strong = cells.filter(function (c) { return c.pct_of_best >= 90; })
                      .sort(function (a, b) { return a.pct_of_best - b.pct_of_best; });
    var catLabel = {};
    D.categories.forEach(function (c) { catLabel[c.id] = c.label; });
    var tr = D.track_record;

    return {
      top_vendor: top.label,
      top_score: top.score,
      cheap_vendor: cheap.label,
      cheap_score: cheap.score,
      cheap_cost: cheap.cost_per_query_usd,
      top_cost: top.cost_per_query_usd,
      cost_ratio: top.cost_per_query_usd / cheap.cost_per_query_usd,
      cost_pct: 100 * cheap.cost_per_query_usd / top.cost_per_query_usd,
      strong_lo: strong.length ? strong[0].pct_of_best : null,
      strong_hi: strong.length ? strong[strong.length - 1].pct_of_best : null,
      strong_n: strong.length,
      weak_lo: weak.length ? weak[0].pct_of_best : null,
      weak_hi: weak.length ? weak[weak.length - 1].pct_of_best : null,
      weak_cats: weak.map(function (c) { return catLabel[c.category].toLowerCase(); }).join(" and "),
      n_categories: D.categories.length,
      n_vendors: D.vendors.length,
      n_judges: D.judges.length,
      fastest: vs.slice().sort(function (a, b) { return a.p50_latency_ms - b.p50_latency_ms; })[0],
      slowest: vs.slice().sort(function (a, b) { return b.p50_latency_ms - a.p50_latency_ms; })[0],
      weeks: tr.weeks_published,
      weeks_plural: tr.weeks_published === 1 ? "week" : "weeks",
      // The cadence sentences. Written here rather than in the pages because
      // CLAUDE.md forbids asserting a schedule the data does not show, and copy
      // typed into HTML cannot notice when it stops being true. `weeks` and
      // `schedule_started` both come from src/export.py, which computes them
      // from the runs themselves.
      schedule_state: !tr.schedule_started
        ? "has not started yet"
        : "has been running since " + tr.first_scheduled_week,
      schedule_note: !tr.schedule_started
        ? "the schedule has not started"
        : tr.scheduled_weeks + " " + (tr.scheduled_weeks === 1 ? "week" : "weeks") + " on schedule",
      trend_note: tr.weeks_published < 3
        ? "Nothing here is a trend, and this site will not call itself continuously run until it is."
        : "Week-over-week movement is visible, and every published week stays in the data export.",
      // The open-gaps copy. Both pages list the scheduled run as unbuilt; once
      // it has run, saying so is the same overclaim in reverse.
      unbuilt: !tr.schedule_started
        ? "Two things this methodology calls for are not implemented: a human-labelled calibration set scored against the judge ensemble monthly, and a scheduled weekly run."
        : "One thing this methodology calls for is not implemented: a human-labelled calibration set scored against the judge ensemble monthly.",
      track_dt: tr.weeks_published < 2
        ? "One week is not a track record"
        : tr.weeks_published + " weeks is a short track record",
      track_dd: tr.weeks_published < 2
        ? "One complete run exists. Week-over-week movement, the thing this benchmark is actually for, cannot be shown yet."
        : tr.weeks_published + " complete runs exist. Week-over-week movement is only ever as good as the number of weeks behind it, and this is a small number.",
      record_note: !tr.schedule_started
        ? "The weekly schedule has not started. The whole premise of this benchmark is elapsed public running time, and that clock has not started ticking."
        : "The weekly schedule has been running since " + tr.first_scheduled_week +
          ". The premise of this benchmark is elapsed public running time, and that is measured in weeks, not commits."
    };
  }

  var DERIVED = derived();

  function resolve(path) {
    var parts = path.split(".");
    var cur = parts[0] === "d" ? DERIVED : D;
    if (parts[0] === "d") parts = parts.slice(1);
    for (var i = 0; i < parts.length && cur != null; i++) cur = cur[parts[i]];
    return cur;
  }

  var FMT = {
    raw: function (v) { return String(v); },
    int: function (v) { return Number(v).toLocaleString(); },
    n1: function (v) { return Number(v).toFixed(1); },
    n2: function (v) { return Number(v).toFixed(2); },
    pct0: function (v) { return Number(v).toFixed(0) + "%"; },
    pct1: function (v) { return Number(v).toFixed(1) + "%"; },
    ratio: function (v) { return Number(v).toFixed(0) + "×"; },
    money: function (v) { return "$" + Number(v).toFixed(v < 0.01 ? 4 : 2); },
    ms: function (v) { return Number(v).toLocaleString() + " ms"; },
    sec: function (v) { return (Number(v) / 1000).toFixed(1) + "s"; },
    date: function (v) { return String(v).slice(0, 10); }
  };

  function fillValues(root) {
    (root || document).querySelectorAll("[data-val]").forEach(function (el) {
      var v = resolve(el.getAttribute("data-val"));
      if (v == null) {
        el.textContent = "—";
        el.setAttribute("title", "no value in the current export");
        return;
      }
      var fmt = FMT[el.getAttribute("data-fmt") || "raw"] || FMT.raw;
      el.textContent = fmt(v);
      // The finished value is in the DOM either way; data-count only says it
      // may roll up to it when it scrolls into view.
      if (el.hasAttribute("data-count") && typeof v === "number") {
        el.setAttribute("data-count-to", v);
      }
    });
  }

  /* --------------------------------------------------------------- stamp */
  function stamp() {
    var el = document.querySelector("[data-stamp]");
    if (!el || !D || !D.latest) return;
    var L = D.latest;
    var bits = [
      ["run", L.week, ""],
      ["queries", L.n_queries + " × " + L.n_vendors + " vendors × " + L.n_judges + " judges", "low"],
      ["complete ensembles", L.completeness.pct + "%", ""],
      ["query set", L.query_set_hash, "low"],
      ["published weeks", String(D.track_record.weeks_published), ""]
    ];
    el.innerHTML = bits.map(function (b) {
      return '<span data-priority="' + b[2] + '">' + b[0] + " <b>" + b[1] + "</b></span>";
    }).join("");
  }

  /* ----------------------------------------------------------------- nav */
  function nav() {
    var here = location.pathname.split("/").pop() || "index.html";
    document.querySelectorAll(".nav a").forEach(function (a) {
      if (a.getAttribute("href") === here) a.setAttribute("aria-current", "page");
    });

    /* The source link points at the repository, or says plainly that there
     * isn't a public one yet. A "Source" link that lands somewhere unhelpful
     * is worse than no link on a site whose whole claim is inspectability. */
    document.querySelectorAll("[data-repo]").forEach(function (a) {
      if (D && D.repo_url) {
        a.href = D.repo_url;
        return;
      }
      var span = document.createElement("span");
      span.textContent = a.textContent;
      span.className = (a.className ? a.className + " " : "") + "inert";
      span.title = "the repository is not public yet";
      span.style.opacity = "0.55";
      a.parentNode.replaceChild(span, a);
    });
  }

  /* -------------------------------------------------------------- reveal */
  /* One observer, applied to anything carrying a reveal role. Elements keep
   * their finished appearance by default and the observer only adds the
   * data-shown flag, so nothing here can hide content. */
  var io = null;

  function armObserver() {
    if (io || !("IntersectionObserver" in window)) return;
    io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        var el = e.target;
        var delay = Number(el.getAttribute("data-delay") || 0);
        if (delay) setTimeout(function () { show(el); }, delay);
        else show(el);
        io.unobserve(el);
      });
    }, { rootMargin: "0px 0px -10% 0px", threshold: 0.08 });
  }

  var REVEALABLE = "[data-reveal], .reveal, .section-head, .chart[data-animate], [data-count]";

  /* Marking an element shown also schedules the moment its animation stops
   * mattering. After that it is plain, finished markup again — which is what
   * makes a stalled frame loop harmless rather than destructive. */
  var SETTLE_MS = 2600;
  function show(el) {
    el.setAttribute("data-shown", "");
    if (el.hasAttribute("data-count")) countUp(el);
    setTimeout(function () { el.setAttribute("data-done", ""); }, SETTLE_MS);
  }

  function showAll(root) {
    (root || document).querySelectorAll(REVEALABLE).forEach(function (el) {
      el.setAttribute("data-shown", "");
      el.setAttribute("data-done", "");
      if (el.hasAttribute("data-count")) {
        var t = Number(el.getAttribute("data-count-to"));
        if (isFinite(t)) {
          var fmt = FMT[el.getAttribute("data-fmt") || "raw"] || FMT.raw;
          el.textContent = fmt(t);
        }
      }
    });
  }

  /* Re-runnable: charts are built after first paint and rebuilt on a theme
   * change, so newly-created figures have to be picked up rather than missed. */
  function scan(root) {
    var items = (root || document).querySelectorAll(REVEALABLE);
    if (!items.length) return;

    if (!("IntersectionObserver" in window) || media("(prefers-reduced-motion: reduce)")) {
      showAll(root);
      return;
    }

    armObserver();
    items.forEach(function (el) {
      if (el.hasAttribute("data-shown")) return;
      io.observe(el);
    });
  }

  /* Counters roll to a value the element already displays.
   *
   * The trap this avoids: the obvious implementation overwrites the finished
   * number with zero on the first frame and relies on requestAnimationFrame to
   * put it back. In a hidden tab, a throttled frame loop, or a headless
   * renderer, the frames never come and the page ships a row of zeroes — a
   * decorative effect that destroys the data it decorates. So the roll only
   * starts when the page is actually visible, and a timer restores the true
   * value regardless of whether a single frame ever ran.
   */
  function countUp(el) {
    var target = Number(el.getAttribute("data-count-to"));
    if (!isFinite(target)) return;
    if (typeof requestAnimationFrame !== "function") return;
    if (document.visibilityState && document.visibilityState !== "visible") return;

    var fmt = FMT[el.getAttribute("data-fmt") || "raw"] || FMT.raw;
    var dur = 900, t0 = null, settled = false;

    function finish() {
      if (settled) return;
      settled = true;
      el.textContent = fmt(target);
      el.classList.remove("counting");
    }
    var guard = setTimeout(finish, dur + 600);

    el.classList.add("counting");
    requestAnimationFrame(function frame(t) {
      if (settled) return;
      if (t0 === null) t0 = t;
      var p = Math.min(1, (t - t0) / dur);
      el.textContent = fmt(target * (1 - Math.pow(1 - p, 4)));
      if (p < 1) { requestAnimationFrame(frame); return; }
      clearTimeout(guard);
      finish();
    });
  }

  /* --------------------------------------------------------- scroll state */
  function scrollState() {
    var head = document.querySelector(".masthead");
    var bar = document.querySelector(".progress");
    var now = document.querySelector("[data-now]");
    if (!head) return;

    // Only needed where the browser has no scroll timeline; where it does, the
    // bar is driven by CSS and never touches the main thread.
    var needsBar = bar && !(window.CSS && CSS.supports && CSS.supports("animation-timeline: scroll()"));

    var ticking = false;
    function apply() {
      ticking = false;
      var y = window.scrollY || document.documentElement.scrollTop || 0;
      if (y > 40) head.setAttribute("data-scrolled", "");
      else head.removeAttribute("data-scrolled");

      if (needsBar) {
        var h = document.documentElement.scrollHeight - window.innerHeight;
        bar.style.setProperty("--p", h > 0 ? Math.min(1, y / h).toFixed(4) : 0);
      }
    }
    function onScroll() {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(apply);
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
    apply();

    /* Which section is in view, named in the masthead. The stamp folds away on
     * scroll and this takes its place, so the bar keeps telling you where you
     * are rather than just shrinking. */
    if (now && "IntersectionObserver" in window) {
      var sections = [].slice.call(document.querySelectorAll("main section[id]"));
      if (!sections.length) return;
      var titles = {};
      sections.forEach(function (sec) {
        var h = sec.querySelector("h2, h1");
        titles[sec.id] = (h ? h.textContent : sec.id).trim();
      });
      var visible = {};
      var sio = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) { visible[e.target.id] = e.isIntersecting; });
        for (var i = 0; i < sections.length; i++) {
          if (visible[sections[i].id]) {
            var t = titles[sections[i].id];
            if (now.textContent !== t) now.textContent = t;
            return;
          }
        }
      }, { rootMargin: "-64px 0px -55% 0px" });
      sections.forEach(function (sec) { sio.observe(sec); });
    }
  }

  function init() {
    wireTheme();
    fillValues();
    stamp();
    nav();
    scrollState();
    // Page figures are built before the scan, so charts created here are
    // observed rather than missed.
    if (window.SBPage && window.SBPage.init) window.SBPage.init();
    scan();
    window.addEventListener("load", function () {
      setTimeout(function () { showAll(); }, 3200);
    });
  }

  window.SBSite = { fillValues: fillValues, derived: DERIVED, fmt: FMT, scan: scan };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

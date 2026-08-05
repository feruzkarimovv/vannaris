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

  // Two glyphs, inlined rather than fetched, because the page's own claim is
  // that it makes no external request. A moon offers dark; a sun offers light.
  var ICON = {
    moon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" ' +
          'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
          '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>',
    sun:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" ' +
          'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
          '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4' +
          'M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>'
  };

  function wireTheme() {
    var btn = document.querySelector("[data-theme-toggle]");
    if (!btn) return;
    // Light is the unconditional default, not a response to the OS setting, so
    // the only thing that can make the page dark is an explicit stamp. Reading
    // prefers-color-scheme here would make the button offer "light" on a page
    // that is already light.
    function current() {
      return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
    }
    function paint() {
      var mode = current();
      btn.setAttribute("aria-label", "Switch to " + (mode === "dark" ? "light" : "dark") + " theme");
      btn.innerHTML = mode === "dark" ? ICON.sun : ICON.moon;
    }
    btn.addEventListener("click", function () {
      var next = current() === "light" ? "dark" : "light";
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

    /* Judge disagreement and the withheld set, both of which have to render
     * something sensible when they are empty. The withheld set in particular
     * spends its first weeks in states where the honest sentence is about what
     * has *not* been measured yet, and a page that assumed the data was there
     * would print an em dash where a caveat belongs. */
    var byCat = (D.latest.judging.disagreement_by_category || []).slice();
    var ranked = byCat.slice().sort(function (a, b) { return b.mean - a.mean; });
    var dis = { worst: ranked[0] || null, best: ranked[ranked.length - 1] || null };
    var pairs = (D.latest.judging.family_pairs || []).slice()
      .sort(function (a, b) { return b.mean_abs_diff - a.mean_abs_diff; });
    var ho = D.heldout || null;
    var hoWeek = D.latest.heldout || null;
    var weeksHeld = ho && ho.weeks_with_set ? ho.weeks_with_set.length : 0;

    function joinList(items) {
      if (items.length <= 1) return items.join("");
      if (items.length === 2) return items[0] + " and " + items[1];
      return items.slice(0, -1).join(", ") + " and " + items[items.length - 1];
    }
    var weakNames = joinList(weak.map(function (c) { return catLabel[c.category].toLowerCase(); }));
    function span(group) {
      return Math.round(group[0].pct_of_best) + "–" +
             Math.round(group[group.length - 1].pct_of_best) + "%";
    }

    /* The cost/quality spread, written as a whole sentence rather than assembled
     * from six slots in the markup. The markup version assumed a shape the data
     * does not guarantee: on a run where the cheap vendor clears 90% of the
     * leader everywhere — or nowhere — half those slots resolve to nothing and
     * the sentence on the landing page reads "reaches —–— of the best score".
     * Composing it here means every branch of the data still produces English. */
    var spreadNote;
    if (!cells.length) {
      spreadNote = "No category on this run carries a complete enough sample to compare the two.";
    } else if (!weak.length) {
      spreadNote = "It reaches " + span(strong) + " of the best available score in every one of " +
        "the " + D.categories.length + " categories.";
    } else if (!strong.length) {
      spreadNote = "It reaches " + span(weak) + " of the best available score, and gets within " +
        "10% of the category leader nowhere.";
    } else {
      spreadNote = "On " + strong.length + " of " + D.categories.length + " categories it reaches " +
        span(strong) + " of the best available score. On " + weakNames + " that falls to " +
        span(weak) + ".";
    }

    /* The vendor a per-vendor page is about, if this is one.
     *
     * Those pages are generated (scripts/make_vendor_pages.py) and carry only
     * an id — every figure on them still resolves through data-val against the
     * same export as every other page, so the smoke test catches a broken one
     * the same way it catches a broken landing page. A page that names a vendor
     * the export does not have leaves this null, and check-site.mjs reports the
     * unresolved slots rather than the page rendering blanks.
     */
    var V = null;
    var wanted = window.SB_VENDOR;
    if (wanted) {
      var self = vs.filter(function (v) { return v.vendor === wanted; })[0];
      if (self) {
        var rank = vs.indexOf(self) + 1;
        var mine = D.latest.cells
          .filter(function (c) { return c.vendor === wanted && c.pct_of_best != null; })
          .sort(function (a, b) { return b.pct_of_best - a.pct_of_best; });
        var leads = mine.filter(function (c) { return c.pct_of_best >= 99.999; });
        var modes = { ranked_results: "a ranked list of results",
                      both: "a synthesized answer and a ranked list",
                      synthesized_answer: "a synthesized answer" };
        var ord = function (n) {
          var s = ["th", "st", "nd", "rd"], m = n % 100;
          return n + (s[(m - 20) % 10] || s[m] || s[0]);
        };
        V = {
          id: self.vendor,
          label: self.label,
          score: self.score,
          cost_per_query_usd: self.cost_per_query_usd,
          cost_usd: self.cost_usd,
          p50_latency_ms: self.p50_latency_ms,
          outright_wins: self.outright_wins,
          shared_best: self.shared_best,
          n_scored: self.n_scored,
          n_queries: self.n_queries,
          coverage_pct: 100 * self.n_scored / self.n_queries,
          rank: rank,
          rank_of: vs.length,
          standing: ord(rank) + " of " + vs.length,
          returns: modes[self.response_mode] || self.response_mode,
          strength: !mine.length
            ? "No category published a comparable cell for it on this run."
            : leads.length
              ? "Leads " + joinList(leads.map(function (c) { return catLabel[c.category].toLowerCase(); })) +
                " outright."
              : "Comes closest on " + catLabel[mine[0].category].toLowerCase() + ", at " +
                Math.round(mine[0].pct_of_best) + "% of the category leader.",
          weakness: mine.length < 2
            ? "Too few comparable cells this run to say where it falls furthest behind."
            : "Furthest behind on " + catLabel[mine[mine.length - 1].category].toLowerCase() +
              ", at " + Math.round(mine[mine.length - 1].pct_of_best) + "% of the leader.",
          gap_note: rank === 1
            ? "Leads the overall table."
            : (vs[0].score - self.score).toFixed(2) + " points behind " + vs[0].label +
              ", which leads the overall table."
        };
      }
    }

    return {
      v: V,
      spread_note: spreadNote,
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
      weak_cats: weakNames,
      n_categories: D.categories.length,
      n_vendors: D.vendors.length,
      n_judges: D.judges.length,
      // Counted rather than assumed equal to the judge count: the cross-family
      // claim on the landing page is only true while it is, and the day two
      // judges share a lab the sentence should stop saying otherwise.
      n_judge_families: D.judges.reduce(function (acc, j) {
        if (acc.indexOf(j.family) === -1) acc.push(j.family);
        return acc;
      }, []).length,
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
        ? "scheduled runs not started"
        : tr.scheduled_weeks + " on schedule",
      trend_note: tr.weeks_published < 3
        ? "Too few runs to show movement."
        : "Every published week stays in the data export.",
      // The open-gaps copy. Both pages list the scheduled run as unbuilt; once
      // it has run, saying so is the same overclaim in reverse.
      unbuilt: !tr.schedule_started
        ? "Two items in this methodology are not yet running: a human-labelled calibration set scored against the judge ensemble monthly, and the scheduled weekly run."
        : "One item in this methodology is not yet running: a human-labelled calibration set scored against the judge ensemble monthly.",
      track_dt: tr.weeks_published < 2
        ? "Single run"
        : tr.weeks_published + " weeks of history",
      track_dd: tr.weeks_published < 2
        ? "One complete run. Week-over-week movement is not measurable until there are more."
        : tr.weeks_published + " complete runs. Movement is only as reliable as the number of weeks behind it.",
      record_note: !tr.schedule_started
        ? "Scheduled runs have not started. Elapsed public running time is what the schedule is for, and it is measured in weeks."
        : "Scheduled since " + tr.first_scheduled_week + ". Elapsed public running time is measured in weeks, not commits.",

      /* ------------------------------------------------- judge disagreement
       * The rates are shares in the export, and the sentence around them has
       * to change shape with the data: which category is worst is a fact about
       * the run, not something to type into the page and let rot. */
      worst_cat: dis.worst && catLabel[dis.worst.category],
      worst_cat_mean: dis.worst && dis.worst.mean,
      best_cat: dis.best && catLabel[dis.best.category],
      best_cat_mean: dis.best && dis.best.mean,
      disagreement_note: !dis.worst
        ? "This run published no judge comparison."
        : catLabel[dis.worst.category] + " splits them hardest, at " +
          dis.worst.mean.toFixed(2) + " points on average against " +
          dis.best.mean.toFixed(2) + " on " + catLabel[dis.best.category].toLowerCase() +
          " — so a rank is least stable exactly where the ensemble is least sure.",
      /* The pair that disagrees most, named. "The judges disagree" is a
       * different claim from "these two labs disagree and the third tracks
       * one of them", and only the second is actionable for a reader. */
      worst_pair: pairs.length
        ? pairs[0].pair.split("/").map(function (f) {
            return f.charAt(0).toUpperCase() + f.slice(1);
          }).join(" and ") + ", at " + pairs[0].mean_abs_diff.toFixed(2) + " points"
        : null,

      /* ------------------------------------------------------ withheld set
       * Four states, and the difference between the middle two is the whole
       * honesty of the mechanism: a set that is registered has committed to
       * nothing yet, and a set that has run once has measured nothing yet. */
      heldout_state: !ho
        ? "No withheld set is registered."
        : !ho.active
          ? "The last withheld set has retired and its questions are published. The next is not registered yet."
          : !weeksHeld
            ? "The set is registered and its hash is committed, but it has not run yet. Nothing is measured against it."
            : weeksHeld + (weeksHeld === 1 ? " week has" : " weeks have") + " run against it.",
      heldout_reading: !hoWeek
        ? "No withheld questions have run, so there is no gap to read."
        : !ho.interpretable
          ? "One run cannot separate a gap from the two sets differing in difficulty. This becomes evidence at three weeks of consistent signal, and there " +
            (weeksHeld === 1 ? "has been 1." : "have been " + weeksHeld + ".")
          : "Read as a series: a vendor scoring consistently better on the published questions across weeks is the signal this exists to catch.",
      heldout_n: ho && ho.sets.length ? ho.sets[ho.sets.length - 1].n_queries : null,
      heldout_sha: ho && ho.sets.length ? ho.sets[ho.sets.length - 1].sha256 : null,
      heldout_sha_short: ho && ho.sets.length
        ? ho.sets[ho.sets.length - 1].sha256.slice(0, 16) + "…" : null,
      heldout_committed: ho && ho.sets.length ? ho.sets[ho.sets.length - 1].committed_at : null,
      heldout_rotation: ho ? ho.rotate_after_weeks : null,
      heldout_max_gap: hoWeek ? hoWeek.max_gap : null,
      heldout_worst_vendor: hoWeek && hoWeek.vendors.length ? hoWeek.vendors[0].label : null,

      /* ------------------------------------------------- routing headroom
       * The measured answer to the question this project started from, and it
       * came back no. Composed here rather than typed into a page for the same
       * reason spread_note is: on a run where two vendors lead different
       * categories this sentence has to say something else, and a hand-written
       * one would go on saying this one. Every branch returns English. */
      routing_note: (function () {
        var R = D.latest.routing || {};
        if (!R.leaders) return "This run published no per-category comparison, so there is no routing gain to report.";
        var name = {};
        vs.forEach(function (v) { name[v.vendor] = v.label; });
        var n = R.n_categories;
        var best = name[R.best_single_vendor] || R.best_single_vendor;
        if (!R.single_leader) {
          var who = Object.keys(R.categories_led).map(function (v) { return name[v] || v; });
          return joinList(who) + " are top in different categories, and routing each category to " +
            "its best vendor scores " + R.oracle_score.toFixed(2) + " against " + best + "'s " +
            R.best_single_score.toFixed(2) + " — a gain of " + R.gain_points.toFixed(2) + " points.";
        }
        var one = name[R.single_leader] || R.single_leader;
        return one + " has the highest score in all " + n + " of " + n + " categories, so a table " +
          "that sent each category to its best vendor would pick " + one + " every time. That is " +
          "worth " + R.gain_points.toFixed(2) + " points over sending every query to " + one + ".";
      })(),

      /* The part that makes the sentence above defensible rather than a second
       * overclaim. Most of the category leads on this run sit inside their own
       * 95% interval, and that cuts towards the conclusion rather than against
       * it: two vendors a run cannot tell apart are two vendors there is
       * nothing to gain by routing between. */
      routing_caveat: (function () {
        var R = D.latest.routing || {};
        var S = (D.latest.separation && D.latest.separation.by_category) || [];
        if (!R.leaders || !S.length) return "Separation between category leaders was not published for this run.";
        var name = {};
        vs.forEach(function (v) { name[v.vendor] = v.label; });
        var n = R.n_categories, sep = R.categories_separated;
        if (sep === n) return "Every one of those leads is separated from second place by a paired 95% interval.";
        /* A rival is named only when the same vendor shares the top tier in
         * every category the run cannot resolve. Counting appearances across
         * all categories names a vendor for categories it is not in, and
         * `single_leader` is null on a split run, so excluding it alone
         * excludes nobody and a category leader ends up named as its own
         * rival. */
        var led = R.categories_led || {};
        var unresolved = S.filter(function (e) {
          return !(e.tiers && e.tiers[0]) || e.tiers[0].vendors.length > 1;
        });
        var shares = {};
        unresolved.forEach(function (e) {
          ((e.tiers && e.tiers[0]) ? e.tiers[0].vendors : []).forEach(function (v) {
            if (!led[v]) shares[v] = (shares[v] || 0) + 1;
          });
        });
        var rival = unresolved.length ? Object.keys(shares).filter(function (v) {
          return shares[v] === unresolved.length;
        }).sort()[0] : null;
        var subject = R.single_leader ? "That lead is" : "Those category leads are";
        var close = R.single_leader
          ? "That cuts towards the same conclusion rather than against it — where a run cannot " +
            "tell two vendors apart, routing between them buys nothing either."
          : "The gain above therefore rests on category leads this run cannot resolve in " +
            (n - sep) + " of " + n + " cases.";
        return subject + " only separated from second place in " + sep + " of " + n +
          " categories; in the other " + (n - sep) + " the paired 95% interval on the gap includes " +
          "zero" + (rival ? ", level with " + (name[rival] || rival) : "") + ". " + close;
      })()
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
    /* For values the export carries as a 0..1 share rather than as a number
     * already scaled to 100 — coverage floors, disagreement rates. Both live
     * in the same bundle and pct0 was being used on both, which rendered the
     * 0.60 cell-coverage floor as "1%" on two published pages: a threshold
     * stated an order of magnitude below the one the code enforces. The two
     * shapes now have two formatters, so the mistake is not available. */
    share0: function (v) { return (Number(v) * 100).toFixed(0) + "%"; },
    share1: function (v) { return (Number(v) * 100).toFixed(1) + "%"; },
    ratio: function (v) { return Number(v).toFixed(0) + "×"; },
    /* Two figures live in this formatter and they have different needs: run
     * totals in dollars, and per-query costs three or four orders of magnitude
     * smaller. A fixed 4dp printed the second badly and, under $0.0001, printed
     * it as $0.0000 — a real number rendered as free. Sub-cent values now get
     * at least the 5dp the tables use, extended for anything smaller. */
    money: function (v) {
      v = Number(v);
      if (!isFinite(v)) return "—";
      if (v >= 0.01) return "$" + v.toFixed(2);
      if (v <= 0) return "$" + v.toFixed(2);
      return "$" + v.toFixed(Math.max(5, Math.min(8, Math.ceil(-Math.log10(v)) + 1)));
    },
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
      a.parentNode.replaceChild(span, a);
    });
  }

  /* The narrow-screen menu. Everything it does is also expressed in the markup
   * (aria-expanded, data-menu) so the CSS, the screen reader and the pointer
   * are all reading the same state rather than three approximations of it. */
  function wireMenu() {
    var bar = document.querySelector(".navbar");
    var btn = bar && bar.querySelector(".nav-toggle");
    var menu = bar && bar.querySelector(".nav");
    if (!bar || !btn || !menu) return;

    function set(open) {
      if (open) bar.setAttribute("data-menu", "open");
      else bar.removeAttribute("data-menu");
      btn.setAttribute("aria-expanded", String(open));
    }
    btn.addEventListener("click", function () {
      set(bar.getAttribute("data-menu") !== "open");
    });
    menu.addEventListener("click", function (e) {
      if (e.target.closest("a")) set(false);
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") set(false);
    });
    document.addEventListener("click", function (e) {
      if (!bar.contains(e.target)) set(false);
    });
    // A resize past the breakpoint leaves the panel open behind a nav bar that
    // is no longer a panel, so the state is cleared rather than left dangling.
    window.addEventListener("resize", function () { set(false); }, { passive: true });
    set(false);
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
    wireMenu();
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

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

  /* Dark is locked. A leftover sb-theme stamp from an older build is ignored. */
  document.documentElement.setAttribute("data-theme", "dark");

  /* --------------------------------------------------------------- values */
  var D = window.SB_DATA;

  /* ISO week ids (2026-W33) name the export files. They are not how a public
   * page should date a run: W33 ran on 13 Aug, not on that week's Monday.
   * Visible copy uses ran_at. This also accepts an ISO week so cadence
   * sentences that only have first_scheduled_week still print a date. */
  var MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  function formatWhen(v) {
    if (v == null || v === "") return "n/a";
    var s = String(v);
    var iso = /^(\d{4})-W(\d{2})$/.exec(s);
    var d;
    if (iso) {
      var year = +iso[1], week = +iso[2];
      var jan4 = new Date(Date.UTC(year, 0, 4));
      var dow = jan4.getUTCDay() || 7;
      d = new Date(jan4);
      d.setUTCDate(jan4.getUTCDate() - (dow - 1) + (week - 1) * 7);
    } else {
      d = new Date(s);
    }
    if (isNaN(d.getTime())) return s;
    return d.getUTCDate() + " " + MONTHS[d.getUTCMonth()] + " " + d.getUTCFullYear();
  }

  /* ------------------------------------------------------------- standing
   * A vendor's rank is the tier this run can resolve, not its row's position.
   * Two vendors it cannot separate carry the same number and an `=`: printing
   * 03 and 04 over a gap of 0.15 points with a standard error of 0.15 asserts
   * a resolution the instrument does not have. Tiers come from paired
   * comparisons on the queries both vendors answered — `separation` in the
   * export.
   *
   * It lives here, once, because four surfaces render a rank: the landing
   * leaderboard, the results table, and the standing sentence and context
   * table on each vendor page. Three of them were still counting rows after
   * tiers arrived, so the site said Serper was 3rd and You.com 4th on one page
   * and that the run could not tell them apart on another.
   */
  function tierMap() {
    var m = {};
    if (!D || !D.latest || !D.latest.separation) return m;
    (D.latest.separation.overall_tiers || []).forEach(function (t) {
      t.vendors.forEach(function (v) { m[v] = t.tier; });
    });
    return m;
  }
  var TIERS = tierMap();

  /* `position` is the fallback, used only when a run publishes no separation
   * at all — the number then means what it meant before tiers existed, rather
   * than the badge rendering empty. */
  function rank(vendor, position) {
    var tier = TIERS[vendor] || (position + 1);
    var peers = (D && D.latest ? D.latest.vendors : []).filter(function (o) {
      return (TIERS[o.vendor] || 0) === tier;
    });
    return {
      tier: tier,
      shared: peers.length > 1,
      peers: peers.filter(function (o) { return o.vendor !== vendor; }),
      text: String(tier).padStart(2, "0") + (peers.length > 1 ? "=" : "")
    };
  }
  function rankBadge(vendor, position) {
    var r = rank(vendor, position);
    return '<span class="rank"' +
      (r.shared ? ' title="tied: not separated from the other vendors in this tier"' : "") +
      ">" + r.text + "</span>";
  }

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
    var cal = D.calibration || null;
    var calDec = cal && cal.decisive ? cal.decisive : null;

    function joinList(items) {
      if (items.length <= 1) return items.join("");
      if (items.length === 2) return items[0] + " and " + items[1];
      return items.slice(0, -1).join(", ") + " and " + items[items.length - 1];
    }
    var weakNames = joinList(weak.map(function (c) { return catLabel[c.category].toLowerCase(); }));
    function span(group) {
      return Math.round(group[0].pct_of_best) + "-" +
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
        var R = rank(wanted, vs.indexOf(self));
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
          rank: R.tier,
          rank_of: vs.length,
          // "joint 3rd", not "3rd", when the run cannot separate this vendor
          // from the one the table happens to print below it.
          standing: (R.shared ? "joint " : "") + ord(R.tier) + " of " + vs.length,
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
          /* The gap, and whether the run can resolve it. A vendor that shares
           * its tier is not "behind" the vendor printed above it in any sense
           * the interval supports, and saying only the point difference on a
           * page about that vendor is the overclaim the badge stopped making. */
          gap_note: (function () {
            var tied = R.peers.map(function (o) { return o.label; });
            if (R.tier === 1) {
              return R.shared
                ? "Shares the top tier with " + joinList(tied) + ". This run cannot separate them."
                : "Leads the overall table, separated from second place by the paired 95% interval.";
            }
            var behind = (vs[0].score - self.score).toFixed(2) + " points behind " + vs[0].label +
              ", which leads the overall table.";
            return R.shared
              ? behind + " Level with " + joinList(tied) + ". This run cannot separate them."
              : behind;
          })()
        };
      }
    }

    var likeRatio = D.latest.cost_spread && D.latest.cost_spread.like_for_like_ratio;
    var findingNote;
    if (!cells.length) {
      findingNote = "This run published no comparable category cells.";
    } else {
      var costBit = likeRatio
        ? Number(likeRatio).toFixed(0) + "× cheaper on like-for-like pay-as-you-go"
        : (top.cost_per_query_usd / cheap.cost_per_query_usd).toFixed(0) + "× cheaper";
      if (!weak.length) {
        findingNote = cheap.label + " reaches " + span(strong) + " of " + top.label +
          " in every category, " + costBit + ".";
      } else if (!strong.length) {
        findingNote = cheap.label + " is " + costBit + " than " + top.label + ".";
      } else {
        findingNote = cheap.label + " reaches " + span(strong) + " of " + top.label +
          " on " + strong.length + " of " + D.categories.length + " categories, " + costBit + ".";
      }
    }

    return {
      v: V,
      spread_note: spreadNote,
      finding_note: findingNote,
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
        : "has been running since " + formatWhen(tr.first_scheduled_week),
      schedule_note: !tr.schedule_started
        ? "scheduled runs not started"
        : tr.scheduled_weeks + " on schedule",
      trend_note: tr.weeks_published < 3
        ? "Too few runs to show movement."
        : "Every published week stays in the data export.",
      // The open-gaps copy. Both pages list the scheduled run as unbuilt; once
      // it has run, saying so is the same overclaim in reverse.
      unbuilt: (function () {
        /* Composed from both facts rather than branching on the schedule alone.
         * A calibration that has run once is not the monthly loop `docs/04`
         * asks for, and it is also no longer "not built" — the sentence has to
         * be able to say both, or it goes on calling a finished piece of work
         * missing. */
        var items = [];
        if (!tr.schedule_started) items.push("the scheduled weekly run");
        items.push(calDec
          ? "the calibration set, which has been scored against the judges once rather than monthly"
          : "a human-labelled calibration set scored against the judge ensemble monthly");
        return (items.length === 1 ? "One item in this methodology is not yet running as designed: "
                                   : "Two items in this methodology are not yet running as designed: ") +
          (items.length === 1 ? items[0] : items[0] + ", and " + items[1]) + ".";
      })(),
      track_dt: tr.weeks_published < 2
        ? "Single run"
        : tr.weeks_published + " weeks of history",
      track_dd: tr.weeks_published < 2
        ? "One complete run. Week-over-week movement is not measurable until there are more."
        : tr.weeks_published + " complete runs. Movement is only as reliable as the number of weeks behind it.",
      record_note: !tr.schedule_started
        ? "Scheduled runs have not started. Elapsed public running time is what the schedule is for, and it is measured in weeks."
        : "Scheduled since " + formatWhen(tr.first_scheduled_week) + ". Elapsed public running time is measured in weeks, not commits.",

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
          ". A rank is least stable exactly where the ensemble is least sure.",
      /* Which reading of the table the run can actually resolve. The
       * methodology page used to send readers to the category columns "rather
       * than the overall score", which was written before separation was
       * published and is backwards against it: on this run the overall lead
       * clears its paired interval and four of the six category leads do not.
       * Composed here rather than typed into the page because on a run where
       * the categories resolve and the overall does not, the advice reverses
       * with them — and a hand-written version would go on saying this one. */
      resolution_note: (function () {
        var R = D.latest.routing || {};
        var top = ((D.latest.separation || {}).overall_tiers || [])[0];
        if (!top || R.categories_separated == null) {
          return "This run published no separation intervals, so neither reading carries one.";
        }
        var n = R.n_categories, sep = R.categories_separated, firm = top.vendors.length === 1;
        var overall = firm
          ? "The overall column separates first place from second."
          : "The overall column does not separate first place from second.";
        var cats = sep === n
          ? "Every one of the " + n + " category columns does the same."
          : "The category columns manage it in " + sep + " of " + n + ".";
        var advice;
        if (firm && sep < n) {
          advice = "So a category ordering is the less resolved reading here, not the more " +
            "precise one: read the overall score first, and treat a category lead that carries " +
            "no interval as a lead this run did not measure.";
        } else if (!firm && sep > 0) {
          advice = "So read the categories that carry an interval first. The overall ordering " +
            "is the less resolved reading on this run.";
        } else if (firm) {
          advice = "Both readings carry an interval on this run.";
        } else {
          advice = "Neither ordering is firm on this run: read the intervals rather than the ranks.";
        }
        return overall + " " + cats + " " + advice;
      })(),

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

      /* --------------------------------------------- judges against humans
       * Every sentence about the calibration branches on whether one has
       * cleared, and none of them is typed into a page. For two published
       * weeks the answer was no and four places said so; on 2026-08-16 a
       * pairwise pass cleared and all four would have gone on saying it, which
       * is the same failure as a cadence claim that outlives its schedule —
       * only pointing the other way, at a project that knows more about its
       * instrument than its site admits.
       *
       * The figure is the decisive stratum only. `src/calibrate.py` prints
       * "the only stratum an agreement figure may quote" above it because the
       * near-tie pairs measure something else entirely, and a pooled number
       * answers neither question. */
      calibration_when: cal ? formatWhen(cal.week || cal.registered_at) : null,
      calibration_pct: calDec ? calDec.concordance : null,
      calibration_ci: calDec
        ? Math.round(calDec.ci95[0] * 100) + "-" + Math.round(calDec.ci95[1] * 100) + "%"
        : null,
      calibration_state: !calDec
        ? "The judges are unaudited against humans"
        : "Judges match a blinded human on " + (calDec.concordance * 100).toFixed(1) +
          "% of " + calDec.n_scored + " decisive pairs",
      calibration_note: !calDec
        ? "No human-labelled set has been scored against the ensemble, so how well these " +
          "judges track a person is unmeasured. The disagreement rates published here are " +
          "agreement between models, which is a weaker and different quantity."
        : "A blinded labeller picked the same response as the ensemble on " +
          (calDec.concordance * 100).toFixed(1) + "% of the " + calDec.n_scored +
          " pairs where both were decisive (95% interval " +
          Math.round(calDec.ci95[0] * 100) + "-" + Math.round(calDec.ci95[1] * 100) +
          "%, clear of the 50% a coin gets). Measured on the run of " +
          formatWhen(cal.week || cal.registered_at) + ".",
      /* What the figure does not establish, published beside it rather than
       * left for a reader to work out. One labeller is the binding limit: it
       * is a measurement of this ensemble against one person's judgement, and
       * `docs/04` asks for the loop to run monthly, which it has not. */
      calibration_labellers: !cal ? null
        : cal.n_labellers + (cal.n_labellers === 1 ? " labeller" : " labellers"),
      calibration_dt: !calDec
        ? "No human calibration"
        : (cal.n_cleared_sets === 1 ? "Calibration has run once, not monthly"
                                    : "Calibration is not yet on a monthly cadence"),
      calibration_limits: !calDec
        ? "Nothing is measured yet."
        : (cal.n_labellers === 1
            ? "One labeller, one run, and no repeat since. "
            : cal.n_labellers + " labellers, one run, and no repeat since. ") +
          "The design calls for this monthly; it has run " +
          (cal.n_cleared_sets === 1 ? "once" : cal.n_cleared_sets + " times") +
          ". It says the ensemble tracks a person on pairs a person can separate — not " +
          "that its 0-10 scores are calibrated, which the earlier absolute pass failed to show.",
      /* The ceiling the headline should be read against, and the failure that
       * would have voided the exercise. A labeller who disagrees with
       * themselves cannot agree with the judges by more, and a labeller who
       * just picks the left-hand side agrees with nothing at all. */
      calibration_check: !cal || !cal.self_agreement || !cal.position_bias
        ? null
        : "Shown the same pair twice, the labeller repeated themselves " +
          (cal.self_agreement.rate * 100).toFixed(0) + "% of the time (" +
          cal.self_agreement.n + " repeats). Shown it with the sides swapped, they followed the " +
          "response rather than the position in " + cal.position_bias.picked_same_response +
          " of " + cal.position_bias.n + ".",
      calibration_near_tie: !cal || !cal.near_tie
        ? null
        : "On the " + cal.near_tie.n + " pairs the judges scored level, the labeller still " +
          "picked a side " + Math.round(cal.near_tie.human_separates_pct * 100) +
          "% of the time — a diagnostic, never an agreement figure: where the ensemble sees " +
          "no difference, a person usually does.",

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
            R.best_single_score.toFixed(2) + ", a gain of " + R.gain_points.toFixed(2) + " points.";
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
          ? "That cuts towards the same conclusion rather than against it. Where a run cannot " +
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
      if (!isFinite(v)) return "n/a";
      if (v >= 0.01) return "$" + v.toFixed(2);
      if (v <= 0) return "$" + v.toFixed(2);
      return "$" + v.toFixed(Math.max(5, Math.min(8, Math.ceil(-Math.log10(v)) + 1)));
    },
    ms: function (v) { return Number(v).toLocaleString() + " ms"; },
    sec: function (v) { return (Number(v) / 1000).toFixed(1) + "s"; },
    date: function (v) { return String(v).slice(0, 10); },
    when: formatWhen
  };

  function fillValues(root) {
    (root || document).querySelectorAll("[data-val]").forEach(function (el) {
      var v = resolve(el.getAttribute("data-val"));
      if (v == null) {
        el.textContent = "n/a";
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
      ["run", formatWhen(L.ran_at), ""],
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

  /* Progress is CSS scroll-timeline. Section title in the masthead, if present,
   * is IntersectionObserver rather than a scroll listener. */
  function scrollState() {
    var now = document.querySelector("[data-now]");
    if (!now || !("IntersectionObserver" in window)) return;
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

  /* ----------------------------------------------------------- instrument
   * The homepage objects. Built from the same export as every data-val, so a
   * plate and a table cell cannot disagree. Empty mounts are a no-op, which is
   * why results/methodology can load this file without growing a plate. */
  function cssVar(name) {
    var v = "";
    try { v = getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
    catch (e) { /* jsdom */ }
    return v;
  }
  /* One hue, lightness rising the whole way. The ramp used to run dark blue
   * through light blue to pink and end on the accent red, which reads as a
   * diverging scale — blue one side, red the other, a neutral middle — over a
   * quantity that has no middle. On a run where every cell lands between 7.2
   * and 9.9 that is the more flattering reading twice over: it invents a
   * midpoint and then paints the two sides of it as opposites. */
  function rampFill(t) {
    var steps = ["--d100", "--d200", "--d300", "--d400", "--d500", "--d600", "--d700"];
    var hex = ["#1a1420", "#3a1526", "#5c1a2e", "#851f37", "#b32540", "#e02f4c", "#ff6b7e"];
    var i = Math.max(0, Math.min(steps.length - 1, Math.round(t * (steps.length - 1))));
    return cssVar(steps[i]) || hex[i];
  }
  function cellMap() {
    var m = {};
    if (!D || !D.latest) return m;
    D.latest.cells.forEach(function (c) {
      m[c.vendor + ":" + c.category] = c;
    });
    return m;
  }
  function plate() {
    var board = document.getElementById("score-board");
    var read = document.getElementById("score-read");
    if (!board || !D || !D.latest) return;
    board.textContent = "";
    var cats = D.categories;
    var vendors = D.latest.vendors;
    var cells = cellMap();
    var scores = [];
    vendors.forEach(function (v) {
      cats.forEach(function (c) {
        var cell = cells[v.vendor + ":" + c.id];
        if (cell && cell.score != null) scores.push(Number(cell.score));
      });
    });
    var lo = scores.length ? Math.floor(Math.min.apply(null, scores) * 2) / 2 : 0;
    var hi = scores.length ? Math.ceil(Math.max.apply(null, scores) * 2) / 2 : 10;
    var short = {
      general_facts: "Facts", breaking_news: "News", local_shopping: "Local",
      code_technical: "Code", multi_hop: "Multi-hop", long_tail: "Long-tail"
    };
    var h = window.SBCharts && window.SBCharts.helpers;
    function fmtScore(v) {
      if (v == null) return "n/a";
      return h ? h.fmt(v) : Number(v).toFixed(2);
    }
    /* Where the ramp crosses over. The two top steps are light enough that
     * light ink drops under 4.5:1 on them; every step below carries light ink
     * at 5.7:1 or better. Moved up one step with the ramp above — left at 4 it
     * put dark ink on #b32540, at 3.1:1. */
    function inkFor(t) {
      var step = Math.round(Math.max(0, Math.min(1, t)) * 6);
      return step >= 5 ? "#07080c" : "#eef2f7";
    }

    var table = document.createElement("table");
    table.className = "plate__table";
    table.style.setProperty("--rows", String(vendors.length));
    table.style.setProperty("--cols", String(cats.length));
    table.setAttribute("aria-label", "Quality by vendor and category, this run, ensemble median 0 to 10");

    var thead = document.createElement("thead");
    var hr = document.createElement("tr");
    var corner = document.createElement("th");
    corner.scope = "col";
    var cornerTxt = document.createElement("span");
    cornerTxt.className = "sr";
    cornerTxt.textContent = "Vendor";
    corner.appendChild(cornerTxt);
    hr.appendChild(corner);
    cats.forEach(function (c) {
      var th = document.createElement("th");
      th.scope = "col";
      th.textContent = short[c.id] || c.label;
      th.title = c.label;
      hr.appendChild(th);
    });
    thead.appendChild(hr);
    table.appendChild(thead);

    var tbody = document.createElement("tbody");
    vendors.forEach(function (v, vi) {
      var tr = document.createElement("tr");
      var th = document.createElement("th");
      th.scope = "row";
      var name = document.createElement("a");
      name.className = "plate__vendor";
      name.href = "vendors/" + v.vendor + ".html";
      name.textContent = v.label;
      th.appendChild(name);
      tr.appendChild(th);
      cats.forEach(function (c, ci) {
        var td = document.createElement("td");
        var cell = cells[v.vendor + ":" + c.id];
        var score = cell && cell.score != null ? Number(cell.score) : null;
        var catName = short[c.id] || c.label;
        var lead = cell && cell.pct_of_best != null && cell.pct_of_best >= 99.999;
        td.className = "plate__cell";
        td.style.setProperty("--i", String(vi * cats.length + ci));
        if (score == null) {
          td.textContent = "n/a";
          td.classList.add("is-empty");
        } else {
          var t = hi === lo ? 0.5 : (score - lo) / (hi - lo);
          var a = document.createElement("a");
          a.href = "vendors/" + v.vendor + ".html";
          a.textContent = fmtScore(score);
          a.setAttribute("aria-label",
            v.label + ", " + c.label + ": " + fmtScore(score) + " out of 10" +
            (lead ? ", category leader" : ""));
          td.appendChild(a);
          td.style.background = rampFill(t);
          td.style.color = inkFor(t);
          if (lead) td.classList.add("is-lead");
        }
        td.addEventListener("mouseenter", function () {
          if (read) read.textContent = v.label + "  " + catName + "  " + fmtScore(score);
        });
        td.addEventListener("focusin", function () {
          if (read) read.textContent = v.label + "  " + catName + "  " + fmtScore(score);
        });
        td.addEventListener("mouseleave", function () {
          if (read) read.textContent = "";
        });
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    board.appendChild(table);

    /* What the colour means, in the two numbers a reader needs to not
     * over-read it. The ramp is stretched across this run's own spread, so the
     * distance between the darkest and the hottest cell is 2.7 points here and
     * would be 0.4 on a tighter run, with the picture looking identical. The
     * judges' own mean spread on a single answer sits next to it because it is
     * the scale the colour differences should be read against: on this run it
     * is about half the entire ramp. */
    var domain = document.getElementById("score-domain");
    if (domain) {
      var md = D.latest.judging && D.latest.judging.mean_disagreement;
      domain.textContent = lo.toFixed(1) + " dark → " + hi.toFixed(1) + " hot" +
        (md ? " · one answer splits the judges by " + Number(md).toFixed(2) + " on average" : "");
    }

    /* Below about 700px the board scrolls inside itself and the last categories
     * sit off the edge with nothing to say so — the columns simply stop. The
     * flag drives a fade on the scrolling edge in CSS; it is set from the
     * measured overflow rather than a width breakpoint, because the number of
     * categories is a property of the export, not of the viewport. */
    function markScroll() {
      var over = board.scrollWidth - board.clientWidth;
      board.classList.toggle("is-scrollable", over > 4);
      board.classList.toggle("is-scrolled-end", over > 4 && board.scrollLeft >= over - 4);
    }
    markScroll();
    board.addEventListener("scroll", markScroll, { passive: true });
    window.addEventListener("resize", markScroll);

    var plateEl = document.getElementById("score-plate");
    if (plateEl) {
      setTimeout(function () { plateEl.setAttribute("data-done", ""); }, 2200);
    }
  }

  /* The one standings list on the landing page.
   *
   * There were two, stacked: this one and a "channels" list under a second
   * heading, printing the same five vendors with the same scores and the same
   * per-query costs, differing only by a sparkline of the six category scores
   * already shown in the heatmap above it. Nothing was measured twice, so
   * nothing was learned twice — and a page that renders one table three times
   * looks like more evidence than the run contains. */
  function roster() {
    var host = document.getElementById("standings-roster");
    if (!host || !D || !D.latest) return;
    host.textContent = "";
    var h = window.SBCharts && window.SBCharts.helpers;
    D.latest.vendors.forEach(function (v, i) {
      var r = rank(v.vendor, i);
      var a = document.createElement("a");
      a.className = "roster__row";
      a.href = "vendors/" + v.vendor + ".html";
      a.style.setProperty("--i", String(i));
      // The tie marker is the one thing on this row a reader cannot guess, so
      // it carries the same explanation the results table's badge does rather
      // than leaving "01=" to be worked out.
      if (r.shared) a.title = "tied: this run cannot separate them";
      a.innerHTML =
        '<span class="roster__n">' + r.text + "</span>" +
        '<span class="roster__name">' + v.label + "</span>" +
        '<span class="roster__score">' + (h ? h.fmt(v.score) : Number(v.score).toFixed(2)) + "</span>" +
        '<span class="roster__meta">$' + Number(v.cost_per_query_usd).toFixed(4) + " / query</span>" +
        '<span class="roster__go" aria-hidden="true">→</span>';
      host.appendChild(a);
    });
  }

  function instrument() {
    plate();
    roster();
  }
  function init() {
    fillValues();
    stamp();
    nav();
    wireMenu();
    scrollState();
    instrument();
    // Page figures are built before the scan, so charts created here are
    // observed rather than missed.
    if (window.SBPage && window.SBPage.init) window.SBPage.init();
    scan();
    window.addEventListener("load", function () {
      setTimeout(function () { showAll(); }, 3200);
    });
  }

  // rank/rankBadge are exported because the tables that render a badge live in
  // each page's own SBPage block, which runs from init() below.
  window.SBSite = { fillValues: fillValues, derived: DERIVED, fmt: FMT, scan: scan,
                    rank: rank, rankBadge: rankBadge, instrument: instrument };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

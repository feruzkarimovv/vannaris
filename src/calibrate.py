"""Judge calibration against a human-labelled gold set.

`docs/04` treats this as a requirement, not a nicety: every LLM-judge framework
surveyed converges on the same loop — baseline the judge, measure it against
human labels, diagnose the specific failure, refine, re-measure — and none of
them treat "write a judge prompt and ship it" as sufficient. This module is that
loop's tooling. It does not produce labels. It draws a defensible sample, hands
the labeller a task that cannot anchor them, and then does the arithmetic that
turns their answers into a statement about the judge.

    python -m src.calibrate sample --n 150          # draw a set, write the task
    python -m src.calibrate import labels.json --labeller feruz
    python -m src.calibrate report

Three design decisions carry most of the weight, and all three are about not
fooling ourselves:

1. **Two strata, never pooled.** A uniformly random sample tells you how well
   the judge tracks a human in general. A sample of the judge's worst moments
   tells you what to fix. Averaging them together produces a number that answers
   neither question and always looks worse than the truth. `report` keeps them
   apart and labels which is the headline.

2. **The labeller is blind.** They see the query and the results; they do not
   see the judge's scores, and they do not see which vendor produced what.
   Showing either turns the exercise into agreement-with-an-anchor, which is
   exactly the bias this whole ensemble exists to avoid — and vendor identity
   in particular invites a brand halo that would then be baked into the "gold"
   standard the judge is corrected against.

3. **The task never enters the repository.** It contains the vendors' actual
   titles, URLs and snippets, and `docs/03` is clear that retrieved content is
   stored for reproducibility and not republished. The labels that come back
   are numbers, and those are as publishable as any judge score.
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import statistics
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import storage
from .judge.ensemble import JUDGES

ROOT = Path(__file__).resolve().parent.parent
UI_TEMPLATE = ROOT / "src" / "calibrate_ui.html"

# Written outside site/ deliberately — see the module docstring. Gitignored.
DEFAULT_OUT = ROOT / "calibration"

# docs/04 cites RAGAS's guidance of 100-200 expert-labelled examples. 150 is the
# middle of that band and, at the observed ~40 seconds an item, about 100
# minutes of work — a number a founder will actually finish in one sitting,
# which matters more than a larger set that never gets labelled.
DEFAULT_N = 150

# What share of the set is drawn from the judge's highest-disagreement
# responses. The rest is uniformly random. Two thirds random keeps the headline
# estimate reasonably precise while still spending real labelling time where the
# judge is least trustworthy.
DEFAULT_DISAGREEMENT_SHARE = 0.34

BLINDING = "vendor identity hidden; judge scores hidden; presentation order shuffled per labeller"

DIMENSIONS = ("relevance", "freshness", "citation_quality", "overall")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------ sampling

def latest_run(conn: sqlite3.Connection) -> str:
    """The most complete run, not the most recent.

    Calibrating against a smoke test would produce a gold set of twenty items
    and a confident-looking agreement number computed from nothing.
    """
    rows = conn.execute(
        """
        SELECT rr.run_id, COUNT(*) AS n
        FROM raw_responses rr
        JOIN judge_scores js ON js.response_id = rr.id
        GROUP BY rr.run_id
        ORDER BY n DESC
        """
    ).fetchall()
    if not rows:
        raise SystemExit("no judged responses in the database — run the benchmark first")
    return rows[0][0]


def candidates(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    """Every response in the run that carries a complete judge ensemble.

    Incomplete ensembles are excluded rather than labelled: the point of the
    exercise is to compare a human against the score the site actually
    publishes, and a partial ensemble never becomes one (`require_full=True` in
    the aggregator).
    """
    rows = []
    for r in conn.execute(
        """
        SELECT rr.id, rr.query_id, rr.vendor, rr.response_mode, rr.answer,
               rr.results, rr.error, q.category, q.text AS query_text,
               q.gold_answer
        FROM raw_responses rr
        JOIN queries q ON q.id = rr.query_id
        WHERE rr.run_id = ? AND rr.error IS NULL
        """,
        (run_id,),
    ):
        d = dict(r)
        scores = {
            js["judge_family"]: js["overall"]
            for js in conn.execute(
                "SELECT judge_family, overall FROM judge_scores WHERE response_id = ?",
                (d["id"],),
            )
            if js["overall"] is not None
        }
        if len(scores) < len(JUDGES):
            continue
        d["judge_scores"] = scores
        vals = list(scores.values())
        d["spread"] = max(vals) - min(vals)
        d["median"] = statistics.median(vals)
        rows.append(d)
    return rows


def draw(rows: list[dict], n: int, seed: int, disagreement_share: float) -> list[dict]:
    """Stratified, seeded, reproducible.

    The random stratum is drawn first and the disagreement stratum is drawn from
    what is left, so no response can appear in both — a duplicate would be
    labelled once and counted twice, in two strata with opposite meanings.
    """
    rng = random.Random(seed)
    n_dis = min(int(round(n * disagreement_share)), len(rows))
    n_rand = min(n - n_dis, len(rows) - n_dis)

    pool = sorted(rows, key=lambda r: r["id"])  # stable order before any shuffle

    # The random stratum is allocated evenly across categories rather than drawn
    # uniformly over responses. The population is already balanced — 25 queries
    # in each of six categories, times the same vendors — so even allocation is
    # proportional and introduces no bias; it only removes variance. That matters
    # at small n and not at large: a 150-item uniform draw lands within a few of
    # even, while a 40-item one produced 13 multi-hop against 1 general-facts,
    # and an agreement figure whose category mix is an accident is a figure that
    # moves when you redraw it.
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in pool:
        by_cat[r["category"]].append(r)
    cats = sorted(by_cat)
    random_pick: list[dict] = []
    # Deterministic remainder: categories take the extra item in a fixed order,
    # so the draw stays a pure function of (rows, seed).
    for i, cat in enumerate(cats):
        want = n_rand // len(cats) + (1 if i < n_rand % len(cats) else 0)
        available = by_cat[cat]
        random_pick.extend(rng.sample(available, min(want, len(available))))
    # A category with too few responses leaves the quota short; top up from
    # whatever is left rather than silently returning a smaller set.
    if len(random_pick) < n_rand:
        chosen = {r["id"] for r in random_pick}
        rest = [r for r in pool if r["id"] not in chosen]
        random_pick.extend(rng.sample(rest, min(n_rand - len(random_pick), len(rest))))
    picked = {r["id"] for r in random_pick}

    # Highest inter-judge spread first; ties broken by id so the draw is a pure
    # function of (rows, seed).
    remaining = sorted(
        (r for r in pool if r["id"] not in picked),
        key=lambda r: (-r["spread"], r["id"]),
    )
    dis_pick = remaining[:n_dis]

    out = []
    for r in random_pick:
        out.append({**r, "stratum": "random"})
    for r in dis_pick:
        out.append({**r, "stratum": "disagreement"})
    rng.shuffle(out)  # presentation order carries no signal about stratum
    for i, r in enumerate(out):
        r["position"] = i
    return out


# -------------------------------------------------------------- task writing

def write_task(set_id: str, picked: list[dict], out_dir: Path) -> Path:
    """The labelling task: one self-contained directory, outside the repository.

    A script assignment rather than fetch(), for the same reason the site uses
    one — it has to work opened from disk, with no server and no build step.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    items = []
    for r in picked:
        results = json.loads(r["results"]) if r["results"] else []
        items.append({
            "response_id": r["id"],
            "position": r["position"],
            "query": r["query_text"],
            "category": r["category"],
            "gold_answer": r["gold_answer"],
            "response_mode": r["response_mode"],
            "answer": r["answer"],
            "results": [
                {"rank": x.get("rank"), "title": x.get("title"),
                 "url": x.get("url"), "snippet": x.get("snippet")}
                for x in results
            ],
        })
    payload = {
        "set_id": set_id,
        "created_at": _now(),
        "blinding": BLINDING,
        "dimensions": list(DIMENSIONS),
        "items": items,
    }
    (out_dir / "task.js").write_text(
        "// Generated by src/calibrate.py — do not edit.\n"
        "// Contains vendor-retrieved content: never commit, never publish.\n"
        "window.VN_TASK = " + json.dumps(payload, indent=1) + ";\n"
    )
    (out_dir / "label.html").write_text(UI_TEMPLATE.read_text())
    return out_dir


def cmd_sample(args: argparse.Namespace) -> int:
    conn = storage.connect(Path(args.db))
    conn.row_factory = sqlite3.Row
    run_id = args.run or latest_run(conn)

    rows = candidates(conn, run_id)
    if len(rows) < args.n:
        print(f"note: run holds {len(rows)} fully-judged responses; sampling all of them")
    picked = draw(rows, min(args.n, len(rows)), args.seed, args.disagreement_share)

    set_id = uuid.uuid4().hex[:12]
    conn.execute(
        "INSERT INTO calibration_sets (id, run_id, created_at, seed, n_target, "
        "disagreement_share, blinding, notes) VALUES (?,?,?,?,?,?,?,?)",
        (set_id, run_id, _now(), args.seed, args.n, args.disagreement_share,
         BLINDING, args.notes),
    )
    conn.executemany(
        "INSERT INTO calibration_items (set_id, response_id, stratum, position) VALUES (?,?,?,?)",
        [(set_id, r["id"], r["stratum"], r["position"]) for r in picked],
    )
    conn.commit()

    out_dir = Path(args.out) / set_id
    write_task(set_id, picked, out_dir)

    # Broken out per stratum, never combined. The disagreement stratum is
    # selected for difficulty and clusters hard in whichever categories the
    # judges find hardest — so a combined category table looks like a badly
    # stratified sample when it is actually two samples with different jobs.
    # Where it clusters is itself a finding, and it is printed as one.
    print(f"calibration set {set_id}  from run {run_id[:8]}  seed {args.seed}")
    for stratum in ("random", "disagreement"):
        rows_s = [r for r in picked if r["stratum"] == stratum]
        if not rows_s:
            continue
        cats = defaultdict(int)
        for r in rows_s:
            cats[r["category"]] += 1
        spread = statistics.fmean(r["spread"] for r in rows_s)
        print(f"  {stratum:<13} {len(rows_s):>3} items, mean inter-judge spread {spread:.2f}")
        print("                " + ", ".join(f"{k} {v}" for k, v in sorted(cats.items())))
    print(f"\n  open  {out_dir / 'label.html'}")
    print(f"  then  python -m src.calibrate import {out_dir / 'labels.json'} --labeller YOURNAME")
    conn.close()
    return 0


# ----------------------------------------------------------------- importing

def cmd_import(args: argparse.Namespace) -> int:
    conn = storage.connect(Path(args.db))
    conn.row_factory = sqlite3.Row
    payload = json.loads(Path(args.labels).read_text())
    set_id = payload["set_id"]

    known = {r["response_id"] for r in conn.execute(
        "SELECT response_id FROM calibration_items WHERE set_id = ?", (set_id,))}
    if not known:
        raise SystemExit(f"no calibration set {set_id} in this database")

    rows, skipped, seconds = [], 0, []
    for lab in payload["labels"]:
        rid = lab["response_id"]
        if rid not in known:
            skipped += 1
            continue
        if lab.get("overall") is None:
            skipped += 1  # an unfinished item is absent data, not a zero
            continue
        rows.append((
            uuid.uuid4().hex, set_id, rid, args.labeller, args.labeller_kind,
            lab.get("relevance"), lab.get("freshness"), lab.get("citation_quality"),
            lab["overall"], lab.get("note"), lab.get("seconds"), _now(),
        ))
        # Collected here rather than read back out of the tuple by index. It was
        # read as rows[i][9], which silently became `note` the moment a column
        # was inserted ahead of it — a positional index into a row built three
        # lines earlier is a bug with a delay fuse.
        if lab.get("seconds"):
            seconds.append(lab["seconds"])
    conn.executemany(
        "INSERT OR REPLACE INTO human_labels (id, set_id, response_id, labeller, "
        "labeller_kind, relevance, freshness, citation_quality, overall, note, "
        "seconds, labelled_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    print(f"imported {len(rows)} label(s) for set {set_id} by {args.labeller} "
          f"[{args.labeller_kind}]"
          + (f"; skipped {skipped} unlabelled/unknown" if skipped else ""))
    if seconds:
        print(f"  median {statistics.median(seconds):.0f}s per item; "
              f"{sum(1 for s in seconds if s < 10)} labelled in under 10s")
    elif args.labeller_kind == "human":
        print("  no time-on-task recorded — a gold set with no timings cannot be "
              "audited for rushing")
    conn.close()
    return 0


# ----------------------------------------------------------------- reporting

def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    return None if dx == 0 or dy == 0 else num / (dx * dy)


def _rank(vals: list[float]) -> list[float]:
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    ranks = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        shared = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = shared
        i = j + 1
    return ranks


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    """Rank correlation, computed on ranks with ties averaged.

    Reported next to Pearson because the two disagree in a way that matters
    here: a judge can be systematically two points high (destroying Pearson's
    usefulness as a "is it right" measure while leaving the ordering perfect),
    and vendor ranking is what the site publishes.
    """
    return _pearson(_rank(xs), _rank(ys)) if len(xs) >= 3 else None


def agreement(pairs: list[tuple[float, float]]) -> dict:
    """One judge's scores against the human's, on the same responses."""
    if not pairs:
        return {"n": 0}
    js = [p[0] for p in pairs]
    hs = [p[1] for p in pairs]
    diffs = [j - h for j, h in pairs]
    return {
        "n": len(pairs),
        "mae": statistics.fmean(abs(d) for d in diffs),
        "bias": statistics.fmean(diffs),          # signed: + means judge is generous
        "pearson": _pearson(js, hs),
        "spearman": _spearman(js, hs),
        "within_1": sum(1 for d in diffs if abs(d) <= 1) / len(diffs),
        "off_by_3": sum(1 for d in diffs if abs(d) > 3),
    }


def collect(conn: sqlite3.Connection, set_id: str) -> dict[str, list[dict]]:
    """Human label joined to every judge score, split by stratum."""
    out: dict[str, list[dict]] = defaultdict(list)
    for r in conn.execute(
        """
        SELECT hl.response_id, hl.overall AS human, hl.labeller, hl.labeller_kind, hl.note,
               ci.stratum, rr.vendor, q.category, q.text AS query_text
        FROM human_labels hl
        JOIN calibration_items ci
          ON ci.set_id = hl.set_id AND ci.response_id = hl.response_id
        JOIN raw_responses rr ON rr.id = hl.response_id
        JOIN queries q ON q.id = rr.query_id
        WHERE hl.set_id = ?
        """,
        (set_id,),
    ):
        d = dict(r)
        d["judges"] = {
            js["judge_family"]: js["overall"]
            for js in conn.execute(
                "SELECT judge_family, overall FROM judge_scores WHERE response_id = ?",
                (d["response_id"],),
            )
            if js["overall"] is not None
        }
        if len(d["judges"]) < len(JUDGES):
            continue
        d["ensemble"] = statistics.median(d["judges"].values())
        out[d["stratum"]].append(d)
    return out


def _fmt(a: dict) -> str:
    if not a.get("n"):
        return "no data"
    def num(x, spec=".2f"):
        return "  n/a" if x is None else format(x, spec)
    return (f"n={a['n']:<4} MAE {a['mae']:.2f}  bias {a['bias']:+.2f}  "
            f"r {num(a['pearson'])}  rho {num(a['spearman'])}  "
            f"within 1pt {a['within_1']:.0%}  off by >3: {a['off_by_3']}")


def cmd_report(args: argparse.Namespace) -> int:
    conn = storage.connect(Path(args.db))
    conn.row_factory = sqlite3.Row
    set_id = args.set or (conn.execute(
        "SELECT id FROM calibration_sets ORDER BY created_at DESC LIMIT 1").fetchone() or [None])[0]
    if not set_id:
        raise SystemExit("no calibration set in this database — run `sample` first")

    meta = conn.execute("SELECT * FROM calibration_sets WHERE id = ?", (set_id,)).fetchone()
    strata = collect(conn, set_id)
    total = sum(len(v) for v in strata.values())
    n_items = conn.execute(
        "SELECT COUNT(*) FROM calibration_items WHERE set_id = ?", (set_id,)).fetchone()[0]

    print(f"calibration set {set_id}  run {meta['run_id'][:8]}  seed {meta['seed']}")
    print(f"blinding: {meta['blinding']}")
    print(f"labelled {total}/{n_items} items\n")
    if not total:
        print("nothing labelled yet — open the task and import the result.")
        return 0

    # A model's labels are not calibration and the report must not let them read
    # as such. Kinds are reported separately and the headline framing is withheld
    # unless a human produced the labels — an LLM grading LLMs measures agreement
    # between models, which is a different question and a much less interesting one.
    kinds = {r.get("labeller_kind") or "unknown"
             for rs in strata.values() for r in rs}
    is_human = kinds == {"human"}
    if not is_human:
        print("!" * 78)
        print(f"LABELLER KIND: {', '.join(sorted(kinds))} — NOT A HUMAN CALIBRATION")
        print("These numbers describe agreement between models. They do not measure")
        print("whether the judges track human judgement, which is what docs/04 requires")
        print("and what the site's caveat is about. Do not publish them as calibration.")
        print("!" * 78)
        print()

    for stratum, headline in (("random", True), ("disagreement", False)):
        rows = strata.get(stratum) or []
        if not rows:
            continue
        if headline:
            title = ("RANDOM STRATUM — this is the headline agreement figure"
                     if is_human else
                     "RANDOM STRATUM — model-vs-model agreement, NOT a calibration figure")
        else:
            title = "DISAGREEMENT STRATUM — the judge's worst moments, diagnostic only"
        print("=" * 78)
        print(title)
        print("=" * 78)
        if not headline:
            print("  Drawn from the highest inter-judge spread. Never quote these numbers as")
            print("  the benchmark's agreement: the sample is selected for difficulty.\n")
        for fam, _model in JUDGES:
            pairs = [(r["judges"][fam], r["human"]) for r in rows if fam in r["judges"]]
            print(f"  {fam:<10} {_fmt(agreement(pairs))}")
        ens = [(r["ensemble"], r["human"]) for r in rows]
        print(f"  {'ENSEMBLE':<10} {_fmt(agreement(ens))}")

        # docs/04 phase 2: split the errors by direction. A judge that is
        # uniformly generous needs a rubric change; one that is generous only on
        # long-tail queries needs a different one.
        gen = [r for r in rows if r["ensemble"] - r["human"] > 2]
        harsh = [r for r in rows if r["human"] - r["ensemble"] > 2]
        print(f"\n  judge >2pts generous: {len(gen)}   judge >2pts harsh: {len(harsh)}")
        by_cat: dict[str, list[float]] = defaultdict(list)
        for r in rows:
            by_cat[r["category"]].append(r["ensemble"] - r["human"])
        print("  bias by category:")
        for cat, ds in sorted(by_cat.items(), key=lambda kv: -abs(statistics.fmean(kv[1]))):
            print(f"    {cat:<16} {statistics.fmean(ds):+.2f}  (n={len(ds)})")
        print()

    worst = sorted(
        [r for rs in strata.values() for r in rs],
        key=lambda r: -abs(r["ensemble"] - r["human"]),
    )[:args.show]
    if worst:
        print("=" * 78)
        print(f"LARGEST DISAGREEMENTS (top {len(worst)}) — read these before changing the rubric")
        print("=" * 78)
        for r in worst:
            print(f"  human {r['human']:>4.1f}  ensemble {r['ensemble']:>4.1f}  "
                  f"[{r['stratum'][:4]}] {r['category']:<15} {r['query_text'][:52]}")
            if r["note"]:
                print(f"      note: {r['note'][:70]}")
    conn.close()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(storage.DB_PATH))
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sample", help="draw a gold set and write the labelling task")
    s.add_argument("--run", help="run id (default: the most complete run)")
    s.add_argument("--n", type=int, default=DEFAULT_N)
    s.add_argument("--seed", type=int, default=1)
    s.add_argument("--disagreement-share", type=float, default=DEFAULT_DISAGREEMENT_SHARE)
    s.add_argument("--out", default=str(DEFAULT_OUT))
    s.add_argument("--notes")
    s.set_defaults(func=cmd_sample)

    i = sub.add_parser("import", help="load a completed labels.json")
    i.add_argument("labels")
    i.add_argument("--labeller", required=True)
    # Required, with no default. A default of "human" would mean the one field
    # that decides whether this is calibration or a curiosity gets set by
    # whoever forgot to pass a flag.
    i.add_argument("--labeller-kind", required=True, choices=["human", "model"],
                   help="'model' labels are never calibration — they measure "
                        "agreement between models, not against human judgement")
    i.set_defaults(func=cmd_import)

    r = sub.add_parser("report", help="judge-vs-human agreement")
    r.add_argument("--set", help="calibration set id (default: most recent)")
    r.add_argument("--show", type=int, default=12)
    r.set_defaults(func=cmd_report)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

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
import math
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
PAIR_UI_TEMPLATE = ROOT / "src" / "calibrate_pair_ui.html"

# Worked examples, shown to the labeller before the first real item and
# reachable from every screen afterwards. `docs/12` names their absence as the
# defect that produced the first pass's ceiling: with nothing showing what a 5
# or a 7 looks like, "it answered my question" became 10 on twelve of fifteen
# items, and a correlation over a variable that barely varies is noise.
#
# Written as descriptions of result sets rather than as scores of any real
# response, so that nothing here can be read back as a label for a vendor.
ANCHORS = [
    {"score": 9, "label": "Excellent",
     "body": "The answer is present, current and easy to find — top two or three "
             "results state it outright, from sources that would actually know. "
             "Nothing stale, nothing that has to be pieced together."},
    {"score": 6, "label": "Usable but flawed",
     "body": "The answer is reachable but you have to work: it sits below the "
             "fold, or one authoritative result is mixed with two that are out "
             "of date, or the topic is right and the specific question asked is "
             "only half addressed."},
    {"score": 3, "label": "Mostly failed",
     "body": "On topic but does not answer the question. Results are stale, "
             "tangential, or the one that would answer it is an aggregator "
             "quoting something you cannot check. A reader would leave and "
             "search again."},
]

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
# Pairwise adds one thing absolute scoring had no need of: which side a
# response is shown on is decided by coin flip rather than by score. Without
# that a labeller who always clicks left scores 100% agreement having read
# nothing, and the swapped stratum exists to check that they did not.
BLINDING_PAIRWISE = (
    "vendor identity hidden; judge scores hidden; ensemble margin hidden; "
    "left/right assignment randomised per pair; presentation order interleaved "
    "by category; repeats and side-swaps held back from the first third"
)

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

    # Then interleave by category, so that stopping early costs balance rather
    # than destroying it. A labeller does not finish: the first pass drew a
    # clean 7-per-category over 42 items and the human labelled 15 of them,
    # all inside the first 20 presented positions. Under a plain shuffle those
    # 15 came out 4 multi-hop against 1 general-facts, and `docs/12` then
    # reported per-category bias off counts as low as n = 2 -- including the
    # "worst category" figure. The set was balanced; what was read was not.
    #
    # Round-robin over categories keeps every prefix as even as the remaining
    # supply allows, so the honest version of "I did the first twenty" is a
    # balanced twenty. The shuffle above still fixes the order within each
    # category, and category turn order is drawn from the same seeded rng, so
    # this stays a pure function of (rows, seed) and no position predicts a
    # stratum.
    queues: dict[str, list[dict]] = defaultdict(list)
    for r in out:
        queues[r["category"]].append(r)
    turn = sorted(queues)
    rng.shuffle(turn)
    ordered: list[dict] = []
    while len(ordered) < len(out):
        for cat in turn:
            if queues[cat]:
                ordered.append(queues[cat].pop(0))

    for i, r in enumerate(ordered):
        r["position"] = i
    return ordered


# ------------------------------------------------------------ pairwise draws

# Defaults chosen from power, not from taste. At the concordance the first pass
# actually suggests (60.8% on the pairs where the ensemble had an opinion), a
# decisive stratum of 75 has a Wilson lower bound of exactly 0.500 -- it clears
# chance only if the point estimate is precisely right, and fails on any adverse
# draw. That is how the first attempt failed, and repeating it at a larger n is
# the one outcome this rebuild has to avoid. 150 tolerates the truth sitting as
# low as 0.584 and still reports something; 75 tolerates 0.607.
#
# The other three are sized the same way: 50 swapped detects a position effect
# larger than ~13 points (25 detects only ~18), and 30 repeats put a 95%
# interval of roughly +/-0.13 around a labeller's self-agreement. All four are
# overridable; the numbers are defaults, not commitments.
DECISIVE_GAP = 1.0
NEAR_TIE_GAP = 0.5
N_DECISIVE = 150
N_NEAR_TIE = 50
N_SWAPPED = 50
N_REPEAT = 30


def build_pairs(rows: list[dict]) -> list[dict]:
    """Every within-query pair of responses, with the ensemble's margin.

    Pairs are formed inside a query and never across one: "which of these two
    answers to the same question is better" is a question a person can answer,
    and "which of these two answers to different questions is better" is not.
    """
    by_query: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_query[r["query_id"]].append(r)
    out = []
    for qid in sorted(by_query):
        items = sorted(by_query[qid], key=lambda r: r["id"])
        for i, a in enumerate(items):
            for b in items[i + 1:]:
                out.append({
                    "query_id": qid,
                    "category": a["category"],
                    "a": a,
                    "b": b,
                    # `median` is the ensemble score the site publishes, and
                    # the same aggregation `collect` reports against.
                    "gap": abs(a["median"] - b["median"]),
                    "has_gold": bool(a.get("gold_answer")),
                })
    return out


def draw_pairs(pairs: list[dict], seed: int, *, n_decisive: int = N_DECISIVE,
               n_near_tie: int = N_NEAR_TIE, n_swapped: int = N_SWAPPED,
               n_repeat: int = N_REPEAT) -> list[dict]:
    """Stratified, seeded, reproducible -- the pairwise analogue of `draw`.

    Four strata, and only the first may ever be quoted as an agreement figure.

    Stratified on **gold presence** as well as category. A question with no
    recorded gold answer is one where the labeller is judging plausibility
    rather than correctness, which is a different task; the first sampler did
    not look at `gold_answer` at all, so what share of the set was answerable
    on the facts was whatever the draw happened to produce. Here it is half,
    by construction, and reported.

    Presentation order is interleaved by category for the same reason `draw`
    interleaves: labellers stop partway, and a prefix has to stay balanced.
    Re-presentations (`swapped`, `repeat`) are additionally held back from the
    first third of the order, because a pair shown twice inside a few screens
    measures short-term memory rather than reliability.
    """
    rng = random.Random(seed)

    def stratify(cands: list[dict], want: int) -> list[dict]:
        """Even over (category, gold presence), deterministic remainder."""
        buckets: dict[tuple, list[dict]] = defaultdict(list)
        for p in cands:
            buckets[(p["category"], p["has_gold"])].append(p)
        keys = sorted(buckets)
        picked: list[dict] = []
        for i, k in enumerate(keys):
            quota = want // len(keys) + (1 if i < want % len(keys) else 0)
            pool = sorted(buckets[k], key=lambda p: (p["a"]["id"], p["b"]["id"]))
            picked.extend(rng.sample(pool, min(quota, len(pool))))
        # A thin bucket leaves the quota short; top up rather than silently
        # returning a smaller stratum than was asked for.
        if len(picked) < want:
            chosen = {id(p) for p in picked}
            rest = [p for p in sorted(cands, key=lambda p: (p["a"]["id"], p["b"]["id"]))
                    if id(p) not in chosen]
            picked.extend(rng.sample(rest, min(want - len(picked), len(rest))))
        return picked

    decisive = stratify([p for p in pairs if p["gap"] >= DECISIVE_GAP], n_decisive)
    used = {id(p) for p in decisive}
    near_tie = stratify([p for p in pairs
                         if p["gap"] <= NEAR_TIE_GAP and id(p) not in used], n_near_tie)

    out: list[dict] = []
    for p in decisive:
        out.append({**p, "stratum": "decisive"})
    for p in near_tie:
        out.append({**p, "stratum": "near_tie"})

    # Sides are assigned by coin flip, not by score. Putting the higher-scoring
    # response on the left every time would let a labeller who always picks
    # left score 100% agreement without reading anything.
    for i, p in enumerate(out):
        p["pair_id"] = f"p{i:04d}"
        p["flip"] = rng.random() < 0.5

    extras: list[dict] = []
    for src in rng.sample(decisive, min(n_swapped, len(decisive))):
        base = next(p for p in out if p["a"] is src["a"] and p["b"] is src["b"])
        extras.append({**base, "stratum": "swapped", "source_pair_id": base["pair_id"],
                       "flip": not base["flip"]})
    for src in rng.sample(decisive + near_tie, min(n_repeat, len(decisive) + len(near_tie))):
        base = next(p for p in out if p["a"] is src["a"] and p["b"] is src["b"])
        extras.append({**base, "stratum": "repeat", "source_pair_id": base["pair_id"],
                       "flip": base["flip"]})
    for i, p in enumerate(extras):
        p["pair_id"] = f"x{i:04d}"
    for p in out:
        p.setdefault("source_pair_id", None)

    ordered = _interleave(out, rng)

    # Each re-presentation is released only once its original is at least
    # MIN_GAP screens behind. Two things go wrong otherwise, and both did:
    # spacing the extras evenly can put a repeat *before* the pair it repeats,
    # which is not a repeat at all; and a repeat shown a few screens after its
    # original measures short-term memory rather than reliability.
    MIN_GAP = 6
    at = {p["pair_id"]: i for i, p in enumerate(ordered)}
    queue = sorted(extras, key=lambda e: (at[e["source_pair_id"]], e["pair_id"]))
    merged: list[dict] = []
    qi = 0
    for i, p in enumerate(ordered):
        merged.append(p)
        # At most one re-presentation between two real screens, so they stay
        # spread out rather than arriving in a block.
        if qi < len(queue) and at[queue[qi]["source_pair_id"]] + MIN_GAP <= i:
            merged.append(queue[qi]); qi += 1
    merged.extend(queue[qi:])

    for i, p in enumerate(merged):
        p["position"] = i
    return merged


def _interleave(items: list[dict], rng: random.Random) -> list[dict]:
    """Round-robin over categories, so every prefix stays balanced."""
    shuffled = list(items)
    rng.shuffle(shuffled)
    queues: dict[str, list[dict]] = defaultdict(list)
    for p in shuffled:
        queues[p["category"]].append(p)
    turn = sorted(queues)
    rng.shuffle(turn)
    out: list[dict] = []
    while len(out) < len(shuffled):
        for cat in turn:
            if queues[cat]:
                out.append(queues[cat].pop(0))
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


def _render(r: dict) -> dict:
    """One response as the labeller sees it — no vendor, no scores."""
    results = json.loads(r["results"]) if r["results"] else []
    return {
        "response_mode": r["response_mode"],
        "answer": r["answer"],
        "results": [
            {"rank": x.get("rank"), "title": x.get("title"),
             "url": x.get("url"), "snippet": x.get("snippet")}
            for x in results
        ],
    }


def write_pair_task(set_id: str, picked: list[dict], out_dir: Path,
                    created_at: str | None = None) -> Path:
    """The pairwise labelling task.

    Carries no stratum, no ensemble margin and no `source_pair_id`: a labeller
    who can see that a pair is a repeat, or that the judges thought it easy,
    is answering a different question. The analysis rejoins all three from the
    database afterwards.

    `created_at` is when the set was *drawn*, not when this file was written.
    They are the same thing for `sample-pairs` and are not for `render`, which
    rebuilds a task drawn weeks earlier; stamping the rebuild date would make a
    set look freshly drawn every time its task was recovered.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    items = []
    for p in sorted(picked, key=lambda p: p["position"]):
        left, right = (p["b"], p["a"]) if p["flip"] else (p["a"], p["b"])
        items.append({
            "pair_id": p["pair_id"],
            "position": p["position"],
            "query": left["query_text"],
            "category": p["category"],
            "gold_answer": left["gold_answer"],
            "left": _render(left),
            "right": _render(right),
        })
    payload = {
        "set_id": set_id,
        "kind": "pairwise",
        "created_at": created_at or _now(),
        "blinding": BLINDING_PAIRWISE,
        # The worked anchors, not the judges' rubric string: that is a format
        # template full of placeholders, and pasting it in front of a person
        # would be showing them a prompt rather than an instruction.
        "anchors": ANCHORS,
        "items": items,
    }
    (out_dir / "task.js").write_text(
        "// Generated by src/calibrate.py — do not edit.\n"
        "// Contains vendor-retrieved content: never commit, never publish.\n"
        "window.VN_TASK = " + json.dumps(payload, indent=1) + ";\n"
    )
    (out_dir / "label.html").write_text(PAIR_UI_TEMPLATE.read_text())
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

def _import_pairs(conn: sqlite3.Connection, args: argparse.Namespace,
                  payload: dict, set_id: str) -> int:
    known = {r["pair_id"] for r in conn.execute(
        "SELECT pair_id FROM calibration_pairs WHERE set_id = ?", (set_id,))}
    if not known:
        raise SystemExit(f"no pairwise calibration set {set_id} in this database")

    rows, skipped, seconds = [], 0, []
    for lab in payload["labels"]:
        pid = lab.get("pair_id")
        if pid not in known or lab.get("choice") not in ("left", "right", "tie"):
            skipped += 1        # unfinished is absent data, not a tie
            continue
        rows.append((uuid.uuid4().hex, set_id, pid, args.labeller, args.labeller_kind,
                     lab["choice"], lab.get("note"), lab.get("seconds"), _now()))
        if lab.get("seconds"):
            seconds.append(lab["seconds"])
    conn.executemany(
        "INSERT OR REPLACE INTO pair_labels (id, set_id, pair_id, labeller, "
        "labeller_kind, choice, note, seconds, labelled_at) VALUES (?,?,?,?,?,?,?,?,?)",
        rows)
    conn.commit()
    print(f"imported {len(rows)} pairwise judgements into {set_id} "
          f"as {args.labeller} [{args.labeller_kind}]"
          + (f"; skipped {skipped} unjudged" if skipped else ""))
    if seconds:
        print(f"  median {statistics.median(seconds):.0f}s per screen; "
              f"{sum(1 for s in seconds if s < 10)} under 10s")
    if args.labeller_kind != "human":
        print("  NOT A CALIBRATION — model labels measure agreement between "
              "models (docs/12).")
    conn.close()
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    conn = storage.connect(Path(args.db))
    conn.row_factory = sqlite3.Row
    payload = json.loads(Path(args.labels).read_text())
    set_id = payload["set_id"]

    # Routed on what the task declared, not on what the file looks like. A
    # pairwise export guessed at as absolute would import zero rows and say so
    # in a way that reads like an empty labelling session.
    if payload.get("kind") == "pairwise":
        return _import_pairs(conn, args, payload, set_id)

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


def _fisher_ci(r: float | None, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """95% interval on a correlation, via the Fisher z transform.

    Reported because the first calibration pass published `r 0.10` on n = 15 and
    that number was read as "the judges do not agree with people". Its interval
    is [-0.437, +0.581]: both signs are inside it, so the pass established
    neither direction. A correlation from fifteen items without its interval is
    not a weak finding, it is not a finding.
    """
    if r is None or n < 4 or abs(r) >= 1:
        return None
    z0 = 0.5 * math.log((1 + r) / (1 - r))
    se = 1 / math.sqrt(n - 3)
    lo, hi = z0 - z * se, z0 + z * se
    back = lambda t: (math.exp(2 * t) - 1) / (math.exp(2 * t) + 1)   # noqa: E731
    return back(lo), back(hi)


def _pearson_ceiling(xs: list[float], ys: list[float]) -> float | None:
    """The largest r these two sets of numbers could produce, marginals fixed.

    Sorting both and correlating is the comonotonic rearrangement, which
    maximises the correlation attainable without changing either distribution.
    It exists to keep an argument honest: the first pass explained its low r as
    an artefact of most human scores being 9 or 10, and that explanation is
    checkable. On those labels the ceiling is 0.935, so compression accounts for
    at most 0.065 of a shortfall of 0.903 -- about 7% of it, not "partly". Any
    future pass that wants to blame its distribution has to clear this number
    first (`docs/12`).
    """
    return _pearson(sorted(xs), sorted(ys))


def agreement(pairs: list[tuple[float, float]]) -> dict:
    """One judge's scores against the human's, on the same responses."""
    if not pairs:
        return {"n": 0}
    js = [p[0] for p in pairs]
    hs = [p[1] for p in pairs]
    diffs = [j - h for j, h in pairs]
    r = _pearson(js, hs)
    return {
        "n": len(pairs),
        "mae": statistics.fmean(abs(d) for d in diffs),
        "bias": statistics.fmean(diffs),          # signed: + means judge is generous
        "pearson": r,
        "pearson_ci95": _fisher_ci(r, len(pairs)),
        "pearson_max": _pearson_ceiling(js, hs),
        "spearman": _spearman(js, hs),
        "within_1": sum(1 for d in diffs if abs(d) <= 1) / len(diffs),
        "off_by_3": sum(1 for d in diffs if abs(d) > 3),
    }


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """Interval on a proportion. Wilson rather than normal-approximation
    because the counts here are small and near the boundary is exactly where
    the normal interval misbehaves."""
    if n <= 0:
        return None
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    # Clamped: at k=0 the arithmetic lands on -2.8e-17, which formats as
    # "-0.0%" — a negative share of a proportion, printed next to a claim about
    # rigour.
    return max(0.0, centre - half), min(1.0, centre + half)


def pairwise_concordance(pairs: list[tuple[float, float]]) -> dict:
    """How often the ensemble orders two responses the way the human did.

    Absolute scores from one labeller already contain ordering information: any
    two items the labeller scored differently are a preference. Reading them
    that way sidesteps the 9-10 ceiling that flattened the first pass, because
    an ordering does not care that both numbers were high.

    Ensemble ties are reported both ways on purpose. Dropping them conditions
    the result on the ensemble having an opinion, which raised the first pass's
    apparent concordance from 47.0% to 60.8% -- a real difference, arrived at by
    conditioning on the thing under audit. Publish the denominator or neither
    number (`docs/12`).
    """
    ordered = [(j1, h1, j2, h2)
               for i, (j1, h1) in enumerate(pairs)
               for (j2, h2) in pairs[i + 1:]
               if h1 != h2]
    if not ordered:
        return {"n_pairs": 0}
    agree = sum(1 for j1, h1, j2, h2 in ordered if (h1 - h2) * (j1 - j2) > 0)
    tied = sum(1 for j1, h1, j2, h2 in ordered if j1 == j2)
    decided = len(ordered) - tied
    return {
        "n_pairs": len(ordered),
        "n_ensemble_tied": tied,
        "agree": agree,
        "concordance_all": agree / len(ordered),
        "ci95_all": _wilson(agree, len(ordered)),
        # Conditional on the ensemble expressing a preference. Higher, and
        # narrower in scope; never report it without `n_ensemble_tied`.
        "concordance_decided": agree / decided if decided else None,
        "ci95_decided": _wilson(agree, decided) if decided else None,
    }


def pairwise_report(labels: list[dict]) -> dict:
    """Judge-vs-human agreement read off a pairwise set.

    `labels` are dicts carrying: stratum, choice ('left'|'right'|'tie'),
    ensemble_choice ('left'|'right'|'tie'), source_pair_id, and shown_left /
    shown_right response ids.

    Three separate questions, deliberately not combined into one number:

    - **concordance**, on the decisive stratum alone. This is the only figure
      that may ever be quoted as agreement. The near-tie stratum is excluded
      because the ensemble has no opinion there by construction, so counting it
      measures the labeller against a coin.
    - **position bias**, from the swapped stratum. A labeller who picks the
      same *side* both times, rather than the same *response*, is answering
      about the layout.
    - **self-agreement**, from the repeat stratum. Without it, a labeller
      disagreeing with the judges cannot be distinguished from a labeller
      disagreeing with themselves, and the first number is worthless without
      the second.

    Re-presentations never count toward concordance. They are the same evidence
    shown twice and pooling them would narrow the interval on nothing.
    """
    out: dict = {}

    decisive = [l for l in labels if l["stratum"] == "decisive"]
    scored = [l for l in decisive if l["choice"] != "tie"]
    agree = sum(1 for l in scored if l["choice"] == l["ensemble_choice"])
    out["decisive"] = {
        "n": len(decisive),
        "n_human_tied": len(decisive) - len(scored),
        "n_scored": len(scored),
        "agree": agree,
        "concordance": agree / len(scored) if scored else None,
        "ci95": _wilson(agree, len(scored)) if scored else None,
    }
    ci = out["decisive"]["ci95"]
    # The whole point of sizing the stratum. Said out loud so that a result
    # which does not clear chance cannot be reported as though it had.
    out["decisive"]["clears_chance"] = bool(ci and ci[0] > 0.5)

    near = [l for l in labels if l["stratum"] == "near_tie"]
    near_scored = [l for l in near if l["choice"] != "tie"]
    out["near_tie"] = {
        "n": len(near),
        "n_human_separated": len(near_scored),
        # Diagnostic only: where the ensemble sees nothing and a human sees a
        # difference, that is a lead on what the rubric is missing.
        "human_separates_pct": len(near_scored) / len(near) if near else None,
    }

    by_id = {l["pair_id"]: l for l in labels}
    swapped = [l for l in labels if l["stratum"] == "swapped" and l.get("source_pair_id") in by_id]
    same_side = 0
    consistent = 0
    for l in swapped:
        src = by_id[l["source_pair_id"]]
        if l["choice"] == "tie" or src["choice"] == "tie":
            continue
        if l["choice"] == src["choice"]:
            same_side += 1          # same SIDE across a swap = picked the position
        if l.get("shown_" + l["choice"]) == src.get("shown_" + src["choice"]):
            consistent += 1         # same RESPONSE across a swap = picked the answer
    n_sw = sum(1 for l in swapped
               if l["choice"] != "tie" and by_id[l["source_pair_id"]]["choice"] != "tie")
    out["position_bias"] = {
        "n": n_sw,
        "picked_same_side": same_side,
        "picked_same_response": consistent,
        "side_rate": same_side / n_sw if n_sw else None,
        "ci95": _wilson(same_side, n_sw) if n_sw else None,
    }

    repeats = [l for l in labels if l["stratum"] == "repeat" and l.get("source_pair_id") in by_id]
    same = sum(1 for l in repeats if l["choice"] == by_id[l["source_pair_id"]]["choice"])
    out["self_agreement"] = {
        "n": len(repeats),
        "agree": same,
        "rate": same / len(repeats) if repeats else None,
        "ci95": _wilson(same, len(repeats)) if repeats else None,
    }
    return out


def collect(conn: sqlite3.Connection, set_id: str) -> dict[tuple, dict[str, list[dict]]]:
    """Labels joined to every judge score, keyed by (labeller, kind) then stratum.

    Keyed by labeller because a set can hold several. Pooling them would average
    a human and a model into one number that describes neither, and the whole
    point of recording the kind is that those two are not interchangeable.
    """
    out: dict[tuple, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
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
        out[(d["labeller"], d.get("labeller_kind") or "unknown")][d["stratum"]].append(d)
    return out


def _fmt(a: dict) -> str:
    if not a.get("n"):
        return "no data"
    def num(x, spec=".2f"):
        return "  n/a" if x is None else format(x, spec)
    ci = a.get("pearson_ci95")
    # An r without its interval is what let `r 0.10` be read as a finding when
    # both signs were inside the interval (docs/12). They travel together.
    ci_s = f" [{ci[0]:+.2f},{ci[1]:+.2f}]" if ci else ""
    return (f"n={a['n']:<4} MAE {a['mae']:.2f}  bias {a['bias']:+.2f}  "
            f"r {num(a['pearson'])}{ci_s}  rho {num(a['spearman'])}  "
            f"within 1pt {a['within_1']:.0%}  off by >3: {a['off_by_3']}")


def cmd_sample_pairs(args: argparse.Namespace) -> int:
    conn = storage.connect(Path(args.db))
    conn.row_factory = sqlite3.Row
    run_id = args.run or latest_run(conn)

    rows = candidates(conn, run_id)
    pairs = build_pairs(rows)
    picked = draw_pairs(pairs, args.seed, n_decisive=args.decisive,
                        n_near_tie=args.near_tie, n_swapped=args.swapped,
                        n_repeat=args.repeat)

    set_id = uuid.uuid4().hex[:12]
    conn.execute(
        "INSERT INTO calibration_sets (id, run_id, created_at, seed, n_target, "
        "disagreement_share, blinding, notes, kind) VALUES (?,?,?,?,?,?,?,?,?)",
        (set_id, run_id, _now(), args.seed, len(picked), 0.0,
         BLINDING_PAIRWISE, args.notes, "pairwise"),
    )
    conn.executemany(
        "INSERT INTO calibration_pairs (set_id, pair_id, left_response_id, "
        "right_response_id, stratum, position, source_pair_id, ensemble_gap) "
        "VALUES (?,?,?,?,?,?,?,?)",
        [(set_id, p["pair_id"],
          (p["b"] if p["flip"] else p["a"])["id"],
          (p["a"] if p["flip"] else p["b"])["id"],
          p["stratum"], p["position"], p.get("source_pair_id"), p["gap"])
         for p in picked],
    )

    # Written before the commit, so a failure here leaves no set behind. The
    # other order left two orphans in the database during development -- rows
    # describing a labelling task that does not exist on disk and can never be
    # labelled, which a later `report` will happily list as awaiting work.
    out_dir = Path(args.out) / set_id
    write_pair_task(set_id, picked, out_dir)
    conn.commit()

    print(f"pairwise calibration set {set_id}  from run {run_id[:8]}  seed {args.seed}")
    print(f"  {len(pairs)} pairs available; drew {len(picked)} screens")
    for stratum in ("decisive", "near_tie", "swapped", "repeat"):
        rs = [p for p in picked if p["stratum"] == stratum]
        if not rs:
            continue
        gold = sum(1 for p in rs if p["has_gold"])
        cats = defaultdict(int)
        for p in rs:
            cats[p["category"]] += 1
        print(f"  {stratum:<10} {len(rs):>3}   gold-backed {gold}/{len(rs)}"
              f"   mean gap {statistics.fmean(p['gap'] for p in rs):.2f}")
        print("             " + ", ".join(f"{k} {v}" for k, v in sorted(cats.items())))

    # The number this set can and cannot produce, printed before a single label
    # exists. A design's power is a property of the design, and stating it
    # afterwards is how an underpowered result gets reported as a finding.
    n_dec = sum(1 for p in picked if p["stratum"] == "decisive")
    floor = next((x / 1000 for x in range(500, 1000)
                  if (_wilson(round(x / 1000 * n_dec), n_dec) or (0,))[0] > 0.5), None)
    print(f"\n  power: with {n_dec} decisive comparisons, the interval clears chance")
    print(f"         only if true concordance is at least "
          f"{floor:.3f}" if floor else "         never clears chance at this n")
    print(f"         (the first pass suggests 0.608, on 51 pairs — docs/12)")
    print(f"\n  open  {out_dir / 'label.html'}")
    print(f"  then  python -m src.calibrate import {out_dir / 'labels.json'} "
          f"--labeller YOURNAME --labeller-kind human")
    conn.close()
    return 0


def load_pair_set(conn: sqlite3.Connection, set_id: str) -> list[dict]:
    """Rebuild a drawn pairwise set from the database, in write_pair_task's shape.

    A drawn set lives in two places. What was drawn is in the database; the task
    the labeller opens is written to disk *outside* git, because it necessarily
    shows the vendors' retrieved content and `docs/03` is why that never gets
    committed. The half that goes missing is therefore always the second one — a
    different machine, a clean checkout, a tidied directory — and until now the
    only way to get it back was `sample-pairs`, which draws a **new** set.

    That is the move this function exists to avoid. Re-drawing would replace a
    sample recorded against a seed and a date with a different one, and would do
    it silently; set `96afde9bfef3` has been in this database since 2026-08-05
    with 280 screens and no task on disk, and re-drawing it would have quietly
    thrown away the sample that was registered in favour of one drawn after
    somebody had already seen the scores. The held-out manifest exists to make
    exactly that impossible for questions, and the argument is the same here.

    `calibration_pairs` stores left and right in the order the labeller was meant
    to see them — `sample-pairs` applies the flip before writing the rows — so
    nothing is re-randomised here and `flip` is False by construction. Position
    bias stays measurable because the `swapped` stratum is recorded as its own
    rows, not recreated by shuffling on the way out.
    """
    rows = conn.execute(
        """
        SELECT cp.pair_id, cp.position,
               q.category, q.text AS query_text, q.gold_answer,
               l.response_mode AS l_mode, l.answer AS l_answer, l.results AS l_results,
               r.response_mode AS r_mode, r.answer AS r_answer, r.results AS r_results
        FROM calibration_pairs cp
        JOIN raw_responses l ON l.id = cp.left_response_id
        JOIN raw_responses r ON r.id = cp.right_response_id
        JOIN queries q ON q.id = l.query_id
        WHERE cp.set_id = ?
        ORDER BY cp.position
        """,
        (set_id,),
    ).fetchall()
    if not rows:
        raise SystemExit(
            f"no pairs recorded for set {set_id!r}. A pairwise set has rows in "
            f"calibration_pairs; an absolute set does not and cannot be rebuilt "
            f"by this command."
        )

    # Pairs are formed inside a query and never across one (see build_pairs), so
    # both sides share the question, and joining it through the left response is
    # not an approximation.
    def side(row: sqlite3.Row, prefix: str) -> dict:
        return {
            "response_mode": row[f"{prefix}_mode"],
            "answer": row[f"{prefix}_answer"],
            "results": row[f"{prefix}_results"],
            "query_text": row["query_text"],
            "gold_answer": row["gold_answer"],
        }

    return [
        {
            "pair_id": r["pair_id"],
            "position": r["position"],
            "category": r["category"],
            "flip": False,
            "a": side(r, "l"),
            "b": side(r, "r"),
        }
        for r in rows
    ]


def cmd_render(args: argparse.Namespace) -> int:
    """Write the labelling task for a set that was already drawn."""
    conn = storage.connect(Path(args.db))
    conn.row_factory = sqlite3.Row
    meta = conn.execute(
        "SELECT id, run_id, created_at, seed, kind FROM calibration_sets WHERE id = ?",
        (args.set,),
    ).fetchone()
    if not meta:
        have = [r["id"] for r in conn.execute("SELECT id FROM calibration_sets")]
        raise SystemExit(
            f"no calibration set {args.set!r} in {args.db}. This database holds: "
            + (", ".join(have) or "none")
        )

    picked = load_pair_set(conn, args.set)
    out_dir = Path(args.out) / args.set
    write_pair_task(args.set, picked, out_dir, created_at=meta["created_at"])
    labelled = conn.execute(
        "SELECT COUNT(*) FROM pair_labels WHERE set_id = ?", (args.set,)
    ).fetchone()[0]
    conn.close()

    print(f"rebuilt pairwise set {args.set}: {len(picked)} screens, drawn "
          f"{meta['created_at'][:10]} with seed {meta['seed']}")
    print("  the set was not re-drawn — these are the pairs recorded when it was "
          "registered")
    print(f"  {labelled} label(s) already in the database for this set")
    print(f"\n  open  {out_dir / 'label.html'}")
    print(f"  then  python -m src.calibrate import {out_dir / 'labels.json'} "
          f"--labeller YOURNAME --labeller-kind human")
    return 0


def _report_pairs(conn: sqlite3.Connection, meta: sqlite3.Row, set_id: str,
                  args: argparse.Namespace) -> int:
    """Agreement on a pairwise set, one labeller at a time."""
    ens = {}
    for r in conn.execute(
        """SELECT cp.pair_id, cp.stratum, cp.source_pair_id, cp.ensemble_gap,
                  cp.left_response_id AS l, cp.right_response_id AS r
           FROM calibration_pairs cp WHERE cp.set_id = ?""", (set_id,)):
        def med(rid):
            v = [x[0] for x in conn.execute(
                "SELECT overall FROM judge_scores WHERE response_id = ?", (rid,))
                if x[0] is not None]
            return statistics.median(v) if v else None
        ml, mr = med(r["l"]), med(r["r"])
        choice = "tie" if ml == mr else ("left" if (ml or 0) > (mr or 0) else "right")
        ens[r["pair_id"]] = {
            "pair_id": r["pair_id"], "stratum": r["stratum"],
            "source_pair_id": r["source_pair_id"], "ensemble_choice": choice,
            "shown_left": r["l"], "shown_right": r["r"],
        }

    labs = defaultdict(list)
    for r in conn.execute(
        "SELECT * FROM pair_labels WHERE set_id = ?", (set_id,)):
        if args.labeller and r["labeller"] != args.labeller:
            continue
        base = ens.get(r["pair_id"])
        if base:
            labs[(r["labeller"], r["labeller_kind"])].append({**base, "choice": r["choice"]})

    n_pairs = len(ens)
    print(f"pairwise calibration set {set_id}  run {meta['run_id'][:8]}  "
          f"seed {meta['seed']}  {n_pairs} screens")
    print(f"blinding: {meta['blinding']}")
    if not labs:
        print("\nnothing judged yet — open the task and import the result.")
        return 0

    for (labeller, kind), rows in sorted(labs.items()):
        print()
        print("#" * 78)
        print(f"LABELLER: {labeller}  [{kind}]  — {len(rows)}/{n_pairs} screens")
        if kind != "human":
            print("NOT A CALIBRATION. These describe agreement between models and say")
            print("nothing about whether the judges track human judgement (docs/04).")
        print("#" * 78)
        rep = pairwise_report(rows)

        d = rep["decisive"]
        print(f"\nDECISIVE — the only stratum an agreement figure may quote")
        if d["n_scored"]:
            lo, hi = d["ci95"]
            print(f"  {d['agree']}/{d['n_scored']} = {d['concordance']:.1%}"
                  f"   95% CI [{lo:.1%}, {hi:.1%}]"
                  f"   ({d['n_human_tied']} called level by the labeller)")
            print("  " + ("clears chance — the interval excludes 50%"
                          if d["clears_chance"] else
                          "DOES NOT clear chance — the interval includes 50%, so this "
                          "is not\n  evidence the judges track human ordering. It does "
                          "not go on the site."))
        else:
            print("  nothing scored yet")

        nt = rep["near_tie"]
        if nt["n"]:
            print(f"\nNEAR-TIE — diagnostic, never quoted as agreement")
            print(f"  the labeller separated {nt['n_human_separated']}/{nt['n']} "
                  f"({nt['human_separates_pct']:.0%}) of the pairs the judges scored level")

        pb = rep["position_bias"]
        if pb["n"]:
            lo, hi = pb["ci95"]
            print(f"\nPOSITION BIAS — same pair, sides swapped")
            print(f"  picked the same SIDE {pb['picked_same_side']}/{pb['n']} "
                  f"= {pb['side_rate']:.1%}   95% CI [{lo:.1%}, {hi:.1%}]")
            print(f"  picked the same RESPONSE {pb['picked_same_response']}/{pb['n']}")
            if lo > 0.5:
                print("  the labeller is picking the position, not the response — "
                      "this set is not usable")

        sa = rep["self_agreement"]
        if sa["n"]:
            lo, hi = sa["ci95"]
            print(f"\nSELF-AGREEMENT — same pair shown twice unchanged")
            print(f"  {sa['agree']}/{sa['n']} = {sa['rate']:.1%}   "
                  f"95% CI [{lo:.1%}, {hi:.1%}]")
            print("  a labeller who disagrees with themselves this often cannot "
                  "disagree\n  with the judges by less — read the figure above "
                  "against this one.")
    conn.close()
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    conn = storage.connect(Path(args.db))
    conn.row_factory = sqlite3.Row
    set_id = args.set or (conn.execute(
        "SELECT id FROM calibration_sets ORDER BY created_at DESC LIMIT 1").fetchone() or [None])[0]
    if not set_id:
        raise SystemExit("no calibration set in this database — run `sample` first")

    meta = conn.execute("SELECT * FROM calibration_sets WHERE id = ?", (set_id,)).fetchone()
    if (meta["kind"] if "kind" in meta.keys() else None) == "pairwise":
        return _report_pairs(conn, meta, set_id, args)
    by_labeller = collect(conn, set_id)
    if args.labeller:
        by_labeller = {k: v for k, v in by_labeller.items() if k[0] == args.labeller}
    n_items = conn.execute(
        "SELECT COUNT(*) FROM calibration_items WHERE set_id = ?", (set_id,)).fetchone()[0]

    print(f"calibration set {set_id}  run {meta['run_id'][:8]}  seed {meta['seed']}")
    print(f"blinding: {meta['blinding']}")
    if not by_labeller:
        print(f"\nnothing labelled yet — open the task and import the result.")
        return 0

    for (labeller, kind), strata in sorted(by_labeller.items()):
        total = sum(len(v) for v in strata.values())
        print()
        print("#" * 78)
        print(f"LABELLER: {labeller}  [{kind}]  — {total}/{n_items} items")
        if kind != "human":
            print("NOT A CALIBRATION. These describe agreement between models and say")
            print("nothing about whether the judges track human judgement (docs/04).")
        print("#" * 78)

        for stratum, is_random in (("random", True), ("disagreement", False)):
            rows = strata.get(stratum) or []
            if not rows:
                continue
            if is_random:
                head = ("headline agreement figure" if kind == "human"
                        else "model-vs-model, not a calibration figure")
                print(f"\nRANDOM STRATUM — {head}")
            else:
                print("\nDISAGREEMENT STRATUM — the judges' worst moments, diagnostic only")
                print("  Selected for difficulty; never quote as the benchmark's agreement.")
            for fam, _model in JUDGES:
                pairs = [(r["judges"][fam], r["human"]) for r in rows if fam in r["judges"]]
                print(f"  {fam:<10} {_fmt(agreement(pairs))}")
            print(f"  {'ENSEMBLE':<10} {_fmt(agreement([(r['ensemble'], r['human']) for r in rows]))}")

            ens_pairs = [(r["ensemble"], r["human"]) for r in rows]
            ceiling = agreement(ens_pairs).get("pearson_max")
            if ceiling is not None:
                print(f"  ceiling: the most these two distributions could correlate "
                      f"is r {ceiling:.3f}")

            # The same labels read as orderings. This is the quantity a ranking
            # actually rests on, and unlike r it is unaffected by a labeller
            # who uses only the top of the scale.
            pc = pairwise_concordance(ens_pairs)
            if pc.get("n_pairs"):
                a_all = f"{pc['concordance_all']:.1%}"
                ci_a = pc["ci95_all"]
                print(f"  ordering: ensemble matches the labeller on {pc['agree']}/"
                      f"{pc['n_pairs']} pairs = {a_all}"
                      + (f"  95% CI [{ci_a[0]:.1%}, {ci_a[1]:.1%}]" if ci_a else ""))
                if pc["n_ensemble_tied"]:
                    ci_d = pc["ci95_decided"]
                    print(f"            {pc['n_ensemble_tied']} of those the ensemble "
                          f"scored level; on the {pc['n_pairs'] - pc['n_ensemble_tied']} "
                          f"it did not, {pc['concordance_decided']:.1%}"
                          + (f"  95% CI [{ci_d[0]:.1%}, {ci_d[1]:.1%}]" if ci_d else ""))
                    print("            (the second conditions on the ensemble having an "
                          "opinion — quote it with its denominator)")
                lo = (pc["ci95_all"] or (0, 0))[0]
                if lo <= 0.5:
                    print("            interval includes 50% — not evidence of "
                          "agreement above chance")

            gen = sum(1 for r in rows if r["ensemble"] - r["human"] > 2)
            harsh = sum(1 for r in rows if r["human"] - r["ensemble"] > 2)
            print(f"  judges >2pts generous: {gen}   >2pts harsh: {harsh}")
            by_cat: dict[str, list[float]] = defaultdict(list)
            for r in rows:
                by_cat[r["category"]].append(r["ensemble"] - r["human"])
            print("  bias by category:")
            for cat, ds in sorted(by_cat.items(), key=lambda kv: -abs(statistics.fmean(kv[1]))):
                print(f"    {cat:<16} {statistics.fmean(ds):+.2f}  (n={len(ds)})")

    # Where two labellers scored the same responses, how far apart are they? For a
    # human and a model this is the number that says what the model pass was
    # worth: agreement with the judges means little if the two labellers who
    # produced it do not agree with each other.
    keys = sorted(by_labeller)
    if len(keys) > 1:
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                ra = {r["response_id"]: r["human"] for rs in by_labeller[a].values() for r in rs}
                rb = {r["response_id"]: r["human"] for rs in by_labeller[b].values() for r in rs}
                shared = sorted(set(ra) & set(rb))
                if len(shared) < 3:
                    continue
                print()
                print("=" * 78)
                print(f"LABELLER AGREEMENT: {a[0]} [{a[1]}] vs {b[0]} [{b[1]}]")
                print("=" * 78)
                print(f"  {_fmt(agreement([(ra[k], rb[k]) for k in shared]))}")
                print(f"  bias sign: positive means {a[0]} scores higher")
                worst = sorted(shared, key=lambda k: -abs(ra[k] - rb[k]))[:5]
                for k in worst:
                    row = next(r for rs in by_labeller[a].values() for r in rs
                               if r["response_id"] == k)
                    print(f"    {ra[k]:>4.1f} vs {rb[k]:>4.1f}  {row['category']:<15} "
                          f"{row['query_text'][:44]}")

    flat = [r for strata in by_labeller.values() for rs in strata.values() for r in rs]
    worst = sorted(flat, key=lambda r: -abs(r["ensemble"] - r["human"]))[:args.show]
    if worst:
        print()
        print("=" * 78)
        print(f"LARGEST JUDGE DISAGREEMENTS (top {len(worst)}) — read before changing the rubric")
        print("=" * 78)
        for r in worst:
            print(f"  {r['labeller'][:12]:<12} {r['human']:>4.1f}  ensemble {r['ensemble']:>4.1f}  "
                  f"{r['category']:<15} {r['query_text'][:44]}")
    conn.close()
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Write a set's labels to the repository as JSON.

    Labels live in the database, and the database is never committed — it holds
    raw vendor payloads. So an hour of labelling survives exactly as long as one
    laptop does, which is the same failure the run history had before per-week
    JSON was committed. Labels are scores, not vendor content, so unlike the
    task itself they are safe to keep in git.
    """
    conn = storage.connect(Path(args.db))
    conn.row_factory = sqlite3.Row
    meta = conn.execute("SELECT * FROM calibration_sets WHERE id = ?", (args.set,)).fetchone()
    if not meta:
        raise SystemExit(f"no calibration set {args.set} in this database")

    items = {r["response_id"]: r["stratum"] for r in conn.execute(
        "SELECT response_id, stratum FROM calibration_items WHERE set_id = ?", (args.set,))}
    labels = []
    for r in conn.execute(
            "SELECT * FROM human_labels WHERE set_id = ? ORDER BY labeller, response_id",
            (args.set,)):
        labels.append({
            "response_id": r["response_id"],
            "stratum": items.get(r["response_id"]),
            "labeller": r["labeller"],
            "labeller_kind": r["labeller_kind"],
            "relevance": r["relevance"], "freshness": r["freshness"],
            "citation_quality": r["citation_quality"], "overall": r["overall"],
            "seconds": r["seconds"], "note": r["note"],
        })
    payload = {
        "set_id": meta["id"], "run_id": meta["run_id"], "seed": meta["seed"],
        "created_at": meta["created_at"], "blinding": meta["blinding"],
        "notes": meta["notes"], "n_items": len(items), "labels": labels,
    }
    out = Path(args.out) / f"{args.set}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=1) + "\n")
    kinds = {}
    for l in labels:
        kinds[(l["labeller"], l["labeller_kind"])] = kinds.get((l["labeller"], l["labeller_kind"]), 0) + 1
    print(f"wrote {out} — {len(labels)} label(s)")
    for (who, kind), n in sorted(kinds.items()):
        print(f"  {who} [{kind}]: {n}")
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

    p = sub.add_parser("sample-pairs",
                       help="draw a blinded pairwise comparison set (the calibration "
                            "that absolute scoring could not deliver)")
    p.add_argument("--run", help="run id (default: the most complete run)")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--decisive", type=int, default=N_DECISIVE,
                   help=f"pairs the ensemble separates by >= {DECISIVE_GAP} "
                        f"(default {N_DECISIVE}; 75 clears chance only if the "
                        f"point estimate is exactly right — see docs/12)")
    p.add_argument("--near-tie", type=int, default=N_NEAR_TIE)
    p.add_argument("--swapped", type=int, default=N_SWAPPED,
                   help=f"position-bias checks (default {N_SWAPPED}; 25 detects "
                        f"only effects above ~18 points)")
    p.add_argument("--repeat", type=int, default=N_REPEAT,
                   help=f"intra-rater repeats (default {N_REPEAT})")
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--notes")
    p.set_defaults(func=cmd_sample_pairs)

    # Recovery, not re-drawing. The task lives outside git (it shows vendor
    # content), so it is the half of a set that goes missing; `sample-pairs`
    # would replace the registered sample rather than restore it.
    d = sub.add_parser("render",
                       help="rebuild the labelling task for a set already drawn, "
                            "without drawing a new one")
    d.add_argument("--set", required=True, help="calibration set id")
    d.add_argument("--out", default=str(DEFAULT_OUT))
    d.set_defaults(func=cmd_render)

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
    r.add_argument("--labeller", help="report only this labeller")
    r.add_argument("--show", type=int, default=12)
    r.set_defaults(func=cmd_report)

    e = sub.add_parser("export", help="write a set's labels to the repository")
    e.add_argument("--set", required=True)
    e.add_argument("--out", default=str(ROOT / "labels"))
    e.set_defaults(func=cmd_export)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

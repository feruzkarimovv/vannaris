"""The private held-out question set, and the commitment that makes it honest.

`docs/04` asks for a rotating held-out set so a vendor cannot hill-climb against
a published list of 150 questions. The obvious implementation — keep some
questions secret — is worthless on its own, because a benchmark that says "we
also ran some private questions, trust us" is asking for exactly the trust this
project exists to make unnecessary. A secret score is a vendor's self-benchmark
with the sign flipped.

So the set is withheld, not hidden. Three things make that a checkable claim
rather than an assertion:

1. **Pre-registration.** The SHA-256 of the set is committed to this repository
   *before* the set ever runs, in `manifest.json`. The questions themselves live
   outside git (see `LOCAL_DIR`). Nobody — including whoever maintains this —
   can swap the questions after seeing the scores without the hash changing in a
   public file with a timestamp on it.
2. **Delayed disclosure.** A set retires on a fixed rotation and is published in
   full at that point, hash and all, so any reader can recompute the numbers it
   produced and check them against what was published at the time. The secrecy
   has a defined end date; the evidence does not.
3. **Scores are never withheld.** Only the question *text* is. Every held-out
   response is in the exported CSVs with its query id, its judge scores, its
   latency and its cost, marked `held_out=1`. What a reader cannot see before
   retirement is which question produced which row.

The one thing this design cannot do, and the methodology page says so plainly:
a held-out question is not invisible to the vendor being asked it. Vendors
receive every query the benchmark sends. What the set defeats is cheap
optimisation against a *published* list, and it detects that by comparing a
vendor's score on the public set against its score on the held-out set in the
same run. A vendor that has tuned for the published questions scores visibly
better on them. That gap is the measurement; see `build_heldout` in export.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Committed. Hashes and shapes only — never question text for a set that is
# still active.
MANIFEST = ROOT / "src" / "queries" / "heldout" / "manifest.json"

# Published in full once a set retires. This is the disclosure half of the
# design, and it is inside the repository precisely so that it is diffable.
RETIRED_DIR = MANIFEST.parent / "retired"

# Where the *active* set's text is allowed to live: outside git (data/heldout/
# is gitignored alongside the database, for the same reason). CI gets it from
# an Actions secret written to this path, so no plaintext ever reaches a commit
# while the set is live.
LOCAL_DIR = ROOT / "data" / "heldout"

# Sets rotate on this cadence. Four weeks is a compromise: long enough that a
# single bad week does not throw away a set, short enough that the disclosure
# promise is worth something to a reader who wants to check the work this
# quarter rather than next year.
ROTATE_AFTER_WEEKS = 4


def digest(queries: list[dict]) -> str:
    """The commitment. Same canonicalisation as `runner.load_queries`, but the
    full 64 hex characters rather than a truncated 16 — this one is doing
    cryptographic work rather than labelling a run."""
    return hashlib.sha256(json.dumps(queries, sort_keys=True).encode()).hexdigest()


def load_manifest(path: Path | str | None = None) -> dict:
    """The register. `path` exists so a test or the generated fixture can stand
    in its own register rather than reaching into the real one — a synthetic
    run must never claim to have used the set this repository committed."""
    p = Path(path) if path else MANIFEST
    if not p.is_file():
        return {"rotate_after_weeks": ROTATE_AFTER_WEEKS, "sets": []}
    return json.loads(p.read_text())


def write_manifest(m: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(m, indent=2) + "\n")


def active(manifest: dict | None = None) -> dict | None:
    """The set currently in rotation, if any. Exactly one may be active: two
    would make "the held-out score" ambiguous in a published number."""
    m = manifest or load_manifest()
    live = [s for s in m.get("sets", []) if not s.get("retired_week")]
    if len(live) > 1:
        raise SystemExit(
            "manifest has more than one active held-out set "
            f"({', '.join(s['id'] for s in live)}) — retire one before running"
        )
    return live[0] if live else None


def entry(set_id: str, manifest: dict | None = None) -> dict | None:
    m = manifest or load_manifest()
    for s in m.get("sets", []):
        if s["id"] == set_id:
            return s
    return None


def local_path(set_id: str) -> Path:
    """Where an active set's text is looked for. `SB_HELDOUT_FILE` overrides,
    which is how CI hands the workflow a secret without a fixed path."""
    override = os.environ.get("SB_HELDOUT_FILE")
    return Path(override) if override else LOCAL_DIR / f"{set_id}.json"


def load_queries(set_id: str, path: Path | None = None,
                 manifest: dict | None = None) -> list[dict] | None:
    """The questions of a set, wherever they legitimately live.

    A retired set reads from the repository; an active one from outside it.
    Returns None when the active set's text is simply not on this machine,
    which is the ordinary case for anyone who is not the maintainer — and
    deliberately not an error, because the export has to run for them too.
    """
    e = entry(set_id, manifest)
    if e and e.get("file"):
        p = MANIFEST.parent / e["file"]
        if p.is_file():
            return json.loads(p.read_text())["queries"]
    p = path or local_path(set_id)
    if p.is_file():
        return json.loads(p.read_text())["queries"]
    return None


def verify(set_id: str, queries: list[dict], manifest: dict | None = None) -> None:
    """Fail loudly if the questions on disk are not the ones pre-registered.

    This is the check the whole design rests on. Without it the commitment is
    decorative: a set could be edited after a bad week and the manifest would
    still carry the hash of something else.
    """
    e = entry(set_id, manifest)
    if not e:
        raise SystemExit(f"held-out set {set_id!r} is not in {MANIFEST}")
    got = digest(queries)
    if got != e["sha256"]:
        raise SystemExit(
            f"held-out set {set_id!r} does not match its committed hash.\n"
            f"  committed: {e['sha256']}\n"
            f"  on disk:   {got}\n"
            "The questions were edited after they were pre-registered. Either "
            "restore them or register a new set — do not run this one."
        )


def shape(queries: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for q in queries:
        counts[q["category"]] = counts.get(q["category"], 0) + 1
    return dict(sorted(counts.items()))


def public_view(manifest: dict | None = None) -> dict:
    """What the export is allowed to say about the held-out sets.

    Everything here is already public or is a hash of something that isn't.
    There is no question text in this structure by construction — the entries
    it copies from never hold any while a set is active.
    """
    m = manifest or load_manifest()
    sets = []
    for s in m.get("sets", []):
        sets.append({
            "id": s["id"],
            "sha256": s["sha256"],
            "n_queries": s["n_queries"],
            "categories": s.get("categories", {}),
            "committed_at": s.get("committed_at"),
            "first_week": s.get("first_week"),
            "retired_week": s.get("retired_week"),
            "published": bool(s.get("file")),
        })
    return {
        "rotate_after_weeks": m.get("rotate_after_weeks", ROTATE_AFTER_WEEKS),
        "sets": sets,
        "active": (active(m) or {}).get("id"),
    }


# ---------------------------------------------------------------------- CLI

def cmd_status(args) -> int:
    m = load_manifest()
    a = active(m)
    print(f"manifest: {MANIFEST}")
    print(f"rotation: every {m.get('rotate_after_weeks', ROTATE_AFTER_WEEKS)} weeks\n")
    if not m.get("sets"):
        print("  no held-out set registered yet")
        return 0
    for s in m["sets"]:
        state = "retired " + s["retired_week"] if s.get("retired_week") else "ACTIVE"
        where = s.get("file") or str(local_path(s["id"]))
        have = "text present" if load_queries(s["id"]) is not None else "text not on this machine"
        print(f"  {s['id']:<20} {state:<18} n={s['n_queries']:<4} {have}")
        print(f"    sha256 {s['sha256']}")
        print(f"    {where}")
    if a:
        qs = load_queries(a["id"])
        if qs is not None:
            verify(a["id"], qs)
            print("\n  active set verified against its committed hash")
    return 0


def cmd_commit(args) -> int:
    """Pre-register a set. Writes the hash to git; leaves the text where it is."""
    path = Path(args.file)
    payload = json.loads(path.read_text())
    queries = payload["queries"]
    m = load_manifest()
    if active(m):
        raise SystemExit(
            f"{active(m)['id']} is still active — retire it before committing a new set"
        )
    if entry(args.id, m):
        raise SystemExit(f"{args.id!r} is already in the manifest")

    m.setdefault("sets", []).append({
        "id": args.id,
        "sha256": digest(queries),
        "n_queries": len(queries),
        "categories": shape(queries),
        "committed_at": args.date or date.today().isoformat(),
        "first_week": None,
        "retired_week": None,
        "file": None,
    })
    write_manifest(m)

    dest = local_path(args.id)
    if path.resolve() != dest.resolve():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(path.read_text())
        print(f"copied questions to {dest} (outside git)")
    print(f"registered {args.id}: {len(queries)} queries, sha256 {digest(queries)}")
    print(f"commit {MANIFEST.relative_to(ROOT)} now — before the set ever runs")
    return 0


def cmd_install(args) -> int:
    """Write the active set's questions from an environment variable.

    This exists so CI does not have to compute a filename in shell. The first
    version of the workflow step did, in a nested command substitution inside a
    quoted redirection, and quoting that correctly across YAML and bash is a
    worse problem than it looks — a step that silently writes an empty file
    produces a run with no held-out questions and no error, which is exactly
    the failure mode a check is supposed to prevent.

    Verifying here means a bad or truncated secret fails the workflow at the
    cheap step rather than after forty minutes of vendor calls.
    """
    a = active()
    if not a:
        raise SystemExit("no held-out set is registered — nothing to install")
    blob = os.environ.get(args.env, "")
    if not blob.strip():
        # Degrading to the public set is right for a fork, which has no secret
        # and should not have its CI broken by ours. It was wrong for the
        # scheduled run, and cost two weeks: 2026-W33 and W34 both published
        # `n_heldout_queries: 0` because this branch printed a line nobody read
        # and returned 0, so every downstream step succeeded and the week
        # looked healthy. (2026-W31 also carries 0, for a different reason —
        # it ran before ho-2026-08 was registered on 2026-08-04.) The secret
        # went in on 2026-08-17; --require is what makes its absence loud, at
        # the cheap step, before the run spends ~$3.40 of vendor money on a
        # week that cannot prove anything.
        if getattr(args, "require", False):
            raise SystemExit(
                f"{args.env} is empty or unset, and --require was given — "
                f"refusing to run the public set alone. Either the secret is "
                f"missing from this environment or it did not reach the step."
            )
        print(f"{args.env} is empty — the public set will run alone")
        return 0

    payload = json.loads(blob)
    queries = payload["queries"] if isinstance(payload, dict) else payload
    verify(a["id"], queries)

    dest = local_path(a["id"])
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({"queries": queries}, indent=1) + "\n")
    print(f"installed {a['id']}: {len(queries)} questions, hash verified, at {dest}")
    return 0


def cmd_retire(args) -> int:
    """Publish a set in full and take it out of rotation."""
    m = load_manifest()
    e = entry(args.id, m)
    if not e:
        raise SystemExit(f"{args.id!r} is not in the manifest")
    if e.get("retired_week"):
        raise SystemExit(f"{args.id!r} retired already, in {e['retired_week']}")

    queries = load_queries(args.id)
    if queries is None:
        raise SystemExit(
            f"cannot retire {args.id!r} without its questions — the point of "
            "retiring is publishing them, and they are not on this machine"
        )
    verify(args.id, queries)

    RETIRED_DIR.mkdir(parents=True, exist_ok=True)
    out = RETIRED_DIR / f"{args.id}.json"
    out.write_text(json.dumps({
        "set_id": args.id,
        "sha256": e["sha256"],
        "committed_at": e.get("committed_at"),
        "retired_week": args.week,
        "note": (
            "Held-out set, published in full on retirement. It was withheld "
            "while live and its hash was committed before it first ran; both "
            "are checkable against the manifest beside this file."
        ),
        "queries": queries,
    }, indent=2) + "\n")

    e["retired_week"] = args.week
    e["file"] = str(out.relative_to(MANIFEST.parent))
    write_manifest(m)
    print(f"published {len(queries)} questions to {out.relative_to(ROOT)}")
    print("the next set must be registered before the next run")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="what is registered, active and present")

    c = sub.add_parser("commit", help="pre-register a set before it runs")
    c.add_argument("--file", required=True, help="JSON file with a `queries` list")
    c.add_argument("--id", required=True, help="set id, e.g. ho-2026-08")
    c.add_argument("--date", default=None)

    i = sub.add_parser("install", help="write the active set's questions from the environment")
    i.add_argument("--env", default="SB_HELDOUT_JSON",
                   help="environment variable holding the set's JSON")
    i.add_argument("--require", action="store_true",
                   help="fail if the set is absent instead of degrading to the "
                        "public set alone (use in the scheduled run, not in forks)")

    r = sub.add_parser("retire", help="publish a set in full and rotate it out")
    r.add_argument("--id", required=True)
    r.add_argument("--week", required=True, help="ISO week it retired, e.g. 2026-W35")

    args = ap.parse_args()
    return {"status": cmd_status, "commit": cmd_commit,
            "install": cmd_install, "retire": cmd_retire}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())

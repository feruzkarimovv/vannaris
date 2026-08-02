#!/usr/bin/env bash
# Every gate, in one command. This is the definition of "did that change work?"
#
# It exists because an autonomous improvement loop needs a single answer it
# cannot argue with. A model asked whether it improved something will say yes;
# this script is the part that disagrees, so it has to be impossible to pass by
# accident. Two rules follow from that:
#
#   - CHECK_STRICT=1 is exported, so a gate whose dependencies are missing fails
#     instead of printing "skipping" and exiting 0. That failure mode is not
#     hypothetical: `npm install --no-save axe-core` once pruned jsdom, which
#     silently turned two green checks into two skipped ones.
#   - Every gate runs even after one fails, and the exit code is the count of
#     failures. Stopping at the first means fixing five things in five rounds.
#   - There are three outcomes, not two. A gate that could not run reports
#     SKIPPED and is named again in the summary, because "all gates passed" must
#     never be reachable by a run in which nothing was actually checked.
#
# Usage:  scripts/check-all.sh [--quick]
#   --quick skips the export, for iterating on the site alone.
set -uo pipefail
cd "$(dirname "$0")/.."

export CHECK_STRICT=1
PY=".venv/bin/python"
[ -x "$PY" ] || PY="python3"
QUICK=0
[ "${1:-}" = "--quick" ] && QUICK=1

# The summary's own arithmetic is part of the gate. `passed` counts every gate
# that reported ok, including the two written inline below rather than through
# run() — they printed ok without being counted, so the footer under-reported
# the number of checks by two. A gate whose summary does not match its own
# output is a gate nobody can quote.
failed=0
passed=0
skipped=0
skips=""

# Three states, not two. A check that could not run is NOT a check that passed —
# that conflation has already bitten this repo once, when a pruned jsdom turned
# two gates into no-ops that still exited 0. Skips are counted, named, and
# printed again in the summary, so "all gates passed" can never mean "nothing
# ran".
#
# The two skips that used to be routine — no database, no calibration set — are
# gone: both inputs are now generated (see make_fixture() below). `--quick` is
# the only remaining path that skips anything, and it is opt-in.
run() {
  local name="$1"; shift
  printf '\n\033[1m── %s\033[0m\n' "$name"
  if "$@"; then
    printf '\033[32m   ok\033[0m\n'
    passed=$((passed + 1))
  else
    printf '\033[31m   FAILED (%s)\033[0m\n' "$name"
    failed=$((failed + 1))
  fi
}

skip() {
  local name="$1" why="$2"
  printf '\n\033[1m── %s\033[0m\n' "$name"
  printf '\033[33m   SKIPPED — %s\033[0m\n' "$why"
  skipped=$((skipped + 1))
  skips="${skips}   · ${name}: ${why}\n"
}

# The two gates that used to skip here — the export and the labeller UI — need
# inputs the repository deliberately does not carry, because both derive from
# raw vendor content (docs/03). Rather than leave them unverifiable outside the
# one machine that holds a real database, their input is generated: a small,
# deterministic, unmistakably-synthetic database built into a temp directory and
# deleted on the way out. See tests/fixtures/README.md for how to tell it apart
# from real data at a glance, and tests/test_fixture_db.py for the assertions
# that keep it covering what it claims to cover.
#
# It never touches site/ — make_fixture_db.py refuses to write there at all —
# and it is only used when no real database exists. Where one does, the gate
# still runs against the real one.
FIXTURE=""
cleanup() { [ -n "$FIXTURE" ] && rm -rf "$FIXTURE"; }
trap cleanup EXIT

make_fixture() {
  [ -n "$FIXTURE" ] && return 0
  FIXTURE=$(mktemp -d "${TMPDIR:-/tmp}/vannaris-fixture.XXXXXX") || return 1
  $PY scripts/make_fixture_db.py --out "$FIXTURE" --quiet || return 1
}

export_fixture() {
  make_fixture || return 1
  $PY -m src.export --db "$FIXTURE/fixture.db" \
                    --queries "$FIXTURE/queries.json" \
                    --out "$FIXTURE/site"
}

labeller_fixture() {
  make_fixture || return 1
  # Drawn through `calibrate sample` rather than hand-built, so the gate
  # exercises the path that actually produces a labelling task. The set id is a
  # fresh uuid, so the directory is found rather than known.
  $PY -m src.calibrate --db "$FIXTURE/fixture.db" sample \
      --n 24 --out "$FIXTURE/calibration" >/dev/null || return 1
  local dir
  dir=$(find "$FIXTURE/calibration" -mindepth 1 -maxdepth 1 -type d | head -1)
  [ -n "$dir" ] || { echo "   fixture calibration set was not written"; return 1; }
  node scripts/check-labeller.mjs "$dir"
}

run "unit tests"        $PY -m unittest discover tests
# The export is the only thing allowed to turn the database into published
# numbers, so "does it still run clean" is a correctness gate, not a build step.
# The export needs a database and the database is gitignored, so this used to
# skip everywhere except the one machine holding a real one. It now falls back
# to the generated fixture, which covers strictly more of the export than a
# single real week does: rejected runs, a suppressed cell, a scheduled trigger.
if [ "$QUICK" = "1" ]; then
  skip "export" "--quick"
elif ls data/*.db >/dev/null 2>&1; then
  run "export" $PY -m src.export
else
  run "export (fixture)" export_fixture
fi
# What the pages are *made of*: landmarks, heading outline, chart mounts,
# table headers, controls, and the name of every data-bound slot, compared
# against a committed snapshot. check-site.mjs proves the figures a page has
# resolve; this proves the page still has them. Deleting a section, a chart or
# a sentence with a figure in it passes every other gate here.
run "site: structure"     node scripts/check-structure.mjs
run "site: data resolves" node scripts/check-site.mjs
run "site: quality"       node scripts/check-quality.mjs
# Same shape as the export gate. The real calibration/ directory is gitignored
# because the task shows the labeller the vendors' actual retrieved content, so
# the fixture stands in for it and the real one is left untouched.
if ls calibration/*/label.html >/dev/null 2>&1; then
  run "labeller UI"           node scripts/check-labeller.mjs
else
  run "labeller UI (fixture)" labeller_fixture
fi

# The claims this project is not allowed to make. Cheap to check, catastrophic
# to get wrong, and exactly the kind of thing a loop optimising for a nicer
# landing page would write without noticing (CLAUDE.md).
printf '\n\033[1m── forbidden claims\033[0m\n'
claims=0
if grep -rniE "continuously (run|updated)|runs (weekly|continuously)|updated weekly" \
     site/*.html README.md 2>/dev/null | grep -viE "not |until |once |when |has not"; then
  echo "   ^ cadence claimed before the data supports it"
  claims=1
fi
# Checked against the published data, not the prose. The methodology page names
# Tavily and Brave precisely to explain why they are absent, which is the
# honest thing to do — an earlier version of this check flagged that sentence
# and would have taught whoever hit it to delete the explanation. What actually
# matters is that no vendor outside the cleared set has a published score.
# Moved out of this file into scripts/check_vendors.py, unchanged in what it
# asserts. It lived here as a heredoc, which meant it ran only where a person
# ran this gate by hand — and the weekly workflow, which commits site/data to
# the default branch every Monday, ran nothing like it. The one automated path
# that publishes was the one path that never checked what it published. Both
# now call the same code, and it has tests.
if ! $PY scripts/check_vendors.py site/data/bundle.js; then
  claims=1
fi
if [ "$claims" = "0" ]; then printf '\033[32m   ok\033[0m\n'; passed=$((passed + 1)); else
  printf '\033[31m   FAILED (forbidden claims)\033[0m\n'; failed=$((failed + 1)); fi

# Committed labels are scores and analysis, never retrieved content. The task a
# labeller sees necessarily shows vendor titles, URLs and snippets, and the risk
# is that a note quotes one back into a file that is in git.
printf '\n\033[1m── labels carry no vendor content\033[0m\n'
if [ -d labels ] && ls labels/*.json >/dev/null 2>&1; then
  if $PY - <<'EOF'
import json, pathlib, re, sys
bad = []
for f in pathlib.Path("labels").glob("*.json"):
    for l in json.loads(f.read_text()).get("labels", []):
        n = l.get("note") or ""
        if re.search(r"https?://", n):
            bad.append(f"{f.name}: note contains a URL")
        for k in ("title", "url", "snippet", "results", "answer"):
            if k in l:
                bad.append(f"{f.name}: label carries a {k!r} field")
for b in sorted(set(bad)):
    print("  " + b)
sys.exit(1 if bad else 0)
EOF
  then printf '\033[32m   ok\033[0m\n'; passed=$((passed + 1))
  else printf '\033[31m   FAILED (labels carry vendor content)\033[0m\n'; failed=$((failed + 1)); fi
else
  skip "labels" "no labels/ exported yet"
fi

# Secrets must never reach a commit. The history was clean when this was
# written; this keeps it that way without anyone remembering to look.
printf '\n\033[1m── no secrets staged\033[0m\n'
if git diff --cached -U0 2>/dev/null | grep -inE "sk-[a-zA-Z0-9]{16,}|api[_-]?key[\"' ]*[:=][\"' ]*[a-zA-Z0-9]{16,}" \
     | grep -viE "os\.environ|getenv|secrets\.|YOUR_|example"; then
  printf '\033[31m   FAILED — key-shaped string in the staged diff\033[0m\n'
  failed=$((failed + 1))
else
  printf '\033[32m   ok\033[0m\n'
  passed=$((passed + 1))
fi

printf '\n'
if [ "$skipped" != "0" ]; then
  printf '\033[33m%d gate(s) SKIPPED — these verified nothing:\033[0m\n' "$skipped"
  printf "$skips"
fi
if [ "$failed" = "0" ]; then
  printf '\033[32m✓ %d gate(s) passed\033[0m' "$passed"
  [ "$skipped" = "0" ] || printf '\033[33m, %d skipped\033[0m' "$skipped"
  printf '\n'
else
  printf '\033[31m✗ %d gate(s) failed\033[0m, %d passed, %d skipped\n' "$failed" "$passed" "$skipped"
fi
exit "$failed"

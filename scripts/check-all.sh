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

failed=0
passed=0
skipped=0
skips=""

# Three states, not two. A check that could not run is NOT a check that passed —
# that conflation has already bitten this repo once, when a pruned jsdom turned
# two gates into no-ops that still exited 0. Skips are counted, named, and
# printed again in the summary, so "all gates passed" can never mean "nothing
# ran". Some skips are legitimate: a fresh checkout has no database and no
# calibration set, because both are deliberately not in git.
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

run "unit tests"        $PY -m unittest discover tests
# The export is the only thing allowed to turn the database into published
# numbers, so "does it still run clean" is a correctness gate, not a build step.
# The export needs a database, and the database is gitignored because it holds
# raw vendor payloads — so a fresh checkout legitimately cannot run this. That
# is a skip, not a pass and not a failure.
if [ "$QUICK" = "1" ]; then
  skip "export" "--quick"
elif ! ls data/*.db >/dev/null 2>&1; then
  skip "export" "no database in data/ — copy one over to check the export here"
else
  run "export" $PY -m src.export
fi
run "site: data resolves" node scripts/check-site.mjs
run "site: quality"       node scripts/check-quality.mjs
if ls calibration/*/label.html >/dev/null 2>&1; then
  run "labeller UI"       node scripts/check-labeller.mjs
else
  skip "labeller UI" "no calibration set drawn — python -m src.calibrate sample"
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
if [ -f site/data/bundle.js ]; then
  stray=$($PY - <<'EOF'
import json, pathlib, re
cleared = {"exa", "perplexity", "youcom", "serper", "linkup"}
raw = pathlib.Path("site/data/bundle.js").read_text()
data = json.loads(raw.split("window.SB_DATA = ", 1)[1].rsplit(";", 1)[0])
ids = {v["id"] for v in data.get("vendors", [])}
for wk in data.get("all_weeks", {}).values():
    ids |= {c.get("vendor") for c in wk.get("cells", []) if c.get("vendor")}
print(",".join(sorted(ids - cleared)))
EOF
)
  if [ -n "$stray" ]; then
    echo "   vendor(s) outside the ToS-cleared set carry published scores: $stray (docs/03)"
    claims=1
  fi
fi
if [ "$claims" = "0" ]; then printf '\033[32m   ok\033[0m\n'; else
  printf '\033[31m   FAILED (forbidden claims)\033[0m\n'; failed=$((failed + 1)); fi

# Secrets must never reach a commit. The history was clean when this was
# written; this keeps it that way without anyone remembering to look.
printf '\n\033[1m── no secrets staged\033[0m\n'
if git diff --cached -U0 2>/dev/null | grep -inE "sk-[a-zA-Z0-9]{16,}|api[_-]?key[\"' ]*[:=][\"' ]*[a-zA-Z0-9]{16,}" \
     | grep -viE "os\.environ|getenv|secrets\.|YOUR_|example"; then
  printf '\033[31m   FAILED — key-shaped string in the staged diff\033[0m\n'
  failed=$((failed + 1))
else
  printf '\033[32m   ok\033[0m\n'
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

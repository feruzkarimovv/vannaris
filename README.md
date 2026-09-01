# Vannaris

Independent benchmark of the web-search APIs that AI agents and RAG pipelines actually call.

Same queries, five vendors, scored by a three-lab LLM-judge ensemble (Anthropic, OpenAI, Google). Methodology, per-judge scores, and the gaps in the data are published, including the parts that make the ranking look weaker.

**Live:** [vannaris.com](https://vannaris.com) · [results](https://vannaris.com/results.html) · [methodology](https://vannaris.com/methodology.html) · [data, CC BY 4.0](https://vannaris.com/data.html)

## Latest published run: `2026-W34` (2026-08-17, scheduled)

| | |
|---|---|
| Queries | 150, six categories |
| Vendors | Exa, Perplexity, Serper, You.com, Linkup |
| Judges | 3 families; published score is the median of a complete ensemble |
| Judgements | 2,238 (746 / 750 responses fully scored, 99.5%) |
| Vendor spend | $3.36 |

Headline findings. Recompute them from the export; do not take this file on trust.

- **23.3× billed cost spread** (Serper vs Exa). Like-for-like list prices are about **7×**.
- Several quality gaps are not distinguishable under paired tests. "Route to the best vendor per category" is not free information.
- Judge families disagree on the same responses. Google's judge alone ranks Perplexity first; the ensemble ranks Exa first. Absolute scores do not survive a judge swap.

If this file and [`site/data/latest.json`](site/data/latest.json) disagree, the export is right.

## What a reviewer should see

Not a chatbot, not a wrapper around one vendor API, not a leaderboard screenshot.

- Cross-model evaluation harness in Python
- Authored 150-query set (not copied from a restricted academic dump)
- Paired significance tests and bootstrap CIs on vendor gaps
- Public export is derived scores, latency, and cost only. Raw vendor pages are not in git, on purpose
- Site figures are generated from the export, not typed in

## Stack

Python · Anthropic / OpenAI / Google judge APIs · vendor adapters · paired tests · bootstrap CIs · static site generated from the export

## Reproduce the numbers (no API keys)

Two CSVs and a few lines of Python rebuild the cost-versus-quality table. Files live in [`site/export/`](site/export/).

```python
import csv, statistics
from collections import defaultdict

panels = defaultdict(list)
for r in csv.DictReader(open("judge-scores.csv")):
    panels[(r["query_id"], r["vendor"], r["category"])].append(float(r["overall"]))

cells = defaultdict(list)
for (qid, vendor, category), scores in panels.items():
    if len(scores) == 3:
        cells[(vendor, category)].append(statistics.median(scores))

means = {k: statistics.mean(v) for k, v in cells.items()}
best = {c: max(s for (v, c2), s in means.items() if c2 == c) for _, c in means}

for (vendor, category), score in sorted(means.items()):
    print(f"{vendor:<11}{category:<16}{score:5.2f}  {100 * score / best[category]:5.1f}% of best")
```

## Run a full evaluation (needs keys)

Five vendor APIs and three judge models.

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python scripts/check_keys.py
.venv/bin/python -m src.runner --limit 5
.venv/bin/python -m src.runner --queries src/queries/full-v1.json
.venv/bin/python -m src.export
```

`--limit` runs are smoke tests. The exporter will not publish a run that is too thin to be a real week.

## Layout

```
src/runner.py              fetch, judge, aggregate
src/export.py              only code allowed to turn the DB into published numbers
src/vendors/               one adapter per API
src/judge/ensemble.py      three-model ensemble, rubric, pins
src/queries/full-v1.json   the 150-query set
site/                      public site; data/ and export/ are generated
.github/workflows/weekly.yml
```

The database is not committed. It holds raw vendor responses.

## Licence

- Data: [CC BY 4.0](LICENSE-DATA)
- Code: [MIT](LICENSE)

Cite the run date, not just the project. These numbers are a snapshot.

## Status

The public face is [vannaris.com](https://vannaris.com). This README is a dated snapshot of run `2026-W34`. Do not describe the benchmark as continuously weekly unless `track_record` in the export says so.

Historical research notes still say "SearchBench" in `docs/` and `applications/`. That is the old working name, left as a record on purpose.

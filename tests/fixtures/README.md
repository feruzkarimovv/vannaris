# Fixtures — everything here is synthetic

Nothing in this directory is a measurement. No vendor was called, no judge was
called, no money was spent, and no number below or produced from here describes
how any real search API performs. If you find one of these values quoted
anywhere outside a test, that is a bug worth stopping for.

## Why there is no database file here

`scripts/check-all.sh` runs two gates that need inputs the repository
deliberately does not carry: the export gate needs a database, and the labeller
gate needs a drawn calibration set. Both are gitignored on purpose — the
database holds raw vendor payloads and the calibration task shows the labeller
the vendors' actual retrieved content, and `docs/03` is why neither is
republished. So on a fresh checkout, on this project's VPS, and on any
contributor's laptop, both gates reported SKIPPED. A skipped gate verified
nothing.

The fix is to generate the input rather than ship it. `scripts/make_fixture_db.py`
builds a small synthetic database deterministically, so the fixture is
reproducible from source instead of stored as a binary blob nobody reviews.
`AUTONOMY.md` also forbids committing `*.db` outright, which settles it.

Run it yourself:

    python scripts/make_fixture_db.py --out /tmp/fx
    python -m src.export --db /tmp/fx/fixture.db --queries /tmp/fx/queries.json \
                         --out /tmp/fx/site

`check-all.sh` does exactly this into a temporary directory that it deletes on
exit, and only when `data/*.db` is absent. Where a real database exists — CI,
and the founder's machine — the gate still runs against the real one.

## How you can tell it apart from real data at a glance

Every one of these is load-bearing, not decoration:

| Signal | Real data | Fixture |
| --- | --- | --- |
| Vendor ids | `exa`, `serper`, `linkup`, `youcom`, `perplexity` | `fixture_alpha`, `fixture_bravo`, `fixture_delta` |
| Weeks | `2026-W__` | `2099-W01`, `2099-W02` |
| Query text | a real question | `FIXTURE QUERY fx-… — synthetic placeholder` |
| Result URLs | real hosts | `example.invalid` (RFC 2606; cannot resolve) |
| Run ids | random hex | `fixrun-2099w01-full` and friends |
| `runs.notes` | usually empty | `SYNTHETIC FIXTURE … Not a measurement.` |

One thing that is *not* fake, and should not surprise you: the exported
`bundle.vendors` list still carries the five real vendor ids, because
`src/export.py` reads it from `REGISTRY` rather than from the data. In a fixture
export those five appear with no scores attached to them at all.

## What the fixture is built to exercise

The point of a fixture is coverage the real data does not give you. One real
week contains one publishable run, no rejected candidates, no scheduled
trigger, and no suppressed cell, so most of the export's defensive logic has
never run outside production. The fixture covers:

- three vendors across all six taxonomy categories;
- complete and incomplete judge ensembles, plus vendor errors;
- one `(vendor, category)` cell pushed under `MIN_CELL_COVERAGE`, so the
  suppression path runs and publishes `null` with its coverage stated;
- two runs that fail canonical selection, for the two different reasons it can
  fail — too few queries per category, and too few complete ensembles;
- two published weeks, so the history merge and track-record arithmetic run;
- a `scheduled` trigger, so `track_record.schedule_started` is exercised as
  true somewhere other than production.

`tests/test_fixture_db.py` asserts each of those is still true. Without it, a
future edit could quietly shrink what the fixture covers while the export gate
kept reporting ok — the gate would still be green and would be checking less.

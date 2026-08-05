-- Vannaris storage schema.
--
-- CLAUDE.md requires three separated layers from the start, because they have
-- different publication rules:
--
--   raw_responses    vendor payloads. Stored for reproducibility, NEVER exported
--                    publicly — docs/03 recommends publishing derived scores
--                    rather than republishing vendor content.
--   judge_scores     one row per (response, judge). Individual scores are kept
--                    so a disputed result can be inspected down to which judge
--                    said what. This layer IS public.
--   weekly_scores    aggregated per (vendor, category, week). Powers the
--                    dashboard and, later, the router's quality signal.
--
-- The public export is judge_scores + weekly_scores + run metadata. That is
-- what "raw data export" means for this project: raw *scoring* data, not raw
-- vendor content.

CREATE TABLE IF NOT EXISTS runs (
    id              TEXT PRIMARY KEY,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    week            TEXT NOT NULL,          -- ISO week, e.g. '2026-W32'
    query_set_hash  TEXT NOT NULL,          -- pins exactly which queries ran
    -- 'manual' | 'scheduled'. CLAUDE.md forbids describing the benchmark as
    -- continuously run before it is; this column is what makes that checkable.
    -- The site's cadence copy is derived from it, so no page can assert a
    -- schedule that never fired.
    trigger         TEXT NOT NULL DEFAULT 'manual',
    -- Which withheld set ran alongside the public one, by id (src/heldout.py).
    -- The set's hash is pre-registered in git before it runs, so this column
    -- makes "that run included that set" checkable rather than asserted.
    heldout_set     TEXT,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS queries (
    id          TEXT PRIMARY KEY,
    category    TEXT NOT NULL,              -- one of the six taxonomy buckets
    text        TEXT NOT NULL,
    source      TEXT,                       -- dataset provenance, or 'authored'
    gold_answer TEXT,
    gold_urls   TEXT,                       -- JSON array
    -- Freshness queries rotate every cycle so vendors cannot overfit to a
    -- static set of "breaking news" questions (docs/04, refresh cadence).
    rotates     INTEGER NOT NULL DEFAULT 0,
    -- 1 for a question from the withheld set (src/heldout.py). Published cells
    -- are computed from held_out = 0 only, so the public table remains
    -- reproducible from the published questions; the held-out rows are
    -- published as scores with their text withheld until the set retires, and
    -- reported as a public-versus-held-out gap per vendor.
    held_out    INTEGER NOT NULL DEFAULT 0
);

-- ---------------------------------------------------------------- raw layer
CREATE TABLE IF NOT EXISTS raw_responses (
    id            TEXT PRIMARY KEY,
    run_id        TEXT NOT NULL REFERENCES runs(id),
    query_id      TEXT NOT NULL REFERENCES queries(id),
    vendor        TEXT NOT NULL,
    response_mode TEXT NOT NULL,            -- ranked_results | synthesized_answer | both
    answer        TEXT,
    citations     TEXT,                     -- JSON array of URLs
    results       TEXT,                     -- JSON array of {url,rank,title,snippet}
    latency_ms    INTEGER,
    cost_usd      REAL,
    -- 'reported' when the vendor returned a billed figure on the call itself,
    -- 'estimated' when it is derived from published pricing. The headline cost
    -- spread depends on which is which, so it is recorded rather than assumed.
    cost_source   TEXT NOT NULL DEFAULT 'estimated',
    error         TEXT,
    raw_payload   TEXT,                     -- NOT EXPORTED
    created_at    TEXT NOT NULL,
    UNIQUE (run_id, query_id, vendor)
);

-- -------------------------------------------------------------- judge layer
CREATE TABLE IF NOT EXISTS judge_scores (
    id                TEXT PRIMARY KEY,
    response_id       TEXT NOT NULL REFERENCES raw_responses(id),
    judge_model       TEXT NOT NULL,
    judge_family      TEXT NOT NULL,        -- anthropic | openai | google
    relevance         REAL,
    freshness         REAL,
    citation_quality  REAL,
    overall           REAL,
    rationale         TEXT,
    -- Verbosity-bias mitigation: response length is recorded and published
    -- alongside the score so outliers are visible (docs/04).
    scored_chars      INTEGER,
    prompt_tokens     INTEGER,
    output_tokens     INTEGER,
    -- What the provider actually served. Two of the three pins are aliases the
    -- provider can repoint without notice, and a silent swap would move every
    -- score without moving anything about the vendors.
    judge_model_returned TEXT,
    created_at        TEXT NOT NULL,
    UNIQUE (response_id, judge_model)
);

-- ---------------------------------------------------------- aggregate layer
--
-- One published cell per (week, vendor, category). That uniqueness is the
-- point — but it also means an INSERT OR REPLACE from a two-query smoke test
-- will silently overwrite a 150-query result and leave behind a cell that
-- looks exactly like a real one. It did, once. Two guards now exist:
-- `run_id` records which run a cell came from, and runner.aggregate() refuses
-- to overwrite a cell built from more queries than the one being written.
-- The published site does not read this table at all: src/export.py recomputes
-- from judge_scores for one explicitly chosen canonical run per week.
CREATE TABLE IF NOT EXISTS weekly_scores (
    id            TEXT PRIMARY KEY,
    week          TEXT NOT NULL,
    run_id        TEXT REFERENCES runs(id),
    vendor        TEXT NOT NULL,
    category      TEXT NOT NULL,
    -- Median across the cross-family ensemble, not mean: one outlier judge
    -- should not move a published number.
    median_score  REAL NOT NULL,
    n_queries     INTEGER NOT NULL,
    n_errors      INTEGER NOT NULL DEFAULT 0,
    p50_latency_ms INTEGER,
    total_cost_usd REAL,
    -- Spread between this vendor and the best vendor in the same category.
    -- This is the number that decides whether quality-based routing has any
    -- economic value at all; surfaced explicitly rather than left implicit.
    delta_from_best REAL,
    created_at    TEXT NOT NULL,
    UNIQUE (week, vendor, category)
);

-- -------------------------------------------------------- calibration layer
--
-- docs/04 is explicit that a judge measured against nothing is an unexamined
-- black box, and that the fix is 100-200 expert-labelled examples with a
-- four-phase loop: baseline, error analysis, targeted refinement, re-measure.
-- These tables are that loop's memory.
--
-- Human labels are scores, not vendor content, so this layer is publishable on
-- the same terms as judge_scores. What is NOT publishable is the labelling task
-- itself: it necessarily shows the labeller the vendor's actual results, so it
-- is written outside the repository (see src/calibrate.py).
CREATE TABLE IF NOT EXISTS calibration_sets (
    id            TEXT PRIMARY KEY,
    run_id        TEXT NOT NULL REFERENCES runs(id),
    created_at    TEXT NOT NULL,
    -- Everything needed to redraw this exact sample. A gold set nobody can
    -- reproduce is an assertion about the judge, not evidence about it.
    seed          INTEGER NOT NULL,
    n_target      INTEGER NOT NULL,
    disagreement_share REAL NOT NULL,
    -- What the labeller could and could not see. Published alongside any
    -- agreement figure, because an unblinded label is a different measurement.
    blinding      TEXT NOT NULL,
    notes         TEXT
);

CREATE TABLE IF NOT EXISTS calibration_items (
    set_id        TEXT NOT NULL REFERENCES calibration_sets(id),
    response_id   TEXT NOT NULL REFERENCES raw_responses(id),
    -- 'random' or 'disagreement'. Load-bearing: the two strata answer different
    -- questions and must never be pooled into one agreement number. The random
    -- stratum estimates how well the judge tracks a human in general; the
    -- disagreement stratum is deliberately drawn from the judge's worst moments
    -- and would drag any headline figure down while measuring nothing
    -- representative.
    stratum       TEXT NOT NULL,
    position      INTEGER NOT NULL,
    PRIMARY KEY (set_id, response_id)
);

CREATE TABLE IF NOT EXISTS human_labels (
    id            TEXT PRIMARY KEY,
    set_id        TEXT NOT NULL REFERENCES calibration_sets(id),
    response_id   TEXT NOT NULL REFERENCES raw_responses(id),
    labeller      TEXT NOT NULL,
    relevance         REAL,
    freshness         REAL,
    citation_quality  REAL,
    overall           REAL NOT NULL,
    note          TEXT,
    -- Time on task. A gold set produced at four seconds an item is not a gold
    -- set, and the only way to know that afterwards is to have recorded it.
    seconds       INTEGER,
    labelled_at   TEXT NOT NULL,
    UNIQUE (set_id, response_id, labeller)
);

CREATE INDEX IF NOT EXISTS idx_raw_run     ON raw_responses(run_id);
CREATE INDEX IF NOT EXISTS idx_judge_resp  ON judge_scores(response_id);
CREATE INDEX IF NOT EXISTS idx_weekly_week ON weekly_scores(week);

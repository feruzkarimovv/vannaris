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
    rotates     INTEGER NOT NULL DEFAULT 0
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

CREATE INDEX IF NOT EXISTS idx_raw_run     ON raw_responses(run_id);
CREATE INDEX IF NOT EXISTS idx_judge_resp  ON judge_scores(response_id);
CREATE INDEX IF NOT EXISTS idx_weekly_week ON weekly_scores(week);

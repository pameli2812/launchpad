-- Launchpad — initial schema
-- Run once against your local postgres:
--   psql -U <user> -d <dbname> -f migrations.sql

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── resumes ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS resumes (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    filename        TEXT        NOT NULL UNIQUE,   -- on-disk name (may include timestamp suffix)
    original_name   TEXT        NOT NULL,           -- original upload filename
    size_bytes      BIGINT      NOT NULL,
    content_hash    TEXT        NOT NULL,           -- sha256[:12] for change detection
    extracted_text  TEXT,                           -- full text extracted at upload time
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── goal_sets ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS goal_sets (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT        NOT NULL,
    is_active   BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Only one goal_set can be active at a time
CREATE UNIQUE INDEX IF NOT EXISTS goal_sets_one_active
    ON goal_sets (is_active)
    WHERE is_active = TRUE;

-- ── goals ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS goals (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    goal_set_id   UUID        NOT NULL REFERENCES goal_sets(id) ON DELETE CASCADE,
    label         TEXT        NOT NULL,
    description   TEXT        NOT NULL DEFAULT '',
    confidence    TEXT        NOT NULL DEFAULT 'high' CHECK (confidence IN ('high','medium','low')),
    auto_inferred BOOLEAN     NOT NULL DEFAULT FALSE,
    sort_order    INT         NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS goals_goal_set_id ON goals(goal_set_id);

-- ── analyses ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analyses (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    jd_id           TEXT        NOT NULL UNIQUE,    -- 8-char uuid prefix kept for API compat
    resume_id       UUID        NOT NULL REFERENCES resumes(id) ON DELETE RESTRICT,
    goal_set_id     UUID        NOT NULL REFERENCES goal_sets(id) ON DELETE RESTRICT,
    goal_set_name   TEXT        NOT NULL,
    goal_set_snapshot JSONB     NOT NULL DEFAULT '[]',
    jd_text         TEXT,
    jd_url          TEXT,
    jd_json         JSONB,
    scorecard       JSONB       NOT NULL DEFAULT '{}',
    overall_fit     FLOAT,
    verdict         TEXT        CHECK (verdict IN ('apply','borderline','skip')),
    jd_title        TEXT,
    company         TEXT,
    status          TEXT        NOT NULL DEFAULT 'pending',
    changes_generated BOOLEAN   NOT NULL DEFAULT FALSE,
    analyzed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS analyses_resume_id    ON analyses(resume_id);
CREATE INDEX IF NOT EXISTS analyses_goal_set_id  ON analyses(goal_set_id);
CREATE INDEX IF NOT EXISTS analyses_analyzed_at  ON analyses(analyzed_at DESC);

-- ── suggestions ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS suggestions (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id   UUID        NOT NULL UNIQUE REFERENCES analyses(id) ON DELETE CASCADE,
    paraphrasing  JSONB       NOT NULL DEFAULT '[]',
    missing       JSONB       NOT NULL DEFAULT '[]',
    remove        JSONB       NOT NULL DEFAULT '[]',
    polish        JSONB       NOT NULL DEFAULT '[]',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Launchpad — Company Suggestion (Resume Builder module)
-- Run after migrations_3.sql.
--   psql -U postgres -d launchpad -f migrations_4.sql
--
-- One row per (user, resume). Re-generating overwrites — same pattern as
-- resume_reviews.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS company_suggestions (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    resume_id   UUID        NOT NULL UNIQUE REFERENCES resumes(id) ON DELETE CASCADE,
    -- Array of company objects (name, industry, size, location, remote_policy,
    -- website, description, why_fit, focus_areas, hiring_likelihood, match_score).
    -- Stored as JSONB so the schema can evolve without an ALTER TABLE.
    companies   JSONB       NOT NULL DEFAULT '[]',
    -- User-supplied focus when generating — preferences like "remote only",
    -- "Series A startups", "EU companies" etc. Helps the LLM target results.
    user_prompt TEXT,
    -- Full LLM payload so we can backfill new fields later without re-paying.
    raw         JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS company_suggestions_user_id ON company_suggestions(user_id);

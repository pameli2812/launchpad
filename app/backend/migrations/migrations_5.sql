-- Launchpad — outreach export flag
-- Run after migrations_4.sql.
--   psql -U postgres -d launchpad -f migrations_5.sql

ALTER TABLE analyses
ADD COLUMN IF NOT EXISTS exported BOOLEAN DEFAULT false;

CREATE INDEX IF NOT EXISTS analyses_exported_idx
    ON analyses (exported, verdict, analyzed_at DESC);

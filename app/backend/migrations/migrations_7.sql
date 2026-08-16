-- migrations_7.sql
-- Outreach enrichment: add job_summary, my_relevance (JSONB), and jd_link (TEXT) to analyses

ALTER TABLE analyses ADD COLUMN IF NOT EXISTS job_summary JSONB DEFAULT NULL;
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS my_relevance JSONB DEFAULT NULL;
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS jd_link TEXT DEFAULT NULL;

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_analyses_job_summary ON analyses USING GIN (job_summary);
CREATE INDEX IF NOT EXISTS idx_analyses_my_relevance ON analyses USING GIN (my_relevance);

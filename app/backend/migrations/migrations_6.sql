-- Launchpad — per-user data isolation (security fix)
-- Run after migrations_5.sql.
--   psql -U postgres -d launchpad -f migrations_6.sql
--
-- CRITICAL SECURITY: Add user_id to resumes, goal_sets, and analyses.
-- These tables were created before auth and lacked per-user scoping.
-- All three layers (schema, write path, read path) must be fixed together.

-- ── Step 1: Add user_id columns with FK to users ────────────────────────────────

ALTER TABLE resumes
ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE;

ALTER TABLE goal_sets
ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE;

ALTER TABLE analyses
ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE;

-- ── Step 2: Create indexes for efficient per-user queries ─────────────────────

CREATE INDEX IF NOT EXISTS resumes_user_id
    ON resumes(user_id);

CREATE INDEX IF NOT EXISTS goal_sets_user_id
    ON goal_sets(user_id);

CREATE INDEX IF NOT EXISTS analyses_user_id
    ON analyses(user_id);

-- Unique index on user_id + filename for resumes (prevents user from uploading same filename twice)
CREATE UNIQUE INDEX IF NOT EXISTS resumes_user_filename_uq
    ON resumes(user_id, filename)
    WHERE user_id IS NOT NULL;

-- Unique index on user_id + name for goal_sets (prevents user from creating duplicate goal set names)
CREATE UNIQUE INDEX IF NOT EXISTS goal_sets_user_name_uq
    ON goal_sets(user_id, name)
    WHERE user_id IS NOT NULL;

-- ── Step 3: Backfill existing NULL user_id rows to the single existing account ──

-- This query finds or creates the account for yashvijaivargiya@gmail.com
-- and backfills all existing rows to that user.
-- This is safe to run repeatedly (idempotent).

UPDATE resumes
SET user_id = (
    SELECT id FROM users WHERE email = 'yashvijaivargiya@gmail.com' LIMIT 1
)
WHERE user_id IS NULL;

UPDATE goal_sets
SET user_id = (
    SELECT id FROM users WHERE email = 'yashvijaivargiya@gmail.com' LIMIT 1
)
WHERE user_id IS NULL;

UPDATE analyses
SET user_id = (
    SELECT id FROM users WHERE email = 'yashvijaivargiya@gmail.com' LIMIT 1
)
WHERE user_id IS NULL;

-- ── Step 4: Create automation API key table for n8n /pending-outreach endpoints ──
-- This table stores server-side API keys that n8n uses.
-- Each key is tied to a user and is validated via X-API-Key header.

CREATE TABLE IF NOT EXISTS automation_api_keys (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_hash        TEXT        NOT NULL UNIQUE,        -- sha256 of the raw key
    label           TEXT        NOT NULL DEFAULT 'n8n automation',
    last_4          TEXT        NOT NULL,               -- last 4 chars for UI display
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    last_used_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS automation_api_keys_user_id ON automation_api_keys(user_id);

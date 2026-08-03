-- Launchpad — Settings / extension imports / resume reviews
-- Run after migrations_2.sql.
--   psql -U postgres -d launchpad -f migrations_3.sql
--
-- All NEW tables in this migration are scoped per-user from day one
-- (user_id NOT NULL FK to users). Existing tables (resumes / goal_sets /
-- analyses) still have no user_id — that's a deferred follow-up migration.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── api_keys ──────────────────────────────────────────────────────────────────
-- Per-user LLM provider API keys. The plaintext key is encrypted with Fernet
-- (symmetric, app-managed via ENCRYPTION_KEY env var) before insert. `last_4`
-- is stored separately so we can show "...XXXX" in the UI without ever
-- decrypting. One row per (user, provider).

CREATE TABLE IF NOT EXISTS api_keys (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider     TEXT        NOT NULL CHECK (provider IN ('anthropic','openai','gemini')),
    encrypted    TEXT        NOT NULL,        -- Fernet ciphertext
    model        TEXT,                         -- optional model override
    last_4       TEXT        NOT NULL,         -- last 4 chars for UI display
    is_active    BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, provider)
);

CREATE INDEX IF NOT EXISTS api_keys_user_id ON api_keys(user_id);

-- ── extension_tokens ──────────────────────────────────────────────────────────
-- Long-lived opaque tokens the browser extension uses to authenticate against
-- /api/imports. Each user can have multiple (label them "Personal laptop",
-- "Work machine" etc.). We store only the sha256 hash; the raw token is
-- returned to the user exactly once at creation time.

CREATE TABLE IF NOT EXISTS extension_tokens (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash   TEXT        NOT NULL UNIQUE,  -- sha256 of the raw token
    label        TEXT        NOT NULL DEFAULT 'Browser extension',
    last_4       TEXT        NOT NULL,
    last_used_at TIMESTAMPTZ,
    revoked      BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS extension_tokens_user_id ON extension_tokens(user_id);

-- ── imports ───────────────────────────────────────────────────────────────────
-- Pending JD imports from the browser extension. The Analyze page polls
-- /api/imports?status=pending and surfaces these inline; on consume they
-- transition to 'consumed' (or 'dismissed' if the user discards them).

CREATE TABLE IF NOT EXISTS imports (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source        TEXT        NOT NULL DEFAULT 'extension',
    url           TEXT,
    host          TEXT,
    job_id        TEXT,                         -- extracted from URL when possible
    jd_title      TEXT,                         -- best-effort, may be null
    jd_text       TEXT        NOT NULL,
    status        TEXT        NOT NULL DEFAULT 'pending'
                              CHECK (status IN ('pending','consumed','dismissed')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    consumed_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS imports_user_status
    ON imports(user_id, status, created_at DESC);

-- ── resume_reviews ────────────────────────────────────────────────────────────
-- LLM-extracted structured profile from a resume. One row per (user, resume).
-- JSON arrays for repeated entities (skills/experience/education) keep schema
-- flexible; raw holds the full LLM payload so we can backfill new fields later
-- without re-calling the model.

CREATE TABLE IF NOT EXISTS resume_reviews (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    resume_id       UUID        NOT NULL UNIQUE REFERENCES resumes(id) ON DELETE CASCADE,
    full_name       TEXT,
    email           TEXT,
    phone           TEXT,
    location        TEXT,
    linkedin        TEXT,
    headline        TEXT,                       -- one-line role/title summary
    summary         TEXT,
    skills          JSONB       NOT NULL DEFAULT '[]',
    experience      JSONB       NOT NULL DEFAULT '[]',
    education       JSONB       NOT NULL DEFAULT '[]',
    certifications  JSONB       NOT NULL DEFAULT '[]',
    projects        JSONB       NOT NULL DEFAULT '[]',
    raw             JSONB,                       -- full LLM response
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS resume_reviews_user_id ON resume_reviews(user_id);

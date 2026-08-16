"""
database.py — async Postgres connection pool + typed query helpers.
Uses psycopg3 (psycopg) API — NOT psycopg2.
Key difference: no .fetchrow()/.fetch() — use cursor.fetchone()/fetchall() instead.
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)

_pool: AsyncConnectionPool | None = None


async def init_pool() -> None:
    global _pool
    url = os.getenv("DATABASE_URL", "postgresql://postgres:root@localhost:5432/launchpad")
    print(f"[DB] Connecting to: {url}")
    _pool = AsyncConnectionPool(
        conninfo=url,
        min_size=2,
        max_size=10,
        kwargs={"row_factory": dict_row},
        open=False,
    )
    await _pool.open()
    # Smoke-test the connection immediately
    async with _pool.connection() as conn:
        cur = await conn.execute("SELECT 1 AS ok")
        row = await cur.fetchone()
        print(f"[DB] Connection OK — smoke test: {row}")
    await _ensure_user_scoping()


async def close_pool() -> None:
    if _pool:
        await _pool.close()
        print("[DB] Pool closed")


async def _ensure_user_scoping() -> None:
    """Ensure user_id columns and indexes exist, backfill existing rows, create automation_api_keys table."""
    async with get_conn() as conn:
        # Add user_id columns with FK constraint
        await conn.execute("ALTER TABLE resumes ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE")
        await conn.execute("CREATE INDEX IF NOT EXISTS resumes_user_id ON resumes(user_id)")
        await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS resumes_user_filename_uq ON resumes(user_id, filename) WHERE user_id IS NOT NULL")

        await conn.execute("ALTER TABLE goal_sets ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE")
        await conn.execute("CREATE INDEX IF NOT EXISTS goal_sets_user_id ON goal_sets(user_id)")
        await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS goal_sets_user_name_uq ON goal_sets(user_id, name) WHERE user_id IS NOT NULL")

        await conn.execute("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE")
        await conn.execute("CREATE INDEX IF NOT EXISTS analyses_user_id ON analyses(user_id)")

        # Backfill existing NULL user_id rows to the single existing account
        owner_id_result = await conn.execute(
            "SELECT id FROM users WHERE email = %s LIMIT 1",
            ("yashvijaivargiya@gmail.com",)
        )
        owner_row = await owner_id_result.fetchone()
        if owner_row:
            owner_id = owner_row["id"]
            await conn.execute("UPDATE resumes SET user_id = %s WHERE user_id IS NULL", (owner_id,))
            await conn.execute("UPDATE goal_sets SET user_id = %s WHERE user_id IS NULL", (owner_id,))
            await conn.execute("UPDATE analyses SET user_id = %s WHERE user_id IS NULL", (owner_id,))

        # Create automation_api_keys table for n8n /pending-outreach endpoints
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS automation_api_keys (
                id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id         UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                key_hash        TEXT        NOT NULL UNIQUE,
                label           TEXT        NOT NULL DEFAULT 'n8n automation',
                last_4          TEXT        NOT NULL,
                is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
                last_used_at    TIMESTAMPTZ,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS automation_api_keys_user_id ON automation_api_keys(user_id)")


@asynccontextmanager
async def get_conn():
    if _pool is None:
        raise RuntimeError("DB pool not initialised — call init_pool() at startup")
    async with _pool.connection() as conn:
        yield conn


# ── resumes ───────────────────────────────────────────────────────────────────

async def db_insert_resume(
    user_id: str,
    filename: str,
    original_name: str,
    size_bytes: int,
    content_hash: str,
    extracted_text: str,
) -> dict:
    print(f"[DB] db_insert_resume: {filename}")
    async with get_conn() as conn:
        cur = await conn.execute(
            """
            INSERT INTO resumes (user_id, filename, original_name, size_bytes, content_hash, extracted_text)
            VALUES (%s::uuid, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, filename) DO UPDATE
              SET size_bytes     = EXCLUDED.size_bytes,
                  content_hash   = EXCLUDED.content_hash,
                  extracted_text = EXCLUDED.extracted_text,
                  uploaded_at    = now()
            RETURNING *
            """,
            (user_id, filename, original_name, size_bytes, content_hash, extracted_text),
        )
        row = await cur.fetchone()
        print(f"[DB] inserted resume id={row['id']}")
        return dict(row)


async def db_list_resumes(user_id: str) -> list[dict]:
    print("[DB] db_list_resumes")
    async with get_conn() as conn:
        cur = await conn.execute(
            "SELECT * FROM resumes WHERE user_id = %s::uuid ORDER BY uploaded_at DESC",
            (user_id,),
        )
        rows = await cur.fetchall()
        print(f"[DB] found {len(rows)} resumes")
        return [dict(r) for r in rows]


async def db_get_resume_by_filename(filename: str, user_id: str | None = None) -> dict | None:
    async with get_conn() as conn:
        if user_id:
            cur = await conn.execute(
                "SELECT * FROM resumes WHERE filename = %s AND user_id = %s::uuid",
                (filename, user_id),
            )
        else:
            cur = await conn.execute(
                "SELECT * FROM resumes WHERE filename = %s",
                (filename,),
            )
        row = await cur.fetchone()
        return dict(row) if row else None


async def db_delete_resume(filename: str, user_id: str) -> bool:
    async with get_conn() as conn:
        async with conn.transaction():
            cur = await conn.execute(
                "SELECT id FROM resumes WHERE filename = %s AND user_id = %s::uuid",
                (filename, user_id),
            )
            resume_row = await cur.fetchone()
            if not resume_row:
                return False

            resume_id = resume_row["id"]

            await conn.execute(
                "DELETE FROM suggestions USING analyses WHERE suggestions.analysis_id = analyses.id AND analyses.resume_id = %s::uuid AND analyses.user_id = %s::uuid",
                (str(resume_id), user_id),
            )
            await conn.execute(
                "DELETE FROM analyses WHERE resume_id = %s::uuid AND user_id = %s::uuid",
                (str(resume_id), user_id),
            )
            await conn.execute(
                "DELETE FROM resume_reviews WHERE resume_id = %s::uuid AND user_id = %s::uuid",
                (str(resume_id), user_id),
            )
            await conn.execute(
                "DELETE FROM company_suggestions WHERE resume_id = %s::uuid AND user_id = %s::uuid",
                (str(resume_id), user_id),
            )

            cur = await conn.execute(
                "DELETE FROM resumes WHERE filename = %s AND user_id = %s::uuid",
                (filename, user_id),
            )
            return cur.rowcount > 0


# ── goal_sets ─────────────────────────────────────────────────────────────────

async def db_list_goal_sets(user_id: str) -> list[dict]:
    print("[DB] db_list_goal_sets")
    async with get_conn() as conn:
        cur = await conn.execute(
            "SELECT * FROM goal_sets WHERE user_id = %s::uuid ORDER BY created_at DESC",
            (user_id,),
        )
        rows = await cur.fetchall()
        goal_sets = [dict(r) for r in rows]
        print(f"[DB] found {len(goal_sets)} goal sets")

        if not goal_sets:
            return []

        ids = [gs["id"] for gs in goal_sets]
        cur2 = await conn.execute(
            "SELECT * FROM goals WHERE goal_set_id = ANY(%s) ORDER BY sort_order",
            (ids,),
        )
        goal_rows = await cur2.fetchall()

        goals_by_set: dict[str, list] = {str(gs["id"]): [] for gs in goal_sets}
        for g in goal_rows:
            goals_by_set[str(g["goal_set_id"])].append(_goal_to_dict(g))

        for gs in goal_sets:
            gs["goals"] = goals_by_set.get(str(gs["id"]), [])
            gs["id"] = str(gs["id"])

        return goal_sets


async def db_get_goal_set(goal_set_id: str, user_id: str | None = None) -> dict | None:
    print(f"[DB] db_get_goal_set: {goal_set_id}")
    async with get_conn() as conn:
        if user_id:
            cur = await conn.execute(
                "SELECT * FROM goal_sets WHERE id = %s::uuid AND user_id = %s::uuid",
                (goal_set_id, user_id),
            )
        else:
            cur = await conn.execute(
                "SELECT * FROM goal_sets WHERE id = %s::uuid", (goal_set_id,)
            )
        row = await cur.fetchone()
        if not row:
            print(f"[DB] goal_set not found: {goal_set_id}")
            return None
        gs = dict(row)
        cur2 = await conn.execute(
            "SELECT * FROM goals WHERE goal_set_id = %s::uuid ORDER BY sort_order",
            (goal_set_id,),
        )
        goal_rows = await cur2.fetchall()
        gs["goals"] = [_goal_to_dict(g) for g in goal_rows]
        gs["id"] = str(gs["id"])
        print(f"[DB] goal_set found: {gs['name']} with {len(gs['goals'])} goals")
        return gs


async def db_insert_goal_set(user_id: str, goal_set_id: str, name: str, goals: list[dict]) -> dict:
    print(f"[DB] db_insert_goal_set: {goal_set_id} / {name}")
    async with get_conn() as conn:
        async with conn.transaction():
            # Let Postgres generate the UUID — frontend ids are short random strings, not UUIDs
            cur = await conn.execute(
                """
                INSERT INTO goal_sets (user_id, name, is_active)
                VALUES (%s::uuid, %s, FALSE)
                RETURNING *
                """,
                (user_id, name,),
            )
            gs = dict(await cur.fetchone())
            db_goal_set_uuid = gs["id"]
            inserted_goals = []
            for i, g in enumerate(goals):
                cur2 = await conn.execute(
                    """
                    INSERT INTO goals
                      (goal_set_id, label, description, confidence, auto_inferred, sort_order)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        db_goal_set_uuid,
                        g["label"],
                        g.get("description", ""),
                        g.get("confidence", "high"),
                        g.get("auto_inferred", False),
                        i,
                    ),
                )
                inserted_goals.append(_goal_to_dict(await cur2.fetchone()))
            gs["goals"] = inserted_goals
            gs["id"] = str(gs["id"])
            return gs


async def db_delete_goal_set(goal_set_id: str, user_id: str) -> bool:
    async with get_conn() as conn:
        cur = await conn.execute(
            "DELETE FROM goal_sets WHERE id = %s::uuid AND user_id = %s::uuid",
            (goal_set_id, user_id),
        )
        return cur.rowcount > 0


async def db_activate_goal_set(goal_set_id: str, user_id: str) -> bool:
    async with get_conn() as conn:
        async with conn.transaction():
            await conn.execute("UPDATE goal_sets SET is_active = FALSE WHERE user_id = %s::uuid", (user_id,))
            cur = await conn.execute(
                "UPDATE goal_sets SET is_active = TRUE WHERE id = %s::uuid AND user_id = %s::uuid",
                (goal_set_id, user_id),
            )
            return cur.rowcount > 0


async def db_deactivate_goal_set(goal_set_id: str, user_id: str) -> bool:
    async with get_conn() as conn:
        cur = await conn.execute(
            "UPDATE goal_sets SET is_active = FALSE WHERE id = %s::uuid AND user_id = %s::uuid",
            (goal_set_id, user_id),
        )
        return cur.rowcount > 0


# ── analyses ──────────────────────────────────────────────────────────────────

async def db_insert_analysis(entry: dict, user_id: str) -> dict:
    print(f"[DB] db_insert_analysis: jd_id={entry.get('jd_id')}")
    async with get_conn() as conn:
        # Resolve resume filename → UUID
        cur = await conn.execute(
            "SELECT id FROM resumes WHERE filename = %s AND user_id = %s::uuid",
            (entry["resume_id"], user_id),
        )
        resume_row = await cur.fetchone()
        resume_uuid = resume_row["id"] if resume_row else None

        # Resolve goal_set name → UUID (frontend sends short string ids, not UUIDs)
        # CRITICAL: Must filter by user_id to prevent using another user's goal set
        cur_gs = await conn.execute(
            "SELECT id FROM goal_sets WHERE name = %s AND user_id = %s::uuid ORDER BY created_at DESC LIMIT 1",
            (entry["goal_set_name"], user_id)
        )
        gs_row = await cur_gs.fetchone()
        goal_set_uuid = gs_row["id"] if gs_row else None
        print(f"[DB] resume_uuid={resume_uuid} goal_set_uuid={goal_set_uuid}")

        cur2 = await conn.execute(
            """
            INSERT INTO analyses (
                jd_id, user_id, resume_id, goal_set_id, goal_set_name, goal_set_snapshot,
                jd_text, jd_url, jd_json, scorecard, overall_fit, verdict,
                jd_title, company, status, changes_generated, analyzed_at,
                jd_link, job_summary, my_relevance
            ) VALUES (
                %s, %s::uuid, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s
            )
            ON CONFLICT (jd_id) DO NOTHING
            RETURNING *
            """,
            (
                entry["jd_id"],
                user_id,
                resume_uuid,
                goal_set_uuid,
                entry["goal_set_name"],
                json.dumps(entry.get("goal_set_snapshot", [])),
                entry.get("jd_text"),
                entry.get("url"),
                json.dumps(entry.get("jd_json")) if entry.get("jd_json") else None,
                json.dumps(entry.get("scorecard", {})),
                entry.get("overall_fit"),
                entry.get("verdict"),
                entry.get("jd_title"),
                entry.get("company"),
                entry.get("status", "pending"),
                entry.get("changes_generated", False),
                entry.get("analyzed_at"),
                entry.get("jd_link"),
                json.dumps(entry.get("job_summary", [])) if entry.get("job_summary") else None,
                json.dumps(entry.get("my_relevance", [])) if entry.get("my_relevance") else None,
            ),
        )
        row = await cur2.fetchone()
        return dict(row) if row else {}


async def db_list_analyses(user_id: str) -> list[dict]:
    print("[DB] db_list_analyses")
    async with get_conn() as conn:
        cur = await conn.execute(
            """
            SELECT a.*, r.filename AS resume_filename,
                   s.paraphrasing, s.missing, s.remove, s.polish
            FROM analyses a
            LEFT JOIN resumes r ON r.id = a.resume_id
            LEFT JOIN suggestions s ON s.analysis_id = a.id
            WHERE a.user_id = %s::uuid
            ORDER BY a.analyzed_at DESC
            """,
            (user_id,),
        )
        rows = await cur.fetchall()
        print(f"[DB] found {len(rows)} analyses")
        return [_analysis_to_dict(r) for r in rows]


async def db_delete_analysis(jd_id: str, user_id: str) -> bool:
    async with get_conn() as conn:
        cur = await conn.execute(
            "DELETE FROM analyses WHERE jd_id = %s AND user_id = %s::uuid",
            (jd_id, user_id),
        )
        return cur.rowcount > 0


# ── suggestions ───────────────────────────────────────────────────────────────

async def db_upsert_suggestions(jd_id: str, suggestions: dict, user_id: str) -> bool:
    async with get_conn() as conn:
        cur = await conn.execute(
            "SELECT a.id FROM analyses a JOIN resumes r ON r.id = a.resume_id WHERE a.jd_id = %s AND a.user_id = %s::uuid",
            (jd_id, user_id),
        )
        analysis = await cur.fetchone()
        if not analysis:
            return False
        await conn.execute(
            """
            INSERT INTO suggestions (analysis_id, paraphrasing, missing, remove, polish)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (analysis_id) DO UPDATE
              SET paraphrasing = EXCLUDED.paraphrasing,
                  missing      = EXCLUDED.missing,
                  remove       = EXCLUDED.remove,
                  polish       = EXCLUDED.polish,
                  created_at   = now()
            """,
            (
                analysis["id"],
                json.dumps(suggestions.get("paraphrasing", [])),
                json.dumps(suggestions.get("missing", [])),
                json.dumps(suggestions.get("remove", [])),
                json.dumps(suggestions.get("polish", [])),
            ),
        )
        return True


# ── api_keys (per-user LLM provider keys, Fernet-encrypted) ──────────────────

async def db_upsert_api_key(
    user_id: str,
    provider: str,
    encrypted: str,
    last_4: str,
    model: str | None = None,
) -> dict:
    async with get_conn() as conn:
        cur = await conn.execute(
            """
            INSERT INTO api_keys (user_id, provider, encrypted, last_4, model, updated_at)
            VALUES (%s::uuid, %s, %s, %s, %s, now())
            ON CONFLICT (user_id, provider) DO UPDATE
              SET encrypted  = EXCLUDED.encrypted,
                  last_4     = EXCLUDED.last_4,
                  model      = EXCLUDED.model,
                  is_active  = TRUE,
                  updated_at = now()
            RETURNING id, provider, last_4, model, is_active, created_at, updated_at
            """,
            (user_id, provider, encrypted, last_4, model),
        )
        return dict(await cur.fetchone())


async def db_list_api_keys(user_id: str) -> list[dict]:
    """Returns all 3 providers (even if user hasn't saved a key for some).
    
    For providers without a key, returns default model but no id/created_at.
    The is_active field is NOT set here (computed in routes/settings.py).
    """
    from routes.settings import MODELS_BY_PROVIDER, FALLBACK_CHAIN
    
    # Get rows user has actually saved
    async with get_conn() as conn:
        cur = await conn.execute(
            """
            SELECT id, provider, last_4, model, is_active, created_at, updated_at
              FROM api_keys
             WHERE user_id = %s::uuid
            """,
            (user_id,),
        )
        saved = {r["provider"]: dict(r) for r in await cur.fetchall()}
    
    # Return all 3 providers, using defaults for missing ones
    result = []
    for provider in FALLBACK_CHAIN:
        if provider in saved:
            result.append(saved[provider])
        else:
            # User hasn't saved a key for this provider
            result.append({
                "id": None,
                "provider": provider,
                "last_4": None,
                "model": MODELS_BY_PROVIDER.get(provider, [""])[0],  # default model
                "is_active": None,  # Will be computed in endpoint
                "created_at": None,
                "updated_at": None,
            })
    
    return result


async def db_get_active_provider(user_id: str) -> str | None:
    """Determine which provider is currently active for this user's analyses.
    
    Active logic:
    1. If user has saved ANY keys, the FIRST in FALLBACK_CHAIN with a saved key is active
    2. If user has NO saved keys, check env vars for server-level defaults:
       - If ANTHROPIC_API_KEY set in .env → active = "server_anthropic"
       - Else if OPENAI_API_KEY set → active = "server_openai"
       - Else if GOOGLE_API_KEY set → active = "server_gemini"
       - Else → active = None (no provider available)
    
    Returns: provider name string or "server_<provider>" or None
    """
    from routes.settings import FALLBACK_CHAIN
    import os
    
    logger.info(f"[LLM] Computing active provider for user: {user_id}")
    
    # Get user's saved keys (all non-deleted keys; soft-delete handled by app logic)
    async with get_conn() as conn:
        cur = await conn.execute(
            """
            SELECT provider FROM api_keys
             WHERE user_id = %s::uuid
            """,
            (user_id,),
        )
        saved_providers = {r["provider"] for r in await cur.fetchall()}
    
    logger.debug(f"[LLM] User {user_id} has saved keys for: {saved_providers}")
    
    # If user has saved keys, return first in chain that's saved
    for provider in FALLBACK_CHAIN:
        if provider in saved_providers:
            logger.info(f"[LLM] ✓ Active provider for user {user_id}: '{provider}' (from saved keys)")
            return provider
    
    # User has no saved keys; check server-level env vars
    env_map = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "gemini": "GOOGLE_API_KEY",
    }
    
    logger.debug(f"[LLM] No saved user keys; checking server-level env vars")
    
    for provider in FALLBACK_CHAIN:
        env_var = env_map.get(provider)
        if env_var and os.getenv(env_var):
            server_provider = f"server_{provider}"
            logger.info(f"[LLM] ✓ Active provider for user {user_id}: '{server_provider}' (from env var {env_var})")
            return server_provider
    
    logger.warning(f"[LLM] ⚠ No active provider found for user {user_id}; no saved keys and no server defaults")
    return None


async def db_get_decryptable_keys(user_id: str) -> dict[str, str]:
    """Returns {provider: ciphertext} for ACTIVE keys. Decryption happens at the
    call site so plaintext keys aren't held in memory longer than needed."""
    async with get_conn() as conn:
        cur = await conn.execute(
            """
            SELECT provider, encrypted
              FROM api_keys
             WHERE user_id = %s::uuid AND is_active = TRUE
            """,
            (user_id,),
        )
        return {r["provider"]: r["encrypted"] for r in await cur.fetchall()}


async def db_delete_api_key(user_id: str, provider: str) -> bool:
    async with get_conn() as conn:
        cur = await conn.execute(
            "DELETE FROM api_keys WHERE user_id = %s::uuid AND provider = %s",
            (user_id, provider),
        )
        return cur.rowcount > 0


# ── imports (pending JD imports from the browser extension) ──────────────────

async def db_insert_import(
    user_id: str,
    jd_text: str,
    url: str | None = None,
    host: str | None = None,
    job_id: str | None = None,
    jd_title: str | None = None,
    source: str = "extension",
) -> dict:
    async with get_conn() as conn:
        cur = await conn.execute(
            """
            INSERT INTO imports (user_id, source, url, host, job_id, jd_title, jd_text)
            VALUES (%s::uuid, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (user_id, source, url, host, job_id, jd_title, jd_text),
        )
        return _import_to_dict(await cur.fetchone())


async def db_list_pending_imports(user_id: str, limit: int = 20) -> list[dict]:
    async with get_conn() as conn:
        cur = await conn.execute(
            """
            SELECT * FROM imports
             WHERE user_id = %s::uuid AND status = 'pending'
             ORDER BY created_at DESC
             LIMIT %s
            """,
            (user_id, limit),
        )
        return [_import_to_dict(r) for r in await cur.fetchall()]


async def db_set_import_status(user_id: str, import_id: str, status: str) -> bool:
    """status ∈ {'consumed', 'dismissed'}. Scoped to user_id so users can't
    touch each other's imports."""
    if status not in ("consumed", "dismissed"):
        raise ValueError("invalid import status")
    async with get_conn() as conn:
        cur = await conn.execute(
            """
            UPDATE imports
               SET status = %s,
                   consumed_at = CASE WHEN %s = 'consumed' THEN now() ELSE consumed_at END
             WHERE id = %s::uuid AND user_id = %s::uuid
            """,
            (status, status, import_id, user_id),
        )
        return cur.rowcount > 0


def _import_to_dict(row: Any) -> dict:
    d = dict(row)
    if d.get("id"):
        d["id"] = str(d["id"])
    if d.get("user_id"):
        d["user_id"] = str(d["user_id"])
    for k in ("created_at", "consumed_at"):
        if d.get(k):
            d[k] = d[k].isoformat()
    return d


# ── resume_reviews (LLM-extracted profile per resume) ────────────────────────

async def db_upsert_resume_review(
    user_id: str,
    resume_id: str,
    review: dict,
) -> dict:
    """One row per (user, resume). Re-extracting overwrites."""
    async with get_conn() as conn:
        cur = await conn.execute(
            """
            INSERT INTO resume_reviews (
                user_id, resume_id,
                full_name, email, phone, location, linkedin, headline, summary,
                skills, experience, education, certifications, projects, raw
            ) VALUES (
                %s::uuid, %s::uuid,
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (resume_id) DO UPDATE SET
                full_name      = EXCLUDED.full_name,
                email          = EXCLUDED.email,
                phone          = EXCLUDED.phone,
                location       = EXCLUDED.location,
                linkedin       = EXCLUDED.linkedin,
                headline       = EXCLUDED.headline,
                summary        = EXCLUDED.summary,
                skills         = EXCLUDED.skills,
                experience     = EXCLUDED.experience,
                education      = EXCLUDED.education,
                certifications = EXCLUDED.certifications,
                projects       = EXCLUDED.projects,
                raw            = EXCLUDED.raw,
                updated_at     = now()
            RETURNING *
            """,
            (
                user_id, resume_id,
                review.get("full_name"), review.get("email"),
                review.get("phone"), review.get("location"),
                review.get("linkedin"), review.get("headline"), review.get("summary"),
                json.dumps(review.get("skills") or []),
                json.dumps(review.get("experience") or []),
                json.dumps(review.get("education") or []),
                json.dumps(review.get("certifications") or []),
                json.dumps(review.get("projects") or []),
                json.dumps(review.get("raw") or {}),
            ),
        )
        return _resume_review_to_dict(await cur.fetchone())


async def db_get_resume_review_by_resume_id(resume_id: str, user_id: str) -> dict | None:
    async with get_conn() as conn:
        cur = await conn.execute(
            "SELECT * FROM resume_reviews WHERE resume_id = %s::uuid AND user_id = %s::uuid",
            (resume_id, user_id),
        )
        row = await cur.fetchone()
        return _resume_review_to_dict(row) if row else None


async def db_patch_resume_review(resume_id: str, user_id: str, patch: dict) -> dict | None:
    """User-edited fields. We allow updating any of the top-level extracted
    fields — but NOT the raw blob (that's an audit trail of what the LLM said)."""
    allowed = {
        "full_name", "email", "phone", "location", "linkedin",
        "headline", "summary",
        "skills", "experience", "education", "certifications", "projects",
    }
    sets: list[str] = []
    values: list[Any] = []
    for k, v in patch.items():
        if k not in allowed:
            continue
        if k in ("skills", "experience", "education", "certifications", "projects"):
            sets.append(f"{k} = %s")
            values.append(json.dumps(v if isinstance(v, list) else []))
        else:
            sets.append(f"{k} = %s")
            values.append(v)
    if not sets:
        return await db_get_resume_review_by_resume_id(resume_id)
    sets.append("updated_at = now()")
    values.extend([resume_id, user_id])
    sql = f"UPDATE resume_reviews SET {', '.join(sets)} WHERE resume_id = %s::uuid AND user_id = %s::uuid RETURNING *"
    async with get_conn() as conn:
        cur = await conn.execute(sql, tuple(values))
        row = await cur.fetchone()
        return _resume_review_to_dict(row) if row else None


async def db_delete_resume_review(resume_id: str, user_id: str) -> bool:
    async with get_conn() as conn:
        cur = await conn.execute(
            "DELETE FROM resume_reviews WHERE resume_id = %s::uuid AND user_id = %s::uuid",
            (resume_id, user_id),
        )
        return cur.rowcount > 0


def _resume_review_to_dict(row: Any) -> dict:
    d = dict(row)
    for k in ("id", "user_id", "resume_id"):
        if d.get(k):
            d[k] = str(d[k])
    for k in ("created_at", "updated_at"):
        if d.get(k):
            d[k] = d[k].isoformat()
    return d


# ── company_suggestions (LLM-suggested target companies per resume) ──────────

async def db_upsert_company_suggestion(
    user_id: str,
    resume_id: str,
    companies: list,
    user_prompt: str | None,
    raw: dict | None,
) -> dict:
    async with get_conn() as conn:
        cur = await conn.execute(
            """
            INSERT INTO company_suggestions
              (user_id, resume_id, companies, user_prompt, raw)
            VALUES (%s::uuid, %s::uuid, %s, %s, %s)
            ON CONFLICT (resume_id) DO UPDATE SET
              companies   = EXCLUDED.companies,
              user_prompt = EXCLUDED.user_prompt,
              raw         = EXCLUDED.raw,
              updated_at  = now()
            RETURNING *
            """,
            (
                user_id, resume_id,
                json.dumps(companies or []),
                user_prompt,
                json.dumps(raw or {}),
            ),
        )
        return _company_suggestion_to_dict(await cur.fetchone())


async def db_get_company_suggestion(resume_id: str, user_id: str) -> dict | None:
    async with get_conn() as conn:
        cur = await conn.execute(
            "SELECT * FROM company_suggestions WHERE resume_id = %s::uuid AND user_id = %s::uuid",
            (resume_id, user_id),
        )
        row = await cur.fetchone()
        return _company_suggestion_to_dict(row) if row else None


async def db_delete_company_suggestion(resume_id: str, user_id: str) -> bool:
    async with get_conn() as conn:
        cur = await conn.execute(
            "DELETE FROM company_suggestions WHERE resume_id = %s::uuid AND user_id = %s::uuid",
            (resume_id, user_id),
        )
        return cur.rowcount > 0


def _company_suggestion_to_dict(row: Any) -> dict:
    d = dict(row)
    for k in ("id", "user_id", "resume_id"):
        if d.get(k):
            d[k] = str(d[k])
    for k in ("created_at", "updated_at"):
        if d.get(k):
            d[k] = d[k].isoformat()
    return d


# ── automation_api_keys (n8n /pending-outreach authentication) ────────────────

async def db_get_user_from_automation_key(key_hash: str) -> dict | None:
    """Look up user by automation API key hash (for n8n /pending-outreach endpoints).
    Returns user dict if key is valid and active, None otherwise.
    Updates last_used_at timestamp."""
    async with get_conn() as conn:
        async with conn.transaction():
            cur = await conn.execute(
                """
                SELECT u.* FROM users u
                JOIN automation_api_keys k ON u.id = k.user_id
                WHERE k.key_hash = %s AND k.is_active = TRUE
                LIMIT 1
                """,
                (key_hash,),
            )
            user = await cur.fetchone()
            if user:
                # Update last_used_at
                await conn.execute(
                    "UPDATE automation_api_keys SET last_used_at = now() WHERE key_hash = %s",
                    (key_hash,),
                )
            return dict(user) if user else None


async def db_list_automation_keys(user_id: str) -> list[dict]:
    """List automation API keys for a user (returns without the key_hash)."""
    async with get_conn() as conn:
        cur = await conn.execute(
            """
            SELECT id, user_id, label, last_4, is_active, last_used_at, created_at
              FROM automation_api_keys
             WHERE user_id = %s::uuid
             ORDER BY created_at DESC
            """,
            (user_id,),
        )
        return [dict(r) for r in await cur.fetchall()]


async def db_upsert_automation_key(
    user_id: str,
    key_hash: str,
    last_4: str,
    label: str = "n8n automation",
) -> dict:
    """Create or reactivate an automation API key."""
    async with get_conn() as conn:
        cur = await conn.execute(
            """
            INSERT INTO automation_api_keys (user_id, key_hash, label, last_4)
            VALUES (%s::uuid, %s, %s, %s)
            ON CONFLICT (key_hash) DO UPDATE
              SET is_active = TRUE,
                  last_used_at = now()
            RETURNING id, user_id, label, last_4, is_active, last_used_at, created_at
            """,
            (user_id, key_hash, label, last_4),
        )
        return dict(await cur.fetchone())


async def db_delete_automation_key(user_id: str, key_id: str) -> bool:
    """Delete an automation API key (owner scoped)."""
    async with get_conn() as conn:
        cur = await conn.execute(
            "DELETE FROM automation_api_keys WHERE id = %s::uuid AND user_id = %s::uuid",
            (key_id, user_id),
        )
        return cur.rowcount > 0


# ── helpers ───────────────────────────────────────────────────────────────────

def _goal_to_dict(row: Any) -> dict:
    return {
        "id": str(row["id"]),
        "goal_set_id": str(row["goal_set_id"]),
        "label": row["label"],
        "description": row["description"],
        "confidence": row["confidence"],
        "auto_inferred": row["auto_inferred"],
        "sort_order": row["sort_order"],
    }


def _analysis_to_dict(row: Any) -> dict:
    d = dict(row)
    for k in ("id", "resume_id", "goal_set_id"):
        if d.get(k):
            d[k] = str(d[k])
    has_suggestions = any(d.get(k) for k in ("paraphrasing", "missing", "remove", "polish"))
    if has_suggestions:
        d["suggestions"] = {
            "paraphrasing": d.pop("paraphrasing") or [],
            "missing":      d.pop("missing") or [],
            "remove":       d.pop("remove") or [],
            "polish":       d.pop("polish") or [],
        }
    else:
        for k in ("paraphrasing", "missing", "remove", "polish"):
            d.pop(k, None)
        d["suggestions"] = None
    if d.get("resume_filename"):
        d["resume_id"] = d.pop("resume_filename")
    return d
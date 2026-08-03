"""Dashboard routes — aggregate stats for the user's overview page.

Returns counts, verdict distribution, fit-score timeline and gap-type
frequencies in a single response so the dashboard renders without N round
trips. All data is currently global (not per-user) — when Chunk 4 lands the
user_id filter just gets added to the WHEREs below.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from auth import get_current_user
from database import get_conn

router = APIRouter()


@router.get("")
@router.get("/", include_in_schema=False)
async def get_dashboard(user: dict = Depends(get_current_user)):
    """One shot. Frontend slices the response into cards + charts."""
    async with get_conn() as conn:
        # ── Totals ──
        cur = await conn.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM resumes WHERE user_id = %s::uuid)                                    AS total_resumes,
              (SELECT COUNT(*) FROM goal_sets WHERE user_id = %s::uuid)                                  AS total_goal_sets,
              (SELECT COUNT(*) FROM analyses WHERE user_id = %s::uuid)                                   AS total_analyses,
              (SELECT COUNT(*) FROM analyses WHERE user_id = %s::uuid AND verdict = 'apply')           AS apply_count,
              (SELECT COUNT(*) FROM analyses WHERE user_id = %s::uuid AND verdict = 'borderline')      AS borderline_count,
              (SELECT COUNT(*) FROM analyses WHERE user_id = %s::uuid AND verdict = 'skip')            AS skip_count,
              (SELECT AVG(overall_fit) FROM analyses WHERE user_id = %s::uuid AND overall_fit IS NOT NULL) AS avg_fit
            """,
            (str(user["id"]), str(user["id"]), str(user["id"]), str(user["id"]), str(user["id"]), str(user["id"]), str(user["id"])),
        )
        totals = dict(await cur.fetchone())

        # ── Fit score timeline (last 30 analyses, oldest-first for the chart) ──
        cur = await conn.execute(
            """
            SELECT a.analyzed_at, a.overall_fit, a.verdict,
                   a.jd_title, a.company, a.jd_id
              FROM analyses a
             WHERE a.user_id = %s::uuid AND a.overall_fit IS NOT NULL
             ORDER BY a.analyzed_at DESC
             LIMIT 30
            """,
            (str(user["id"]),),
        )
        timeline_rows = await cur.fetchall()
        timeline = [
            {
                "analyzed_at": r["analyzed_at"].isoformat() if r.get("analyzed_at") else None,
                "overall_fit": float(r["overall_fit"]),
                "verdict":     r["verdict"],
                "jd_title":    r["jd_title"],
                "company":     r["company"],
                "jd_id":       r["jd_id"],
            }
            for r in reversed(timeline_rows)   # chart wants chronological order
        ]

        # ── Gap-type frequency (across all analyses) ──
        # Gaps are stored as a JSONB array on each scorecard. Postgres
        # jsonb_array_elements unwraps; we then group by the 'type' field.
        cur = await conn.execute(
            """
            SELECT  COALESCE(g->>'type', 'Other') AS type,
                    COUNT(*)                     AS count
              FROM  analyses,
                    LATERAL jsonb_array_elements(scorecard->'gaps') g
             WHERE  user_id = %s::uuid AND scorecard->'gaps' IS NOT NULL
             GROUP  BY 1
             ORDER  BY 2 DESC
             LIMIT  10
            """,
            (str(user["id"]),),
        )
        gap_types = [
            {"type": r["type"], "count": int(r["count"])}
            for r in await cur.fetchall()
        ]

        # ── Per-resume usage (which resume is most analyzed) ──
        cur = await conn.execute(
            """
            SELECT  r.filename, COUNT(a.id) AS count
              FROM  resumes r
              LEFT  JOIN analyses a ON a.resume_id = r.id AND a.user_id = %s::uuid
             WHERE r.user_id = %s::uuid
             GROUP  BY r.id, r.filename
             ORDER  BY 2 DESC
             LIMIT  5
            """,
            (str(user["id"]), str(user["id"])),
        )
        top_resumes = [
            {"filename": r["filename"], "count": int(r["count"])}
            for r in await cur.fetchall()
        ]

    return {
        "totals": {
            "resumes":      int(totals.get("total_resumes") or 0),
            "goal_sets":    int(totals.get("total_goal_sets") or 0),
            "analyses":     int(totals.get("total_analyses") or 0),
            "avg_fit":      round(float(totals["avg_fit"]), 2) if totals.get("avg_fit") else None,
        },
        "verdicts": {
            "apply":      int(totals.get("apply_count") or 0),
            "borderline": int(totals.get("borderline_count") or 0),
            "skip":       int(totals.get("skip_count") or 0),
        },
        "timeline":   timeline,
        "gap_types":  gap_types,
        "top_resumes": top_resumes,
    }

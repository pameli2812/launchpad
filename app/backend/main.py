"""
FastAPI backend for Launchpad - Resume AI Analyzer
"""

import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from fastapi import Depends

from database import init_pool, close_pool
from routes import (
    setup, analyze, history, dashboard,
    settings as settings_routes,
    imports as imports_routes,
    resume_review as resume_review_routes,
    company_suggestion as company_suggestion_routes,
    ats_rank as ats_rank_routes,
)
from llm_keys_dep import load_user_llm_keys
import auth   # auth routes live in auth.py at the same level


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    yield
    await close_pool()


app = FastAPI(
    title="Launchpad API",
    description="Resume AI Analysis Backend",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(setup.router,                  prefix="/api/setup",          tags=["setup"])
# Analyze routes get the per-user LLM key dep applied at the router level — no
# need for every handler to repeat Depends(load_user_llm_keys). The dep itself
# pulls Depends(get_current_user), so analyze becomes implicitly auth-gated.
app.include_router(analyze.router,                prefix="/api/analyze",        tags=["analyze"],
                   dependencies=[Depends(load_user_llm_keys)])
app.include_router(history.router,                prefix="/api/history",        tags=["history"])
app.include_router(auth.router,                   prefix="/api/auth",           tags=["auth"])
app.include_router(settings_routes.router,        prefix="/api/settings",       tags=["settings"])
app.include_router(imports_routes.router,         prefix="/api/imports",        tags=["imports"])
app.include_router(resume_review_routes.router,      prefix="/api/resume-review",       tags=["resume-review"])
app.include_router(company_suggestion_routes.router, prefix="/api/company-suggestion",  tags=["company-suggestion"])
app.include_router(dashboard.router,                 prefix="/api/dashboard",           tags=["dashboard"])
app.include_router(ats_rank_routes.router,           prefix="/api/ats",                 tags=["ats"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "launchpad-api", "version": "2.0.0"}


@app.get("/")
async def root():
    return {"message": "Welcome to Launchpad API", "docs": "/docs", "health": "/health"}


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("API_PORT", 8000)), reload=True)


@app.get("/health/db")
async def health_db():
    """Debug endpoint — confirms DB connection and lists tables."""
    from database import get_conn
    try:
        async with get_conn() as conn:
            cur = await conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"
            )
            tables = [r["table_name"] for r in await cur.fetchall()]
            cur2 = await conn.execute("SELECT COUNT(*) AS n FROM resumes")
            resumes = (await cur2.fetchone())["n"]
            cur3 = await conn.execute("SELECT COUNT(*) AS n FROM goal_sets")
            goal_sets = (await cur3.fetchone())["n"]
        return {
            "status": "connected",
            "tables": tables,
            "counts": {"resumes": resumes, "goal_sets": goal_sets},
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}
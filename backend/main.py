"""
FastAPI backend for Launchpad - Resume AI Analyzer
Provides RESTful API endpoints for resume analysis, goal management, and history tracking
"""

import os
import sys
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "launchpad"))

from routes import setup, analyze, history

app = FastAPI(
    title="Launchpad API",
    description="Resume AI Analysis Backend",
    version="1.0.0",
)

# ─────────────────────────────────────────────
# CORS Configuration
# ─────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local React dev
        "http://localhost:5173",  # Vite default
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# Include Routers
# ─────────────────────────────────────────────
app.include_router(setup.router, prefix="/api/setup", tags=["setup"])
app.include_router(analyze.router, prefix="/api/analyze", tags=["analyze"])
app.include_router(history.router, prefix="/api/history", tags=["history"])

# ─────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "launchpad-api",
        "version": "1.0.0",
    }

# ─────────────────────────────────────────────
# Root Endpoint
# ─────────────────────────────────────────────
@app.get("/")
async def root():
    """Root endpoint with API documentation"""
    return {
        "message": "Welcome to Launchpad API",
        "docs": "/docs",
        "health": "/health",
    }

# ─────────────────────────────────────────────
# Error Handlers
# ─────────────────────────────────────────────
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("API_PORT", 8000)),
        reload=True,
    )

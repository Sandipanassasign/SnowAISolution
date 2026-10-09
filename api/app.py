"""
FastAPI application — the main entry point for the web server.

Serves both the REST API and the static frontend dashboard.
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.database import init_db
from api.routes import pipeline, tickets
from api.scheduler import get_schedule_info, start_scheduler, stop_scheduler

load_dotenv()

# ── Logging ──────────────────────────────────────────────────────────
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("automation.log", mode="a", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# ── Lifespan ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    logger.info("Initializing database...")
    init_db()

    logger.info("Starting scheduler...")
    start_scheduler()

    logger.info("ServiceNow AI Automation server is ready.")
    yield

    # Shutdown
    logger.info("Shutting down scheduler...")
    stop_scheduler()
    logger.info("Server stopped.")


# ── App ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="ServiceNow AI Automation",
    description="Automated CR triage, LLM extraction, and stakeholder notification",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow dashboard served from same origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ───────────────────────────────────────────────────────────
app.include_router(pipeline.router)
app.include_router(tickets.router)


@app.get("/api/schedule")
def get_schedule():
    """Get current scheduler status."""
    return get_schedule_info()


# ── Serve frontend ──────────────────────────────────────────────────
_frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if _frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
    logger.info("Serving frontend from %s", _frontend_dir)

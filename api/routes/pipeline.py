"""
Pipeline API routes — trigger and monitor pipeline execution.
"""

from __future__ import annotations

import logging
import threading

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.database import SessionLocal, get_db
from api.models import PipelineRun, RunStatus
from api.pipeline_service import run_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

# Track if a pipeline is currently running
_pipeline_lock = threading.Lock()
_is_running = False


class PipelineRunResponse(BaseModel):
    """Response schema for pipeline run status."""

    id: int
    trigger: str
    status: str
    started_at: str
    finished_at: str | None = None
    tickets_found: int
    tickets_notified: int
    error_message: str | None = None

    class Config:
        from_attributes = True


def _run_in_background(trigger: str, run_id: int | None = None) -> None:
    """Execute the pipeline in a background thread."""
    global _is_running
    db = SessionLocal()
    try:
        run_pipeline(db, trigger=trigger, run_id=run_id)
    finally:
        _is_running = False
        db.close()


@router.post("/run", response_model=PipelineRunResponse)
def trigger_pipeline(db: Session = Depends(get_db)):
    """Trigger an immediate pipeline execution.

    Returns 409 if a pipeline is already running.
    """
    global _is_running

    if _is_running:
        # Find the currently running pipeline
        running = (
            db.query(PipelineRun)
            .filter(PipelineRun.status == RunStatus.RUNNING)
            .order_by(PipelineRun.id.desc())
            .first()
        )
        if running:
            return PipelineRunResponse(
                id=running.id,
                trigger=running.trigger,
                status=running.status.value,
                started_at=running.started_at.isoformat(),
                finished_at=None,
                tickets_found=running.tickets_found,
                tickets_notified=running.tickets_notified,
                error_message="Pipeline is already running",
            )

    with _pipeline_lock:
        _is_running = True

    # Create an initial run record so we can return it immediately
    run = PipelineRun(trigger="manual", status=RunStatus.RUNNING)
    db.add(run)
    db.commit()
    db.refresh(run)

    # Launch in background thread
    thread = threading.Thread(
        target=_run_in_background,
        args=("manual", run.id),
        daemon=True,
    )
    thread.start()

    logger.info("Pipeline triggered manually (Run #%d)", run.id)

    return PipelineRunResponse(
        id=run.id,
        trigger=run.trigger,
        status=run.status.value,
        started_at=run.started_at.isoformat(),
        finished_at=None,
        tickets_found=0,
        tickets_notified=0,
    )


@router.get("/status", response_model=PipelineRunResponse)
def get_pipeline_status(db: Session = Depends(get_db)):
    """Get the most recent pipeline run status."""
    latest = (
        db.query(PipelineRun)
        .order_by(PipelineRun.id.desc())
        .first()
    )

    if not latest:
        return PipelineRunResponse(
            id=0,
            trigger="none",
            status="idle",
            started_at="",
            tickets_found=0,
            tickets_notified=0,
            error_message="No pipeline runs yet",
        )

    return PipelineRunResponse(
        id=latest.id,
        trigger=latest.trigger,
        status=latest.status.value,
        started_at=latest.started_at.isoformat(),
        finished_at=latest.finished_at.isoformat() if latest.finished_at else None,
        tickets_found=latest.tickets_found,
        tickets_notified=latest.tickets_notified,
        error_message=latest.error_message,
    )


@router.get("/runs", response_model=list[PipelineRunResponse])
def list_pipeline_runs(
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """List recent pipeline runs."""
    runs = (
        db.query(PipelineRun)
        .order_by(PipelineRun.id.desc())
        .limit(limit)
        .all()
    )

    return [
        PipelineRunResponse(
            id=r.id,
            trigger=r.trigger,
            status=r.status.value,
            started_at=r.started_at.isoformat(),
            finished_at=r.finished_at.isoformat() if r.finished_at else None,
            tickets_found=r.tickets_found,
            tickets_notified=r.tickets_notified,
            error_message=r.error_message,
        )
        for r in runs
    ]

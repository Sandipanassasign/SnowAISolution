"""
Pipeline service — database-aware version of the orchestration logic.

Wraps the existing src/ pipeline functions with database persistence
so every run, extraction, and notification is recorded.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from api.models import CRStatus, NotificationLog, PipelineRun, ProcessedCR, RunStatus
from src.llm_extractor import extract_impact_data
from src.notifier import dispatch_notification, map_stakeholders
from src.schema import NotificationPayload
from src.snow_client import fetch_snow_tickets

logger = logging.getLogger(__name__)


def run_pipeline(
    db: Session,
    trigger: str = "manual",
    run_id: int | None = None,
) -> PipelineRun:
    """Execute the full 4-step pipeline with database persistence.

    Args:
        db: SQLAlchemy database session.
        trigger: How the run was initiated ("manual" or "scheduled").
        run_id: Optional existing PipelineRun ID to resume/populate.

    Returns:
        The PipelineRun record with results.
    """
    # ── Create or load pipeline run record ────────────────────────────
    if run_id:
        run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
        if not run:
            run = PipelineRun(id=run_id, trigger=trigger, status=RunStatus.RUNNING)
            db.add(run)
            db.commit()
            db.refresh(run)
    else:
        run = PipelineRun(trigger=trigger, status=RunStatus.RUNNING)
        db.add(run)
        db.commit()
        db.refresh(run)

    logger.info("Pipeline run #%d started (trigger=%s)", run.id, trigger)

    try:
        # ── Step 1: Fetch tickets ────────────────────────────────────
        logger.info("[Run #%d] Step 1/4 — Fetching scheduled CRs", run.id)
        tickets = fetch_snow_tickets(state="Scheduled")
        run.tickets_found = len(tickets)
        db.commit()

        if not tickets:
            logger.info("[Run #%d] No tickets found.", run.id)
            run.status = RunStatus.COMPLETED
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
            return run

        notified_count = 0

        for ticket in tickets:
            # ── Create ProcessedCR record ────────────────────────────
            cr = ProcessedCR(
                pipeline_run_id=run.id,
                cr_number=ticket.number,
                sys_id=ticket.sys_id,
                short_description=ticket.short_description,
                description=ticket.description,
                status=CRStatus.PROCESSING,
            )
            db.add(cr)
            db.commit()
            db.refresh(cr)

            # ── Step 2: Extract impact data ──────────────────────────
            logger.info(
                "[Run #%d] Step 2/4 — Extracting %s", run.id, ticket.number
            )
            impact = extract_impact_data(ticket)

            if impact is None:
                cr.status = CRStatus.EXTRACTION_FAILED
                cr.error_message = "LLM failed to extract structured data"
                db.commit()
                continue

            cr.lob_impacted = impact.lob_impacted
            cr.mail_codes = ", ".join(impact.mail_codes)
            cr.status = CRStatus.EXTRACTED
            db.commit()

            # ── Step 3: Map stakeholders ─────────────────────────────
            logger.info(
                "[Run #%d] Step 3/4 — Mapping LOB '%s'",
                run.id,
                impact.lob_impacted,
            )
            stakeholder = map_stakeholders(impact)

            if stakeholder is None:
                cr.status = CRStatus.MAPPING_FAILED
                cr.error_message = f"No mapping for LOB: {impact.lob_impacted}"
                db.commit()
                continue

            cr.qa_lead = stakeholder.qa_lead
            cr.status = CRStatus.MAPPED
            db.commit()

            # ── Step 4: Dispatch notification ────────────────────────
            logger.info(
                "[Run #%d] Step 4/4 — Dispatching for %s",
                run.id,
                ticket.number,
            )
            payload = NotificationPayload(
                change_order_number=impact.change_order_number,
                short_description=ticket.short_description,
                mail_codes=impact.mail_codes,
                lob_impacted=impact.lob_impacted,
                stakeholder=stakeholder,
                description=ticket.description,
            )

            recipients = stakeholder.qa_team or [stakeholder.qa_lead]
            success = dispatch_notification(payload)

            # Log the notification attempt
            notif_log = NotificationLog(
                processed_cr_id=cr.id,
                recipients=", ".join(recipients),
                subject=f"[CR Notification] {payload.change_order_number}",
                success=1 if success else 0,
                error_message=None if success else "SMTP dispatch failed",
            )
            db.add(notif_log)

            if success:
                cr.status = CRStatus.NOTIFIED
                cr.notified_at = datetime.now(timezone.utc)
                notified_count += 1
            else:
                cr.status = CRStatus.NOTIFICATION_FAILED
                cr.error_message = "SMTP dispatch failed"

            db.commit()

        # ── Finalize run ─────────────────────────────────────────────
        run.tickets_notified = notified_count
        run.status = RunStatus.COMPLETED
        run.finished_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            "[Run #%d] Complete — %d/%d notified",
            run.id,
            notified_count,
            len(tickets),
        )

    except Exception as e:
        logger.exception("[Run #%d] Pipeline failed", run.id)
        run.status = RunStatus.FAILED
        run.error_message = str(e)
        run.finished_at = datetime.now(timezone.utc)
        db.commit()

    return run

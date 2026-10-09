"""
Ticket API routes — query processed Change Requests.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.database import get_db
from api.models import ProcessedCR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


class TicketResponse(BaseModel):
    """Response schema for a processed Change Request."""

    id: int
    pipeline_run_id: int
    cr_number: str
    short_description: str
    description: str
    status: str
    lob_impacted: str | None = None
    mail_codes: str | None = None
    qa_lead: str | None = None
    processed_at: str
    notified_at: str | None = None
    error_message: str | None = None

    class Config:
        from_attributes = True


class NotificationResponse(BaseModel):
    """Response schema for an email notification attempt."""

    id: int
    recipients: str
    subject: str
    success: bool
    error_message: str | None = None
    sent_at: str

    class Config:
        from_attributes = True


class TicketDetailResponse(TicketResponse):
    """Extended schema for Change Request drill-down view."""

    sys_id: str
    notifications: list[NotificationResponse] = []


class TicketStats(BaseModel):
    """Dashboard summary statistics."""

    total_processed: int
    total_notified: int
    total_failed: int
    lob_breakdown: dict[str, int]


@router.get("", response_model=list[TicketResponse])
def list_tickets(
    lob: str | None = Query(None, description="Filter by LOB"),
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List processed Change Requests with optional filters."""
    query = db.query(ProcessedCR).order_by(ProcessedCR.processed_at.desc())

    if lob:
        query = query.filter(ProcessedCR.lob_impacted.ilike(f"%{lob}%"))
    if status:
        query = query.filter(ProcessedCR.status == status)

    tickets = query.offset(offset).limit(limit).all()

    return [
        TicketResponse(
            id=t.id,
            pipeline_run_id=t.pipeline_run_id,
            cr_number=t.cr_number,
            short_description=t.short_description,
            description=t.description,
            status=t.status.value,
            lob_impacted=t.lob_impacted,
            mail_codes=t.mail_codes,
            qa_lead=t.qa_lead,
            processed_at=t.processed_at.isoformat(),
            notified_at=t.notified_at.isoformat() if t.notified_at else None,
            error_message=t.error_message,
        )
        for t in tickets
    ]


@router.get("/stats", response_model=TicketStats)
def get_ticket_stats(db: Session = Depends(get_db)):
    """Get summary statistics for the dashboard."""
    total = db.query(ProcessedCR).count()
    notified = db.query(ProcessedCR).filter(
        ProcessedCR.status == "notified"
    ).count()
    failed = db.query(ProcessedCR).filter(
        ProcessedCR.status.in_([
            "extraction_failed",
            "mapping_failed",
            "notification_failed",
        ])
    ).count()

    # LOB breakdown
    lob_rows = (
        db.query(ProcessedCR.lob_impacted)
        .filter(ProcessedCR.lob_impacted.isnot(None))
        .all()
    )
    lob_counts: dict[str, int] = {}
    for (lob,) in lob_rows:
        lob_counts[lob] = lob_counts.get(lob, 0) + 1

    return TicketStats(
        total_processed=total,
        total_notified=notified,
        total_failed=failed,
        lob_breakdown=lob_counts,
    )


@router.get("/{cr_number}", response_model=TicketDetailResponse)
def get_ticket(cr_number: str, db: Session = Depends(get_db)):
    """Get complete drill-down details for a specific Change Request."""
    ticket = (
        db.query(ProcessedCR)
        .filter(ProcessedCR.cr_number == cr_number)
        .order_by(ProcessedCR.processed_at.desc())
        .first()
    )

    if not ticket:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"CR {cr_number} not found")

    notifs = [
        NotificationResponse(
            id=n.id,
            recipients=n.recipients,
            subject=n.subject,
            success=bool(n.success),
            error_message=n.error_message,
            sent_at=n.sent_at.isoformat(),
        )
        for n in ticket.notifications
    ]

    return TicketDetailResponse(
        id=ticket.id,
        pipeline_run_id=ticket.pipeline_run_id,
        cr_number=ticket.cr_number,
        sys_id=ticket.sys_id,
        short_description=ticket.short_description,
        description=ticket.description,
        status=ticket.status.value,
        lob_impacted=ticket.lob_impacted,
        mail_codes=ticket.mail_codes,
        qa_lead=ticket.qa_lead,
        processed_at=ticket.processed_at.isoformat(),
        notified_at=ticket.notified_at.isoformat() if ticket.notified_at else None,
        error_message=ticket.error_message,
        notifications=notifs,
    )


@router.post("/{cr_number}/reprocess", response_model=TicketDetailResponse)
def reprocess_ticket(cr_number: str, db: Session = Depends(get_db)):
    """Re-run LLM extraction, stakeholder mapping, and notification for a CR."""
    from datetime import datetime, timezone
    from fastapi import HTTPException

    from api.models import CRStatus, NotificationLog
    from src.llm_extractor import extract_impact_data
    from src.notifier import dispatch_notification, map_stakeholders
    from src.schema import ChangeRequestRecord, NotificationPayload

    ticket = (
        db.query(ProcessedCR)
        .filter(ProcessedCR.cr_number == cr_number)
        .order_by(ProcessedCR.processed_at.desc())
        .first()
    )

    if not ticket:
        raise HTTPException(status_code=404, detail=f"CR {cr_number} not found")

    record = ChangeRequestRecord(
        number=ticket.cr_number,
        sys_id=ticket.sys_id,
        short_description=ticket.short_description,
        description=ticket.description,
        state="Scheduled",
    )

    ticket.status = CRStatus.PROCESSING
    ticket.error_message = None
    db.commit()

    impact = extract_impact_data(record)
    if impact is None:
        ticket.status = CRStatus.EXTRACTION_FAILED
        ticket.error_message = "LLM failed to extract structured data on retry"
        db.commit()
        return get_ticket(cr_number, db)

    ticket.lob_impacted = impact.lob_impacted
    ticket.mail_codes = ", ".join(impact.mail_codes)
    ticket.status = CRStatus.EXTRACTED
    db.commit()

    stakeholder = map_stakeholders(impact)
    if stakeholder is None:
        ticket.status = CRStatus.MAPPING_FAILED
        ticket.error_message = f"No mapping for LOB: {impact.lob_impacted}"
        db.commit()
        return get_ticket(cr_number, db)

    ticket.qa_lead = stakeholder.qa_lead
    ticket.status = CRStatus.MAPPED
    db.commit()

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

    notif = NotificationLog(
        processed_cr_id=ticket.id,
        recipients=", ".join(recipients),
        subject=f"[CR Notification] {payload.change_order_number}",
        success=1 if success else 0,
        error_message=None if success else "SMTP dispatch failed on retry",
    )
    db.add(notif)

    if success:
        ticket.status = CRStatus.NOTIFIED
        ticket.notified_at = datetime.now(timezone.utc)
    else:
        ticket.status = CRStatus.NOTIFICATION_FAILED
        ticket.error_message = "SMTP dispatch failed on retry"

    db.commit()
    return get_ticket(cr_number, db)

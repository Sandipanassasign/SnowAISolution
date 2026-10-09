"""
SQLAlchemy ORM models for the audit trail database.

Tracks every pipeline run, every processed Change Request,
and every notification dispatch attempt.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from api.database import Base


class CRStatus(str, enum.Enum):
    """Processing status for a Change Request."""

    PROCESSING = "processing"
    EXTRACTED = "extracted"
    EXTRACTION_FAILED = "extraction_failed"
    MAPPED = "mapped"
    MAPPING_FAILED = "mapping_failed"
    NOTIFIED = "notified"
    NOTIFICATION_FAILED = "notification_failed"


class RunStatus(str, enum.Enum):
    """Status of a pipeline run."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineRun(Base):
    """Represents a single execution of the full pipeline."""

    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trigger = Column(String(20), nullable=False, default="manual")  # "manual" | "scheduled"
    status = Column(Enum(RunStatus), nullable=False, default=RunStatus.RUNNING)
    started_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    finished_at = Column(DateTime, nullable=True)
    tickets_found = Column(Integer, default=0)
    tickets_notified = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    # Relationship
    processed_crs = relationship("ProcessedCR", back_populates="pipeline_run")

    def __repr__(self) -> str:
        return f"<PipelineRun #{self.id} {self.status.value}>"


class ProcessedCR(Base):
    """A Change Request that has been processed by the pipeline."""

    __tablename__ = "processed_crs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pipeline_run_id = Column(Integer, ForeignKey("pipeline_runs.id"), nullable=False)

    # ServiceNow fields
    cr_number = Column(String(20), nullable=False, index=True)
    sys_id = Column(String(64), nullable=False)
    short_description = Column(Text, nullable=False)
    description = Column(Text, nullable=False)

    # Extraction results
    status = Column(Enum(CRStatus), nullable=False, default=CRStatus.PROCESSING)
    lob_impacted = Column(String(100), nullable=True)
    mail_codes = Column(Text, nullable=True)  # Stored as comma-separated
    qa_lead = Column(String(200), nullable=True)

    # Timestamps
    processed_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    notified_at = Column(DateTime, nullable=True)

    # Error tracking
    error_message = Column(Text, nullable=True)

    # Relationship
    pipeline_run = relationship("PipelineRun", back_populates="processed_crs")
    notifications = relationship("NotificationLog", back_populates="processed_cr")

    def __repr__(self) -> str:
        return f"<ProcessedCR {self.cr_number} [{self.status.value}]>"

    @property
    def mail_codes_list(self) -> list[str]:
        """Return mail_codes as a list."""
        if not self.mail_codes:
            return []
        return [code.strip() for code in self.mail_codes.split(",")]


class NotificationLog(Base):
    """Log of every notification dispatch attempt."""

    __tablename__ = "notification_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    processed_cr_id = Column(Integer, ForeignKey("processed_crs.id"), nullable=False)

    recipients = Column(Text, nullable=False)  # Comma-separated email list
    subject = Column(Text, nullable=False)
    success = Column(Integer, nullable=False, default=0)  # 0=failed, 1=success
    error_message = Column(Text, nullable=True)
    sent_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationship
    processed_cr = relationship("ProcessedCR", back_populates="notifications")

    def __repr__(self) -> str:
        status = "✅" if self.success else "❌"
        return f"<NotificationLog {status} CR#{self.processed_cr_id}>"

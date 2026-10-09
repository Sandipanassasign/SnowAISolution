"""
Pydantic data models for ServiceNow Change Request impact extraction.

These models define the structured output schema that the LLM must conform to
when extracting impact data from unstructured CR description fields.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ImpactData(BaseModel):
    """Structured impact data extracted from a Change Request description.

    The LLM parses the free-text CR description and populates these fields.
    """

    change_order_number: str = Field(
        ...,
        description="The Change Order number (e.g., CHG0034512).",
    )
    mail_codes: list[str] = Field(
        ...,
        description="List of mail codes impacted by this change (e.g., ['45A', '99B']).",
    )
    lob_impacted: str = Field(
        ...,
        description="The Line of Business impacted (e.g., 'Retail Banking', 'Card Services').",
    )


class ChangeRequestRecord(BaseModel):
    """Represents a single Change Request record from the ServiceNow API response."""

    number: str = Field(..., description="Change Request number (e.g., CHG0034512).")
    state: str = Field(..., description="Current state of the CR (e.g., 'Scheduled').")
    short_description: str = Field(..., description="Brief summary of the change.")
    description: str = Field(..., description="Full description text of the change.")
    sys_id: str = Field(..., description="ServiceNow system ID for the record.")


class StakeholderInfo(BaseModel):
    """Stakeholder contact information for a given LOB."""

    qa_lead: str = Field(..., description="Primary QA lead email address.")
    qa_team: list[str] = Field(
        default_factory=list,
        description="List of QA team member email addresses.",
    )
    escalation: str = Field(
        default="",
        description="Escalation contact email address.",
    )


class NotificationPayload(BaseModel):
    """Complete payload assembled for email dispatch."""

    change_order_number: str
    short_description: str
    mail_codes: list[str]
    lob_impacted: str
    stakeholder: StakeholderInfo
    description: str

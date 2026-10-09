"""
Stakeholder mapping and email notification dispatch.

Maps extracted LOB data to QA stakeholders and sends formatted
notification emails through the internal SMTP server.
"""

from __future__ import annotations

import json
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

from src.schema import ImpactData, NotificationPayload, StakeholderInfo

load_dotenv()

logger = logging.getLogger(__name__)

# Path to the stakeholder mapping file
_STAKEHOLDER_MAP_PATH = Path(__file__).resolve().parent.parent / "config" / "stakeholder_map.json"


def _load_stakeholder_map() -> dict[str, dict]:
    """Load the LOB-to-stakeholder mapping from the config JSON file."""
    if not _STAKEHOLDER_MAP_PATH.exists():
        logger.error("Stakeholder map not found at %s", _STAKEHOLDER_MAP_PATH)
        raise FileNotFoundError(
            f"Stakeholder map not found: {_STAKEHOLDER_MAP_PATH}"
        )

    with open(_STAKEHOLDER_MAP_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    logger.info("Loaded stakeholder map with %d LOB entries.", len(data))
    return data


def map_stakeholders(impact: ImpactData) -> StakeholderInfo | None:
    """Look up the QA stakeholders for the extracted LOB.

    Args:
        impact: The structured impact data containing the LOB name.

    Returns:
        A StakeholderInfo model if a match is found, or None if the LOB
        is not in the mapping.
    """
    stakeholder_map = _load_stakeholder_map()

    lob = impact.lob_impacted

    # Try exact match first, then case-insensitive
    if lob in stakeholder_map:
        raw = stakeholder_map[lob]
    else:
        # Case-insensitive fallback
        normalized = {k.lower(): v for k, v in stakeholder_map.items()}
        raw = normalized.get(lob.lower())

    if raw is None:
        logger.warning(
            "No stakeholder mapping found for LOB '%s'. Available LOBs: %s",
            lob,
            list(stakeholder_map.keys()),
        )
        return None

    stakeholder = StakeholderInfo(**raw)
    logger.info(
        "Mapped LOB '%s' to QA Lead: %s",
        lob,
        stakeholder.qa_lead,
    )
    return stakeholder


def _build_email_body(payload: NotificationPayload) -> str:
    """Build a formatted HTML email body from the notification payload."""
    mail_codes_str = ", ".join(payload.mail_codes) if payload.mail_codes else "N/A"

    return f"""\
    <html>
    <body style="font-family: Arial, sans-serif; color: #333;">
        <h2 style="color: #1a5276;">🔔 Change Request Notification</h2>
        <table style="border-collapse: collapse; width: 100%; max-width: 600px;">
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">
                    Change Order
                </td>
                <td style="padding: 8px; border: 1px solid #ddd;">
                    {payload.change_order_number}
                </td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">
                    Summary
                </td>
                <td style="padding: 8px; border: 1px solid #ddd;">
                    {payload.short_description}
                </td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">
                    Impacted LOB
                </td>
                <td style="padding: 8px; border: 1px solid #ddd;">
                    {payload.lob_impacted}
                </td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">
                    Mail Codes
                </td>
                <td style="padding: 8px; border: 1px solid #ddd;">
                    {mail_codes_str}
                </td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">
                    QA Lead
                </td>
                <td style="padding: 8px; border: 1px solid #ddd;">
                    {payload.stakeholder.qa_lead}
                </td>
            </tr>
        </table>
        <h3>Description</h3>
        <p style="background: #f9f9f9; padding: 12px; border-left: 4px solid #1a5276;">
            {payload.description}
        </p>
        <hr>
        <p style="font-size: 0.85em; color: #888;">
            This is an automated notification from the ServiceNow AI Automation system.
        </p>
    </body>
    </html>
    """


def dispatch_notification(payload: NotificationPayload) -> bool:
    """Send the notification email via the internal SMTP server.

    Args:
        payload: The complete notification payload with stakeholder info.

    Returns:
        True if the email was sent successfully, False otherwise.
    """
    smtp_host = os.getenv("SMTP_HOST", "smtp.internal.bank.com")
    smtp_port = int(os.getenv("SMTP_PORT", "25"))
    from_address = os.getenv("SMTP_FROM_ADDRESS", "servicenow-automation@bank.com")

    recipients = payload.stakeholder.qa_team or [payload.stakeholder.qa_lead]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = (
        f"[CR Notification] {payload.change_order_number} — "
        f"{payload.short_description}"
    )
    msg["From"] = from_address
    msg["To"] = ", ".join(recipients)

    html_body = _build_email_body(payload)
    msg.attach(MIMEText(html_body, "html"))

    if os.getenv("MOCK_MODE", "false").lower() == "true":
        logger.info(
            "MOCK_MODE enabled: Simulated email notification sent for %s to %s",
            payload.change_order_number,
            recipients,
        )
        return True

    try:
        logger.info(
            "Dispatching notification for %s to %s via %s:%d",
            payload.change_order_number,
            recipients,
            smtp_host,
            smtp_port,
        )
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.sendmail(from_address, recipients, msg.as_string())

        logger.info(
            "Successfully sent notification for %s.",
            payload.change_order_number,
        )
        return True

    except Exception:
        logger.exception(
            "Failed to send notification for %s.",
            payload.change_order_number,
        )
        return False

"""
ServiceNow AI Automation — Seed Demo Data

Populates the SQLite database with realistic sample Change Requests,
pipeline runs, and notification audit logs so the dashboard can be
demonstrated and verified immediately.

Usage:
    python scripts/seed_demo_data.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure project root is in sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from api.database import SessionLocal, init_db
from api.models import CRStatus, NotificationLog, PipelineRun, ProcessedCR, RunStatus

SAMPLE_RECORDS = [
    {
        "cr_number": "CHG0034512",
        "sys_id": "sys_chg_001",
        "short_description": "Upgrade Retail Banking core payment gateway to v4.2",
        "description": "Scheduled deployment of retail payment gateway release 4.2. Impacted LOB: Retail Banking. Mail codes: 45A, 99B. Testing window: Saturday 02:00-06:00 UTC.",
        "lob_impacted": "Retail Banking",
        "mail_codes": "45A, 99B",
        "qa_lead": "jane.doe@bank.com",
        "recipients": "jane.doe@bank.com, john.smith@bank.com",
        "status": CRStatus.NOTIFIED,
        "minutes_ago": 12,
    },
    {
        "cr_number": "CHG0034513",
        "sys_id": "sys_chg_002",
        "short_description": "Commercial Treasury cash management schema migration",
        "description": "Database schema migration for Commercial Banking treasury ledger. Mail codes: 12C, 88D. Point of contact QA lead needed for signoff.",
        "lob_impacted": "Commercial Banking",
        "mail_codes": "12C, 88D",
        "qa_lead": "alice.wong@bank.com",
        "recipients": "alice.wong@bank.com, bob.kumar@bank.com",
        "status": CRStatus.NOTIFIED,
        "minutes_ago": 45,
    },
    {
        "cr_number": "CHG0034514",
        "sys_id": "sys_chg_003",
        "short_description": "Digital Channels mobile banking biometrics update",
        "description": "App store update for iOS/Android retail digital banking channels introducing FaceID authentication SDK v3. Mail code: 01A.",
        "lob_impacted": "Digital Channels",
        "mail_codes": "01A",
        "qa_lead": "grace.lee@bank.com",
        "recipients": "grace.lee@bank.com, henry.patel@bank.com",
        "status": CRStatus.NOTIFIED,
        "minutes_ago": 78,
    },
    {
        "cr_number": "CHG0034515",
        "sys_id": "sys_chg_004",
        "short_description": "Wealth Management portfolio rebalancing batch job tuning",
        "description": "Quarterly batch optimization for Wealth Management client reporting pipeline. Mail code: WM-88.",
        "lob_impacted": "Wealth Management",
        "mail_codes": "WM-88",
        "qa_lead": "carlos.reyes@bank.com",
        "recipients": "carlos.reyes@bank.com, diana.chen@bank.com",
        "status": CRStatus.NOTIFIED,
        "minutes_ago": 120,
    },
    {
        "cr_number": "CHG0034516",
        "sys_id": "sys_chg_005",
        "short_description": "Card Services fraud detection scoring engine ruleset update",
        "description": "Deployment of updated card fraud risk model parameters. Mail codes: CRD-04, CRD-09. All credit/debit card streams affected.",
        "lob_impacted": "Card Services",
        "mail_codes": "CRD-04, CRD-09",
        "qa_lead": "emily.taylor@bank.com",
        "recipients": "emily.taylor@bank.com, frank.nair@bank.com",
        "status": CRStatus.NOTIFIED,
        "minutes_ago": 180,
    },
    {
        "cr_number": "CHG0034517",
        "sys_id": "sys_chg_006",
        "short_description": "Retail branch workstation security agent patch",
        "description": "Patch deployment for retail branch terminals. Mail codes: 45A, 46B. Impacted LOB: Retail Banking.",
        "lob_impacted": "Retail Banking",
        "mail_codes": "45A, 46B",
        "qa_lead": "jane.doe@bank.com",
        "recipients": "jane.doe@bank.com, john.smith@bank.com",
        "status": CRStatus.NOTIFIED,
        "minutes_ago": 240,
    },
    {
        "cr_number": "CHG0034518",
        "sys_id": "sys_chg_007",
        "short_description": "Legacy mainframe batch job cleanup (missing metadata)",
        "description": "Decommission orphaned mainframe JCL scripts in environment partition B.",
        "lob_impacted": None,
        "mail_codes": None,
        "qa_lead": None,
        "recipients": None,
        "status": CRStatus.EXTRACTION_FAILED,
        "error_message": "LLM failed to extract structured data: description lacked LOB identifiers",
        "minutes_ago": 300,
    },
    {
        "cr_number": "CHG0034519",
        "sys_id": "sys_chg_008",
        "short_description": "Digital Channels push notification gateway certificate rotation",
        "description": "Rotate APNs and FCM TLS certificates for mobile notifications. Mail code: 01A. LOB: Digital Channels.",
        "lob_impacted": "Digital Channels",
        "mail_codes": "01A",
        "qa_lead": "grace.lee@bank.com",
        "recipients": "grace.lee@bank.com, henry.patel@bank.com",
        "status": CRStatus.NOTIFIED,
        "minutes_ago": 360,
    },
]


def seed_database() -> None:
    """Populate database with sample runs and Change Requests."""
    init_db()
    db = SessionLocal()

    try:
        now = datetime.now(timezone.utc)

        # Clear existing demo data to prevent duplicates if re-run
        db.query(NotificationLog).delete()
        db.query(ProcessedCR).delete()
        db.query(PipelineRun).delete()
        db.commit()

        # Create two pipeline runs: one completed earlier, one recent
        run_earlier = PipelineRun(
            trigger="scheduled",
            status=RunStatus.COMPLETED,
            started_at=now - timedelta(hours=6),
            finished_at=now - timedelta(hours=6, seconds=-14),
            tickets_found=4,
            tickets_notified=3,
        )
        db.add(run_earlier)
        db.commit()
        db.refresh(run_earlier)

        run_recent = PipelineRun(
            trigger="manual",
            status=RunStatus.COMPLETED,
            started_at=now - timedelta(minutes=15),
            finished_at=now - timedelta(minutes=14, seconds=42),
            tickets_found=4,
            tickets_notified=4,
        )
        db.add(run_recent)
        db.commit()
        db.refresh(run_recent)

        for i, item in enumerate(SAMPLE_RECORDS):
            target_run = run_recent if i < 4 else run_earlier
            item_time = now - timedelta(minutes=item["minutes_ago"])

            cr = ProcessedCR(
                pipeline_run_id=target_run.id,
                cr_number=item["cr_number"],
                sys_id=item["sys_id"],
                short_description=item["short_description"],
                description=item["description"],
                lob_impacted=item["lob_impacted"],
                mail_codes=item["mail_codes"],
                qa_lead=item["qa_lead"],
                status=item["status"],
                error_message=item.get("error_message"),
                processed_at=item_time,
                notified_at=item_time if item["status"] == CRStatus.NOTIFIED else None,
            )
            db.add(cr)
            db.commit()
            db.refresh(cr)

            if item["status"] == CRStatus.NOTIFIED:
                notif = NotificationLog(
                    processed_cr_id=cr.id,
                    recipients=item["recipients"],
                    subject=f"[CR Notification] {cr.cr_number} — {cr.short_description[:40]}",
                    success=1,
                    sent_at=item_time,
                )
                db.add(notif)
                db.commit()

        print(f"✅ Successfully seeded database with {len(SAMPLE_RECORDS)} sample CRs and 2 pipeline runs.")
        print("You can now run: python main.py --serve")
        print("And open: http://localhost:8000")

    finally:
        db.close()


if __name__ == "__main__":
    seed_database()

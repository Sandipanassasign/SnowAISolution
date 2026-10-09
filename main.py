"""
ServiceNow AI Automation — Main Entry Point

Supports three modes:
  python main.py              → One-shot pipeline run (CLI)
  python main.py --poll       → Continuous polling (CLI)
  python main.py --serve      → Web dashboard + API server (default port 8000)
"""

from __future__ import annotations

import logging
import os
import sys
import time

from dotenv import load_dotenv

load_dotenv()


def _configure_logging() -> None:
    """Set up structured logging based on LOG_LEVEL environment variable."""
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


def _run_cli_oneshot() -> None:
    """Run the pipeline once and exit (original CLI behavior)."""
    from src.llm_extractor import extract_impact_data
    from src.notifier import dispatch_notification, map_stakeholders
    from src.schema import NotificationPayload
    from src.snow_client import fetch_snow_tickets

    logger.info("═" * 60)
    logger.info("One-shot pipeline execution")
    logger.info("═" * 60)

    tickets = fetch_snow_tickets(state="Scheduled")

    if not tickets:
        logger.info("No scheduled Change Requests found.")
        return

    logger.info("Found %d ticket(s).", len(tickets))
    dispatched = 0

    for ticket in tickets:
        logger.info("Processing %s — %s", ticket.number, ticket.short_description)

        impact = extract_impact_data(ticket)
        if impact is None:
            logger.warning("Skipping %s: extraction failed.", ticket.number)
            continue

        stakeholder = map_stakeholders(impact)
        if stakeholder is None:
            logger.warning("Skipping %s: no stakeholder mapping.", ticket.number)
            continue

        payload = NotificationPayload(
            change_order_number=impact.change_order_number,
            short_description=ticket.short_description,
            mail_codes=impact.mail_codes,
            lob_impacted=impact.lob_impacted,
            stakeholder=stakeholder,
            description=ticket.description,
        )

        if dispatch_notification(payload):
            dispatched += 1

    logger.info("Done. Dispatched %d/%d notification(s).", dispatched, len(tickets))


def _run_cli_polling() -> None:
    """Run the pipeline in continuous polling mode."""
    interval = int(os.getenv("SNOW_POLL_INTERVAL_SECONDS", "300"))
    logger.info("Polling mode (interval: %ds). Press Ctrl+C to stop.", interval)

    while True:
        try:
            _run_cli_oneshot()
        except KeyboardInterrupt:
            logger.info("Polling stopped by user.")
            break
        except Exception:
            logger.exception("Pipeline error. Will retry.")

        time.sleep(interval)


def _run_server() -> None:
    """Start the FastAPI web server with dashboard."""
    import uvicorn

    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", "8000"))

    logger.info("Starting web server at http://%s:%d", host, port)
    logger.info("Dashboard: http://localhost:%d", port)
    logger.info("API docs:  http://localhost:%d/docs", port)

    uvicorn.run(
        "api.app:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


def main() -> None:
    """Entry point — dispatch to the correct mode."""
    _configure_logging()

    if "--serve" in sys.argv:
        _run_server()
    elif "--poll" in sys.argv:
        _run_cli_polling()
    else:
        _run_cli_oneshot()


if __name__ == "__main__":
    main()

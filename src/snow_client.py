"""
ServiceNow Change Request ingestion module.

Fetches scheduled Change Requests from the ServiceNow Table API,
respecting VDI SSL constraints and proxy configuration.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import requests
import urllib3
from dotenv import load_dotenv

from src.schema import ChangeRequestRecord

load_dotenv()

logger = logging.getLogger(__name__)


def _get_ssl_verify() -> bool | str:
    """Determine SSL verification setting based on environment.

    Returns:
        - Path to CA bundle if SSL_CERT_FILE or REQUESTS_CA_BUNDLE is set.
        - False if DISABLE_SSL_VERIFY is 'true' (local dev only).
        - True otherwise (default secure behavior).
    """
    cert_file = os.getenv("SSL_CERT_FILE") or os.getenv("REQUESTS_CA_BUNDLE")
    if cert_file:
        logger.info("Using custom CA bundle: %s", cert_file)
        return cert_file

    if os.getenv("DISABLE_SSL_VERIFY", "false").lower() == "true":
        logger.warning("SSL verification DISABLED — local dev mode only!")
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        return False

    return True


def _get_session() -> requests.Session:
    """Build a configured requests session with auth and SSL settings."""
    session = requests.Session()

    instance_url = os.getenv("SNOW_INSTANCE_URL")
    username = os.getenv("SNOW_USERNAME")
    password = os.getenv("SNOW_PASSWORD")

    if not instance_url:
        raise ValueError("SNOW_INSTANCE_URL environment variable is not set.")
    if not username or not password:
        raise ValueError("SNOW_USERNAME and SNOW_PASSWORD must be set.")

    session.auth = (username, password)
    session.headers.update({
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    session.verify = _get_ssl_verify()

    # Proxy configuration (if set)
    http_proxy = os.getenv("HTTP_PROXY")
    https_proxy = os.getenv("HTTPS_PROXY")
    if http_proxy or https_proxy:
        session.proxies = {
            "http": http_proxy or "",
            "https": https_proxy or "",
        }
        logger.info("Using proxy configuration.")

    return session


def fetch_snow_tickets(
    state: str = "Scheduled",
    limit: int = 50,
) -> list[ChangeRequestRecord]:
    """Poll ServiceNow for Change Requests in the specified state.

    Args:
        state: The CR state to filter on (default: 'Scheduled').
        limit: Maximum number of records to retrieve per request.

    Returns:
        A list of ChangeRequestRecord objects parsed from the API response.

    Raises:
        requests.HTTPError: If the ServiceNow API returns a non-2xx status.
    """
    if os.getenv("MOCK_MODE", "false").lower() == "true":
        logger.info("MOCK_MODE enabled: Returning synthetic Change Requests.")
        return [
            ChangeRequestRecord(
                number="CHG0034601",
                sys_id="mock_sys_001",
                state=state,
                short_description="Core Banking payment router microservice upgrade to v2.4",
                description="Deployment of payment router microservice. Impacted LOB: Retail Banking. Mail codes: 45A, 99B. Testing window: Saturday 02:00-05:00 UTC.",
            ),
            ChangeRequestRecord(
                number="CHG0034602",
                sys_id="mock_sys_002",
                state=state,
                short_description="Commercial Banking treasury ledger index optimization",
                description="Database re-indexing on Commercial Banking treasury trade ledger. Mail codes: 12C. All commercial clients affected during maintenance.",
            ),
        ]

    instance_url = os.getenv("SNOW_INSTANCE_URL", "").rstrip("/")
    endpoint = f"{instance_url}/api/now/table/change_request"

    params: dict[str, Any] = {
        "sysparm_query": f"state={state}",
        "sysparm_limit": str(limit),
        "sysparm_fields": "number,state,short_description,description,sys_id",
    }

    session = _get_session()

    logger.info(
        "Fetching change requests from %s (state=%s, limit=%d)",
        endpoint,
        state,
        limit,
    )

    response = session.get(endpoint, params=params)

    if not response.ok:
        logger.error(
            "ServiceNow API error [%d]: %s",
            response.status_code,
            response.text,
        )
        response.raise_for_status()

    payload = response.json()
    results: list[dict[str, Any]] = payload.get("result", [])

    logger.info("Retrieved %d change request(s).", len(results))

    records: list[ChangeRequestRecord] = []
    for raw_record in results:
        try:
            record = ChangeRequestRecord(**raw_record)
            records.append(record)
        except Exception:
            logger.exception(
                "Failed to parse CR record: %s",
                raw_record,
            )

    return records

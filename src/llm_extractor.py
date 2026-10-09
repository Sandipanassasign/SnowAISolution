"""
LLM-based impact data extraction using LlamaIndex structured outputs.

Takes an unstructured Change Request description and forces the LLM to
return structured ImpactData conforming to the Pydantic schema.
"""

from __future__ import annotations

import logging
import os

import httpx
from dotenv import load_dotenv
from llama_index.core.llms import ChatMessage
from llama_index.llms.openai_like import OpenAILike
from pydantic import ValidationError

from src.schema import ChangeRequestRecord, ImpactData

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Extraction prompt template
# ---------------------------------------------------------------------------
_EXTRACTION_SYSTEM_PROMPT = """\
You are a data extraction assistant for a banking Change Management system.
Given a Change Request description, extract the following fields as JSON:

1. **change_order_number**: The Change Order / CHG number (e.g., CHG0034512).
2. **mail_codes**: A JSON array of mail code strings mentioned (e.g., ["45A", "99B"]).
3. **lob_impacted**: The Line of Business impacted (e.g., "Retail Banking").

Respond ONLY with valid JSON matching this exact schema:
{
  "change_order_number": "<string>",
  "mail_codes": ["<string>", ...],
  "lob_impacted": "<string>"
}

If a field cannot be determined from the text, use "UNKNOWN" for strings
and an empty array [] for mail_codes.
Do NOT include any explanation, markdown fences, or extra text.
"""

_EXTRACTION_USER_TEMPLATE = """\
Change Request Number: {cr_number}
Description:
{description}
"""


def _build_llm() -> OpenAILike:
    """Construct the LlamaIndex LLM client with VDI-safe settings.

    Uses OpenAILike to point at any OpenAI-compatible endpoint
    (works with Azure, vLLM, Anthropic-bridge, etc.).
    """
    api_key = os.getenv("LLM_API_KEY")
    api_base = os.getenv("LLM_API_BASE_URL")
    model_name = os.getenv("LLM_MODEL_NAME", "claude-opus-4-20250514")

    if not api_key:
        raise ValueError("LLM_API_KEY environment variable is not set.")
    if not api_base:
        raise ValueError("LLM_API_BASE_URL environment variable is not set.")

    # Handle SSL for the LLM endpoint in VDI
    ssl_verify = os.getenv("DISABLE_SSL_VERIFY", "false").lower() != "true"
    cert_file = os.getenv("SSL_CERT_FILE") or os.getenv("REQUESTS_CA_BUNDLE")

    # Build a custom httpx client for VDI SSL constraints
    if cert_file:
        http_client = httpx.Client(verify=cert_file)
    elif not ssl_verify:
        logger.warning("SSL verification DISABLED for LLM endpoint — local dev only!")
        http_client = httpx.Client(verify=False)
    else:
        http_client = httpx.Client()

    return OpenAILike(
        model=model_name,
        api_key=api_key,
        api_base=api_base,
        is_chat_model=True,
        temperature=0.0,
        max_tokens=512,
        http_client=http_client,
    )


def extract_impact_data(
    record: ChangeRequestRecord,
) -> ImpactData | None:
    """Extract structured impact data from a Change Request using the LLM.

    Args:
        record: A ChangeRequestRecord containing the raw description text.

    Returns:
        An ImpactData model if extraction succeeds, or None on failure.
    """
    if os.getenv("MOCK_MODE", "false").lower() == "true":
        import re
        logger.info("MOCK_MODE enabled: Simulating LLM extraction for %s", record.number)
        lobs = ["Retail Banking", "Commercial Banking", "Digital Channels", "Wealth Management", "Card Services"]
        detected_lob = next((lob for lob in lobs if lob.lower() in (record.description or "").lower()), "Retail Banking")
        codes = re.findall(r"\b\d{2}[A-Z]\b", record.description or "")
        return ImpactData(
            change_order_number=record.number,
            mail_codes=codes or ["45A"],
            lob_impacted=detected_lob,
        )

    llm = _build_llm()

    user_content = _EXTRACTION_USER_TEMPLATE.format(
        cr_number=record.number,
        description=record.description,
    )

    messages = [
        ChatMessage(role="system", content=_EXTRACTION_SYSTEM_PROMPT),
        ChatMessage(role="user", content=user_content),
    ]

    try:
        response = llm.chat(messages)
        raw_output = response.message.content
        logger.debug("LLM raw output for %s: %s", record.number, raw_output)
    except Exception:
        logger.exception("LLM call failed for CR %s", record.number)
        return None

    # ------------------------------------------------------------------
    # Parse the LLM output into the Pydantic model
    # ------------------------------------------------------------------
    try:
        # Strip potential markdown fences the LLM might add despite instructions
        cleaned = raw_output.strip()
        if cleaned.startswith("```"):
            # Remove ```json ... ``` wrappers
            lines = cleaned.split("\n")
            cleaned = "\n".join(
                line for line in lines if not line.strip().startswith("```")
            )

        impact = ImpactData.model_validate_json(cleaned)
        logger.info(
            "Successfully extracted impact data for %s: LOB=%s, mail_codes=%s",
            record.number,
            impact.lob_impacted,
            impact.mail_codes,
        )
        return impact

    except (ValidationError, ValueError):
        logger.exception(
            "Failed to parse LLM output into ImpactData for CR %s. Raw output: %s",
            record.number,
            raw_output,
        )
        return None

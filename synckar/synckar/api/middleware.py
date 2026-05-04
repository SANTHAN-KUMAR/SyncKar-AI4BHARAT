"""
HMAC-SHA256 Webhook Signature Verification Middleware — AGENTS.md §5.
Verifies webhook payloads are authentically from known source systems.
"""

import hashlib
import hmac
from typing import Optional

import structlog
from fastapi import Request, HTTPException

from synckar.config import settings

logger = structlog.get_logger()

# Webhook secrets per system — in production, loaded from Vault
# For prototype, stored as env vars or set to a default
WEBHOOK_SECRETS: dict[str, str] = {
    "sws": "sws-webhook-secret-key",
    "shop_establishment": "shop-webhook-secret-key",
    "factories": "factories-webhook-secret-key",
}


def compute_hmac_sha256(payload: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 signature for a payload."""
    return hmac.new(
        key=secret.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()


async def verify_webhook_signature(
    request: Request,
    system_id: str,
    signature_header: Optional[str] = None,
) -> bool:
    """
    Verify the HMAC-SHA256 signature of a webhook request.
    The signature is expected in the X-Signature-256 header.
    Returns True if valid or if no secret is configured (dev mode).
    """
    secret = WEBHOOK_SECRETS.get(system_id)
    if not secret:
        logger.debug("webhook_no_secret_configured", system_id=system_id)
        return True  # No secret configured — dev mode

    # Get signature from header
    sig_header = signature_header or request.headers.get("X-Signature-256")
    if not sig_header:
        logger.warning("webhook_missing_signature", system_id=system_id)
        raise HTTPException(status_code=401, detail="Missing webhook signature")

    # Read and verify body
    body = await request.body()
    expected = compute_hmac_sha256(body, secret)

    if not hmac.compare_digest(sig_header, expected):
        logger.error(
            "webhook_signature_invalid",
            system_id=system_id,
            expected=expected[:16],
            received=sig_header[:16],
        )
        raise HTTPException(status_code=403, detail="Invalid webhook signature")

    logger.debug("webhook_signature_valid", system_id=system_id)
    return True

"""
Webhook receiver — POST /api/webhooks/{system_id}
For systems that can push events (Tier 2 adapters).
"""

import json
import time

import redis
import structlog
from fastapi import APIRouter, Request, HTTPException

from synckar.models.service_request import CanonicalServiceRequest
from synckar.pipeline.outbox import write_to_outbox
from synckar.api.middleware import verify_webhook_signature
from synckar.config import settings

logger = structlog.get_logger()
router = APIRouter()


def _check_rate_limit(system_id: str, limit: int, window_seconds: int = 60) -> bool:
    r = redis.Redis.from_url(settings.redis.url, decode_responses=True)
    key = f"webhook_rate_limit:{system_id}"
    now = int(time.time())
    member = f"{now}-{time.time_ns()}"

    pipe = r.pipeline()
    pipe.zremrangebyscore(key, 0, now - window_seconds)
    pipe.zadd(key, {member: now})
    pipe.zcard(key)
    pipe.expire(key, window_seconds)
    results = pipe.execute()

    return results[2] <= limit


@router.post("/{system_id}")
async def receive_webhook(system_id: str, request: Request):
    """
    Receive a webhook push from an external system.
    The payload is translated and written to the outbox.
    """
    # Rate limit to protect ingress
    if not _check_rate_limit(system_id, settings.webhook_rate_limit_per_minute):
        raise HTTPException(status_code=429, detail="Webhook rate limit exceeded")

    # Verify signature (reject if invalid or missing when secret is configured)
    await verify_webhook_signature(request, system_id)

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    logger.info("webhook_received", system_id=system_id, ubid=body.get("ubid"))

    # Route to the appropriate adapter's translate_inbound
    if system_id == "sws":
        from synckar.adapters.sws.translator import translate_inbound
        event = translate_inbound(body)
        topic = "sws.changes"
    elif system_id == "shop_establishment":
        from synckar.adapters.departments.shop_establishment.translator import translate_inbound
        event = translate_inbound(body)
        topic = "dept.shop_establishment.changes"
    elif system_id == "factories":
        from synckar.adapters.departments.factories.translator import translate_inbound
        event = translate_inbound(body)
        topic = "dept.factories.changes"
    else:
        raise HTTPException(status_code=404, detail=f"Unknown system_id: {system_id}")

    write_to_outbox(event, topic=topic)

    return {
        "status": "accepted",
        "correlation_id": str(event.correlation_id),
        "ubid": event.ubid,
    }

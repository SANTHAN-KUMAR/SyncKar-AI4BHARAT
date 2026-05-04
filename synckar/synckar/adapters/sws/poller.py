"""
SWS Adapter — poller module.
High-water mark polling for the SWS system.
Maintains watermark in Redis. Silently skips records without UBID (C10).
"""

from datetime import datetime, timezone

import structlog

from synckar.config import settings
from synckar.adapters.sws.client import SWSClient
from synckar.adapters.sws.translator import translate_inbound
from synckar.models.service_request import CanonicalServiceRequest
from synckar.observability.drift_detector import DriftDetector
from synckar.pipeline import loop_guard, watermark

logger = structlog.get_logger()

SYSTEM_ID = "sws"


class SWSPoller:
    """Stateful poller for SWS changes using high-water mark strategy."""

    def __init__(
        self,
        client: SWSClient | None = None,
    ):
        self.client = client or SWSClient()

    def get_watermark(self) -> str:
        """Get the last-processed watermark from Redis/DB."""
        return watermark.get_watermark(SYSTEM_ID, "2000-01-01T00:00:00Z")

    def set_watermark(self, value: str) -> None:
        """Update the watermark in Redis/DB."""
        watermark.set_watermark(SYSTEM_ID, value)

    def poll(self) -> list[CanonicalServiceRequest]:
        """
        Poll SWS for changes since the last watermark.
        Returns a list of CanonicalServiceRequest events.
        Silently skips records without UBID (C10).
        """
        watermark = self.get_watermark()
        logger.debug("sws_polling", since=watermark)

        raw_changes = self.client.poll_changes(since=watermark)

        if not raw_changes:
            return []

        # Run drift detection on the first raw change
        drift_detector = DriftDetector(
            system_id="sws",
            expected_fields={"ubid", "event_id", "field_name", "old_value", "new_value", "timestamp", "source"}
        )
        drift_detector.check(raw_changes[0])

        events = []
        latest_timestamp = watermark

        for change in raw_changes:
            ubid = change.get("ubid")

            # C10: Records without UBID are silently skipped
            if not ubid:
                logger.debug("sws_skip_no_ubid", change=change)
                continue

            try:
                if loop_guard.is_recent_write(
                    SYSTEM_ID,
                    ubid,
                    change.get("field_name", ""),
                    str(change.get("new_value", "")),
                ):
                    logger.debug("loop_guard_skip", system=SYSTEM_ID, ubid=ubid)
                    continue
                event = translate_inbound(change)
                events.append(event)

                # Track latest timestamp for watermark update
                ts = change.get("timestamp", "")
                if ts > latest_timestamp:
                    latest_timestamp = ts

            except Exception as e:
                logger.error(
                    "sws_translate_error",
                    ubid=ubid,
                    error=str(e),
                )
                continue

        # Update watermark to latest processed timestamp
        if latest_timestamp > watermark:
            self.set_watermark(latest_timestamp)
            logger.info(
                "sws_poll_complete",
                changes_found=len(events),
                new_watermark=latest_timestamp,
            )

        return events

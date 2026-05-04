"""
Factories Adapter — poller module.
High-water mark polling (Tier 3).
# DECISION: Using high-water mark instead of snapshot diff for prototype simplicity.
Silently skips records without UBID (C10).
"""

import structlog

from synckar.config import settings
from synckar.adapters.departments.factories.client import FactoriesClient
from synckar.adapters.departments.factories.translator import translate_inbound
from synckar.models.service_request import CanonicalServiceRequest
from synckar.observability.drift_detector import DriftDetector
from synckar.pipeline import loop_guard, watermark

logger = structlog.get_logger()

SYSTEM_ID = "factories"


class FactoriesPoller:
    """High-water mark poller for Factories department."""

    def __init__(
        self,
        client: FactoriesClient | None = None,
    ):
        self.client = client or FactoriesClient()

    def get_watermark(self) -> str:
        return watermark.get_watermark(SYSTEM_ID, "2000-01-01T00:00:00Z")

    def set_watermark(self, value: str) -> None:
        watermark.set_watermark(SYSTEM_ID, value)

    def poll(self) -> list[CanonicalServiceRequest]:
        watermark = self.get_watermark()
        raw_changes = self.client.poll_changes(since=watermark)
        if not raw_changes:
            return []

        # Run drift detection on the first raw change
        drift_detector = DriftDetector(
            system_id="factories",
            expected_fields={"ubid", "field_name", "old_value", "new_value", "timestamp"}
        )
        drift_detector.check(raw_changes[0])

        events = []
        latest = watermark
        for change in raw_changes:
            # C10: Records without UBID are silently skipped
            if not change.get("ubid"):
                logger.debug("factories_skip_no_ubid")
                continue
            try:
                if loop_guard.is_recent_write(
                    SYSTEM_ID,
                    change.get("ubid", ""),
                    change.get("field_name", ""),
                    str(change.get("new_value", "")),
                ):
                    logger.debug("loop_guard_skip", system=SYSTEM_ID, ubid=change.get("ubid"))
                    continue
                event = translate_inbound(change)
                events.append(event)
                ts = change.get("timestamp", "")
                if ts > latest:
                    latest = ts
            except Exception as e:
                logger.error("factories_translate_error", error=str(e))

        if latest > watermark:
            self.set_watermark(latest)
        logger.info("factories_poll_complete", changes=len(events))
        return events

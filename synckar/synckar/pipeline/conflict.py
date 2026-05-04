"""
Conflict Detection & Resolution — AGENTS.md §8, ARCHITECTURE.md §6.

Sliding-window conflict detector:
  - Redis key: conflict_window:{ubid}:{field_name} with TTL = conflict_window_seconds
  - Value: JSON {source_system, broker_sequence, payload_hash, correlation_id}
  - If key exists from a DIFFERENT source → conflict detected

Policy Matrix (implement exactly — AGENTS.md §8):
  - UNIVERSAL_DEMOGRAPHICS: SWS wins (source priority)
  - REGULATORY_COMPLIANCE:  Department wins (domain priority)
  - UNRESTRICTED_METADATA:  LWW — higher broker_sequence wins
  - UNMAPPED:               DLQ — alert Data Steward

Critical invariant: ALWAYS write ConflictAuditRecord after any conflict (C5).
"""

import json
from enum import Enum
from uuid import UUID

import redis
import structlog

from synckar.config import settings
from synckar.models.audit import ConflictAuditRecord
from synckar.models.service_request import CanonicalServiceRequest

logger = structlog.get_logger()


class DataCategory(str, Enum):
    """Data categories that drive conflict resolution policy."""
    UNIVERSAL_DEMOGRAPHICS = "universal_demographics"  # SWS_WINS
    REGULATORY_COMPLIANCE = "regulatory_compliance"    # DEPT_WINS
    UNRESTRICTED_METADATA = "unrestricted_metadata"    # LWW (higher broker_sequence)
    UNMAPPED = "unmapped"                              # DLQ — alert Data Steward


class ResolutionPolicy(str, Enum):
    """Resolution policies applied to conflicts."""
    SWS_WINS = "SWS_WINS"
    DEPT_WINS = "DEPT_WINS"
    LAST_WRITE_WINS = "LAST_WRITE_WINS"
    DLQ = "DLQ"


# Exact field-to-category mapping from AGENTS.md §8
FIELD_CATEGORY_MAP: dict[str, DataCategory] = {
    "registered_address": DataCategory.UNIVERSAL_DEMOGRAPHICS,
    "primary_contact": DataCategory.UNIVERSAL_DEMOGRAPHICS,
    "authorized_signatory": DataCategory.UNIVERSAL_DEMOGRAPHICS,
    "license_status": DataCategory.REGULATORY_COMPLIANCE,
    "safety_clearance": DataCategory.REGULATORY_COMPLIANCE,
    "labor_violations": DataCategory.REGULATORY_COMPLIANCE,
    "employee_headcount": DataCategory.UNRESTRICTED_METADATA,
    "operational_status": DataCategory.UNRESTRICTED_METADATA,
    "last_inspection_date": DataCategory.UNRESTRICTED_METADATA,
}

# Category → policy mapping
CATEGORY_POLICY_MAP: dict[DataCategory, ResolutionPolicy] = {
    DataCategory.UNIVERSAL_DEMOGRAPHICS: ResolutionPolicy.SWS_WINS,
    DataCategory.REGULATORY_COMPLIANCE: ResolutionPolicy.DEPT_WINS,
    DataCategory.UNRESTRICTED_METADATA: ResolutionPolicy.LAST_WRITE_WINS,
    DataCategory.UNMAPPED: ResolutionPolicy.DLQ,
}


class ConflictWindowEntry:
    """Data stored in the Redis sliding window for conflict detection."""

    def __init__(
        self,
        source_system: str,
        broker_sequence: int | None,
        correlation_id: str,
        value: str,
    ):
        self.source_system = source_system
        self.broker_sequence = broker_sequence
        self.correlation_id = correlation_id
        self.value = value

    def to_json(self) -> str:
        return json.dumps({
            "source_system": self.source_system,
            "broker_sequence": self.broker_sequence,
            "correlation_id": self.correlation_id,
            "value": self.value,
        })

    @classmethod
    def from_json(cls, data: str) -> "ConflictWindowEntry":
        d = json.loads(data)
        return cls(
            source_system=d["source_system"],
            broker_sequence=d.get("broker_sequence"),
            correlation_id=d["correlation_id"],
            value=d["value"],
        )


class SlidingWindowConflictDetector:
    """
    Checks for conflicting events within a configurable time window.
    Uses Redis TTL keys for automatic window expiry.

    Key pattern: conflict_window:{ubid}:{field_name}
    TTL: conflict_window_seconds (default 900s / 15 minutes)
    """

    def __init__(self, redis_client: redis.Redis | None = None):
        if redis_client:
            self._redis = redis_client
        else:
            self._redis = redis.Redis.from_url(
                settings.redis.url,
                decode_responses=True,
            )
        self._window_ttl = settings.pipeline.conflict_window_seconds

    def check_and_register(
        self,
        event: CanonicalServiceRequest,
    ) -> ConflictWindowEntry | None:
        """
        Check if a conflicting event exists in the window for this UBID + field.
        If no conflict, register this event in the window.

        Returns:
            ConflictWindowEntry of the EXISTING event if conflict detected.
            None if no conflict.
        """
        key = self._make_key(event.ubid, event.field_name)

        try:
            existing_raw = self._redis.get(key)

            if existing_raw:
                existing = ConflictWindowEntry.from_json(existing_raw)

                # Conflict only if from a DIFFERENT source system
                if existing.source_system != event.source_system.value:
                    logger.warning(
                        "conflict_detected",
                        ubid=event.ubid,
                        field=event.field_name,
                        source_a=existing.source_system,
                        source_b=event.source_system.value,
                        broker_seq_a=existing.broker_sequence,
                        broker_seq_b=event.broker_sequence,
                    )
                    return existing

            # Same-source update — preserve TTL to avoid extending window
            if existing_raw and existing.source_system == event.source_system.value:
                if existing.value == event.new_value:
                    return None
                ttl = self._redis.ttl(key)
                ttl = ttl if ttl and ttl > 0 else self._window_ttl
                new_entry = ConflictWindowEntry(
                    source_system=event.source_system.value,
                    broker_sequence=event.broker_sequence,
                    correlation_id=str(event.correlation_id),
                    value=event.new_value,
                )
                self._redis.set(key, new_entry.to_json(), ex=ttl)
                return None

            # No conflict — register this event in the window
            new_entry = ConflictWindowEntry(
                source_system=event.source_system.value,
                broker_sequence=event.broker_sequence,
                correlation_id=str(event.correlation_id),
                value=event.new_value,
            )
            self._redis.set(key, new_entry.to_json(), ex=self._window_ttl)

            return None

        except redis.ConnectionError as e:
            logger.warning("redis_unavailable_conflict", error=str(e))
            # Redis down — proceed without conflict detection
            # (conservative: we'd rather miss a conflict than block propagation)
            return None

    @staticmethod
    def _make_key(ubid: str, field_name: str) -> str:
        """Redis key pattern from ARCHITECTURE.md §6."""
        return f"conflict_window:{ubid}:{field_name}"


def get_field_category(field_name: str) -> DataCategory:
    """Look up the data category for a field. Defaults to UNMAPPED."""
    return FIELD_CATEGORY_MAP.get(field_name, DataCategory.UNMAPPED)


def get_resolution_policy(category: DataCategory) -> ResolutionPolicy:
    """Get the resolution policy for a data category."""
    return CATEGORY_POLICY_MAP[category]


def compute_temporal_confidence(
    source_a_tier: int,
    source_b_tier: int,
) -> str:
    """
    Compute temporal confidence based on adapter tiers.
    ARCHITECTURE.md §6:
      HIGH   = both sources are webhook/real-time (tier 1-2)
      MEDIUM = one source is polling-based (tier 3-4)
      LOW    = both sources are polling-based or snapshot-derived
    """
    a_realtime = source_a_tier <= 2
    b_realtime = source_b_tier <= 2

    if a_realtime and b_realtime:
        return "HIGH"
    elif a_realtime or b_realtime:
        return "MEDIUM"
    else:
        return "LOW"


def resolve_conflict(
    incoming_event: CanonicalServiceRequest,
    existing_entry: ConflictWindowEntry,
    incoming_tier: int = 1,
    existing_tier: int = 1,
) -> ConflictAuditRecord:
    """
    Apply the Policy Matrix to resolve a detected conflict.
    ALWAYS returns a ConflictAuditRecord — never silently proceeds (C5).

    The caller is responsible for:
    1. Persisting the ConflictAuditRecord to the conflict_log table.
    2. Either propagating the winning value or routing to DLQ.
    """
    category = get_field_category(incoming_event.field_name)
    policy = get_resolution_policy(category)
    temporal_conf = compute_temporal_confidence(incoming_tier, existing_tier)

    incoming_is_sws = incoming_event.source_system.value == "sws"
    existing_is_sws = existing_entry.source_system == "sws"

    # Apply policy
    if policy == ResolutionPolicy.SWS_WINS:
        if incoming_is_sws:
            winning_value = incoming_event.new_value
            losing_value = existing_entry.value
        else:
            winning_value = existing_entry.value
            losing_value = incoming_event.new_value

    elif policy == ResolutionPolicy.DEPT_WINS:
        if incoming_is_sws:
            winning_value = existing_entry.value
            losing_value = incoming_event.new_value
        else:
            winning_value = incoming_event.new_value
            losing_value = existing_entry.value

    elif policy == ResolutionPolicy.LAST_WRITE_WINS:
        # Higher broker_sequence wins — ARCHITECTURE.md §6
        incoming_seq = incoming_event.broker_sequence or 0
        existing_seq = existing_entry.broker_sequence or 0
        if incoming_seq >= existing_seq:
            winning_value = incoming_event.new_value
            losing_value = existing_entry.value
        else:
            winning_value = existing_entry.value
            losing_value = incoming_event.new_value

    else:  # DLQ
        winning_value = ""  # No winner — both go to DLQ
        losing_value = ""

    record = ConflictAuditRecord(
        correlation_id=incoming_event.correlation_id,
        ubid=incoming_event.ubid,
        field=incoming_event.field_name,
        source_a_system=existing_entry.source_system,
        source_a_value=existing_entry.value,
        source_a_broker_seq=existing_entry.broker_sequence,
        source_b_system=incoming_event.source_system.value,
        source_b_value=incoming_event.new_value,
        source_b_broker_seq=incoming_event.broker_sequence,
        policy_applied=policy.value,
        winning_value=winning_value,
        losing_value=losing_value,
        temporal_confidence=temporal_conf,
    )

    logger.info(
        "conflict_resolved",
        ubid=incoming_event.ubid,
        field=incoming_event.field_name,
        policy=policy.value,
        winning_value=winning_value[:50],
        temporal_confidence=temporal_conf,
    )

    return record

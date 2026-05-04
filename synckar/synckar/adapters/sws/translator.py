"""
SWS Adapter — translator module.
Translates between SWS native format and CanonicalServiceRequest.
SWS is the canonical system, so translation is minimal (field names match).
"""

from uuid import uuid4

import structlog

from synckar.exceptions import TranslationError
from synckar.models.service_request import (
    CanonicalServiceRequest,
    RequestType,
    SourceSystem,
    derive_event_id,
)

logger = structlog.get_logger()

# SWS field names are canonical — they match CanonicalServiceRequest directly
FIELD_TO_REQUEST_TYPE = {
    "registered_address": RequestType.ADDRESS_CHANGE,
    "primary_contact": RequestType.ADDRESS_CHANGE,
    "authorized_signatory": RequestType.SIGNATORY_UPDATE,
    "employee_headcount": RequestType.CLOSURE_REQUEST,
    "operational_status": RequestType.CLOSURE_REQUEST,
    "license_status": RequestType.LICENSE_RENEWAL,
    "safety_clearance": RequestType.LICENSE_RENEWAL,
    "last_inspection_date": RequestType.LICENSE_RENEWAL,
}


def translate_inbound(raw_change: dict, mapping_version: str = "v1") -> CanonicalServiceRequest:
    """
    Translate a raw SWS change event into a CanonicalServiceRequest.
    SWS fields are canonical, so this is a direct mapping.

    The raw_change dict is expected to have:
      ubid, field_name, old_value, new_value, event_id (optional), timestamp
    """
    ubid = raw_change.get("ubid")
    if not ubid:
        raise TranslationError(
            "SWS change event missing UBID",
            system_id="sws",
        )

    field_name = raw_change.get("field_name", "")
    old_value = raw_change.get("old_value")
    new_value = raw_change.get("new_value", "")

    # Use native event_id if available, otherwise derive one
    event_id = raw_change.get("event_id")
    if not event_id:
        event_id = derive_event_id(ubid, field_name, old_value, new_value)

    request_type = FIELD_TO_REQUEST_TYPE.get(field_name, RequestType.ADDRESS_CHANGE)

    return CanonicalServiceRequest(
        correlation_id=uuid4(),
        ubid=ubid,
        request_type=request_type,
        source_system=SourceSystem.SWS,
        source_event_id=event_id,
        field_name=field_name,
        old_value=old_value,
        new_value=str(new_value),
        raw_payload=raw_change,
        mapping_version=mapping_version,
    )


def translate_outbound(request: CanonicalServiceRequest) -> dict:
    """
    Translate a CanonicalServiceRequest into SWS API update format.
    SWS fields are canonical — direct mapping.
    """
    return {
        request.field_name: request.new_value,
        "modified_by": f"synckar_{request.source_system.value}",
    }

"""
Factories Adapter — translator module.
Uses versioned mapping YAMLs for bidirectional field translation.
# DECISION: Using REST client for prototype. Production would use zeep SOAP client.
"""

import os
from uuid import uuid4

import structlog

from synckar.exceptions import TranslationError
from synckar.models.service_request import (
    CanonicalServiceRequest,
    RequestType,
    SourceSystem,
    derive_event_id,
)
from synckar.models.mapping import load_mapping, apply_transform, AdapterMapping

logger = structlog.get_logger()

FIELD_TO_REQUEST_TYPE = {
    "registered_address": RequestType.ADDRESS_CHANGE,
    "primary_contact": RequestType.ADDRESS_CHANGE,
    "authorized_signatory": RequestType.SIGNATORY_UPDATE,
    "license_status": RequestType.LICENSE_RENEWAL,
    "safety_clearance": RequestType.LICENSE_RENEWAL,
    "labor_violations": RequestType.LICENSE_RENEWAL,
    "employee_headcount": RequestType.CLOSURE_REQUEST,
    "operational_status": RequestType.CLOSURE_REQUEST,
    "last_inspection_date": RequestType.LICENSE_RENEWAL,
}

_SCHEMA_REGISTRY_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "schema_registry", "factories"
)
_MAPPING_DIR = os.path.join(os.path.dirname(__file__), "mappings")
_mapping_cache: dict[str, AdapterMapping] = {}


def _get_mapping(version: str = "v1") -> AdapterMapping:
    if version not in _mapping_cache:
        for base_dir in [_SCHEMA_REGISTRY_DIR, _MAPPING_DIR]:
            path = os.path.join(base_dir, f"mapping_{version}.yaml")
            if os.path.exists(path):
                _mapping_cache[version] = load_mapping(path)
                return _mapping_cache[version]
        raise TranslationError(
            f"Mapping version {version} not found for factories",
            system_id="factories",
        )
    return _mapping_cache[version]


def translate_inbound(
    raw_change: dict,
    mapping_version: str = "v1",
) -> CanonicalServiceRequest:
    """Translate Factories change → CanonicalServiceRequest (reverse mapping)."""
    ubid = raw_change.get("ubid")
    if not ubid:
        raise TranslationError("Factories change missing UBID", system_id="factories")

    mapping = _get_mapping(mapping_version)
    dept_field = raw_change.get("field_name", "")
    old_value = raw_change.get("old_value")
    new_value = raw_change.get("new_value", "")

    fm = mapping.get_source_field(dept_field)
    canonical_field = fm.source_field if fm else dept_field

    event_id = raw_change.get("event_id")
    if not event_id:
        event_id = derive_event_id(ubid, canonical_field, old_value, new_value)

    return CanonicalServiceRequest(
        correlation_id=uuid4(),
        ubid=ubid,
        request_type=FIELD_TO_REQUEST_TYPE.get(canonical_field, RequestType.ADDRESS_CHANGE),
        source_system=SourceSystem.FACTORIES,
        source_event_id=event_id,
        field_name=canonical_field,
        old_value=old_value,
        new_value=str(new_value),
        raw_payload=raw_change,
        mapping_version=mapping_version,
    )


def translate_outbound(request: CanonicalServiceRequest) -> dict:
    """Translate CanonicalServiceRequest → Factories native format (forward mapping)."""
    mapping = _get_mapping(request.mapping_version)
    fm = mapping.get_target_field(request.field_name)

    if not fm:
        logger.warning("factories_unmapped_field", field=request.field_name)
        return {request.field_name: request.new_value}

    transformed = apply_transform(request.new_value, fm.transform)
    return {fm.target_field: transformed}

"""
Shop Establishment Adapter — translator module.
Uses versioned mapping YAMLs for bidirectional field translation.
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
    "employee_headcount": RequestType.CLOSURE_REQUEST,
    "operational_status": RequestType.CLOSURE_REQUEST,
}

_MAPPING_DIR = os.path.join(os.path.dirname(__file__), "mappings")
_SCHEMA_REGISTRY_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "schema_registry", "shop_establishment"
)

_mapping_cache: dict[str, AdapterMapping] = {}


def _get_mapping(version: str = "v1") -> AdapterMapping:
    """Load and cache the mapping YAML for the given version."""
    if version not in _mapping_cache:
        for base_dir in [_SCHEMA_REGISTRY_DIR, _MAPPING_DIR]:
            path = os.path.join(base_dir, f"mapping_{version}.yaml")
            if os.path.exists(path):
                _mapping_cache[version] = load_mapping(path)
                return _mapping_cache[version]
        raise TranslationError(
            f"Mapping version {version} not found for shop_establishment",
            system_id="shop_establishment",
        )
    return _mapping_cache[version]


def translate_inbound(
    raw_change: dict,
    mapping_version: str = "v1",
) -> CanonicalServiceRequest:
    """
    Translate a Shop Establishment change into CanonicalServiceRequest.
    Uses REVERSE mapping: target_field → source_field.
    """
    ubid = raw_change.get("ubid")
    if not ubid:
        raise TranslationError(
            "Shop Est change missing UBID",
            system_id="shop_establishment",
        )

    mapping = _get_mapping(mapping_version)
    dept_field = raw_change.get("field_name", "")
    old_value = raw_change.get("old_value")
    new_value = raw_change.get("new_value", "")

    # Reverse lookup: dept field → canonical field
    fm = mapping.get_source_field(dept_field)
    canonical_field = fm.source_field if fm else dept_field

    event_id = raw_change.get("event_id")
    if not event_id:
        event_id = derive_event_id(ubid, canonical_field, old_value, new_value)

    return CanonicalServiceRequest(
        correlation_id=uuid4(),
        ubid=ubid,
        request_type=FIELD_TO_REQUEST_TYPE.get(canonical_field, RequestType.ADDRESS_CHANGE),
        source_system=SourceSystem.SHOP_ESTABLISHMENT,
        source_event_id=event_id,
        field_name=canonical_field,
        old_value=old_value,
        new_value=str(new_value),
        raw_payload=raw_change,
        mapping_version=mapping_version,
    )


def translate_outbound(request: CanonicalServiceRequest) -> dict:
    """
    Translate a CanonicalServiceRequest into Shop Est native format.
    Uses FORWARD mapping: source_field → target_field + transform.
    """
    mapping = _get_mapping(request.mapping_version)
    fm = mapping.get_target_field(request.field_name)

    if not fm:
        logger.warning(
            "shop_unmapped_field",
            field=request.field_name,
            version=request.mapping_version,
        )
        return {request.field_name: request.new_value}

    transformed_value = apply_transform(request.new_value, fm.transform)
    return {fm.target_field: transformed_value}

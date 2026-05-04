"""
Unit tests for adapter translators and clients — AGENTS.md §7, §15.

Covers:
  - SWS translate_inbound: happy path + missing UBID error
  - SWS translate_outbound: direct field mapping
  - Factories translate_inbound: reverse mapping (dept field → canonical)
  - Factories translate_outbound: forward mapping + transform
  - Shop translate_inbound: reverse mapping
  - Shop translate_outbound: forward mapping + truncate transform
  - Client HTTP error mapping: 4xx → PermanentWriteError, 5xx → TargetWriteError
  - UBID not found → UBIDNotFound
"""

from unittest import mock

import pytest
import httpx

from synckar.exceptions import (
    PermanentWriteError,
    TargetWriteError,
    TranslationError,
    UBIDNotFound,
)
from synckar.models.service_request import (
    CanonicalServiceRequest,
    RequestType,
    SourceSystem,
)


# ─── SWS Translator ───────────────────────────────────────────────────────────

class TestSWSTranslator:
    def test_translate_inbound_happy_path(self):
        from synckar.adapters.sws.translator import translate_inbound

        raw = {
            "ubid": "KA-TEST-0001",
            "field_name": "registered_address",
            "old_value": "Old Addr",
            "new_value": "New Addr",
            "timestamp": "2026-01-01T00:00:00Z",
            "event_id": "sws-evt-001",
        }
        event = translate_inbound(raw)

        assert event.ubid == "KA-TEST-0001"
        assert event.field_name == "registered_address"
        assert event.new_value == "New Addr"
        assert event.source_system == SourceSystem.SWS
        assert event.source_event_id == "sws-evt-001"

    def test_translate_inbound_derives_event_id_when_missing(self):
        from synckar.adapters.sws.translator import translate_inbound

        raw = {
            "ubid": "KA-TEST-0001",
            "field_name": "registered_address",
            "old_value": "Old",
            "new_value": "New",
            "timestamp": "2026-01-01T00:00:00Z",
            # no event_id
        }
        event = translate_inbound(raw)
        assert event.source_event_id is not None
        assert len(event.source_event_id) == 16  # derive_event_id returns 16 chars

    def test_translate_inbound_raises_on_missing_ubid(self):
        from synckar.adapters.sws.translator import translate_inbound

        raw = {"field_name": "registered_address", "new_value": "New"}
        with pytest.raises(TranslationError):
            translate_inbound(raw)

    def test_translate_outbound_direct_mapping(self):
        from synckar.adapters.sws.translator import translate_outbound

        event = CanonicalServiceRequest(
            ubid="KA-TEST-0001",
            request_type=RequestType.ADDRESS_CHANGE,
            source_system=SourceSystem.FACTORIES,
            source_event_id="evt_001",
            field_name="authorized_signatory",
            new_value="Rajesh Kumar",
            raw_payload={},
        )
        result = translate_outbound(event)

        assert result["authorized_signatory"] == "Rajesh Kumar"
        assert "modified_by" in result

    def test_translate_inbound_signatory_maps_to_signatory_update_type(self):
        from synckar.adapters.sws.translator import translate_inbound

        raw = {
            "ubid": "KA-TEST-0001",
            "field_name": "authorized_signatory",
            "old_value": "Old Name",
            "new_value": "New Name",
            "timestamp": "2026-01-01T00:00:00Z",
        }
        event = translate_inbound(raw)
        assert event.request_type == RequestType.SIGNATORY_UPDATE


# ─── Factories Translator ─────────────────────────────────────────────────────

class TestFactoriesTranslator:
    @pytest.fixture(autouse=True)
    def patch_mapping(self):
        from synckar.models.mapping import AdapterMapping, FieldMapping
        mapping = AdapterMapping(
            version="v1",
            certified_by="test",
            fields=[
                FieldMapping(source_field="registered_address", target_field="factory_address", transform="none"),
                FieldMapping(source_field="authorized_signatory", target_field="signatory_name", transform="none"),
                FieldMapping(source_field="employee_headcount", target_field="worker_count", transform="int"),
            ],
        )
        with mock.patch("synckar.adapters.departments.factories.translator._get_mapping", return_value=mapping):
            yield

    def test_translate_inbound_reverse_maps_dept_field(self):
        from synckar.adapters.departments.factories.translator import translate_inbound

        raw = {
            "ubid": "KA-TEST-0001",
            "field_name": "factory_address",  # dept field
            "old_value": "Old",
            "new_value": "New Factory Addr",
            "timestamp": "2026-01-01T00:00:00Z",
        }
        event = translate_inbound(raw)

        assert event.field_name == "registered_address"  # canonical field
        assert event.new_value == "New Factory Addr"
        assert event.source_system == SourceSystem.FACTORIES

    def test_translate_inbound_raises_on_missing_ubid(self):
        from synckar.adapters.departments.factories.translator import translate_inbound

        with pytest.raises(TranslationError):
            translate_inbound({"field_name": "factory_address", "new_value": "x"})

    def test_translate_outbound_forward_maps_canonical_field(self):
        from synckar.adapters.departments.factories.translator import translate_outbound

        event = CanonicalServiceRequest(
            ubid="KA-TEST-0001",
            request_type=RequestType.ADDRESS_CHANGE,
            source_system=SourceSystem.SWS,
            source_event_id="evt_001",
            field_name="registered_address",
            new_value="999 MG Road",
            raw_payload={},
        )
        result = translate_outbound(event)

        assert "factory_address" in result
        assert result["factory_address"] == "999 MG Road"

    def test_translate_outbound_applies_int_transform(self):
        from synckar.adapters.departments.factories.translator import translate_outbound

        event = CanonicalServiceRequest(
            ubid="KA-TEST-0001",
            request_type=RequestType.ADDRESS_CHANGE,
            source_system=SourceSystem.SWS,
            source_event_id="evt_001",
            field_name="employee_headcount",
            new_value="42.0",
            raw_payload={},
        )
        result = translate_outbound(event)

        assert result["worker_count"] == "42"

    def test_translate_outbound_unmapped_field_falls_back(self):
        from synckar.adapters.departments.factories.translator import translate_outbound

        event = CanonicalServiceRequest(
            ubid="KA-TEST-0001",
            request_type=RequestType.ADDRESS_CHANGE,
            source_system=SourceSystem.SWS,
            source_event_id="evt_001",
            field_name="unknown_field",
            new_value="value",
            raw_payload={},
        )
        result = translate_outbound(event)
        assert result["unknown_field"] == "value"


# ─── Shop Establishment Translator ────────────────────────────────────────────

class TestShopTranslator:
    @pytest.fixture(autouse=True)
    def patch_mapping(self):
        from synckar.models.mapping import AdapterMapping, FieldMapping
        mapping = AdapterMapping(
            version="v1",
            certified_by="test",
            fields=[
                FieldMapping(source_field="registered_address", target_field="Buss_Addr_Line1", transform="truncate(120)"),
                FieldMapping(source_field="authorized_signatory", target_field="Auth_Sign_Name", transform="uppercase"),
            ],
        )
        with mock.patch("synckar.adapters.departments.shop_establishment.translator._get_mapping", return_value=mapping):
            yield

    def test_translate_inbound_reverse_maps_dept_field(self):
        from synckar.adapters.departments.shop_establishment.translator import translate_inbound

        raw = {
            "ubid": "KA-TEST-0001",
            "field_name": "Buss_Addr_Line1",
            "old_value": "Old",
            "new_value": "New Shop Addr",
            "timestamp": "2026-01-01T00:00:00Z",
        }
        event = translate_inbound(raw)

        assert event.field_name == "registered_address"
        assert event.source_system == SourceSystem.SHOP_ESTABLISHMENT

    def test_translate_inbound_raises_on_missing_ubid(self):
        from synckar.adapters.departments.shop_establishment.translator import translate_inbound

        with pytest.raises(TranslationError):
            translate_inbound({"field_name": "Buss_Addr_Line1", "new_value": "x"})

    def test_translate_outbound_applies_truncate_transform(self):
        from synckar.adapters.departments.shop_establishment.translator import translate_outbound

        long_address = "A" * 200
        event = CanonicalServiceRequest(
            ubid="KA-TEST-0001",
            request_type=RequestType.ADDRESS_CHANGE,
            source_system=SourceSystem.SWS,
            source_event_id="evt_001",
            field_name="registered_address",
            new_value=long_address,
            raw_payload={},
        )
        result = translate_outbound(event)

        assert "Buss_Addr_Line1" in result
        assert len(result["Buss_Addr_Line1"]) == 120

    def test_translate_outbound_applies_uppercase_transform(self):
        from synckar.adapters.departments.shop_establishment.translator import translate_outbound

        event = CanonicalServiceRequest(
            ubid="KA-TEST-0001",
            request_type=RequestType.SIGNATORY_UPDATE,
            source_system=SourceSystem.SWS,
            source_event_id="evt_001",
            field_name="authorized_signatory",
            new_value="john doe",
            raw_payload={},
        )
        result = translate_outbound(event)

        assert result["Auth_Sign_Name"] == "JOHN DOE"


# ─── Client HTTP error mapping ────────────────────────────────────────────────

class TestSWSClientErrors:
    def _make_http_error(self, status_code: int) -> httpx.HTTPStatusError:
        request = httpx.Request("PUT", "http://mock-sws/api/businesses/KA-TEST-0001")
        response = httpx.Response(status_code, request=request, text="error")
        return httpx.HTTPStatusError("error", request=request, response=response)

    def test_4xx_maps_to_permanent_write_error(self):
        from synckar.adapters.sws.client import SWSClient

        client = SWSClient(base_url="http://mock-sws:8000")
        with mock.patch("httpx.Client") as mock_client_cls:
            mock_client = mock.MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.put.side_effect = self._make_http_error(422)

            with pytest.raises(PermanentWriteError):
                client.update_business("KA-TEST-0001", {"registered_address": "x"})

    def test_5xx_maps_to_target_write_error(self):
        from synckar.adapters.sws.client import SWSClient

        client = SWSClient(base_url="http://mock-sws:8000")
        with mock.patch("httpx.Client") as mock_client_cls:
            mock_client = mock.MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.put.side_effect = self._make_http_error(503)

            with pytest.raises(TargetWriteError):
                client.update_business("KA-TEST-0001", {"registered_address": "x"})

    def test_404_maps_to_ubid_not_found(self):
        from synckar.adapters.sws.client import SWSClient

        client = SWSClient(base_url="http://mock-sws:8000")
        with mock.patch("httpx.Client") as mock_client_cls:
            mock_client = mock.MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.put.return_value = mock.Mock(status_code=404)

            with pytest.raises(UBIDNotFound):
                client.update_business("KA-TEST-0001", {"registered_address": "x"})

    def test_connect_error_maps_to_target_write_error(self):
        from synckar.adapters.sws.client import SWSClient

        client = SWSClient(base_url="http://mock-sws:8000")
        with mock.patch("httpx.Client") as mock_client_cls:
            mock_client = mock.MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.put.side_effect = httpx.ConnectError("Connection refused")

            with pytest.raises(TargetWriteError):
                client.update_business("KA-TEST-0001", {"registered_address": "x"})


class TestFactoriesClientErrors:
    def _make_http_error(self, status_code: int) -> httpx.HTTPStatusError:
        request = httpx.Request("PUT", "http://mock-factories/api/records/by-ubid/KA-TEST-0001")
        response = httpx.Response(status_code, request=request, text="error")
        return httpx.HTTPStatusError("error", request=request, response=response)

    def test_4xx_maps_to_permanent_write_error(self):
        from synckar.adapters.departments.factories.client import FactoriesClient

        client = FactoriesClient(base_url="http://mock-factories:8002")
        with mock.patch("httpx.Client") as mock_client_cls:
            mock_client = mock.MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.put.side_effect = self._make_http_error(400)

            with pytest.raises(PermanentWriteError):
                client.update_record("KA-TEST-0001", {"factory_address": "x"})

    def test_5xx_maps_to_target_write_error(self):
        from synckar.adapters.departments.factories.client import FactoriesClient

        client = FactoriesClient(base_url="http://mock-factories:8002")
        with mock.patch("httpx.Client") as mock_client_cls:
            mock_client = mock.MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.put.side_effect = self._make_http_error(500)

            with pytest.raises(TargetWriteError):
                client.update_record("KA-TEST-0001", {"factory_address": "x"})

    def test_404_maps_to_ubid_not_found(self):
        from synckar.adapters.departments.factories.client import FactoriesClient

        client = FactoriesClient(base_url="http://mock-factories:8002")
        with mock.patch("httpx.Client") as mock_client_cls:
            mock_client = mock.MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.put.return_value = mock.Mock(status_code=404)

            with pytest.raises(UBIDNotFound):
                client.update_record("KA-TEST-0001", {"factory_address": "x"})


class TestShopClientErrors:
    def _make_http_error(self, status_code: int) -> httpx.HTTPStatusError:
        request = httpx.Request("PUT", "http://mock-shop/api/records/by-ubid/KA-TEST-0001")
        response = httpx.Response(status_code, request=request, text="error")
        return httpx.HTTPStatusError("error", request=request, response=response)

    def test_4xx_maps_to_permanent_write_error(self):
        from synckar.adapters.departments.shop_establishment.client import ShopEstablishmentClient

        client = ShopEstablishmentClient(base_url="http://mock-shop:8001")
        with mock.patch("httpx.Client") as mock_client_cls:
            mock_client = mock.MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.put.side_effect = self._make_http_error(400)

            with pytest.raises(PermanentWriteError):
                client.update_record("KA-TEST-0001", {"Buss_Addr_Line1": "x"})

    def test_5xx_maps_to_target_write_error(self):
        from synckar.adapters.departments.shop_establishment.client import ShopEstablishmentClient

        client = ShopEstablishmentClient(base_url="http://mock-shop:8001")
        with mock.patch("httpx.Client") as mock_client_cls:
            mock_client = mock.MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.put.side_effect = self._make_http_error(503)

            with pytest.raises(TargetWriteError):
                client.update_record("KA-TEST-0001", {"Buss_Addr_Line1": "x"})

    def test_404_maps_to_ubid_not_found(self):
        from synckar.adapters.departments.shop_establishment.client import ShopEstablishmentClient

        client = ShopEstablishmentClient(base_url="http://mock-shop:8001")
        with mock.patch("httpx.Client") as mock_client_cls:
            mock_client = mock.MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.put.return_value = mock.Mock(status_code=404)

            with pytest.raises(UBIDNotFound):
                client.update_record("KA-TEST-0001", {"Buss_Addr_Line1": "x"})

    def test_connect_error_maps_to_target_write_error(self):
        from synckar.adapters.departments.shop_establishment.client import ShopEstablishmentClient

        client = ShopEstablishmentClient(base_url="http://mock-shop:8001")
        with mock.patch("httpx.Client") as mock_client_cls:
            mock_client = mock.MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.put.side_effect = httpx.ConnectError("Connection refused")

            with pytest.raises(TargetWriteError):
                client.update_record("KA-TEST-0001", {"Buss_Addr_Line1": "x"})

    def test_get_record_returns_none_on_404(self):
        from synckar.adapters.departments.shop_establishment.client import ShopEstablishmentClient

        client = ShopEstablishmentClient(base_url="http://mock-shop:8001")
        with mock.patch("httpx.Client") as mock_client_cls:
            mock_client = mock.MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock.Mock(status_code=404)

            result = client.get_record("KA-TEST-9999")
            assert result is None

"""Retained Willys picking metadata must not relax exact price-context binding."""
import json
from pathlib import Path

import httpx
import pytest

from grocery_data.app.connectors.http import RetryPolicy
from grocery_data.app.connectors.willys.client import WillysClient
from grocery_data.app.connectors.willys.models import validated_store_context
from grocery_data.app.connectors.willys.parser import WillysParser
from grocery_data.app.domain import (
    Chain,
    CoverageLevel,
    GeographicArea,
    RawBatch,
    RawFetch,
    SourceStore,
)
from grocery_data.app.monitoring import SchemaDiff
from grocery_data.app.services.collector import _review_schema_diff

VERSION = "willys-parser-v6-picking-contract"
INVALID = [None, True, 0, 1, "false", {}, []]
PATHS = ("2176:store_context:$[].hasPickingBaseStore",
         "2354:store_context:$[].hasPickingBaseStore", "stores:$[][].hasPickingBaseStore")


def schema(paths=PATHS):
    return {p.rsplit(":", 1)[0]: {"paths": {
        p.rsplit(":", 1)[1]: ["boolean"],
        p.rsplit(":", 1)[1].replace("hasPickingBaseStore", "storeId"): ["string"],
    }} for p in paths}


def raw(payload, kind, store_id="2176"):
    return RawFetch(chain=Chain.WILLYS, store_external_id=store_id,
                    kind=kind, method="GET", url="https://public.example/store",
                    http_status=200, content_type="application/json",
                    payload=json.dumps(payload).encode(), connector_version="willys-v1")


def store():
    return SourceStore(chain=Chain.WILLYS, external_id="2176", name="Willys Lund",
                       coverage=CoverageLevel.FULL_CATALOG,
                       raw_reference="retained:store", source_fields={"hasPickingBaseStore": False})


def test_review_requires_new_parser_exact_path_and_boolean_identity_evidence():
    diff = SchemaDiff(added=PATHS)
    assert _review_schema_diff(Chain.WILLYS, VERSION, diff, schemas=schema()) is None
    assert _review_schema_diff(Chain.WILLYS, "willys-parser-v5", diff, schemas=schema()) == diff
    assert _review_schema_diff(Chain.WILLYS, VERSION, diff) == diff
    for field, types in [("hasPickingBaseStore", ["boolean", "null"]), ("storeId", ["number"])]:
        observed = schema()
        observed["2176:store_context"]["paths"]["$[]." + field] = types
        assert _review_schema_diff(Chain.WILLYS, VERSION, diff, schemas=observed).added == (PATHS[0],)
    unknown = "2176:store_context:$[].other.hasPickingBaseStore"
    assert _review_schema_diff(Chain.WILLYS, VERSION, SchemaDiff(added=(unknown,)), schemas=schema((unknown,)))


def test_optional_flag_removal_preserves_identity_and_other_schema_gates():
    observed = schema()
    for group in observed.values():
        group["paths"] = {k: v for k, v in group["paths"].items() if k.endswith("storeId")}
    assert _review_schema_diff(Chain.WILLYS, VERSION, SchemaDiff(removed=PATHS), schemas=observed) is None
    removed = PATHS + ("2176:store_context:$[].storeId",)
    assert _review_schema_diff(Chain.WILLYS, VERSION, SchemaDiff(removed=removed), schemas=observed).removed == (removed[-1],)
    assert _review_schema_diff(Chain.WILLYS, VERSION, SchemaDiff(removed=PATHS), schemas={})


def test_retained_reduced_rows_bind_to_both_stores_without_rewriting_values():
    fixture = json.loads((Path(__file__).parent / "fixtures/willys-picking-store-20261014.json").read_text())
    for record in fixture["records"]:
        for row in record["rows"]:
            assert row["hasPickingBaseStore"] is False
            assert validated_store_context(row, row["storeId"])
            assert not validated_store_context(row, "other")
    rows = fixture["records"][0]["rows"]
    parsed = WillysParser().parse_stores(RawBatch(chain=Chain.WILLYS, documents=(raw(rows, "stores", None),)),
                                      ["retained:stores"], GeographicArea(city="Lund"))
    assert {s.external_id for s in parsed} == {"2176", "2354"}
    assert all(s.source_fields["hasPickingBaseStore"] is False for s in parsed)


@pytest.mark.parametrize("value", INVALID)
def test_invalid_flags_stop_store_discovery_and_saved_catalogue(value):
    row = {"storeId": "2176", "name": "Willys Lund", "hasPickingBaseStore": value}
    assert not validated_store_context(row, "2176")
    with pytest.raises(ValueError, match="picking base"):
        WillysParser().parse_stores(RawBatch(chain=Chain.WILLYS, documents=(raw([row], "stores"),)),
                                  ["retained:stores"], GeographicArea(city="Lund"))
    result = WillysParser().parse_catalog(RawBatch(chain=Chain.WILLYS, documents=(raw(row, "store_context"),)),
                                         ["retained:context"], store())
    assert not result.products and result.failures[0].error_code == "price_context_unverified"


@pytest.mark.parametrize("payload", [
    {"storeId": "wrong", "other": {"storeId": "2176"}},
    {"storeId": "wrong", "pickingStore": {"storeId": "2176"}},
    {"storeId": "2176", "pickingStore": {"storeId": "wrong"}},
    {"hasPickingBaseStore": True, "pickingStore": {"storeId": "2176"}},
    {"store": None}, [{"storeId": "2176"}],
])
def test_nested_or_conflicting_ids_cannot_authorize(payload):
    assert not validated_store_context(payload, "2176")


def test_saved_context_is_required_for_flagged_store_and_all_contexts_must_agree():
    valid = raw({"storeId": "2176", "hasPickingBaseStore": False}, "store_context")
    fixture = Path(__file__).parents[1] / "app/connectors/willys/fixtures/fixed_package.json"
    product = raw(json.loads(fixture.read_bytes()), "catalog_page")
    parser = WillysParser()
    result = parser.parse_catalog(RawBatch(chain=Chain.WILLYS, documents=(valid, product)), ["ctx", "product"], store())
    assert result.products and not result.failures
    for contexts in [(), (valid.model_copy(update={"store_external_id": "wrong"}),),
                     (valid, raw({"storeId": "wrong"}, "store_context")),
                     (valid.model_copy(update={"http_status": 500}),)]:
        docs = (*contexts, product)
        result = parser.parse_catalog(RawBatch(chain=Chain.WILLYS, documents=docs), ["raw"] * len(docs), store())
        assert not result.products and result.failures[0].error_code == "price_context_unverified"
    for payload in [{"storeId": "2176"}, {"pickingStore": {"storeId": "2176"}}]:
        assert validated_store_context(payload, "2176")


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [False, *INVALID])
async def test_live_transport_checks_picking_flag_before_catalogue(value):
    requests = []

    def handler(request):
        requests.append(request.url.path)
        if request.url.path.endswith("csrf-token"):
            return httpx.Response(200, json="test-only-token")
        if request.url.path.endswith("store/activate"):
            return httpx.Response(200, json={})
        assert request.url.path.endswith("store/active")
        return httpx.Response(200, json={"storeId": "2176", "hasPickingBaseStore": value})

    async with httpx.AsyncClient(base_url="https://public.example", transport=httpx.MockTransport(handler)) as http:
        client = WillysClient(base_url="https://public.example", client=http, requests_per_second=10000,
                              retry_policy=RetryPolicy(attempts=1))
        if value is False:
            await client._activate_store("2176", [])
        else:
            with pytest.raises(RuntimeError, match="requested store context"):
                await client._activate_store("2176", [])
    assert len(requests) == 3


@pytest.mark.parametrize("payload", [
    {"storeId": "2176", "hasPickingBaseStore": True},
    {"storeId": "wrong", "other": {"storeId": "2176"}},
])
def test_independent_artifact_qualifier_also_rejects_unreviewed_context(tmp_path, payload):
    from grocery_data.app.services import source_artifact as artifacts
    from grocery_data.tests.test_source_artifact import artifact

    verified = artifacts.verify_source_artifact(artifact(tmp_path))
    documents = tuple(
        d.model_copy(update={"payload": json.dumps(payload).encode()})
        if d.kind == "store_context" and d.store_external_id == "2176" else d
        for d in verified.documents
    )
    with pytest.raises(artifacts.SourceArtifactError, match="context"):
        artifacts._willys_completion(documents)

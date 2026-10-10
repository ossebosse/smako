"""Historical rejection reproduction, not approval of a DOM-derived price."""
import hashlib
import json
from datetime import datetime
from pathlib import Path

from grocery_data.app.connectors.coop import CoopParser
from grocery_data.app.domain import RawBatch, RawFetch, SourceStore


def test_exact_retained_varpinge_scan_offer_is_blocked_by_structured_schema():
    payload = (Path(__file__).parent / "fixtures/coop-varpinge-20261009.json").read_bytes()
    assert hashlib.sha256(payload).hexdigest() == "b2a497fed951a9f7da34dc4ab14863e2772145ff80211f59705b996ca738252b"
    value = json.loads(payload)
    assert "Sverige/Scan" in value["cards"][2]["aria_label"]
    assert "Medlemspris 65 kronor per kilo, Max 2 styck per hushåll" in value["cards"][2]["aria_label"]
    fields = "priceInformation.buyAmount, priceInformation.claim, priceInformation.payAmount"
    assert value["structured_offers"]["schema_review_reason"].endswith(fields)
    # The capture preserved field names, not their rejected values/types.
    assert "data" not in value["structured_offers"]
    store = SourceStore(chain="coop", external_id="3659", name="Coop Värpinge Lund",
        city="Lund", coverage="offers_only", price_context_type="physical_store", raw_reference="retained",
        source_fields={"store_page_path":value["store_page_path"], "ledger_account_number":"216526"})
    document = RawFetch(chain="coop", store_external_id="3659", kind="rendered_offers_page", method="GET",
        url="https://www.coop.se"+value["store_page_path"],
        fetched_at=datetime.fromisoformat("2026-10-09T13:30:40.294974+00:00"),
        http_status=200, payload=payload, connector_version="retained-physical-evidence")
    parsed = CoopParser().parse_catalog(RawBatch(chain="coop", documents=(document,)), ["raw:8be3ac4751d44c5799afc2f87abe3b1c"], store)
    assert not parsed.products
    assert len(parsed.failures) == 1
    assert fields in parsed.failures[0].error_message
    assert "public_structured_schema_unrecognized" in parsed.failures[0].error_message

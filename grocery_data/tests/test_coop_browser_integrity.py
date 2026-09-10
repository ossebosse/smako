from __future__ import annotations

import pytest

from grocery_data.app.connectors.coop import CoopBrowserOffersTransport
from grocery_data.app.domain import Chain, CoverageLevel, SourceStore


def _store() -> SourceStore:
    return SourceStore(
        chain=Chain.COOP,
        external_id="2696",
        name="Stora Coop Lund",
        city="Lund",
        coverage=CoverageLevel.OFFERS_ONLY,
        raw_reference="raw:store",
        source_fields={"store_page_path": "/butiker-erbjudanden/stora-coop/stora-coop-lund/"},
    )


def test_browser_transport_validates_exact_public_store_context() -> None:
    CoopBrowserOffersTransport._validate_store_context(
        "https://www.coop.se/butiker-erbjudanden/stora-coop/stora-coop-lund/",
        "  Stora Coop Lund  ",
        _store(),
    )

    with pytest.raises(RuntimeError, match="changed store context"):
        CoopBrowserOffersTransport._validate_store_context(
            "https://www.coop.se/butiker-erbjudanden/stora-coop/stora-coop-stadion/",
            "Stora Coop Stadion",
            _store(),
        )
    with pytest.raises(RuntimeError, match="heading"):
        CoopBrowserOffersTransport._validate_store_context(
            "https://www.coop.se/butiker-erbjudanden/stora-coop/stora-coop-lund/",
            "Stora Coop Stadion",
            _store(),
        )


def test_browser_transport_requires_complete_declared_offer_set() -> None:
    card = {
        "href": None,
        "ariaLabel": "Smör, Valio, 500 g, Medlemspris, 39 kronor per styck",
    }
    payload = CoopBrowserOffersTransport._sanitized_payload(
        [card],
        declared_total=1,
        store=_store(),
    )
    assert b'"declared_total":1' in payload

    stable_payload = CoopBrowserOffersTransport._sanitized_payload(
        [card],
        declared_total=None,
        store=_store(),
    )
    assert b'"capture_evidence":"dom_stable"' in stable_payload
    assert b'"captured_total":1' in stable_payload
    with pytest.raises(RuntimeError, match="incomplete"):
        CoopBrowserOffersTransport._sanitized_payload(
            [card],
            declared_total=2,
            store=_store(),
        )


def test_browser_transport_does_not_confuse_offer_group_size_with_page_total() -> None:
    visible = "Se 2 varor Bryggkaffe. 52 erbjudanden. Se 9 varor Kaffe."
    assert CoopBrowserOffersTransport._declared_offer_total(visible) == 52

    assert CoopBrowserOffersTransport._declared_offer_total("Se 2 varor utan total") is None
    with pytest.raises(RuntimeError, match="conflicting"):
        CoopBrowserOffersTransport._declared_offer_total("52 erbjudanden 51 erbjudanden")

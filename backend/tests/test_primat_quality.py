from copy import deepcopy

import pytest
from app.models.product import SaleModel
from app.providers.primat import PrimatPriceProvider as P


def row():
    return {
        "chain": "ica",
        "store_id": "1088004",
        "product_id": "2129118",
        "name": "Smör & Raps Normalsaltat",
        "brand": "Bregott",
        "category": "Mejeri & Ost > Smör & Margarin > Bordsask smör",
        "amount": 750,
        "unit": "g",
        "package": "750 g",
        "gtin": "7311870011076",
        "prices": {"regular": 69.43},
    }


@pytest.fixture
def provider():
    return P("deterministic-test-only")


@pytest.mark.parametrize("category", ["Smör & Margarin", "Ägg & Jäst", "Mjölk", "Grädde"])
def test_broad_dairy_root_does_not_prove_variable_package(provider, category):
    r = row() | {"category": "Mejeri & Ost > " + category}
    p = provider._parse_product(r)
    assert p.sale_model == SaleModel.FIXED_PACKAGE
    assert p.package_quantity == 750
    assert p.normalized_unit_price == pytest.approx(69.43 / 0.75, abs=0.01)
    assert p.gtin == r["gtin"]


def test_actual_cheese_category_remains_conservative(provider):
    p = provider._parse_product(row() | {"category": "Mejeri & Ost > Ost > Hårdost"})
    assert p.sale_model == SaleModel.UNKNOWN


@pytest.mark.parametrize("gtin", [None, "7311870011077", "123456789", "not-an-ean"])
def test_invalid_or_missing_gtin_never_manufactures_identity(provider, gtin):
    assert provider._parse_product(row() | {"gtin": gtin}).gtin is None


@pytest.mark.parametrize(
    "amount,unit,package,expected",
    [
        (750, "g", "750 g", (750, "g")),
        (1, "kg", "1 kg", (1000, "g")),
        (1.5, "l", "1.5 l", (1500, "ml")),
        (500, "ml", "500 ml", (500, "ml")),
        (10, "st", "10 st", (10, "st")),
        (1, "l", "6 x 1 l", (6000, "ml")),
    ],
)
def test_authoritative_package_dimensions(amount, unit, package, expected):
    assert P._normalise_package(amount, unit, package, "")[:2] == expected


@pytest.mark.parametrize(
    "amount,unit,package,name",
    [
        (0, "g", "500 g", ""),
        (-500, "g", "500 g", ""),
        (float("inf"), "g", None, ""),
        (500, "nonsense", None, ""),
        (1e12, "kg", None, ""),
        (0.00001, "g", None, ""),
        (1.5, "st", None, ""),
        (10, "st", "10 st", "Kapslar 57 g"),
        (500, "ml", "500 g", ""),
        (None, None, None, "Pasta 500 g"),
        (500, "g", "750 g", ""),
    ],
)
def test_invalid_packages_fail_closed(amount, unit, package, name):
    assert P._normalise_package(amount, unit, package, name) is None


def offer_row(label="Kampanjpris"):
    r = row()
    r["prices"]["offer"] = {
        "price": 50,
        "label": label,
        "valid_from": "2020-01-01",
        "valid_until": "2099-01-01",
    }
    return r


def test_public_and_member_prices_use_same_denominator(provider):
    r = offer_row()
    assert provider._parse_product(r).effective_price == 50
    r["prices"]["member"] = 50
    public = provider._parse_product(r)
    member = P("deterministic-test-only", use_member_prices=True)._parse_product(r)
    assert public.effective_price == 69.43
    assert member.effective_price == 50
    assert member.normalized_unit_price == pytest.approx(50 / 0.75, abs=0.01)


def test_multibuy_requires_structured_quantity(provider):
    r = offer_row("2 för 100kr")
    assert provider._parse_product(r).effective_price == 69.43
    r["prices"]["multiprice"] = {"quantity": 2, "price": 50}
    p = provider._parse_product(r)
    assert p.effective_price == 69.43
    assert p.offers[0].required_packages == 2 and p.offers[0].price == 100


@pytest.mark.parametrize(
    "change",
    [
        {"scope": "category"},
        {"eligibility": "USER_SPECIFIC"},
        {"label": "Alla varor"},
        {"valid_until": "invalid"},
    ],
)
def test_ambiguous_and_personal_promotions_rejected(provider, change):
    r = offer_row()
    r["prices"]["offer"].update(change)
    p = provider._parse_product(r)
    assert not p.offers and p.effective_price == 69.43


def test_expired_offer_only_cannot_become_ordinary(provider):
    r = offer_row()
    r["prices"]["offer"]["valid_until"] = "2020-01-02"
    assert provider._parse_product(r).effective_price == 69.43
    del r["prices"]["regular"]
    assert provider._parse_product(r) is None


def test_observation_not_changed_by_price_policy(provider):
    p = provider._parse_product(row())
    assert p.source_provenance.source_observed_at == provider._observed_at
    assert provider.apply_price_policy([deepcopy(p)])[0].source_provenance == p.source_provenance


def test_gtin_package_identity_and_shared_search_pricing(provider):
    from app.models.product import ProductCandidate
    from app.services.user_pricing import price_contracts_for_candidate

    from backend.tests.test_product_search import prepare, search
    from grocery_data.app.domain.promotion_pricing import UserPricingContext
    from grocery_data.app.services.fixed_checkout_price import resolve_effective_price

    provider._observed_at = __import__("backend.tests.test_product_search", fromlist=["NOW"]).NOW
    provider._observation_id = "frozen"
    a = provider._parse_product(row())
    b = provider._parse_product(row() | {"store_id": "1004409"})
    prepared = prepare(a, b)
    result = search(prepared, "Bregott")["results"][0]
    assert result["identity_basis"] == "verified_gtin" and len(result["prices"]) == 2
    contracts = price_contracts_for_candidate(ProductCandidate.from_product(a, 1))
    economics = resolve_effective_price(
        contracts, 1, UserPricingContext(), on_date=provider._observed_at.date()
    )
    for price in result["prices"]:
        assert price["effective_price"] == float(economics.displayed_unit_price)
        assert price["observed_at"] == a.source_provenance.source_observed_at
        assert price["unit_price"] == pytest.approx(a.normalized_unit_price)
    no_gtin = provider._parse_product(row() | {"store_id": "1004409", "gtin": None})
    assert len(search(prepare(a, no_gtin), "Bregott")["results"]) == 2


def test_entire_user_specific_row_is_excluded(provider):
    assert provider._parse_product(row() | {"eligibility": "USER_SPECIFIC"}) is None

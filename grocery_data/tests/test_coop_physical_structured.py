"""Retained REAL public responses, plus clearly marked adversarial mutations.

Fixture observations are September 21; replay never substitutes today's clock.
"""
import json
from datetime import date, datetime
from pathlib import Path

import pytest

from grocery_data.app.connectors.coop import CoopParser
from grocery_data.app.connectors.coop.structured_offers import sanitized_response
from grocery_data.app.domain import RawBatch, SourceStore
from grocery_data.app.normalization import ProductNormalizer
from grocery_data.app.services.offer_rows import qualify_rows

FIXTURES = Path(__file__).parent / "fixtures/coop-physical-20260921"


def source(account="3839"):
    store = SourceStore.model_validate_json((FIXTURES / f"{account}-store.json").read_bytes())
    batch = RawBatch.model_validate_json((FIXTURES / f"{account}-batch.json").read_bytes())
    return store, batch


def parse(account="3839", mutate=None):
    store, batch = source(account)
    if mutate:
        value = json.loads(batch.documents[0].payload)
        mutate(value)
        batch = batch.model_copy(update={"documents": (batch.documents[0].model_copy(
            update={"payload": json.dumps(value).encode()}),)})
    parsed = CoopParser().parse_catalog(batch, ["raw:real-retained"], store)
    approved, evidence = qualify_rows(parsed, store=store, observed_at=batch.documents[0].fetched_at)
    return parsed, approved, evidence


@pytest.mark.parametrize("account,total,accepted", [("3839",135,93),("3815",356,246)])
def test_actual_full_denominator_row_approval_and_observation(account,total,accepted):
    original, approved, evidence = parse(account)
    assert not original.failures
    assert len(original.products) == total
    assert len(approved.products) == accepted
    assert len(approved.failures) == total-accepted
    assert evidence["full_parse"]["denominator"] == total
    assert evidence["full_parse"]["threshold"] == .95
    for p in original.products:
        assert p.gtin is None  # externalId is NOT claimed to be GTIN.
        assert p.regular_price is None and p.sale_price is None
        assert p.store_external_id == account
        n = ProductNormalizer().normalize(p, parser_version=CoopParser.parser_version)
        assert n.offers == p.offers and n.observed_at == p.fetched_at
        assert p.offers[0].source_payload["source_sha256"] == source(account)[1].documents[0].payload_hash
    for p in approved.products:
        assert p.offers[0].source_payload["campaign_evidence"]["observed_current_at"] == p.fetched_at.isoformat().replace("+00:00", "Z")


def test_actual_member_variants_exclusions_pack_and_public_multibuy():
    original, approved, _ = parse()
    bregott = [p for p in approved.products if "Bregott" in p.name]
    assert len(bregott) == 6
    assert {p.package_quantity for p in bregott} == {350,500}
    assert all("Gäller ej ekologiskt" in p.offers[0].description for p in bregott)
    assert len({p.offers[0].source_payload["price_contract_id"] for p in bregott}) == 1
    flour = next(p for p in approved.products if p.name == "Kärnvetemjöl")
    assert flour.package_quantity == 2000 and flour.package_unit == "g"
    assert flour.offers[0].quantity == 2 and flour.offers[0].price == 26
    assert not flour.offers[0].member_only
    assert flour.offers[0].valid_from == date(2026,9,21)
    assert flour.offers[0].valid_to == date(2026,9,27)
    soda = [p for p in original.products if p.offers[0].source_payload["deposit_text"]]
    assert soda and not any(p.external_product_id in {q.external_product_id for q in approved.products} for p in soda)


def test_actual_percentage_and_printed_regular_never_become_ordinary_purchase():
    original, approved, _ = parse("3815")
    lamps = [p for p in original.products if p.offers[0].type.value == "percent_discount"]
    assert len(lamps) == 74
    assert all(p.offers[0].price is None for p in lamps)
    assert all(p.offers[0].source_payload["source_record"]["priceInformation"]["discountValue"] == 20 for p in lamps)
    glitter = next(p for p in original.products if p.name == "Glitter set")
    assert glitter.regular_price is None and glitter.offers[0].price == 199
    assert glitter.offers[0].source_payload["source_record"]["priceInformation"]["termStyle"] == "Regular Price"
    assert glitter.external_product_id in {p.external_product_id for p in approved.products}
    assert glitter.source_fields["purchase_terms"]["purchase_form"] == "piece"
    assert glitter.offers[0].valid_to == date(2026, 9, 27)
    assert all(p.external_product_id not in {a.external_product_id for a in approved.products} for p in lamps)


@pytest.mark.parametrize("mutation", [
    lambda e: e.update(store_external_id="730400"),
    lambda e: e["structured_offers"].update(ledger_account_number="730400"),
    lambda e: e["structured_offers"]["data"]["sortingGroups"][0].update(offerAmount=999),
    lambda e: e["structured_offers"]["data"]["sortingGroups"][0]["offers"][0].update(storeLedgerAccountNumber="other-store"),
    lambda e: e["structured_offers"]["data"]["sortingGroups"][0]["offers"][0]["priceInformation"].update(discountValue=1),
])
def test_adversarial_shared_errors_stop_entire_candidate(mutation):
    _, approved, evidence = parse(mutate=mutation)
    assert not approved.products
    assert evidence["shared_blockers"]


def one_ad_mutation(change):
    def mutate(e):
        g = e["structured_offers"]["data"]["sortingGroups"][0]
        row = next(r for r in g["offers"] if r["content"]["title"] == "Nötfärs")
        change(row)
        g["offers"]=[row];g["offerAmount"]=1
        e["structured_offers"]["data"]["sortingGroups"]=[g]
        e["cards"]=[next(c for c in e["cards"] if "Nötfärs," in c["aria_label"])]
        e["captured_total"]=1
    return mutate


@pytest.mark.parametrize("change,reason", [
    (lambda r:r.update(campaignEndDate=None),"campaign_dates_unverified"),
    (lambda r:r.update(campaignEndDate="2026-09-21T12:00:00"),"subday_campaign_time_requires_review"),
    (lambda r:r["content"].update(description="Personligt erbjudande"),"additional_eligibility_requires_review"),
    (lambda r:r["content"].update(description="Gäller endast fredag"),"additional_eligibility_requires_review"),
    (lambda r:r["content"].update(recyclingInformationText="Pant tillkommer."),"deposit_amount_unverified"),
    (lambda r:r["content"].update(dealOfferLimitText="Max 2 per kund och dag"),"purchase_limit_unrecognized"),
    (lambda r:r["content"].update(description="Gäller ej ekologisk",onlineProductName="Ekologisk nötfärs"),"variant_excluded_by_campaign"),
])
def test_adversarial_uncertain_conditions_retained_but_not_buyable(change,reason):
    original, approved, evidence = parse(mutate=one_ad_mutation(change))
    assert len(original.products)==1 and not original.failures
    assert not approved.products
    assert reason in evidence["decisions"][0]["blockers"]


def test_real_historical_plain_prices_fixed_without_invented_dates():
    store,batch=source("3815")
    data=(FIXTURES/'20260920-coop-3815-context-cards.json').read_bytes()
    old=json.loads((FIXTURES/'20260920-coop-3815-date-context.json').read_bytes())
    raw=batch.documents[0].model_copy(update={"payload":data,"fetched_at":datetime.fromisoformat(old['observed_at'])})
    parsed=CoopParser().parse_catalog(batch.model_copy(update={"documents":(raw,)}),["historical-raw"],store)
    shot=next(p for p in parsed.products if p.name=='Shot')
    assert shot.regular_price is None and shot.sale_price is None
    assert shot.offers[0].price==33 and shot.offers[0].valid_to is None
    assert shot.source_fields["purchase_blockers"]==["structured_campaign_variant_evidence_missing"]


def test_sanitization_drops_nonbusiness_runtime_fields():
    _store,batch=source()
    data=json.loads(batch.documents[0].payload)["structured_offers"]["data"]
    data["secret"]="must-not-survive"
    assert 'must-not-survive' not in json.dumps(sanitized_response(data))
    # New row fields may be new conditions: block rather than silently drop.
    data['sortingGroups'][0]['offers'][0]['content']['activationRequired']=True
    with pytest.raises(ValueError, match="schema review"):
        sanitized_response(data)


def test_actual_full_public_response_retains_percentage_and_unresolved_pil():
    data = sanitized_response(json.loads((FIXTURES / "3815-public-full-response.json").read_bytes()))
    original, approved, evidence = parse("3815", mutate=lambda e: e["structured_offers"].update(data=data))
    assert not original.failures and len(original.products) == 356
    lamps = [p for p in original.products if p.offers[0].type.value == "percent_discount"]
    assert len(lamps) == 74 and all(p.offers[0].price is None for p in lamps)
    flagged = [p for p in original.products if "source_is_pil_requires_review" in p.source_fields["purchase_blockers"]]
    assert flagged
    assert not {p.external_product_id for p in flagged} & {p.external_product_id for p in approved.products}
    assert evidence["full_parse"]["denominator"] == 356


def test_adversarial_percentage_flag_cannot_be_used_as_monetary_price():
    original, approved, _ = parse(mutate=one_ad_mutation(lambda r: r["priceInformation"].update(isPercentageDiscount=True)))
    assert original.products[0].offers[0].price is None
    assert not approved.products

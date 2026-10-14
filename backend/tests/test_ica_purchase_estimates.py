import copy
import json
import unittest
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from app.models.ingredient import NormalizedIngredient
from app.models.product import OfferMetadata, ProductCandidate
from app.services.basket_calculator import calculate_item
from app.services.user_pricing import price_candidate_for_context

from grocery_data.app.connectors.ica.parser import IcaParser, estimate_swedish_deposit
from grocery_data.app.domain import ProductParseResult, SourceStore
from grocery_data.app.domain.campaign_validity import CampaignEvidence
from grocery_data.app.domain.promotion_pricing import DepositContract, UserPricingContext
from grocery_data.app.domain.purchase_terms import PurchaseTerms
from grocery_data.app.services.offer_rows import qualify_rows, row_blockers

DATA = json.loads((Path(__file__).parent / 'fixtures/ica_soder_offers_20261014.json').read_text(encoding='utf-8-sig'))
STORE = SourceStore.model_validate(DATA['store'])
NOW = datetime(2026, 10, 14, 5, 33, 53, tzinfo=UTC)


def parse(row):
    return IcaParser()._parse_offer(row, STORE, 'snapshot.json#' + str(row['id']), NOW)


ROWS = {r['details']['name']: r for r in DATA['rows']}


def candidate(name):
    p = parse(ROWS[name])
    o = p.offers[0]
    terms = PurchaseTerms.model_validate(p.source_fields['purchase_terms'])
    offer = OfferMetadata(kind='multipack' if o.quantity else 'campaign',
        description=o.description or name, price=float(o.price), required_packages=o.quantity or 1,
        price_basis_unit=o.source_payload['price_basis_unit'], max_quantity=o.max_quantity,
        valid_from=date(2026, 10, 14), valid_to=o.valid_to, price_contract_id=p.external_product_id,
        purchase_terms=terms, deposit=o.source_payload.get('estimatedDeposit'),
        campaign_evidence=CampaignEvidence(store_external_id=STORE.external_id,
            offer_id=p.external_product_id, source_reference=p.raw_reference, observed_current_at=NOW, checked_at=NOW))
    return ProductCandidate(product_id=p.external_product_id, product_name=name,
        canonical_name=name.casefold(), store_id='own:ica:1004358', store_name=STORE.name,
        chain='ica', gtin=p.gtin, price=None, effective_price=float(o.price)/(o.quantity or 1),
        sale_price=float(o.price)/(o.quantity or 1), match_score=1, offers=[offer],
        purchase_terms=terms, sale_unit=p.sale_unit, semantic_confidence='high',
        package_quantity=p.package_quantity, package_unit=p.package_unit)


def basket(name, amount, unit='g'):
    c = price_candidate_for_context(candidate(name), UserPricingContext(), on_date=NOW.date(),
        planning_mode='estimated', allow_campaign_choice=True)
    return calculate_item(NormalizedIngredient(canonical_name=name.casefold(), required_quantity=amount, unit=unit), c)


class IcaEstimateTests(unittest.TestCase):
    def test_source_counts_and_qualification(self):
        products = [parse(r) for r in DATA['rows']]
        qualified, evidence = qualify_rows(ProductParseResult(products=products, failures=[]), store=STORE, observed_at=NOW)
        self.assertEqual(len(products), 63)
        self.assertEqual(len(qualified.products), 61)
        self.assertFalse(evidence['shared_blockers'])
        for name in ['Satsumas', 'Purjolök', 'Kassler', 'Hushållsost', 'Läsk', 'Kolsyrat vatten', 'Energidryck']:
            self.assertFalse(row_blockers(parse(ROWS[name])), name)

    def test_loose_produce_200g(self):
        for name in ['Satsumas', 'Purjolök']:
            b = basket(name, 200)
            self.assertEqual(b.total_price, 4)
            self.assertEqual(b.purchased_quantity, 200)
            self.assertEqual(b.quantity_confidence, 'estimated')

    def test_kassler_whole_approximate_package_and_limit(self):
        b = basket('Kassler', 200)
        self.assertEqual(b.total_price, 41.4)
        self.assertEqual(b.purchased_quantity, 600)
        self.assertEqual(b.waste_quantity, 400)
        self.assertIsNone(b.gtin)
        self.assertEqual(basket('Kassler', 700).total_price, 82.8)
        with self.assertRaises(ValueError):
            basket('Kassler', 1300)

    def test_cheese_interval_preserved(self):
        b = basket('Hushållsost', 200)
        self.assertEqual(b.total_price, 86.9)
        self.assertEqual(b.purchase_terms.minimum_package_g, 1100)
        self.assertEqual(b.purchase_terms.maximum_package_g, 2200)
        self.assertEqual(b.quantity_confidence, 'estimated')
        self.assertIsNone(b.gtin)

    def test_plants_explicitly_excluded(self):
        for name in ['Höststjärna', 'Rosor 9-pack']:
            self.assertIn('non_food_ornamental_plant', row_blockers(parse(ROWS[name])))

    def test_deposits_multiply_containers_and_complete_multibuy(self):
        for name, count, total, deposit, merchandise in [
            ('Läsk', 1, 70, 20, 50), ('Kolsyrat vatten', 1, 29, 9, 20),
            ('Energidryck', 1, 12, 2, 10), ('Läsk', 2, 140, 40, 100),
        ]:
            b = basket(name, count, 'st')
            self.assertEqual(b.total_price, total, name)
            self.assertEqual(b.deposit_total, deposit, name)
            self.assertEqual(b.merchandise_total, merchandise, name)
            self.assertEqual(b.applied_offer.deposit.confidence, 'estimated')
            self.assertIn('Uppskattad pant', b.purchase_warning)

    def test_exact_mode_rejects_estimates(self):
        for name in ['Kassler', 'Purjolök', 'Läsk']:
            with self.assertRaises(ValueError):
                price_candidate_for_context(candidate(name), UserPricingContext(), on_date=NOW.date(), allow_campaign_choice=True)

    def test_no_deposit_default_on_undeclared_or_ambiguous_package(self):
        details = ROWS['Energidryck']['details']
        self.assertIsNone(estimate_swedish_deposit(details, '10 kr'))
        self.assertIsNone(estimate_swedish_deposit({**details, 'packageInformation': '33-50 cl'}, '+pant'))
        self.assertIsNone(estimate_swedish_deposit({**details, 'name': 'Mjölk'}, '+pant'))
        self.assertEqual(estimate_swedish_deposit({**details, 'packageInformation': '75 cl'}, '+pant').per_container, 2)

    def test_verified_deposit_still_requires_gtin_and_overrides_estimate(self):
        with self.assertRaises(ValueError):
            DepositContract(per_container=2, containers_per_package=1, inclusion='additional', evidence='source')
        row = copy.deepcopy(ROWS['Energidryck'])
        row['eans'] = row['eans'][:1]
        row['reviewedDeposit'] = {'gtin': row['eans'][0]['id'], 'per_container': '1', 'containers_per_package': 1,
                                 'inclusion': 'additional', 'evidence': 'explicit source label'}
        o = parse(row).offers[0]
        self.assertNotIn('estimatedDeposit', o.source_payload)
        self.assertEqual(Decimal(o.source_payload['reviewedDeposit']['per_container']), 1)

    def test_no_loose_meat_inference_or_wrong_store(self):
        row = copy.deepcopy(ROWS['Purjolök'])
        row['category']['articleGroupName'] = 'Färskvaror'
        self.assertIn('weight_purchase_form_unproven', row_blockers(parse(row)))
        row['stores'] = [{'BMSStoreId': 'wrong', 'storeInd': True}]
        with self.assertRaises(ValueError):
            parse(row)


if __name__ == '__main__':
    unittest.main()

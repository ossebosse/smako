"""Optional ICA OWN offers in the normal provider/materialisation chain.

Uses the existing OWN API, product models, matcher and pricing. This is an
additive source boundary, never a complete-catalogue claim or mandatory source.
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.models import Product, Store
from app.providers.base import GroceryPriceProvider
from app.providers.federated import FederatedGroceryPriceProvider
from app.providers.own import OwnGroceryPriceProvider
from app.services.source_promotion_groups import groups_in_context


def qualification_evidence(database: Path, *, chain='ica') -> dict[str, dict]:
    with sqlite3.connect(f"file:{database.resolve().as_posix()}?mode=ro&immutable=1", uri=True) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute("""
            SELECT p.id, sp.source_fields, sp.gtin, sp.external_product_id, s.external_id,
                   cs.parser_version, cs.id AS snapshot_id, cs.scope_key FROM products p
            JOIN source_products sp ON sp.id=p.source_product_id
            JOIN stores s ON s.id=sp.store_id
            JOIN catalog_snapshots cs ON cs.id=sp.catalog_snapshot_id
            WHERE cs.is_active=1 AND cs.state='promoted' AND sp.chain=?
              AND cs.coverage='offers_only'
        """, (chain,)).fetchall()
    return {str(r["id"]): dict(r) for r in rows}


class IcaAreaOfferProvider(GroceryPriceProvider):
    offer_chain = 'ica'
    accepted_parsers = frozenset({'ica-parser-v6', 'ica-parser-v7', 'ica-parser-v8'})
    source_name = "ica-area-offers"
    attribution_text = "Befintliga baskällor med frivilliga butiksspecifika ICA-erbjudanden"

    def __init__(self, base, own: OwnGroceryPriceProvider, *, database: Path,
                 city: str, account_ids: frozenset[str], municipal_stores: dict | None = None):
        super().__init__(use_member_prices=False)
        self.base, self.own = base, own
        self.city, self.account_ids = city, account_ids
        self.municipal_stores = municipal_stores
        self.stores: dict[str, Store] = {}
        self.products: dict[str, list[Product]] = {}
        self.diagnostics: dict[str, dict] = {}
        try:
            self.evidence = qualification_evidence(database, chain=self.offer_chain)
        except (OSError, sqlite3.Error) as exc:
            self.evidence = {}
            self.diagnostics["evidence"] = {"status": "error", "error": type(exc).__name__}
        self.own.campaign_snapshot_ids = frozenset(r['snapshot_id'] for r in self.evidence.values()
            if r['scope_key'].endswith(':offer-rows') and r['parser_version'] in self.accepted_parsers)
        self._loaded = False

    async def find_stores(self, postal_code):
        baseline = await self.base.find_stores(postal_code)
        if not self._loaded:
            self._loaded = True
            try:
                if self.municipal_stores is None:
                    stores = await self.own.find_offer_stores(postal_code)
                else:
                    from app.errors import PriceProviderError
                    stores = []
                    for locality in sorted({s.city for s in self.municipal_stores.values() if s.city}):
                        try:
                            stores.extend(await self.own.find_offer_stores_in_locality(locality))
                        except PriceProviderError:
                            self.diagnostics['locality:' + locality] = {'status': 'no_qualified_source'}
            except Exception as exc:  # noqa: BLE001 - optional source must not block baseline
                self.diagnostics["discovery"] = {"status": "error", "error": type(exc).__name__}
                return baseline
            for store in stores:
                account = store.source_store_id
                if account not in self.account_ids:
                    continue
                if self.municipal_stores is None:
                    if store.city.casefold() != self.city.casefold():
                        continue
                else:
                    official = self.municipal_stores.get(account)
                    if (official is None or store.chain.casefold() != self.offer_chain
                            or store.address != official.address
                            or store.postal_code != ''.join((official.postal_code or '').split())
                            or store.city.casefold() != (official.city or '').casefold()):
                        self.diagnostics[account] = {'status': 'municipal_identity_mismatch'}
                        continue
                reasons = Counter()
                audit = {"status": "success", "received": 0, "accepted": 0, "rejected": {}}
                self.diagnostics[account] = audit
                try:
                    accepted = []
                    rows = await self.own.get_offers(store.store_id)
                    audit["received"] = len(rows)
                    audit["own_projection"] = getattr(self.own, "offer_projection_diagnostics", {}).get(store.store_id, {})
                    context_id = FederatedGroceryPriceProvider._context_id(store)
                    # Exact official ID or exact public address identifies a
                    # physical checkout. The product retains its OWN channel.
                    same_place = [s for s in baseline if s.chain.casefold() == self.offer_chain
                                  and s.price_context_type == "physical_store"
                                  and ((s.physical_store_external_id == account)
                                       or (s.address and s.postal_code and
                                           (s.address.casefold(), s.postal_code) ==
                                           ((store.address or "").casefold(), store.postal_code)))]
                    if len(same_place) == 1:
                        context_id = same_place[0].store_id
                    for product in rows:
                        evidence = self.evidence.get(product.product_id, {})
                        fields = json.loads(evidence.get("source_fields") or "{}")
                        if evidence.get("parser_version") not in self.accepted_parsers:
                            reasons["requires_condition_preserving_parser"] += 1
                            continue
                        terms = product.purchase_terms
                        bound = bool(terms and terms.model_dump(mode='json') == fields.get('purchase_terms')
                                     and terms.usage != 'blocked')
                        open_group = bound and terms.usage == 'variant_selection_required'
                        if (terms or fields.get('purchase_terms')) and not bound:
                            reasons['purchase_terms_source_mismatch'] += 1
                            continue
                        if ((not open_group and fields.get("variant_count") != 1)
                                or not self.exact_variant(product, fields, account)):
                            reasons["exact_single_variant_not_proven"] += 1
                            continue
                        if not bound and (str(product.sale_model) != "fixed_package" or not product.package_quantity):
                            reasons["exact_purchase_package_missing"] += 1
                            continue
                        provenance = product.source_provenance
                        if provenance is None or provenance.source_observed_at is None:
                            reasons["observation_missing"] += 1
                            continue
                        if self.municipal_stores is not None and (
                                evidence.get('external_id') != account
                                or not evidence.get('scope_key', '').endswith(':offer-rows')
                                or evidence.get('snapshot_id') != provenance.source_snapshot_id
                                or provenance.provider_store_id != store.store_id
                                or product.store_id != store.store_id
                                or product.chain.casefold() != self.offer_chain):
                            reasons['municipal_source_snapshot_identity_mismatch'] += 1
                            continue
                        offers = [o for o in product.offers if o.valid_to is not None]
                        if not offers:
                            reasons["bounded_contract_missing"] += 1
                            continue
                        offers = [o.model_copy(update={
                            "price_contract_id": o.price_contract_id if bound and o.price_contract_id else f"own:{provenance.source_snapshot_id}:{evidence['external_product_id']}",
                            # A currently displayed weekly offer is proven from
                            # observation, never retrospectively before it.
                            "valid_from": o.valid_from if o.campaign_evidence else o.valid_from or provenance.source_observed_at.astimezone(ZoneInfo("Europe/Stockholm")).date(),
                        }) for o in offers]
                        if any(o.campaign_evidence is not None and (
                            o.campaign_evidence.store_external_id != account
                            or o.campaign_evidence.offer_id != evidence['external_product_id']
                            or o.campaign_evidence.observed_current_at != provenance.source_observed_at)
                            for o in offers):
                            reasons['campaign_evidence_identity_mismatch'] += 1
                            continue
                        if not any(o.is_active(datetime.now(ZoneInfo("Europe/Stockholm")).date()) for o in offers):
                            reasons["no_current_contract"] += 1
                            continue
                        accepted.append(product.model_copy(update={
                            "store_id": context_id, "price": None, "offers": offers,
                            "promotion_groups": groups_in_context(product, context_id),
                            # OWN can retain a conditional ranking value in its
                            # generic sale field. It is not an unconditional
                            # one-package purchase price in this shared source.
                            "conditional_price_signal": not any(o for o in offers
                                if str(o.eligibility) == 'public' and o.required_packages == 1
                                and o.is_active(datetime.now(ZoneInfo('Europe/Stockholm')).date())),
                            "price_context_type": "physical_store", "coverage": "offers_only",
                            "source_provenance": provenance.model_copy(update={
                                "store_id": context_id, "provider_store_id": account,
                                "source_channel": "offers", "price_context": "physical_store",
                                **self.retailer_identity(fields),
                            }),
                        }))
                    self.products.setdefault(context_id, []).extend(accepted)
                    audit["accepted"] = len(accepted)
                    audit["rejected"] = dict(reasons)
                    if audit["accepted"] and not same_place:
                        self.stores[context_id] = store.model_copy(update={"store_id": context_id})
                except Exception as exc:  # noqa: BLE001 - isolate each optional store atomically
                    audit.update(status="error", error=type(exc).__name__)
        return [*baseline, *self.stores.values()]

    async def search_products(self, query, store_ids):
        base_ids = [s for s in store_ids if s not in self.stores]
        rows = await self.base.search_products(query, base_ids) if base_ids else []
        # Normal ProductMatcher remains the authority, as with frozen Primat.
        return [*rows, *(p for s in store_ids for p in self.products.get(s, []))]

    async def get_store_products(self, store_id):
        base = [] if store_id in self.stores else await self.base.get_store_products(store_id)
        return [*base, *self.products.get(store_id, [])]

    async def get_offers(self, store_id):
        base = [] if store_id in self.stores else await self.base.get_offers(store_id)
        return [*base, *self.products.get(store_id, [])]

    def report(self):
        return {**self.base.report(), "ica_area_offers": self.diagnostics}

    def exact_variant(self, product, fields, account):
        return bool(product.gtin or (product.purchase_terms
            and product.purchase_terms.usage == 'variant_selection_required'
            and product.purchase_terms.model_dump(mode='json') == fields.get('purchase_terms')))

    def retailer_identity(self, fields):
        return {}

    async def aclose(self):
        await self.base.aclose()

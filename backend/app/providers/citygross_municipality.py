"""Municipal City Gross sources projected through OWN, with exact source scope."""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime
from urllib.parse import urljoin, urlsplit

from app.errors import PriceProviderError
from app.providers.base import GroceryPriceProvider
from app.providers.federated import FederatedGroceryPriceProvider
from app.providers.ica_area_offers import IcaAreaOfferProvider
from app.services.source_promotion_groups import groups_in_context

from grocery_data.app.services.campaign_refresh_policy import STOCKHOLM


class CityGrossMunicipalityProvider(IcaAreaOfferProvider):
    source_name = "citygross-municipality"
    attribution_text = "Kommunvalda City Gross-källor från egen insamling"

    def __init__(self, base, sources, *, allow_empty_base=False):
        GroceryPriceProvider.__init__(self, use_member_prices=False)
        self.base = base
        self.sources = sources
        self.allow_empty_base = allow_empty_base
        self.stores, self.products, self.diagnostics = {}, {}, {}
        self._catalog_search_sources = {}
        self._validated_products = {}
        self._loaded = False

    async def find_stores(self, postal_code):
        # Explicit municipal scope replaces legacy locality/name selections,
        # including the verified zero-store case. Other chains are unchanged.
        try:
            baseline = [s for s in await self.base.find_stores(postal_code) if s.chain != "citygross"]
        except PriceProviderError:
            if not self.allow_empty_base:
                raise
            baseline = []
            self.diagnostics["base"] = {"status": "no_base_contexts_in_explicit_own_only_build"}
        if self._loaded:
            return [*baseline, *self.stores.values()]
        self._loaded = True
        for source in self.sources:
            try:
                await self._load_source(source, postal_code)
            except Exception as exc:  # noqa: BLE001 - optional source preserves valid base
                key = ",".join(source.get("store_ids", [])) or "setup"
                self.diagnostics[key] = {"status": "failed", "error_type": type(exc).__name__}
        return [*baseline, *self.stores.values()]

    async def _load_source(self, source, postal_code):
        from grocery_data.app.connectors.citygross.municipality_inventory import (
            approved_citygross_stores,
        )

        inventory = approved_citygross_stores(source["inventory"])
        selected = set(source["store_ids"])
        if not selected.issubset(inventory):
            raise ValueError("City Gross source selection lacks municipal proof")
        snapshots = set(source["snapshot_ids"])
        own = source["own"]
        with sqlite3.connect(source["database"].resolve().as_uri() + "?mode=ro&immutable=1", uri=True) as db:
            db.row_factory = sqlite3.Row
            evidence = {str(r["id"]): dict(r) for r in db.execute("""
                SELECT p.id, sp.external_product_id, sp.store_id, sp.store_external_id, sp.source_fields,
                       cs.id AS snapshot_id, cs.coverage FROM products p
                JOIN source_products sp ON sp.id=p.source_product_id
                JOIN catalog_snapshots cs ON cs.id=sp.catalog_snapshot_id
                WHERE cs.is_active=1 AND cs.state='promoted' AND sp.chain='citygross'
                  AND cs.coverage IN ('full_online_catalog','offers_only')
            """) if r["snapshot_id"] in snapshots}
        for identity in sorted(selected):
            official = inventory[identity]
            audit = {"status": "unknown", "received": 0, "accepted": 0, "rejected": {}}
            self.diagnostics[identity] = audit
            stores = await own._find_stores_for_coverage(
                postal_code, accepted_coverage={"full_online_catalog", "offers_only"},
                source_locality=official.city, empty_message="No qualified City Gross source")
            matches = [s for s in stores if s.chain == "citygross" and s.source_store_id == identity
                       and s.physical_store_external_id == official.physical_store_external_id
                       and s.price_context_type == "online_store" and s.address == official.address
                       and s.postal_code == "".join((official.postal_code or "").split())
                       and s.source_provenance and s.source_provenance.source_snapshot_id in snapshots]
            if len(matches) != 1:
                audit.update(status="missing_or_changed_official_identity")
                continue
            store = matches[0]
            context = FederatedGroceryPriceProvider._context_id(store)
            rows = await (own.get_offers(store.store_id) if store.coverage == "offers_only"
                          else own.get_store_products(store.store_id))
            audit["received"] = len(rows)
            accepted, reasons = [], Counter()
            today = datetime.now(STOCKHOLM).date()
            for product in rows:
                ev = evidence.get(product.product_id)
                prov = product.source_provenance
                if (not ev or ev["store_external_id"] != identity or not prov
                        or product.store_id != store.store_id or ev["store_id"] != store.store_id
                        or prov.provider_store_id not in {identity, store.store_id}
                        or prov.source_snapshot_id != ev["snapshot_id"]):
                    reasons["source_identity_mismatch"] += 1
                    continue
                fields = json.loads(ev["source_fields"] or "{}")
                metadata = {key: fields[key] for key in ("maximum_purchase_units",
                            "quantity_limit_source_url") if fields.get(key) is not None}
                if fields.get("official_product_url"):
                    url = urljoin("https://www.citygross.se/", fields["official_product_url"])
                    if urlsplit(url).netloc != "www.citygross.se" or urlsplit(url).scheme != "https":
                        reasons["unofficial_product_url"] += 1
                        continue
                    metadata["official_product_url"] = url
                if store.coverage == "offers_only" and (product.price is not None
                        or not any(o.is_active(today) for o in product.offers)):
                    reasons["no_current_offer_only_contract"] += 1
                    continue
                # Preserve online channel and exact source IDs. Coverage never
                # implies that an online campaign is a physical shelf price.
                accepted.append(product.model_copy(update={"store_id": context,
                    "promotion_groups": groups_in_context(product, context),
                    "price_context_type": "online_store", "coverage": store.coverage,
                    "source_provenance": prov.model_copy(update={"store_id": context,
                        "provider_store_id": identity,
                        "source_role": "offers" if store.coverage == "offers_only" else "basket",
                        "price_context": "online_store", "coverage": store.coverage,
                        "retailer_product_id": ev["external_product_id"],
                        "retailer_id_namespace": "citygross:online-product",
                        **metadata})}))
            audit.update(status="success", accepted=len(accepted), rejected=dict(reasons),
                         coverage=store.coverage, price_context="online_store")
            if accepted:
                if context in self.stores:
                    raise ValueError("duplicate approved City Gross price context")
                self.stores[context] = store.model_copy(update={"store_id": context,
                    "source_provenance": store.source_provenance.model_copy(update={
                        "store_id": context, "provider_store_id": identity,
                        "source_role": "offers" if store.coverage == "offers_only" else "basket"})})
                self.products[context] = accepted
                self._validated_products[context] = {p.product_id: p for p in accepted}
                if store.coverage == "full_online_catalog":
                    self._catalog_search_sources[context] = (own, store.store_id)

    async def search_products(self, query, store_ids):
        base_ids = [identity for identity in store_ids if identity not in self.stores]
        rows = await self.base.search_products(query, base_ids) if base_ids else []
        for context in store_ids:
            if context not in self.stores:
                continue
            if context not in self._catalog_search_sources:
                # Offers need the existing all-row matcher semantics because a
                # campaign may describe several ingredients in one source row.
                rows.extend(self.products[context])
                continue
            own, native_store_id = self._catalog_search_sources[context]
            hits = await own.search_products(query, [native_store_id])
            validated = self._validated_products[context]
            rows.extend(validated[hit.product_id] for hit in hits
                        if hit.store_id == native_store_id and hit.product_id in validated)
        return rows

    def report(self):
        return {**self.base.report(), "citygross_municipality": self.diagnostics}

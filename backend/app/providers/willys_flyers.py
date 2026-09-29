"""Optional exact municipal Willys reklamblad campaign rows through ordinary OWN projection."""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime

from app.errors import PriceProviderError
from app.providers.base import GroceryPriceProvider
from app.providers.federated import FederatedGroceryPriceProvider
from app.providers.ica_area_offers import IcaAreaOfferProvider
from app.services.source_promotion_groups import groups_in_context

from grocery_data.app.connectors.willys.flyer_contract import household_contract
from grocery_data.app.connectors.willys.flyer_inventory import approved_flyer_stores
from grocery_data.app.services.campaign_refresh_policy import STOCKHOLM
from grocery_data.app.services.offer_rows import WILLYS_FLYER_POLICIES


class WillysFlyerProvider(IcaAreaOfferProvider):
    source_name = "willys-flyer-offers"
    attribution_text = "Frivilliga kommunvalda Willys reklamblad-erbjudanden"

    def __init__(self, base, sources, *, allow_empty_base=False):
        GroceryPriceProvider.__init__(self, use_member_prices=False)
        self.base, self.sources, self.allow_empty_base = base, sources, allow_empty_base
        self.stores, self.products, self.diagnostics = {}, {}, {}
        self._loaded = False

    async def find_stores(self, postal_code):
        try:
            baseline = await self.base.find_stores(postal_code)
        except PriceProviderError:
            if not self.allow_empty_base:
                raise
            baseline = []
        if not self._loaded:
            self._loaded = True
            for source in self.sources:
                try:
                    await self._load_source(source)
                except Exception as exc:  # noqa: BLE001 - optional source
                    self.diagnostics[",".join(source["store_ids"])] = {"status": "failed", "error_type": type(exc).__name__}
        # This is source availability only. Existing checkout/user store filters
        # remain authoritative; no user preferences are written here.
        return [*baseline, *self.stores.values()]

    async def _load_source(self, source):
        official = approved_flyer_stores(source["inventory"])
        if not set(source["store_ids"]).issubset(official):
            raise ValueError("source escaped municipality")
        with sqlite3.connect(source["database"].resolve().as_uri() + "?mode=ro&immutable=1", uri=True) as db:
            db.row_factory = sqlite3.Row
            evidence = {str(r["id"]): dict(r) for r in db.execute("""SELECT p.id, sp.external_product_id,
                sp.store_external_id, sp.source_fields, cs.id AS snapshot_id, cs.parser_version, cs.scope_key
                FROM products p JOIN source_products sp ON sp.id=p.source_product_id
                JOIN catalog_snapshots cs ON cs.id=sp.catalog_snapshot_id
                WHERE cs.is_active=1 AND cs.state='promoted' AND cs.coverage='offers_only' AND sp.chain='willys'""")
                if r["snapshot_id"] in source["snapshot_ids"]}
        own = source["own"]
        for identity in source["store_ids"]:
            store = official[identity]
            stores = await own.find_offer_stores_in_locality(store.city)
            matches = [s for s in stores if s.chain == "willys" and s.source_store_id == identity
                and s.address == store.address and s.postal_code == "".join((store.postal_code or "").split())
                and s.price_context_type == "physical_store"]
            if len(matches) != 1:
                self.diagnostics[identity] = {"status": "missing_or_changed_official_identity"}
                continue
            native = matches[0]
            context = FederatedGroceryPriceProvider._context_id(native)
            rows = await own.get_offers(native.store_id)
            accepted, reasons = [], Counter()
            for product in rows:
                ev = evidence.get(product.product_id, {})
                fields = json.loads(ev.get("source_fields") or "{}")
                prov = product.source_provenance
                if (ev.get("parser_version") not in {"willys-flyer-text-v1", "willys-flyer-text-v2"} or not ev.get("scope_key", "").endswith(":offer-rows")
                        or fields.get("willys_flyer_policy") not in WILLYS_FLYER_POLICIES or not fields.get("willys_flyer_purchase_qualified")
                        or fields.get("purchase_blockers") or not fields.get("document_product_binding")
                        or not prov or ev.get("store_external_id") != identity
                        or prov.source_snapshot_id != ev.get("snapshot_id") or product.price is not None
                        or not product.offers or not all(o.campaign_evidence
                            and o.campaign_evidence.store_external_id == identity
                            and o.campaign_evidence.offer_id == ev["external_product_id"]
                            and o.campaign_evidence.observed_current_at == prov.source_observed_at
                            and o.price_contract_id and o.is_active(datetime.now(STOCKHOLM).date()) for o in product.offers)):
                    reasons["purchase_scope_or_campaign_unverified"] += 1
                    continue
                # Reconcile legacy/manual and automatic spelling/number formats
                # for the same source-declared household scope; no price changes.
                contract = household_contract(fields['document_product_binding'])
                accepted.append(product.model_copy(update={"store_id": context,
                    "promotion_groups": groups_in_context(product, context),
                    "offers": [o.model_copy(update={"price_contract_id": contract}) for o in product.offers],
                    "price_context_type": "physical_store",
                    "conditional_price_signal": not any(str(o.eligibility) == "public" and o.required_packages == 1 for o in product.offers),
                    "source_provenance": prov.model_copy(update={
                        "store_id": context, "provider_store_id": identity, "source_channel": "offers",
                        "source_role": "offers", "retailer_product_id": ev["external_product_id"],
                        "retailer_id_namespace": "willys:flyer-document-ad"})}))
            self.diagnostics[identity] = {"status": "success", "received": len(rows),
                "accepted": len(accepted), "rejected": dict(reasons),
                "own_projection": getattr(own, "offer_projection_diagnostics", {}).get(native.store_id, {})}
            if accepted:
                if context in self.stores:
                    raise ValueError("duplicate Willys reklamblad physical context")
                self.stores[context] = native.model_copy(update={"store_id": context})
                self.products[context] = accepted

    def report(self):
        return {**self.base.report(), "willys_flyers": self.diagnostics}

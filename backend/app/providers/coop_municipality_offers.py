"""Explicit optional physical Coop rows from approved municipality inventory.

Reuses OWN projection and the existing optional provider's search/materialisation
methods. Online, X:-tra and uncertain municipality identities are not admitted.
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.providers.base import GroceryPriceProvider
from app.providers.federated import FederatedGroceryPriceProvider
from app.providers.ica_area_offers import IcaAreaOfferProvider
from app.services.source_promotion_groups import groups_in_context


def approved_inventory(inventory, *, include_xtra=False):
    area = inventory.get("area", {})
    if area.get("mode") != "municipality" or not area.get("municipality_code"):
        raise ValueError("explicit municipality inventory required")
    from grocery_data.app.services.area_membership import approved_municipal_stores

    concepts = ("Coop", "Stora Coop", "X:-tra") if include_xtra else ("Coop", "Stora Coop")
    verified = approved_municipal_stores(inventory, concepts=concepts)
    selected = set(inventory.get("selected_store_ids", []))
    if not selected.issubset(verified):
        raise ValueError("selection is not bound to requested municipality")
    result = {}
    for row in inventory.get("stores", []):
        store = row["store"]
        fields = store["source_fields"]
        if store["external_id"] not in selected:
            continue
        if (
            store["chain"] != "coop"
            or row["geographic_evidence"]["status"] != "inside"
            or fields.get("concept") not in concepts
            or fields.get("identity_conflict")
            or not store.get("address")
            or not store.get("city")
            or not fields.get("ledger_account_number")
        ):
            raise ValueError("unverified municipality/store identity")
        if store["external_id"] in result:
            raise ValueError("duplicate physical store identity")
        result[store["external_id"]] = store
    if set(result) != selected:
        raise ValueError("inventory selection lacks store evidence")
    return result


class CoopMunicipalityOfferProvider(IcaAreaOfferProvider):
    source_name = "coop-municipality-offers"
    attribution_text = "Befintliga baskällor med frivilliga fysiska Coop-erbjudanden"

    def __init__(self, base, own, *, database: Path, inventory: dict, include_xtra=False):
        GroceryPriceProvider.__init__(self, use_member_prices=False)
        self.base, self.own = base, own
        self.stores, self.products, self.diagnostics = {}, {}, {}
        self._loaded = False
        self.selected, self.evidence = {}, {}
        try:
            self.selected = approved_inventory(inventory, include_xtra=include_xtra)
            with sqlite3.connect(
                f"file:{database.resolve().as_posix()}?mode=ro&immutable=1", uri=True
            ) as db:
                db.row_factory = sqlite3.Row
                rows = db.execute("""SELECT p.id, sp.source_fields, sp.external_product_id,
                    s.external_id, cs.parser_version, cs.id AS snapshot_id, cs.scope_key
                    FROM products p JOIN source_products sp ON sp.id=p.source_product_id
                    JOIN stores s ON s.id=sp.store_id
                    JOIN catalog_snapshots cs ON cs.id=sp.catalog_snapshot_id
                    WHERE cs.is_active=1 AND cs.state='promoted' AND sp.chain='coop'
                    AND cs.coverage='offers_only'""").fetchall()
            self.evidence = {str(r["id"]): dict(r) for r in rows}
        except (OSError, ValueError, KeyError, sqlite3.Error) as exc:
            self.selected = {}
            self.diagnostics["setup"] = {"status": "error", "error": type(exc).__name__}

    async def find_stores(self, postal_code):
        baseline = await self.base.find_stores(postal_code)
        if self._loaded:
            return [*baseline, *self.stores.values()]
        self._loaded = True
        for account, official in self.selected.items():
            audit = {"status": "unknown", "received": 0, "accepted": 0, "rejected": {}}
            self.diagnostics[account] = audit
            try:
                stores = await self.own.find_offer_stores_in_locality(official["city"])
                matches = [
                    s
                    for s in stores
                    if s.chain == "coop"
                    and s.source_store_id == account
                    and s.price_context_type == "physical_store"
                    and s.address == official["address"]
                    and s.postal_code == official["postal_code"]
                ]
                if len(matches) != 1:
                    audit.update(status="missing_or_changed_official_identity")
                    continue
                store = matches[0]
                same_place = [
                    s
                    for s in baseline
                    if s.chain == "coop"
                    and s.price_context_type == "physical_store"
                    and (
                        s.physical_store_external_id == account
                        or (
                            s.address
                            and s.postal_code
                            and (s.address.casefold(), s.postal_code)
                            == (store.address.casefold(), store.postal_code)
                        )
                    )
                ]
                if len(same_place) > 1:
                    audit.update(status="ambiguous_physical_identity")
                    continue
                context = (
                    same_place[0].store_id
                    if same_place
                    else FederatedGroceryPriceProvider._context_id(store)
                )
                rows = await self.own.get_offers(store.store_id)
                audit["received"] = len(rows)
                accepted = []
                reasons = Counter()
                today = datetime.now(ZoneInfo("Europe/Stockholm")).date()
                for product in rows:
                    ev = self.evidence.get(product.product_id, {})
                    fields = json.loads(ev.get("source_fields") or "{}")
                    terms = product.purchase_terms
                    bound = bool(terms and terms.model_dump(mode='json') == fields.get('purchase_terms') and terms.usage != 'blocked')
                    if (
                        ev.get("parser_version") not in ({"xtra-pdf-text-v1", "xtra-pdf-text-v2"} if official["source_fields"]["concept"] == "X:-tra" else {"coop-parser-v3", "coop-parser-v4", "coop-parser-v5", "coop-parser-v6", "coop-parser-v7", "coop-parser-v8"})
                        or not ev.get("scope_key", "").endswith(":offer-rows")
                        or fields.get("coop_physical_policy") != ("coop-xtra-pdf-text-v1" if official["source_fields"]["concept"] == "X:-tra" else "coop-physical-structured-v1")
                        or fields.get("coop_purchase_qualified") is not True
                        or (fields.get("variant_count") != 1 and not (bound and terms.usage=='variant_selection_required'))
                        or ((terms or fields.get('purchase_terms')) and not bound)
                        or fields.get("purchase_blockers")
                    ):
                        reasons["row_qualification_unverified"] += 1
                        continue
                    provenance = product.source_provenance
                    if (
                        ev.get("external_id") != account
                        or not provenance
                        or provenance.provider_store_id != account
                        or provenance.source_snapshot_id != ev.get("snapshot_id")
                        or product.price is not None
                        or (not bound and (str(product.sale_model) != "fixed_package" or not product.package_quantity))
                        or not product.offers
                    ):
                        reasons["source_purchase_identity_mismatch"] += 1
                        continue
                    if any(
                        not o.campaign_evidence
                        or o.campaign_evidence.store_external_id != account
                        or o.campaign_evidence.offer_id != ev["external_product_id"]
                        or o.campaign_evidence.observed_current_at != provenance.source_observed_at
                        or not o.price_contract_id
                        for o in product.offers
                    ):
                        reasons["campaign_evidence_mismatch"] += 1
                        continue
                    if not any(o.is_active(today) for o in product.offers):
                        reasons["no_current_contract"] += 1
                        continue
                    # Preserve the existing cross-store household cap identity.
                    accepted.append(
                        product.model_copy(
                            update={
                                "store_id": context,
                                "promotion_groups": groups_in_context(product, context),
                                "price_context_type": "physical_store",
                                "source_provenance": provenance.model_copy(
                                    update={"store_id": context, "source_channel": "offers",
                                            "retailer_product_id": fields.get("source_variant_id"),
                                            "retailer_id_namespace": "coop:public-product" if official["source_fields"]["concept"] != "X:-tra" else None,
                                            "retailer_identity_source_sha256": fields.get("source_sha256")}
                                ),
                            }
                        )
                    )
                self.products[context] = accepted
                audit.update(status="success", accepted=len(accepted), rejected=dict(reasons))
                if accepted and not same_place:
                    self.stores[context] = store.model_copy(update={"store_id": context})
            except Exception as exc:  # noqa: BLE001 - optional store cannot break a valid base
                audit.update(status="error", error=type(exc).__name__)
        return [*baseline, *self.stores.values()]

    def report(self):
        base = self.base.report()
        return {**base, "coop_municipality_offers": {**base.get("coop_municipality_offers", {}), **self.diagnostics}}

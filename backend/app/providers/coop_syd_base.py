"""Apply the owner's explicit Stora Coop base-price policy in normal builds.

The existing OWN catalogue supplies ordinary prices and immutable lineage.
Physical campaigns continue through the ordinary municipal offer provider.
"""

from app.errors import PriceProviderError
from app.models import Store
from app.providers.base import GroceryPriceProvider
from app.providers.coop_municipality_offers import approved_inventory
from app.providers.federated import FederatedGroceryPriceProvider

from grocery_data.app.domain.coop_syd_base import (
    POLICY_VERSION,
    SOURCE_CONTEXT_ID,
    TARGETS,
)


def assigned_stores(inventory):
    code = inventory.get("area", {}).get("municipality_code")
    expected = TARGETS.get(code, {})
    if not expected:
        return {}
    approved = approved_inventory(inventory, include_xtra=True)
    result = {}
    for identity, ledger in expected.items():
        if identity not in approved:
            continue
        store = approved[identity]
        fields = store["source_fields"]
        if (fields.get("ledger_account_number") != ledger
                or fields.get("source_id_namespace") != "coop-public-store-registry"):
            raise ValueError("Stora Coop base-price assignment identity changed")
        result[identity] = store
    return result


class CoopSydBaseProvider(GroceryPriceProvider):
    source_name = "stora-coop-syd-base"
    attribution_text = "Stora Coop med baspriser från Coop Online Syd"

    def __init__(self, base, own, *, inventory):
        super().__init__(use_member_prices=False)
        self.base, self.own = base, own
        self.targets = assigned_stores(inventory)
        self.stores, self.products = {}, {}
        self.diagnostics = {}
        self._loaded = False

    async def find_stores(self, postal_code):
        baseline = await self.base.find_stores(postal_code)
        self._baseline_ids = {s.store_id for s in baseline}
        if not self.targets:
            return baseline
        if not self._loaded:
            # Look up the source in its existing verified service area. This
            # reads the frozen OWN database, never another retailer or network.
            sources = await self.own.find_stores("22660")
            sources = [s for s in sources if s.chain == "coop"
                       and s.source_store_id == SOURCE_CONTEXT_ID
                       and s.price_context_type == "online_fulfillment"
                       and s.coverage == "full_online_catalog"]
            if len(sources) != 1:
                raise PriceProviderError("Coop Online Syd base source is unavailable or ambiguous")
            source = sources[0]
            lineage = source.source_provenance
            if (not lineage or lineage.source_provider != "own"
                    or lineage.provider_store_id != SOURCE_CONTEXT_ID):
                raise PriceProviderError("Coop Online Syd base source lacks exact lineage")
            rows = await self.own.get_store_products(source.store_id)
            ordinary = []
            for product in rows:
                if product.price is None or product.price <= 0:
                    continue
                provenance = product.source_provenance
                # OWN catalog rows use the verified local StoreModel ID;
                # store discovery supplies its exact public 730400 mapping.
                if (product.store_id != source.store_id or product.chain != "coop"
                        or not provenance or provenance.source_provider != "own"
                        or provenance.source_channel != "catalog"
                        or provenance.provider_store_id not in {SOURCE_CONTEXT_ID, source.store_id}
                        or provenance.source_snapshot_id != lineage.source_snapshot_id):
                    raise PriceProviderError("Coop Online Syd product lineage changed")
                ordinary.append(product)
            if not ordinary:
                raise PriceProviderError("Coop Online Syd has no qualified ordinary prices")
            for identity, official in self.targets.items():
                matches = [s for s in baseline if s.chain == "coop"
                           and s.price_context_type == "physical_store"
                           and s.physical_store_external_id == identity]
                if len(matches) > 1:
                    raise PriceProviderError("Ambiguous Stora Coop destination")
                target = matches[0] if matches else Store(
                    store_id="own:coop:" + identity, chain="coop", name=official["name"],
                    city=official["city"], address=official["address"],
                    postal_code=official["postal_code"], latitude=official.get("latitude"),
                    longitude=official.get("longitude"), physical_store_external_id=identity,
                    source_store_id=identity, price_context_type="physical_store",
                )
                if (target.address != official["address"]
                        or target.postal_code != official["postal_code"]
                        or target.city.casefold() != official["city"].casefold()):
                    raise PriceProviderError("Stora Coop destination identity changed")
                context = (target.store_id if matches else
                           FederatedGroceryPriceProvider._context_id(target))
                provenance = lineage.model_copy(update={
                    "store_id": context, "source_role": "owner_assigned_base_price",
                })
                self.stores[context] = target.model_copy(update={
                    "store_id": context, "coverage": "full_online_catalog",
                    "tier": "full_online_catalog", "price_semantics": "online_price",
                    "price_label": "Baspris från Coop Online Syd",
                    "confirmed_at": lineage.source_observed_at.isoformat(),
                    "source_provenance": provenance,
                })
                self.products[context] = [p.model_copy(update={
                    "product_id": p.product_id + ":stora-syd:" + identity,
                    "store_id": context, "store_name": target.name,
                    "price_context_type": "physical_store", "coverage": "full_online_catalog",
                    "price": p.price, "effective_price": p.price, "sale_price": p.price,
                    "member_price": None, "offers": [], "promotion_groups": (),
                    "purchase_terms": None, "conditional_price_signal": False,
                    "conditional_variant_choice": False,
                    "source_provenance": p.source_provenance.model_copy(update={
                        "store_id": context, "source_role": "owner_assigned_base_price",
                        "provider_store_id": SOURCE_CONTEXT_ID,
                        "price_context": source.price_context_type,
                    }),
                }) for p in ordinary]
                self.diagnostics[identity] = {
                    "context_id": context, "base_products": len(ordinary),
                    "source_snapshot_id": lineage.source_snapshot_id,
                    "source_observed_at": lineage.source_observed_at.isoformat(),
                }
            self._loaded = True
        # Replace the metadata of the same physical checkout; no duplicate shop.
        return [*(s for s in baseline if s.store_id not in self.stores),
                *self.stores.values()]

    async def search_products(self, query, store_ids):
        base_ids = [s for s in store_ids if s in self._baseline_ids]
        rows = await self.base.search_products(query, base_ids) if base_ids else []
        return [*rows, *(p for s in store_ids for p in self.products.get(s, []))]

    async def get_store_products(self, store_id):
        # New destinations can exist even when their weekly offer feed is empty.
        rows = await self.base.get_store_products(store_id) if store_id in self._baseline_ids else []
        return [*rows, *self.products.get(store_id, [])]

    async def get_offers(self, store_id):
        return await self.base.get_offers(store_id) if store_id in self._baseline_ids else []

    def report(self):
        return {**self.base.report(), "stora_coop_syd_base": {
            "policy": POLICY_VERSION, "stores": self.diagnostics,
        }}

    async def aclose(self):
        await self.base.aclose()

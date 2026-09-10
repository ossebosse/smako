"""Consumer retrieval over the activated artifact. No provider dependencies or I/O.

Text postings only select alternatives. Only validated GTIN evidence groups rows;
conflicting package evidence deliberately splits even a shared GTIN.
"""

from __future__ import annotations

import hashlib
import re
from bisect import bisect_left
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal
from zoneinfo import ZoneInfo

from app.models.product import ProductCandidate, QuantityConfidence, SaleModel
from app.services.ingredient_normalizer import _search_text
from app.services.price_universe_runtime import normalized_memberships
from app.services.product_lookup import _package_description
from app.services.user_pricing import price_contracts_for_candidate
from pydantic import BaseModel, ConfigDict, Field, field_validator

from grocery_data.app.domain.identifiers import InvalidGtinError, normalize_gtin
from grocery_data.app.domain.promotion_pricing import (
    MembershipProgram,
    PromotionEligibility,
    PromotionMechanism,
    UserPricingContext,
)
from grocery_data.app.services.fixed_checkout_price import resolve_effective_price

if TYPE_CHECKING:
    from app.services.price_universe_runtime import PreparedPriceUniverse

_VARIANTS = {
    "mjolken": "mjolk",
    "kaffet": "kaffe",
    "kaffen": "kaffe",
    "kycklingfileer": "kycklingfile",
    "toalettpappret": "toalettpapper",
    "agg": "agg",
    "aggen": "agg",
    "potatisar": "potatis",
}
_COMPOUNDS = ("mjolk", "kaffe", "kycklingfile", "toalettpapper")
_COFFEE_TERMS = {
    "kaffe",
    "bryggkaffe",
    "kokkaffe",
    "snabbkaffe",
    "pulverkaffe",
    "bonkaffe",
    "espressokaffe",
    "kaffebonor",
    "espressobonor",
}
_QUANTITY = re.compile(r"(\d+(?:[.,]\d+)?)\s*(kg|gram|g|ml|cl|dl|liter|litre|l|st)\b")
_CHAIN_LABELS = {
    "coop": "Coop",
    "hemkop": "Hemköp",
    "willys": "Willys",
    "ica": "ICA",
    "lidl": "Lidl",
    "citygross": "City Gross",
}


def search_text(value: str) -> str:
    """Reuse Swedish metadata normalization; normalize explicit query quantities."""

    def quantity(match: re.Match) -> str:
        amount = Decimal(match[1].replace(",", "."))
        unit = match[2]
        factor, base = {
            "kg": (1000, "g"),
            "gram": (1, "g"),
            "g": (1, "g"),
            "l": (1000, "ml"),
            "liter": (1000, "ml"),
            "litre": (1000, "ml"),
            "dl": (100, "ml"),
            "cl": (10, "ml"),
            "ml": (1, "ml"),
            "st": (1, "st"),
        }[unit]
        return f" {format((amount * factor).normalize(), 'f')} {base} "

    value = _QUANTITY.sub(quantity, value.casefold())
    tokens = re.findall(r"[a-z0-9]+", _search_text(value))
    return " ".join(_VARIANTS.get(token, token) for token in tokens)


class ProductSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    query: str = Field(min_length=1, max_length=120)
    postal_code: str = Field(default="22350", pattern=r"^[0-9]{5}$")
    memberships: tuple[MembershipProgram, ...] = Field(default=(), max_length=6)
    limit: int = Field(default=20, ge=1, le=40)
    offset: int = Field(default=0, ge=0, le=1000)
    view: Literal["relevance", "cheapest", "campaigns", "multiple", "unit"] = "relevance"
    unit: Literal["kg", "l", "st"] | None = None
    product_key: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        value = value.strip()
        if not search_text(value):
            raise ValueError("Skriv ett produktnamn eller en streckkod.")
        if re.fullmatch(r"[0-9 -]+", value):
            normalize_gtin(value)
        return value

    @field_validator("postal_code", mode="before")
    @classmethod
    def postal(cls, value: str) -> str:
        return str(value).replace(" ", "")


class ProductSearchIndex:
    """Immutable postings and prevalidated contracts prepared before activation."""

    def __init__(self, prepared: PreparedPriceUniverse):
        self.prepared = prepared
        self.stores = MappingProxyType({s.store_id: s for s in prepared.stores})
        postings, names, groups, gtins = (defaultdict(set) for _ in range(4))
        row_keys, contracts = {}, {}
        coffee_related = set()
        non_human_food = set()
        for i, product in enumerate(prepared.universe.products):
            if product.store_id not in self.stores:
                continue
            gtin = None
            if product.gtin:
                try:
                    gtin = normalize_gtin(product.gtin).normalized_gtin
                except InvalidGtinError:
                    pass
            # Unknown or contradictory sizes cannot silently inherit a comparison.
            package = (product.package_quantity, product.package_unit, product.sale_model)
            evidence = (
                ("gtin", gtin, package)
                if gtin and package[0]
                else ("context_product", product.store_id, product.product_id)
            )
            key = hashlib.sha256(repr(evidence).encode()).hexdigest()[:32]
            if (
                product.product_role == "non_human_food"
                or product.canonical_food == "non_human_food"
            ):
                non_human_food.add(key)
            row_keys[i] = key
            groups[key].add(i)
            if gtin:
                gtins[gtin].add(key)
            package_text = _package_description(product) or ""
            for name in (
                product.name,
                f"{product.name} {package_text}",
                f"{product.brand or ''} {product.name} {package_text}",
            ):
                names[search_text(name)].add(key)
            text = search_text(f"{product.name} {product.brand or ''} {package_text}")
            if re.search(r"\b(?:till|for|med) kaffe\b", text):
                coffee_related.add(key)
            tokens = set(text.split())
            # Compound heads match goods, not accessories or flavoured sweets.
            tokens.update(
                {
                    term
                    for term in _COMPOUNDS
                    if term != "kaffe" and any(t.endswith(term) for t in tokens)
                }
            )
            if tokens & _COFFEE_TERMS or set(search_text(product.category).split()) & _COFFEE_TERMS:
                tokens.add("kaffe")
            for token in tokens:
                postings[token].add(key)
            candidate = ProductCandidate.from_product(product, 1)
            try:
                contracts[i] = tuple(
                    c
                    for c in price_contracts_for_candidate(candidate)
                    if c.eligibility in {PromotionEligibility.PUBLIC, PromotionEligibility.MEMBER}
                )
            except ValueError:
                # Invalid offer axes cannot become an authoritative campaign.
                candidate = candidate.model_copy(
                    update={"offers": [], "member_price": None, "effective_price": product.price}
                )
                contracts[i] = price_contracts_for_candidate(candidate)
        self.postings = MappingProxyType({k: frozenset(v) for k, v in postings.items()})
        self.names = MappingProxyType({k: frozenset(v) for k, v in names.items()})
        self.groups = MappingProxyType({k: tuple(sorted(v)) for k, v in groups.items()})
        self.gtins = MappingProxyType({k: frozenset(v) for k, v in gtins.items()})
        self.contracts = MappingProxyType(contracts)
        self.vocabulary = tuple(sorted(postings))
        self.row_count = len(row_keys)
        self.coffee_related = frozenset(coffee_related)
        self.non_human_food = frozenset(non_human_food)
        # Reporting the existing chain universe grants no context eligibility.
        # Missing artifacts cannot tell us whether a source failed or a mapping
        # is absent; use a truthful general reason, never manufacture freshness.
        self.chain_contexts = MappingProxyType(
            {
                chain: frozenset(s.store_id for s in self.stores.values() if s.chain == chain)
                for chain in sorted(
                    set(normalized_memberships({})) | {s.chain for s in self.stores.values()}
                )
            }
        )

    def retrieve(self, request: ProductSearchRequest):
        query = search_text(request.query)
        if request.product_key:
            return (
                {request.product_key} if request.product_key in self.groups else set(),
                set(),
                False,
            )
        if re.fullmatch(r"[0-9 -]+", request.query):
            keys = self.gtins.get(normalize_gtin(request.query).normalized_gtin, frozenset())
            return set(keys), set(keys), True
        exact = set(self.names.get(query, ()))
        matches = None
        for token in set(query.split()):
            keys = set(self.postings.get(token, ()))
            if not keys and len(token) >= 3:
                start = bisect_left(self.vocabulary, token)
                # Bounded prefix expansion, never a fuzzy scan over product rows.
                for word in self.vocabulary[start : start + 32]:
                    if not word.startswith(token):
                        break
                    keys.update(self.postings[word])
            matches = keys if matches is None else matches & keys
        selected = (matches or set()) | exact
        if query == "kaffe":
            selected -= self.coffee_related
        if query in {"kaffe", "mjolk", "kycklingfile"}:
            selected -= self.non_human_food
        return selected, exact, False

    def search(
        self,
        request: ProductSearchRequest,
        *,
        now: datetime,
        stale_hours: float = 48,
        warning_hours: float = 36,
    ) -> dict:
        prepared = self.prepared
        usable, stale, ages = prepared._context_partition(now=now, stale_age_hours=stale_hours)
        states = tuple((key, "AGING" if ages[key] >= warning_hours else "FRESH") for key in usable)
        target_date = now.astimezone(ZoneInfo("Europe/Stockholm")).date()
        user = UserPricingContext(memberships=request.memberships)
        cache_key = repr(
            (
                prepared.universe.universe_id,
                request.model_dump_json(),
                user.cache_identity,
                states,
                stale,
                target_date,
            )
        )
        return prepared.product_search_cache.get_or_compute(
            cache_key,
            lambda: self._results(request, usable, stale, dict(states), target_date, user),
        )

    def _price(self, position, states, target_date, user):
        product = self.prepared.universe.products[position]
        store = self.stores[product.store_id]
        contracts = self.contracts[position]
        resolution = resolve_effective_price(contracts, 1, user, on_date=target_date)
        public = resolve_effective_price(contracts, 1, UserPricingContext(), on_date=target_date)
        effective = float(resolution.displayed_unit_price)
        promotions = []
        for contract in contracts:
            if not contract.is_active(target_date) or contract.mechanism in {
                PromotionMechanism.REGULAR,
                PromotionMechanism.OTHER,
            }:
                continue
            price = contract.resolved_price(Decimal(str(product.price)))
            if price is None:
                continue
            promotions.append(
                {
                    "description": contract.description,
                    "price": float(price),
                    "required_packages": contract.required_packages,
                    "max_quantity": contract.max_quantity,
                    "membership_required": contract.eligibility == PromotionEligibility.MEMBER,
                    "membership_label": (
                        contract.membership_program.consumer_label
                        if contract.membership_program
                        else None
                    ),
                    "eligible": user.allows(contract),
                    "valid_from": contract.valid_from,
                    "valid_to": contract.valid_to,
                }
            )
        fixed = product.sale_model in {SaleModel.FIXED_PACKAGE, SaleModel.SOLD_BY_PIECE}
        unit_price = unit = None
        if (
            fixed
            and product.package_quantity
            and product.package_unit
            and product.quantity_confidence
            in {QuantityConfidence.EXACT, QuantityConfidence.DERIVED}
        ):
            unit = {"g": "kg", "ml": "l", "st": "st"}[product.package_unit]
            unit_price = round(
                effective * (1 if unit == "st" else 1000) / product.package_quantity, 2
            )
        online = store.price_semantics == "online_price" or (
            store.price_context_type or ""
        ).casefold() in {"online_fulfillment", "online_store"}
        linked = (store.price_context_type or "").casefold() in {
            "physical_store",
            "physical-store",
            "store_linked",
        }
        applied = resolution.applied_promotion
        source = product.source_provenance
        return {
            "chain": store.chain,
            "store_name": store.name,
            "context_type": store.price_context_type,
            "context_label": "Onlinepris"
            if online
            else ("Butikskopplat pris" if linked else "Annat prisunderlag"),
            "availability_label": "Källrapporterat sortiment; inte lagerbesked eller garanterat hyllpris.",
            "regular_price": product.price,
            "current_public_price": float(public.displayed_unit_price),
            "effective_price": effective if fixed else None,
            "price_basis": "package" if fixed else "not_compared",
            "comparison_reason": (
                "package_semantics_unproven"
                if not fixed
                else "quantity_not_verified"
                if unit_price is None
                else None
            ),
            "comparison_label": (
                "Relevant produkt, men förpackningens pris eller mängd kan inte jämföras säkert."
                if not fixed
                else "Aktuellt förpackningspris. Jämförpris saknas eftersom mängden är osäker."
                if unit_price is None
                else "Aktuellt jämförbart pris."
            ),
            "sale_unit": product.sale_unit,
            "unit_price": unit_price,
            "unit": unit,
            "membership_required": bool(
                applied and applied.eligibility == PromotionEligibility.MEMBER
            ),
            "membership_label": (
                applied.membership_program.consumer_label
                if applied and applied.membership_program
                else None
            ),
            "promotions": promotions,
            "freshness": states[product.store_id],
            "observed_at": source.source_observed_at if source else None,
            "source_provider": source.source_provider if source else None,
            **(
                {"collection_location": source.collection_location}
                if source and source.collection_location
                else {}
            ),
        }

    def _results(self, request, usable, stale, states, target_date, user):
        keys, exact, barcode = self.retrieve(request)
        results = []
        matching_chains = set()
        # Bounded by the immutable beta dataset; no raw-row scan. Only postings hits.
        for key in sorted(keys):
            positions = [
                i for i in self.groups[key] if self.prepared.universe.products[i].store_id in usable
            ]
            if not positions:
                continue
            # One comparison per approved context. Repeated source listings do
            # not manufacture another store; retain its latest observation.
            positions = list(
                {
                    self.prepared.universe.products[i].store_id: i
                    for i in sorted(
                        positions,
                        key=lambda i: (
                            self.prepared.universe.products[i].source_provenance.source_observed_at,
                            i,
                        ),
                    )
                }.values()
            )
            prices = [self._price(i, states, target_date, user) for i in positions]
            matching_chains.update(p["chain"] for p in prices)
            prices.sort(
                key=lambda p: (
                    p["effective_price"] is None,
                    p["effective_price"] or float("inf"),
                    p["store_name"],
                )
            )
            product = self.prepared.universe.products[positions[0]]
            verified = bool(product.gtin and product.gtin in self.gtins)
            row = {
                "product_key": key,
                "name": product.name,
                "brand": product.brand,
                "package": _package_description(product),
                "gtin": product.gtin if verified else None,
                "identity_basis": "verified_gtin" if verified else "context_product",
                "comparison_semantics": "same_product" if verified else "single_context_product",
                "prices": prices,
                "best_price": prices[0]["effective_price"],
                "has_campaign": any(p["promotions"] for p in prices),
            }
            if request.view == "campaigns" and not row["has_campaign"]:
                continue
            if request.view == "multiple" and not (verified and len(prices) > 1):
                continue
            if request.view == "unit":
                compatible = [
                    p["unit_price"]
                    for p in prices
                    if p["unit"] == request.unit and p["unit_price"] is not None
                ]
                if not compatible or request.unit is None:
                    continue
                row["sort_unit_price"] = min(compatible)
            results.append(row)
        results.sort(
            key=lambda r: (
                0 if request.view != "relevance" or r["product_key"] in exact else 1,
                r.get("sort_unit_price", r["best_price"]) is None,
                r.get("sort_unit_price", r["best_price"]) or float("inf"),
                r["name"],
                r["product_key"],
            )
        )
        specific = len(results) == 1 and results[0]["identity_basis"] == "verified_gtin"
        page = results[request.offset : request.offset + request.limit]
        result_chains = {p["chain"] for row in results for p in row["prices"]}
        page_chains = {p["chain"] for row in page for p in row["prices"]}
        coverage = []
        for chain, contexts in self.chain_contexts.items():
            current = contexts.intersection(usable)
            old = contexts.intersection(stale)
            if not contexts:
                status, reason, label = (
                    "INELIGIBLE",
                    "no_eligible_price_context",
                    "Saknar aktuellt verifierat prisunderlag",
                )
            elif not current:
                status, reason, label = "STALE", "stale_price_contexts", "Prisunderlag för gammalt"
            elif chain in page_chains:
                status, reason, label = "VISIBLE", "current_match", "Aktuell"
            elif chain in result_chains:
                status, reason, label = (
                    "OTHER",
                    "outside_page",
                    "Aktuella träffar på andra resultatsidor",
                )
            elif chain in matching_chains:
                status, reason, label = "OTHER", "filtered_out", "Ingen träff med valt filter"
            else:
                status, reason, label = (
                    "NO_MATCH",
                    "no_exact_identity" if barcode else "no_relevant_match",
                    "Ingen verifierad streckkodsträff" if barcode else "Ingen relevant träff",
                )
            coverage.append(
                {
                    "chain": chain,
                    "label": _CHAIN_LABELS.get(chain, chain.title()),
                    "status": status,
                    "reason": reason,
                    "status_label": label,
                    "current_contexts": len(current),
                    "stale_contexts": len(old),
                }
            )
        return {
            "query": request.query,
            "price_universe_id": self.prepared.universe.universe_id,
            "price_area": self.prepared.universe.key.city,
            "postal_code": request.postal_code,
            "semantics": "exact_identity" if specific else "matching_alternatives",
            "exact_gtin": barcode,
            "exact_match_found": bool(results) if barcode else bool(exact),
            "searchable_products": len(self.groups),
            "index_rows": self.row_count,
            "total": len(results),
            "offset": request.offset,
            "next_offset": request.offset + request.limit
            if request.offset + request.limit < min(len(results), 1040)
            else None,
            "excluded_stale_context_count": len(stale),
            "live_provider_calls": 0,
            "chain_coverage": coverage,
            "results": page,
        }

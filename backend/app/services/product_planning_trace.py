"""Bounded request-local evidence of actual product decisions, not inferred losses."""
import hashlib
import json


def recipe_identity(recipe):
    if recipe is None:
        return {"id": "explicit-shopping", "name": None}
    # Derived canonical names are added by clean_recipe. They must not split
    # the same real recipe into unrelated pre/post qualification traces.
    value = recipe.model_dump(mode="json", exclude={"ingredients": {"__all__": {"canonical_name"}}})
    return {"id": hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:20], "name": recipe.name}


class ProductPlanningTrace:
    def __init__(self, prepared, *, limit=256, event_limit=4096):
        self.limit, self.event_limit = limit, event_limit
        self.products = {}
        self.omitted_products = 0
        self.omitted_events = 0
        self.context_count = 0
        self.recipe_needs = {}
        self.comparisons = []
        self.search = {}
        self._recipe_ids = {}
        indexes = {}
        pool = prepared.economic_pool
        for label, index in (("economic", pool.candidates_by_name),
                             ("matched", pool.matched_candidates_by_name)):
            for name, candidates in index.items():
                for c in candidates:
                    indexes.setdefault((c.store_id, c.product_id), {}).setdefault(label, set()).add(name)
        for p in prepared.universe.products:
            if not (p.purchase_terms or p.coverage == "offers_only"):
                continue
            key = (p.store_id, p.product_id)
            if len(self.products) >= limit:
                self.omitted_products += 1
                continue
            prov = p.source_provenance
            self.products[key] = {
                "product_id": p.product_id, "name": p.name, "store_id": p.store_id,
                "store_name": p.store_name, "chain": p.chain, "channel": p.price_context_type,
                "source_product_id": prov.retailer_product_id if prov else None,
                "snapshot_id": prov.source_snapshot_id if prov else None,
                "observed_at": prov.source_observed_at.isoformat() if prov and prov.source_observed_at else None,
                "offers": [{"id": o.price_contract_id,
                            "source_offer_id": o.campaign_evidence.offer_id if o.campaign_evidence else None,
                            "price": o.price, "required_packages": o.required_packages,
                            "membership": o.membership_program, "valid_from": str(o.valid_from), "valid_to": str(o.valid_to)}
                           for o in p.offers],
                "indexes": {k: sorted(v) for k, v in indexes.get(key, {}).items()},
                "contexts": {}, "selected": False,
            }

    def identity(self, recipe):
        key = id(recipe)
        if key not in self._recipe_ids:
            if len(self._recipe_ids) >= 512:
                self._recipe_ids.clear()
            self._recipe_ids[key] = (recipe, recipe_identity(recipe))
        return self._recipe_ids[key][1]

    def search_decision(self, slots, outcome, *, result=None, reason=None, depth=None):
        # Aggregate actual beam events per recipe. Never infer economic loss
        # from a pruned branch; retain one complete quote as concrete evidence.
        for slot in slots:
            if slot.recipe is None:
                continue
            identity = self.identity(slot.recipe)
            if identity["id"] not in self.search and len(self.search) >= 512:
                continue
            row = self.search.setdefault(identity["id"], {"recipe": identity, "events": {}})
            event = row["events"].setdefault(outcome, {"count": 0, "first_depth": depth})
            event["count"] += 1
            if reason and "example_reason" not in event:
                event["example_reason"] = reason
            if result and "example_basket" not in event:
                basket = result["basket"]
                event["example_basket"] = {"total": basket.total, "quality": basket.verification_status,
                    "stores": [s.store_id for s in basket.stores],
                    "products": [{"product_id": i.product_id, "store_id": i.store_id,
                                  "packages": i.packages_needed, "line_total": i.total_price}
                                 for s in basket.stores for i in s.items]}

    def event(self, product, recipe, ingredient, stage, outcome, reason, **evidence):
        row = self.products.get((product.store_id, product.product_id))
        if row is None:
            return
        identity = self.identity(recipe)
        key = identity["id"] + ":" + ingredient
        context = row["contexts"].get(key)
        if context is None:
            if self.context_count >= self.event_limit:
                self.omitted_events += 1
                return
            context = {"recipe": identity, "ingredient": ingredient, "events": {}, "first_stop": None}
            row["contexts"][key] = context
            self.context_count += 1
        event = {"stage": stage, "outcome": outcome, "reason": reason, **evidence}
        context["events"].setdefault(stage + ":" + outcome, event)
        if outcome == "stopped" and context["first_stop"] is None:
            context["first_stop"] = event

    def recipe(self, recipe, stage=None, reason=None):
        identity = self.identity(recipe)
        from app.services.ingredient_normalizer import canonicalize_ingredient_name
        names = sorted({canonicalize_ingredient_name(i.name) for i in recipe.ingredients})
        self.recipe_needs[identity["id"]] = {**identity, "ingredients": names, "ingredient_amounts": [i.model_dump(mode="json") for i in recipe.ingredients],
            "instructions": list(recipe.instructions), "stopped_at": stage, "reason": reason}
        if stage:
            # Distinguish a recipe rejected before product retrieval from a
            # later meal rejection after this product was actually evaluated.
            # Neither is automatically an economic product rejection.
            for row in self.products.values():
                relevant = set(row["indexes"].get("matched", [])) & set(names)
                if relevant:
                    evaluated = any(c["recipe"]["id"] == identity["id"] for c in row["contexts"].values())
                    row.setdefault("recipe_outcomes" if evaluated else "unreached_recipes", {})[identity["id"]] = {
                        "recipe": identity, "stage": stage, "reason": reason,
                        "matched_ingredients": sorted(relevant), "product_evaluated": evaluated,
                    }

    def finalize(self, basket):
        selected = {(i.store_id, i.product_id) for s in basket.stores for i in s.items}
        for key, row in self.products.items():
            row["selected"] = key in selected

    def snapshot(self):
        return {
            "version": "product-decision-path-v1", "product_limit": self.limit,
            "context_limit": self.event_limit, "omitted_products": self.omitted_products,
            "omitted_context_events": self.omitted_events,
            "products": [{**r, "contexts": list(r["contexts"].values())} for r in self.products.values()],
            "recipe_search": list(self.search.values()),
            "recipe_needs": list(self.recipe_needs.values()), "whole_basket_comparisons": self.comparisons,
            "interpretation": "First stops are per actual recipe/ingredient path. An unreached path is not a passed gate. Index absence and final nonselection do not prove economic rejection. Comparisons are explicitly bounded final-menu counterfactuals through the same optimizer, nutrition and audit.",
        }

"""Request-local first-rejection counts and search branching, never general logs."""

from collections import Counter

STAGES = {
    "policy_taste": "Policy/smak",
    "nutrition": "Näringskrav",
    "nutrition_bound": "Näringsgräns från kvalificerade produkter",
    "organic": "Eko",
    "store_cap": "Butikstak",
    "variation": "Variationskrav",
    "preparation": "Tillagning/beredning",
    "product_qualification": "Produktkvalificering",
    "price_basket": "Pris/korg",
}


class PlanningDiagnostics:
    def __init__(self):
        self.pools = []
        self.filters = Counter()
        self.details = []
        self.search = []
        self.branches = {}
        self.singleton_passed = 0
        self.missing_needs = {}
        self.estimate_alternatives = []
        self.nutrition_searches = []
        self.omitted_nutrition_searches = 0

    def reject(self, stage, recipe, reason):
        self.filters[stage] += 1
        self.details.append({"stage": stage, "recipe": recipe.name, "reason": reason})

    def branch(self, depth, stage):
        attempt = self.search[-1].get("attempt", 1) if self.search else 1
        self.branches.setdefault((attempt, depth), Counter())[stage] += 1

    def snapshot(self):
        raw = sum(p["raw"] for p in self.pools)
        return {
            "version": "candidate-and-branch-counts-v1",
            "product_decisions": self.product_trace.snapshot() if hasattr(self, "product_trace") else None,
            "raw_recipe_pool": raw,
            "pools": self.pools,
            "candidate_rejections": [
                {"stage": key, "label": label, "rejected": self.filters[key]}
                for key, label in STAGES.items()
            ],
            "singleton_passed": self.singleton_passed,
            "not_singleton_evaluated": max(
                0, raw - sum(self.filters.values()) - self.singleton_passed
            ),
            "search": [
                {
                    **row,
                    "rejections": {
                        key: self.branches.get((row.get("attempt", 1), row["depth"]), {}).get(key, 0) for key in STAGES
                    },
                }
                for row in self.search
            ],
            "candidate_details": self.details,
            "missing_needs": list(self.missing_needs.values()),
            "estimate_alternatives": self.estimate_alternatives,
            "nutrition_searches": self.nutrition_searches,
            "omitted_nutrition_searches": self.omitted_nutrition_searches,
            "counting": "Varje rå kandidat räknas vid sitt första avslag. Därefter räknas menyförslag separat per sökdjup; variation och gemensamt butikstak gäller kombinationer. Noll avslag betyder inte att ett otestat steg har passerat. Sökningen är begränsad och bevisar inte global omöjlighet.",
        }

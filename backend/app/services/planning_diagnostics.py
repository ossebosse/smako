"""Request-local first-rejection counts and search branching, never general logs."""

from collections import Counter

STAGES = {
    "policy_taste": "Policy/smak",
    "nutrition": "Näringskrav",
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

    def reject(self, stage, recipe, reason):
        self.filters[stage] += 1
        self.details.append({"stage": stage, "recipe": recipe.name, "reason": reason})

    def branch(self, depth, stage):
        self.branches.setdefault(depth, Counter())[stage] += 1

    def snapshot(self):
        raw = sum(p["raw"] for p in self.pools)
        return {
            "version": "candidate-and-branch-counts-v1",
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
                        key: self.branches.get(row["depth"], {}).get(key, 0) for key in STAGES
                    },
                }
                for row in self.search
            ],
            "candidate_details": self.details,
            "missing_needs": list(self.missing_needs.values()),
            "estimate_alternatives": self.estimate_alternatives,
            "counting": "Varje rå kandidat räknas vid sitt första avslag. Därefter räknas menyförslag separat per sökdjup; variation och gemensamt butikstak gäller kombinationer. Noll avslag betyder inte att ett otestat steg har passerat. Sökningen är begränsad och bevisar inte global omöjlighet.",
        }

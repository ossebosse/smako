"""Frozen category cases using the existing planner acceptance/audit harness.

Run each arm with the same prices, facts, clock and registered recipe library.
--uncapped is the existing full-pool algorithm, not a global optimum oracle.
"""
from backend.scripts import planner_acceptance_matrix as matrix

matrix.CASES.update({
    "category-122": {"meals": [{"count": 5, "servings": 4,
        "distribution": {"chicken": 1, "vegetarian": 2, "meat": 2}}]},
    "category-vegetarian": {"meals": [{"count": 5, "servings": 4,
        "distribution": {"vegetarian": 5}}]},
    "category-open": {"meals": [{"count": 5, "servings": 4,
        "distribution": {"chicken": 1, "vegetarian": 2}}]},
    "category-no-fish": {"meals": [{"count": 5, "servings": 4,
        "distribution": {"fish": 0}}]},
})

if __name__ == "__main__":
    matrix.main()

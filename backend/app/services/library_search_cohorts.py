"""Stable publication prefixes for the existing merged library search.

Completed checkpoints follow a 1/2/5 progression above the bounded base.
Their paths are identical in nested larger libraries; arbitrary intermediate
library sizes are still heuristic searches, not a global monotonicity proof.
"""
from bisect import bisect_right

from app.services.meal_library_content import identity

BASE_PREFIX_LIMIT = 512
SMALL_POOL_LIMIT = 4096
MERGED_SEARCH_CONTRACT = {
    'version': 'smako-merged-library-search-v3',
    'base_prefix_recipe_limit': BASE_PREFIX_LIMIT,
    'completed_prefix_progression': '1000,2000,5000 times powers of ten',
    'unordered_small_pool_state_limit': SMALL_POOL_LIMIT,
    'checkpoint_trajectory': 'probe completed prefixes without changing the geometric path',
}


def merged_library_cohorts(options, recipes, generations, *, first_generation, base_limit=BASE_PREFIX_LIMIT):
    ordered = sorted(enumerate(recipes), key=lambda row: (generations[identity(row[1])], row[0]))
    positions = {identity(recipe): index for index, (_, recipe) in enumerate(ordered, 1)}
    ends = {}
    for index, (_, recipe) in enumerate(ordered, 1):
        ends[generations[identity(recipe)]] = index
    size = len(ordered)
    first = max((end for generation, end in ends.items() if generation <= first_generation), default=0)
    base = max((end for end in ends.values() if first <= end <= base_limit), default=first)
    protected = {base, size}
    decade = 1000
    while decade <= size:
        protected.update(n * decade for n in (1, 2, 5) if n * decade <= size)
        decade *= 10
    slot_positions = {id(slot.recipe): positions.get(identity(slot.recipe), size)
                      for group in options for slot in group if slot.recipe and slot.recipe.design}
    counts = sorted(slot_positions[id(slot.recipe)] for group in options for slot in group
                    if slot.recipe and slot.recipe.design)
    geometric, last_count = {first}, bisect_right(counts, first)
    for boundary in sorted(ends.values()):
        if boundary <= first or boundary == size:
            continue
        count = bisect_right(counts, boundary)
        if count >= max(1, 2 * last_count):
            geometric.add(boundary)
            last_count = count
    chosen = sorted(geometric | protected)
    cohorts = []
    for boundary in chosen:
        generation = generations[identity(ordered[boundary - 1][1])] if boundary else first_generation
        cohorts.append((generation, [[slot for slot in group if not slot.recipe or not slot.recipe.design
                                      or slot_positions[id(slot.recipe)] <= boundary] for group in options]))
    return (cohorts, frozenset(index for index, boundary in enumerate(chosen) if boundary in protected),
            tuple(chosen), frozenset(index for index, boundary in enumerate(chosen) if boundary not in geometric))

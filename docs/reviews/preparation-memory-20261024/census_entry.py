"""Diagnostic-only memoization eviction after real frozen qualification.

No plan or audit cell is produced. Authoritative prices, facts, request and
qualified recipes stay referenced. Each row measures incremental reclamation;
shared references make group order significant. Use only isolated test state.
"""
from __future__ import annotations

import json
import runpy
from dataclasses import fields
from functools import wraps
from pathlib import Path

from app.services import reference_library

reference_library.PIN = Path('/review/backend/app/data/recipes/reference-library-262.json')

from app.services.personal_planner import PersonalPlanner
from app.services.planner_memory import release_idle_memory
from app.services.planner_shared_cache import SHARED_RESOLUTION


def memory():
    result = {}
    for line in Path('/proc/self/status').read_text().splitlines():
        if line.startswith(('VmRSS:', 'VmHWM:')):
            key, value, _ = line.split()
            result[key.rstrip(':')] = int(value) * 1024
    for key in ('current', 'peak'):
        result['cgroup_' + key] = int(Path('/sys/fs/cgroup/memory.' + key).read_text())
    stats = dict(line.split() for line in Path('/sys/fs/cgroup/memory.stat').read_text().splitlines())
    result.update({key: int(stats[key]) for key in ('anon', 'file', 'kernel')})
    return result


original = PersonalPlanner._candidates


@wraps(original)
def qualify(self, *args, **kwargs):
    recipes = original(self, *args, **kwargs)
    report = {'status': 'DIAGNOSTIC_ONLY_NO_MENU_OR_AUDIT',
              'qualified_recipes_held_alive': len(recipes),
              'facts_held_alive': len(self.facts),
              'products_held_alive': len(self.prepared.universe.products),
              'initial': memory(), 'groups': []}

    def reclaim(name, mappings, extra=None):
        counts = {key: len(mapping) for key, mapping in mappings}
        before = memory()
        for _, mapping in mappings:
            mapping.clear()
        if extra is not None:
            extra()
        outcome = release_idle_memory()
        report['groups'].append({'group': name, 'entries_before': counts,
                                 'before': before, 'after': memory(), 'collection': outcome})
        Path('/output/cache-census.json').write_text(json.dumps(report, indent=2))

    session = self.optimizer._quote_cache_context.get()
    quote_maps = [(field.name, getattr(session, field.name)) for field in fields(session)
                  if isinstance(getattr(session, field.name), dict)] if session else []
    reclaim('quote_session', quote_maps)
    reclaim('slot_nutrition', [('slot_nutrition_cache', self.slot_nutrition_cache)])
    reclaim('nutrition_evidence', [('nutrition_cache', self.nutrition_cache)])
    reclaim('resolution', [(name, getattr(self, name)) for name in (
        'lookup_cache', 'lookup_failures', '_resolution_trace', 'candidate_sequences',
        'qualified_nutrition_candidates')], SHARED_RESOLUTION.clear)
    reclaim('recipe_work', [(name, getattr(self, name)) for name in (
        'normalized_recipe_rows', 'clean_recipe_cache', '_need_row_templates',
        '_json_memo', '_merged_profile_memo', 'ecological_results')]
        + [(name, value) for name, value in vars(self.recipe_computations).items() if isinstance(value, dict)])
    reclaim('product_trace', [(name, getattr(self.product_trace, name)) for name in (
        'products', 'recipe_needs', 'search', '_recipe_ids')])
    assert len(recipes) == report['qualified_recipes_held_alive']
    assert len(self.facts) == report['facts_held_alive']
    assert len(self.prepared.universe.products) == report['products_held_alive']
    report['final'] = memory()
    Path('/output/cache-census.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({'diagnostic_complete': True, 'initial': report['initial'],
                      'final': report['final']}), flush=True)
    raise SystemExit(0)


PersonalPlanner._candidates = qualify
runpy.run_path('/review/docs/reviews/integration-scaling-20261023/run_matrix.py', run_name='__main__')

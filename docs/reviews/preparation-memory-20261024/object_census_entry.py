"""Diagnostic-only live object census after frozen qualification, no menu/audit."""
from __future__ import annotations

import gc
import json
import runpy
import sys
from collections import defaultdict
from functools import wraps
from pathlib import Path

from app.services import reference_library
from app.services.personal_planner import PersonalPlanner
from app.services.planner_memory import release_idle_memory
from pydantic import BaseModel

reference_library.PIN = Path('/review/backend/app/data/recipes/reference-library-262.json')
original = PersonalPlanner._candidates


def memory():
    result = {}
    for line in Path('/proc/self/status').read_text().splitlines():
        if line.startswith(('VmRSS:', 'VmHWM:')):
            key,value,_ = line.split()
            result[key.rstrip(':')]=int(value)*1024
    for key in ('current','peak'):
        result['cgroup_'+key]=int(Path('/sys/fs/cgroup/memory.'+key).read_text())
    return result


@wraps(original)
def qualify(self,*args,**kwargs):
    recipes=original(self,*args,**kwargs)
    before=memory()
    collection=release_idle_memory()
    after=memory()
    counters=defaultdict(lambda: {'count':0,'instance_bytes':0,'field_dict_bytes':0,'field_set_bytes':0})
    objects=gc.get_objects()
    for value in objects:
        cls=type(value)
        key=f'{cls.__module__}.{cls.__qualname__}'
        row=counters[key]
        row['count']+=1
        row['instance_bytes']+=sys.getsizeof(value)
        if isinstance(value,BaseModel):
            row['field_dict_bytes']+=sys.getsizeof(value.__dict__)
            row['field_set_bytes']+=sys.getsizeof(value.__pydantic_fields_set__)
    del objects,value
    rows=sorted(({'type':key,**value} for key,value in counters.items()),
                key=lambda row:sum(row[name] for name in ('instance_bytes','field_dict_bytes','field_set_bytes')),
                reverse=True)
    report={'status':'DIAGNOSTIC_ONLY_NO_MENU_OR_AUDIT','source_commit':'193629fbd0a0360955726f7a28bc30700ed8fc87',
        'qualified_recipes_held_alive':len(recipes),'servings':args[0].servings,
        'products_held_alive':len(self.prepared.universe.products),'facts_held_alive':len(self.facts),
        'before_collection':before,'after_collection':after,'collection':collection,'types':rows,
        'limits':['GC-tracked objects only; untracked strings/numeric containers are not exhaustive',
            'Model field dictionaries/sets overlap generic container counts; do not add type rows as exclusive sizes']}
    Path('/output/object-census.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'diagnostic_complete':True,'after_collection':after,'largest':rows[:10]}),flush=True)
    raise SystemExit(0)


PersonalPlanner._candidates=qualify
runpy.run_path('/review/docs/reviews/integration-scaling-20261023/run_matrix.py',run_name='__main__')

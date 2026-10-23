"""Record improving search paths alongside the ordinary acceptance matrix."""

from app.services.menu_optimizer import MenuOptimizer

from backend.scripts import planner_acceptance_matrix as matrix

original=MenuOptimizer.optimize_library_slots
quality=matrix.quality
events=[]

def traced(self,cohorts,**kwargs):
    events.clear()
    observer=kwargs.get('decision_observer')
    trace=kwargs['search_trace']
    best=None
    def observe(slots,outcome,**values):
        nonlocal best
        result=values.get('result')
        if result and len(slots)==5 and outcome in {'retained','priced'}:
            paid=result['basket'].total
            if outcome=='retained' or best is None or paid<best:
                events.append({'outcome':outcome,'paid':paid,'phase':trace[-1].get('library_phase') if trace else None,'generation':trace[-1].get('library_generation') if trace else None,'recipes':[s.recipe.design.base_id+':'+s.recipe.design.variant_id for s in slots]})
            best=paid if best is None else min(best,paid)
        if observer:observer(slots,outcome,**values)
    kwargs['decision_observer']=observe
    return original(self,cohorts,**kwargs)

def capture(plan,request):
    row=quality(plan,request)
    row['review_search_events']=list(events)
    row['review_search_trace']=plan.personal.checks['planning_diagnostics']['search']
    return row

MenuOptimizer.optimize_library_slots=traced
matrix.quality=capture
matrix.main()

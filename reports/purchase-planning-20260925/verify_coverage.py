"""All stores, immutable before/after source replay, existing collector and PU."""
import asyncio
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from app.models.ingredient import NormalizedIngredient
from app.services.basket_auditor import BasketAuditor
from app.services.basket_calculator import BasketCalculator
from app.services.personal_planner import PersonalPlanner
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.product_matcher import ProductMatcher
from app.services.production_price_universe_build import build_city_price_universe
from app.services.user_pricing import price_candidate_for_context
from grocery_data.app.domain import RawBatch
from grocery_data.app.domain.promotion_pricing import UserPricingContext
from grocery_data.app.storage import create_database_engine, create_schema
from grocery_data.scripts.collect_lidl_municipality import collect as collect_lidl, retained_bundle
from grocery_data.scripts.collect_willys_flyers import collect as collect_willys

R = Path(__file__).resolve().parent / "final"
R.mkdir(exist_ok=True)
OLD = R.parent.parent


def write(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf-8')


def sources(root):
    inv = json.loads((root/'inventory.json').read_bytes())
    return [dict(database=root/s['database'], store_ids=[s['store_id']],
                 snapshot_ids=[s['snapshot_id']], inventory=inv)
            for s in json.loads((root/'coverage.json').read_bytes())['stores'] if s['status']=='success']


def purchases(prepared):
    from app.models.product import ProductCandidate
    from app.services.personal_source_facts import load_retained_facts
    facts = load_retained_facts(prepared, database=OLD/'offer-expansion-20260924/base/grocery.sqlite', raw_root=OLD/'offer-expansion-20260924/base/raw')
    context = UserPricingContext.from_chain_flags({'willys': True, 'lidl': True})
    rows = []
    for p in prepared.universe.products:
        terms=p.purchase_terms
        row={'chain':p.chain,'store':p.source_provenance.provider_store_id,'name':p.name,
             'id':p.source_provenance.retailer_product_id,'ordinary_price':p.price,
             'terms':terms.model_dump(mode='json') if terms else None,
             'offer':p.offers[0].model_dump(mode='json'),'observed_at':p.source_provenance.source_observed_at}
        if terms and terms.usage == 'blocked':
            row.update(usage=terms.usage, exact_purchase=False)
            try: price_candidate_for_context(ProductCandidate.from_product(p,1),context,on_date=date(2026,9,24),planning_mode='estimated')
            except ValueError:pass
            else: raise AssertionError('group became a specific product purchase')
            rows.append(row);continue
        conditional=bool(terms and terms.usage=='variant_selection_required')
        estimated=terms and terms.usage=='estimated'
        quantity=1 if conditional else 200 if estimated else p.package_quantity*p.offers[0].required_packages
        unit='st' if conditional else 'g' if estimated else p.package_unit
        need=NormalizedIngredient(canonical_name=p.name.casefold(),required_quantity=quantity,unit=unit)
        matches=ProductMatcher().match(need,[p])
        row['matched']=bool(matches)
        if matches or conditional or estimated:
            candidate=price_candidate_for_context(matches[0] if matches else ProductCandidate.from_product(p,1).model_copy(update={'semantic_confidence':'high','semantic_evidence':['explicit source product choice']}),context,on_date=date(2026,9,24),planning_mode='estimated' if estimated else 'exact',allow_campaign_choice=conditional)
            item=BasketCalculator().calculate_item(need,candidate)
            audit=BasketAuditor(pantry_items=frozenset()).audit([need],[item],user_pricing_context=context)
            row.update(usage='conditional' if conditional else 'estimated' if estimated else 'exact',audit_passed=audit.passed,checkout=item.model_dump(mode='json'))
            assert audit.passed,(p.name,audit)
            assert (item.verification_status=='VERIFIED_WITH_ESTIMATES')==bool(estimated)
        fact=facts.get((p.store_id,p.product_id))
        planner=SimpleNamespace(spec=SimpleNamespace(allow_nutrition_estimates=False),source_facts=lambda _,f=fact:f)
        from app.services.ingredient_normalizer import canonicalize_ingredient_name
        name=canonicalize_ingredient_name(p.name)
        row['nutrition_purchase_unit']=False
        row['nutrition_edible_grams_available']=False
        row['recipe_nutrition_approved']=False
        if not conditional:
            declared=PersonalPlanner._nutrition_evidence(planner,p,name,unit,{'kcal','protein_g','fat_g','carbs_g'},None)
            row['nutrition_purchase_unit']=bool(declared)
            planner.spec.allow_nutrition_estimates=True
            generic=PersonalPlanner._nutrition_evidence(planner,p,name,'g',{'kcal','protein_g','fat_g','carbs_g'},None)
            row['nutrition_edible_grams_available']=bool(generic)
            if generic:
                row['nutrition_evidence']={'source':generic.source,'values':generic.nutrition,'basis':generic.nutrition_basis,'fields':generic.field_sources}
            from app.models.recipe import Recipe,RecipeIngredient
            recipe_need=NormalizedIngredient(canonical_name='bröd',required_quantity=100,unit='g')
            recipe_matches=ProductMatcher().match(recipe_need,[p])
            if recipe_matches:
                recipe=Recipe(name='Uppmätt bröd som sålt',servings=1,ingredients=[RecipeIngredient(name='bröd',quantity=100,unit='g')],instructions=['Servera tillsammans.'])
                recipe_fact=PersonalPlanner._nutrition_evidence(planner,p,'bröd','g',{'kcal','protein_g','fat_g','carbs_g'},recipe)
                if recipe_fact:
                    recipe_item=BasketCalculator().calculate_item(recipe_need,price_candidate_for_context(recipe_matches[0],context,on_date=date(2026,9,24)))
                    assert BasketAuditor(pantry_items=frozenset()).audit([recipe_need],[recipe_item],user_pricing_context=context).passed
                    row['recipe_nutrition_approved']=True
        rows.append(row)
    return rows


async def main():
    database=R/'empty-base.sqlite'
    if not database.exists():
        engine=create_database_engine('sqlite:///'+database.as_posix());create_schema(engine);engine.dispose()
    bundle=retained_bundle(OLD/'offer-coverage-20260924/lidl-live-source')
    for code,city,postal in [('1281','Lund','22223'),('1280','Malmö','21120')]:
        wr=R/f'willys-{code}';lr=R/f'lidl-{code}'
        if not wr.exists():
            old=OLD/f'willys-auto-20260924/live-collection-{code}'
            inv=json.loads((old/'inventory.json').read_bytes())
            ids=inv['selected_store_ids']
            raw={i:RawBatch.model_validate_json((old/i/'source.json').read_bytes()) for i in ids}
            result=await collect_willys(inv,ids,wr,raw_by_store=raw)
            assert all(s['status']=='success' for s in result['stores']),result
            print('Willys',code,[(s['store_id'],s['own']) for s in result['stores']],flush=True)
        if not lr.exists():
            inv=json.loads((OLD/f'lidl-municipality-20260923/package-live-verification/{code}/inventory.json').read_bytes())
            result=await collect_lidl(inv,inv['selected_store_ids'],lr,bundle=bundle)
            assert all(s['status']=='success' for s in result['stores']),result
            print('Lidl',code,[(s['store_id'],s['own']) for s in result['stores']],flush=True)
        builds=[]
        for phase in ('first','second'):
            output=R/f'prepared-{code}-{phase}.json'
            build=await build_city_price_universe(database=database,city=city,postal_code=postal,external_cache=None,
                output=output,max_price_age_hours=48,willys_flyer_enabled=True,willys_flyer_sources=sources(wr),
                lidl_municipal_enabled=True,lidl_sources=sources(lr))
            prepared=PreparedPriceUniverseArtifact.model_validate_json(output.read_bytes()).restore()
            signature=[p.model_dump(mode='json') for p in prepared.universe.products]
            if builds:assert signature==previous
            previous=signature
            builds.append({'phase':phase,'result':build,'products':len(signature)})
        rows=purchases(prepared)
        write(R/f'verification-{code}.json',{'scope':'isolated inactive PU with empty base; no complete-base publication claim',
            'comparison_date':'2026-09-24','network_requests':0,'observations_rewritten':False,
            'builds':builds,'purchases':rows})
        print(city,len(rows),'PU',sum(bool(r.get('audit_passed')) for r in rows),'audit',flush=True)


if __name__=='__main__':asyncio.run(main())

"""Read-only future-clock admission test of the actually published candidate."""
import hashlib,socket
from datetime import datetime,UTC,timedelta
from pathlib import Path
from unittest.mock import patch
from job import configure,save
configure();P=Path('/work/physical-probe')
import job
job.P=P
from grocery_data.app.services.prepared_universe_activation import PreparedUniverseArtifactStore
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from grocery_data.app.domain.campaign_validity import is_campaign_only,STOCKHOLM
from grocery_data.app.domain.promotion_pricing import UserPricingContext
from app.models.product import ProductCandidate
from app.services.user_pricing import price_candidate_for_context
f=PreparedUniverseArtifactStore(P/'price-universes').resolve_active_artifact('Lund',verify_hash=True)
if f is None:save('expiry-admission',{'status':'blocked','reason':'no current published artifact'});raise SystemExit
raw=f.read_bytes();prepared=PreparedPriceUniverseArtifact.model_validate_json(raw).restore()
def denied(*args,**kwargs):raise AssertionError('network in future-clock admission test')
now=datetime.now(UTC);rows=[]
with patch.object(socket,'getaddrinfo',denied):
 for label,when in [('actual_now',now),('tomorrow_test_clock',now+timedelta(days=1)),('49h_test_clock',now+timedelta(hours=49)),('8days_test_clock',now+timedelta(days=8))]:
  view=prepared.request_view(now=when);day=when.astimezone(STOCKHOLM).date();candidates={}
  for index in [view.economic_pool.candidates_by_name,view.economic_pool.semantic_candidates_by_name,view.economic_pool.matched_candidates_by_name,view.economic_pool.projection_shortlist_support_by_name]:
   for group in index.values():
    for c in group:candidates[c.store_id,c.product_id]=c
  expired=[p for p in prepared.universe.products if p.price is None and p.offers and not any(o.is_active(day) for o in p.offers)]
  retained=[p.product_id for p in expired if (p.store_id,p.product_id) in candidates]
  leaked=[];rejected={}
  for p in expired:
   try:price_candidate_for_context(ProductCandidate.from_product(p,1),UserPricingContext.from_chain_flags({'ica':True,'coop':True,'willys':True,'lidl':True,'hemkop':True}),on_date=day,planning_mode='estimated')
   except ValueError as error:rejected[str(error)]=rejected.get(str(error),0)+1
   else:leaked.append(p.product_id)
  rows.append({'label':label,'clock':when,'candidate_products':len(candidates),'base_candidate_products':sum(not is_campaign_only(c) for c in candidates.values()),'actual_regular_price_candidates':sum(c.price is not None for c in candidates.values()),'inactive_campaign_products_in_artifact':len(expired),'inactive_products_retained_in_legacy_index':len(retained),'expired_purchase_admissions':leaked,'purchase_rejections':rejected,'usable_context_ids':view.usable_context_ids,'excluded_stale_context_ids':view.excluded_stale_context_ids})
  assert not leaked
assert not rows[-1]['base_candidate_products']
assert not rows[2]['base_candidate_products']
assert not rows[-1]['candidate_products']
assert f.read_bytes()==raw
save('expiry-admission',{'scope':'Independent OWN-only physical probe, not complete Lund: ordinary request_view on actual published data; explicit future clocks, no collection/rebuild or observation changes','artifact_sha256':hashlib.sha256(raw).hexdigest(),'external_requests':0,'results':rows});print('future-clock admission verified')

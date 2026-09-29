"""Consolidate current package/publication evidence without activating anything."""
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

R=Path(__file__).resolve().parent
S=R/'server-results'
read=lambda p: json.loads(p.read_bytes())
policy=read(S/'policy-result.json')
collection=read(S/'coop-live/coverage.json')
profile=read(S/'profile/coop-acceptance.json')
publication=read(S/'publication-result.json')
image=read(R/'package-result.json')
old=read(R.parent/'coop-nutrition-20260922/server-results/base-final/frozen-base-manifest.json')
base=read(S/'base-final/frozen-base-manifest.json')
assert old['database_sha256']==base['database_sha256']
assert old['primat']['artifact_sha256']==base['primat']['artifact_sha256']
assert all(not s['qualification']['shared_blockers'] for s in collection['stores'])
observed=datetime.fromisoformat(publication['rollback']['oldest_base_observed_at'])
now=datetime.now(UTC)
tz=ZoneInfo('Europe/Stockholm')
decision={'checked_at':now.isoformat(),'checked_at_stockholm':now.astimezone(tz).isoformat(),
 'ready_for_unattended_activation':False,'production_activation':False,
 'image_id':image['image_id'],'candidate_universe_id':profile['universe_id'],
 'coop_approved_rows':sum(s['own'] for s in collection['stores']),
 'coop_quarantine':sum(s['quarantined'] for s in collection['stores']),
 'coop_store_ids':[s['store_id'] for s in collection['stores']],
 'all_lund_shared_blockers_empty':True,'same_complete_base_database_and_primat_as_prior_evidence':True,
 'base_oldest_observed_at':observed.isoformat(),'base_age_hours':round((now-observed).total_seconds()/3600,3),
 'base_due_35h':(observed+timedelta(hours=35)).isoformat(),
 'base_warning_36h':(observed+timedelta(hours=36)).isoformat(),
 'base_hard_stop_48h':(observed+timedelta(hours=48)).isoformat(),
 'profile':{k:profile[k] for k in ['result','slots','portions','cost','stores','verification','http_seconds','total_seconds','saved_equals_readback','isolated_health','isolated_ready']},
 'selected_physical_coop_rows':sum(p['selected'] for p in profile['coop_trace']),
 'basket_audits':len(profile['basket_audits']),
 'publication_checks':publication['checks'],'production_manifest_unchanged':publication['production_manifest_unchanged'],
 'blocking_gap':'No durable municipal source pointer and no Coop forwarding/rebuild/reload bridge in ordinary scheduled refresh.',
 'xtra_separate':'Fresh packaged PDF text import verified; excluded from full production-builder Coop candidate. Optional omission remains explicit.',
 'planned_not_installed':policy['selected_stores']}
(R/'decision.json').write_text(json.dumps(decision,ensure_ascii=False,indent=2),encoding='utf8')
lines=['# Nästa uppdateringar – policyförslag, inte installerat schema','',
 '| Butik | Senast lyckad källa (Stockholm) | Nästa kontroll | Prisets 48 h-stopp | Skäl |',
 '|---|---|---|---|---|']
for s in policy['selected_stores']:
 fmt=lambda v: datetime.fromisoformat(v).astimezone(tz).isoformat() if v else 'okänt'
 lines.append('| '+' | '.join([s['name']+' ('+s['store_id']+')',fmt(s['last_success']),fmt(s['next_fetch_at']),fmt(s['price_hard_stop_at']),s['reason']])+' |')
lines+=['','Coop/X:-tra har inte ICA:s särskilda undantag från generell prisålder. 35 h-kontroll används därför före 36/48 h-gränserna. Kampanjens tidigare start/slut går före denna tid. Skansvägens torsdagssida börjar 24 september 00:00, men källkontrollen föreslås redan 23 september cirka 22:34.',
 'Vid misslyckad hämtning bevarar policyprovet senaste lyckade observation och föreslår första återförsöket efter 15 minuter, därefter begränsad backoff. Detta förlänger inte kampanjdatum eller 48 h-stopp. Den beständiga kopplingen från denna policy till publicerad Coop-källa saknas fortfarande i ordinarie drift.',
 'Basens äldsta observation: '+observed.astimezone(tz).isoformat()+'. Föreslagen 35 h-kontroll: '+(observed+timedelta(hours=35)).astimezone(tz).isoformat()+'. Varning: '+(observed+timedelta(hours=36)).astimezone(tz).isoformat()+'. Stopp/rollbackgräns: '+(observed+timedelta(hours=48)).astimezone(tz).isoformat()+'.',
 'Befintligt produktionscron lästes utan ändring: daglig refresh 03:17 Europe/Stockholm, nästa 23 september. Det är bara cirka 55 sekunder före den nuvarande basens stopp. Det är ingen säker insamlingsmarginal och inte ett installerat 35 h-schema. Den väntande ICA-/Windows-ändringen är orörd.']
(R/'UPDATES.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
print(json.dumps({k:decision[k] for k in ['checked_at_stockholm','image_id','coop_approved_rows','base_age_hours','ready_for_unattended_activation']},ensure_ascii=False))

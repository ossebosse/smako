#!/usr/bin/env python3
"""Fristående leveranskontroll. Kräver Python 3 och jsonschema; inte Smakos validator.
Kör från valfri katalog: python kontroll/validera_leverans.py
Rapporten skrivs till kontrollrapport.json och returkoden är 1 vid strukturellt fel.
"""
from __future__ import annotations
from pathlib import Path
import collections, datetime, hashlib, importlib.metadata, json, math, re, sys
try:
    from jsonschema import Draft202012Validator
except ImportError:
    raise SystemExit('Installera beroendet med: python -m pip install jsonschema')
ROOT=Path(__file__).resolve().parent.parent

def read(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))

def main() -> int:
    errors: list[str]=[];warnings=[];rows=[];pack_checks=[];measurements=[]
    # All JSON, including preserved history, must be readable UTF-8.
    json_count=0
    for p in ROOT.rglob('*.json'):
        try: read(p);json_count+=1
        except (OSError,UnicodeError,json.JSONDecodeError) as exc:errors.append(f'{p.relative_to(ROOT)}: {exc}')
    schema=read(ROOT/'referens/leveransschema.json')
    registry={x['key']:x for x in read(ROOT/'referens/ingrediensregister.json')['ingredients']}
    proposal_data=read(ROOT/'registerforslag.json');proposals={x['key']:x for x in proposal_data['proposals']}
    reserved=read(ROOT/'referens/reserverade-idn.json');reserved_bases=set(reserved['base_ids']);reserved_tuples=set(reserved['recipe_ids'])|set(reserved['revoked_recipe_ids'])
    past=read(ROOT/'historik/tidigare-levererade-index.json');past_bases={x['base_id'] for x in past['bases']}
    past_tuples={v['base_id']+':'+v['version']+':'+v['variant_id'] for b in past['bases'] for v in b['variant_references']}
    overview=read(ROOT/'leveransoversikt.json');overview_rows={(v['base_id'],v['variant_id']):v for v in overview['variants']}
    candidate=read(ROOT/'kandidatregister.json');candidate_ids={c['base_id'] for c in candidate['candidates']}
    pack_ids=[];seen_variants=set();base_files=collections.defaultdict(set);by_base=collections.defaultdict(list);used_unknown=collections.defaultdict(list)
    for p in sorted((ROOT/'paket').glob('*.json')):
        data=read(p);rel=str(p.relative_to(ROOT));pack_ids.append(data['pack_id'])
        for error in Draft202012Validator(schema).iter_errors(data):errors.append(f'{rel}:{list(error.path)}: {error.message}')
        if p.stat().st_size>=16*1024*1024:errors.append(rel+': filstorlek >=16 MiB')
        pack_checks.append({'file':rel,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'base_count':len({r['base_id'] for r in data['recipes']}),'variant_count':len(data['recipes'])})
        for r in data['recipes']:
            rows.append(r);b=r['base_id'];v=r['variant_id'];key=b+':'+r['version']+':'+v;pair=(b,v)
            if key in seen_variants:errors.append(key+': duplicerad variant')
            seen_variants.add(key);base_files[b].add(rel);by_base[b].append(r)
            if b in reserved_bases or key in reserved_tuples:errors.append(key+': original-ID reserverat')
            if b in past_bases or key in past_tuples:errors.append(key+': tidigare levererat ID')
            if r['version']!='1.0.0':errors.append(key+': fel version')
            if not b.startswith('smako-'+r['cuisine']+'-'):errors.append(key+': ID och kök skiljer sig')
            if r['servings']!=(4 if r['meal_type']=='dinner' else 1):errors.append(key+': fel portionsantal')
            if not all(term in r.get('notes','').lower() for term in ['ai','inte provlagat','smako']):errors.append(key+': saknad statusnot')
            if any(field in r for field in ['requirements','approved','ingredient_count','nutrition','content_hash','runtime_id']):errors.append(key+': oväntade runtimefält')
            cs=r['components'];ids=[c['id'] for c in cs]
            if len(ids)!=len(set(ids)):errors.append(key+': duplicerade komponent-ID:n')
            ingredients=[i for c in cs for i in c['ingredients']];names={i['name'] for i in ingredients};known=True
            for c in cs:
                for i in c['ingredients']:
                    ik=i['name']+'|'+i['form'];definition=registry.get(ik,proposals.get(ik))
                    if not definition:errors.append(key+': okänd och odokumenterad identitet '+ik)
                    elif i.get('unit')!=definition['unit']:errors.append(key+': fel enhet '+ik)
                    if isinstance(i['quantity'],bool) or not isinstance(i['quantity'],(int,float)) or not math.isfinite(i['quantity']) or i['quantity']<=0:errors.append(key+': ogiltig mängd '+ik)
                    if 'requirements' in i:errors.append(key+': inköpskrav ska ärvas, inte skrivas om')
                    if ik not in registry:
                        known=False;used_unknown[ik].append((b,v,c['id'],i['quantity'],i['unit']))
            for n in names:
                if len({i['form'] for i in ingredients if i['name']==n})>1:errors.append(key+': flera former av samma namn')
            used=set();ends=[];active=0
            for n,s in enumerate(r['steps'],1):
                used.update(s['uses'])
                if set(s['uses'])-names:errors.append(key+': uses innehåller olistade namn')
                if not isinstance(s['minutes'],(int,float)) or s['minutes']<1:errors.append(key+': steg under en minut')
                deps=s.get('after',[])
                if any(not isinstance(d,int) or d<1 or d>=n for d in deps):errors.append(key+': felaktigt stegeberoende');deps=[]
                ends.append(s['minutes']+max([ends[d-1] for d in deps] or [0]));active+=0 if s.get('passive',False) else s['minutes']
                if re.search(r'\b\d+(?:[.,]\d+)?\s*(?:dl|liter|litre|l)\s+(?:hett |kallt |ljummet |kokhett |varmt )?vatten',s['text'],re.I):errors.append(key+': processvatten inte i ml')
                if re.search(r'\b\d+(?:[.,]\d+)?\s*(?:g|gram|kg)\b',s['text'],re.I):errors.append(key+': låst råvaruvikt i löptext')
                if re.search(r'som (?:grundreceptet|föregående variant)',s['text'],re.I):errors.append(key+': variant är inte självständig')
            if names-used:errors.append(key+': oanvända ingredienser '+str(sorted(names-used)))
            total=max(max(ends),active);waiting=total-active
            if active>180 or total>2880 or waiting>1440:errors.append(key+': tidsgräns överskriden utan godkännande')
            count=len({i['name']+'|'+i['form'] for i in ingredients if i['name'] not in {'salt','svartpeppar','peppar','vatten'}})
            measured={'base_id':b,'variant_id':v,'ingredient_count':count,'active_minutes':active,'total_minutes':total,'waiting_minutes':waiting,'known_only':known}
            measurements.append(measured);ov=overview_rows.get(pair)
            if not ov:errors.append(key+': saknas i översikt')
            else:
                for f in ['ingredient_count','active_minutes','total_minutes','waiting_minutes']:
                    if ov[f]!=measured[f]:errors.append(key+': översikt skiljer sig för '+f)
                if ov['requires_registry_review']==known:errors.append(key+': inkonsekvent registerstatus')
    if len(pack_ids)!=len(set(pack_ids)):errors.append('Pack-ID:n är inte unika')
    if set(by_base)!=candidate_ids:errors.append('Kandidatregister och författade bas-ID:n skiljer sig')
    for b,rr in by_base.items():
        expected={'simple','standard','extended'} if rr[0]['meal_type']=='dinner' else {'simple','extended'}
        if {r['variant_id'] for r in rr}!=expected:errors.append(b+': saknade/felaktiga varianter')
        if len(base_files[b])!=1:errors.append(b+': familj splittrad mellan paket')
        for field in ['cuisine','meal_type','servings','version']:
            if len({r[field] for r in rr})!=1:errors.append(b+': inkonsekvent '+field)
        counts=[m['ingredient_count'] for m in measurements if m['base_id']==b]
        if len(counts)!=len(set(counts)):errors.append(b+': samma ingrediensantal i flera varianter')
    if len(rows)!=overview['summary']['authored_variants'] or len(by_base)!=overview['summary']['authored_bases']:errors.append('Faktiskt antal skiljer sig från leveransöversiktens deklaration')
    if set(used_unknown)!=set(proposals):errors.append('Förslagslista matchar inte faktiskt använda okända identiteter')
    for ik,actual in used_unknown.items():
        documented=[(x['base_id'],x['variant_id'],x['component_id'],x['quantity'],x['unit']) for x in proposals[ik]['uses']]
        if collections.Counter(actual)!=collections.Counter(documented):errors.append(ik+': förslagsanvändningar stämmer inte')
    known_ids={b for b in by_base if all(m['known_only'] for m in measurements if m['base_id']==b)}
    for b,files in base_files.items():
        in_known='kanda-identiteter' in next(iter(files))
        if in_known!=(b in known_ids):errors.append(b+': fel paket efter registerstatus')
    for q in overview['quota_by_cuisine_and_meal']:
        actual=sum(rr[0]['cuisine']==q['cuisine'] and rr[0]['meal_type']==q['meal_type'] for rr in by_base.values())
        if actual!=q['new_editorially_accepted_bases']:errors.append('Kvotcell fel: '+str(q))
        if q['cumulative_distinct_ids_provisional']>q['target']:errors.append('Kvotcell överskrider mål')
    # Cross-document completeness and count interval exceptions.
    if len(overview_rows)!=len(overview['variants']):errors.append('Dubblerade variantposter i översikten')
    if set(overview_rows)!={(r['base_id'],r['variant_id'])for r in rows}:errors.append('Översiktens variantmängd matchar inte paketens')
    if len(candidate['candidates'])!=len(candidate_ids):errors.append('Dubblerade kandidater')
    declared_ex={(x['base_id'],x['variant_id']):x for x in overview['ingredient_count_exceptions']}
    actual_ex=set()
    for m in measurements:
        r=next(r for r in rows if (r['base_id'],r['variant_id'])==(m['base_id'],m['variant_id']))
        limits=({'simple':(5,7),'standard':(8,11),'extended':(12,15)}if r['meal_type']=='dinner'else{'simple':(3,5),'extended':(6,8)})
        lo,hi=limits[r['variant_id']]
        if not lo<=m['ingredient_count']<=hi:
            pair=(r['base_id'],r['variant_id']);actual_ex.add(pair)
            if pair not in declared_ex or not declared_ex[pair].get('reason'):errors.append('Oredovisat ingrediensintervallundantag '+str(pair))
            elif declared_ex[pair]['actual_count']!=m['ingredient_count']:errors.append('Felräknat undantag '+str(pair))
    if actual_ex!=set(declared_ex):errors.append('Listan över ingrediensintervallundantag matchar inte verkliga antal')
    without_10_15={b for b,rr in by_base.items()if rr[0]['meal_type']=='dinner'and not any(10<=m['ingredient_count']<=15 for m in measurements if m['base_id']==b)}
    if without_10_15!=set(overview['dinner_bases_without_10_15_variant']):errors.append('Fel lista över middagar utanför standardfiltret')
    if sum(q['target']for q in overview['quota_by_cuisine_and_meal'])!=1000:errors.append('Målkvoterna summerar inte till 1000')
    for q in overview['quota_by_cuisine_and_meal']:
        pcount=sum(b['cuisines']==[q['cuisine']] and b['meal_types']==[q['meal_type']] for b in past['bases'])
        if pcount!=q['previous_distinct_ids_provisional']:errors.append('Tidigare kvotcell matchar inte historik')
        if q['remaining_bases_provisional']!=q['target']-q['previous_distinct_ids_provisional']-q['new_editorially_accepted_bases']:errors.append('Återstående kvot fel')
    source_data=read(ROOT/'kallor.json');source_ids={x['source_id']for x in source_data['sources']}
    for c in candidate['candidates']:
        if not set(c['source_ids'])<=source_ids:errors.append(c['base_id']+': källreferens saknas')
        refs={(x['base_id'],x['variant_id'])for x in c['variant_references']}
        if refs!={(r['base_id'],r['variant_id'])for r in by_base[c['base_id']]}:errors.append(c['base_id']+': variantreferenser fel')
    dupe=read(ROOT/'dubblettgranskning.json')
    if {x['base_id']for x in dupe['accepted']}!=set(by_base):errors.append('Dubblettbeslut och receptfamiljer skiljer sig')
    for x in dupe['accepted']:
        if x['decision']!='accept' or not x['post_authoring_culinary_reason']:errors.append('Ofullständigt slutligt likhetsbeslut')
        if x['nearest_new_after_authoring']['base_id']not in by_base:errors.append('Närmaste nya familj saknas i aktuella leveransen')
    final_pass=read(ROOT/'granskning/efter-forfattning-maskin.json')
    if final_pass['new_variants']!=len(rows) or len(final_pass['rows'])!=len(rows):errors.append('Efterjämförelsen matchar inte faktiskt antal varianter')
    if final_pass['editorial_completion'].get('status')!='completed_ai_editorial_review':errors.append('Eftergranskningen är inte avslutad')
    checkpoint=read(ROOT/'checkpoint.json')
    if set(checkpoint['completed_base_ids'])!=set(by_base) or set(checkpoint['completed_variant_ids'])!=seen_variants:errors.append('Checkpoint matchar inte faktiska paket')
    if set(checkpoint['all_previously_issued_new_base_ids'])!=set(by_base)|past_bases:errors.append('Checkpoint tappar äldre bas-ID:n')
    if set(checkpoint['all_previously_issued_new_variant_ids'])!=seen_variants|past_tuples:errors.append('Checkpoint tappar äldre variant-ID:n')
    # Check the supplied text corrections: a simple/standard angamat must not assume spinach.
    for r in rows:
        if r['base_id']=='smako-swedish-angamat-sommargronsaker' and r['variant_id']!='extended':
            if any('spenat' in s['text'].lower()for s in r['steps']):errors.append(r['base_id']+': kvarvarande olistad spenathänvisning')

    warnings.extend({'type':'ingredient_interval_exception',**x} for x in overview['ingredient_count_exceptions'])
    warnings.extend({'type':'process_review',**x} for x in overview['process_review'])
    warnings.append({'type':'registry_hold','proposal_count':len(proposals),'blocked_bases':len(by_base)-len(known_ids),'directly_blocked_variants':sum(not m['known_only'] for m in measurements),'whole_family_hold_variants':sum(len(rr) for b,rr in by_base.items() if b not in known_ids)})
    warnings.append({'type':'historical_conflicts','file':'historik/tidigare-leveranskonflikter.json','scope':'Äldre filer, inte nya ID-kollisioner.'})
    warnings.append({'type':'not_trial_cooked','scope':f'Samtliga {len(rows)} varianter; tider och mängder är författaruppskattningar.'})
    report={'checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'tool':'Fristående Python + JSON Schema; inte Smakos validator','python_version':sys.version.split()[0],'jsonschema_version':importlib.metadata.version('jsonschema'),'validator_file':'kontroll/validera_leverans.py','validator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'structural_error_count':len(errors),'errors':errors,'warning_count':len(warnings),'warnings':warnings,'counts':{'bases':len(by_base),'variants':len(rows),'packs':len(pack_checks),'known_identity_complete_families':len(known_ids),'json_files_parsed_before_report_write':json_count},'packs':pack_checks,'measurements':measurements,'checks_run':['UTF-8/JSON för alla befintliga leveransfiler','JSON Schema mot alla faktiska nya paket','Bas-ID, varianttuple, pack-ID och historiska/reserverade ID:n','Köks-/måltids-/portionskvoter och variantfamiljer','Ingrediensantal, mängder, former, enheter och fullständig förslagskoppling','Kanonisk uses-täckning, komponent-ID:n och tidigare-indexerade beroenden','Processvattenenheter och låsta gramvikter i löptext','Tidskritisk väg, aktiv tid och giltiga tidsgränser','Familjevis separation av kända/okända identiteter','Paketstorlek och SHA-256','Maskinjämförelse före/efter författning dokumenterad i separata filer','Korsreferenser mellan paket, kandidatregister, källor, kvoter, eftergranskning och checkpoint','Alla ingrediensintervallundantag kontrollerade mot faktiska antal'],'semantic_review_scope':'AI-redaktionell granskning av huvudkedjor och relevanta närträffar; ingen smak-, produkt- eller mänsklig kvalitetsattest. uses-täckning är en strukturell kontroll, inte ett bevis på praktisk tillagning.','not_run':['Smakos native import-/standardiseringsvalidator','Produktbindning och köpbarhet','Närings- och allergenberäkning','Produktgodkännande av vegetarianism/löpe/eko','Provlagning och uppmätta tids-/utbytesvärden','Betaaktivering eller runtimegeneration','Storlek efter Smakos framtida standardisering'],'archive_check':'Görs efter paketering; separat leveranskvitto sparas efter återöppning.'}
    (ROOT/'kontrollrapport.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'structural_errors':len(errors),'warnings':len(warnings),'counts':report['counts'],'errors':errors},ensure_ascii=False,indent=2))
    return int(bool(errors))
if __name__=='__main__':raise SystemExit(main())

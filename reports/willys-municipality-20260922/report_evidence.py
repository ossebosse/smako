"""Summarize saved evidence, not a collector or price publisher."""
import difflib
import hashlib
import json
import subprocess
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).parent
ROOT = HERE.parents[1]


def read(name):
    return json.loads((HERE/name).read_bytes())


def main():
    inventories={code:read('inventory-'+code+'.json') for code in ('1281','1280')}
    sources={}
    for code,path in [('1281',HERE/'lund-requalified/lund.smako-source'),('1280',next((HERE/'malmo-final-relay/completed').glob('*.smako-source')))]:
        with zipfile.ZipFile(path) as z:
            manifest=json.loads(z.read('manifest.json'))
        observed=datetime.fromisoformat(manifest['observed_from'].replace('Z','+00:00'))
        sources[code]={k:manifest[k] for k in ('observed_from','observed_to','request_count','row_count','product_count','catalog_completion')}
        sources[code].update(artifact_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),next_fetch_at=(observed+timedelta(hours=35)).astimezone(ZoneInfo('Europe/Stockholm')).isoformat(),hard_stop=(observed+timedelta(hours=48)).astimezone(ZoneInfo('Europe/Stockholm')).isoformat())
    own={}
    pu={}
    if (HERE/'decision-current.json').exists():
        for scope in read('decision-current.json')['universes'].values():
            pu.update(scope.get('willys_by_source_store',{}))
    for filename in ('server-results/result-cycle-restart.json','server-results/result-malmo-build-restart.json'):
        if (HERE/filename).exists():
            own.update({r[0]:r[1] for r in read(filename)['own']})
    summaries=[]
    lines=['# Willys: kommunernas butiker','', 'Nätinventering 22 september 2026. Kommunbevis: officiell registerposition mot SCB RegSO 2025, 10 m osäkerhetszon vid gräns. Kundpostnummer/adressort används inte som kommungräns. Alla insamlade priser är butiksknuten online_price, inte verifierade fysiska hyllpriser. Inget aktiverat i betan.','', '| Kommun | Butik / ID | Adress | Urval / status | Kompletta kategorier / sidor | Validerade källposter | OWN | PriceUniverse |','|---|---|---|---|---:|---:|---:|---:|']
    for code,inventory in inventories.items():
        counts={}
        for row in inventory['stores']:
            status=row['geographic_evidence']['status'];counts[status]=counts.get(status,0)+1
            if status!='inside':continue
            store=row['store'];sid=store['external_id'];completion=sources[code]['catalog_completion'].get(sid)
            state='Insamlad och godkänd; endast test' if completion else 'Ej insamlad: källan anger inte onlineStore; fysisk pristransport ej verifierad'
            pages=f"{completion['completed_categories']}/{completion['expected_categories']} / {completion['pages_fetched']}" if completion else '—'
            lines.append(f"| {inventory['area']['city']} | {store['name']} / {sid} | {store['address']}, {store['city']} | {state} | {pages} | {completion['products_observed'] if completion else '—'} | {own.get(sid,'—')} | {pu.get(sid,'—')} |")
        summaries.append({'municipality_code':code,'statuses':counts,'unresolved_registry_rows':inventory['unresolved_registry_rows'],'selected_store_ids':inventory['selected_store_ids'],'complete':False})
    lines.extend(['','Båda kommunernas fullständiga registerjämförelse, inklusive utanför/okänd, finns i ALL-STORES.md och inventory-1281/1280.json. Registerpost 2002 saknar identifierbart butiksnamn/adress och kvarstår som okänd. Det officiella registrets 258 rader har behandlats, men ingen oberoende total för samtliga fysiska verksamheter finns. Därför påstås inte fullständig fysisk butikstäckning.','','Källa: https://www.willys.prod.axcsfprod.aws.axfoodapp.cloud/axfood/rest/v1/store (används av befintlig officiell Willys-transport). Sid-/kategorifullständighet och originaltider ligger i källartefakternas manifest.'])
    (HERE/'COVERAGE.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    rows={code:{r['store']['external_id']:r for r in inventory['stores']} for code,inventory in inventories.items()}
    lines=['# Alla upptäckta registerrader','', 'Samma nationella register, inga misslyckade/okända rader borttagna. Inom/utanför grundas på verifierad position mot respektive kommungräns. Prisantal och insamlingsstatus för kommunbutiker finns i COVERAGE.md.','', '| Käll-ID | Butik | Adress | Lund 1281 | Malmö 1280 | Online enligt källa |','|---|---|---|---|---|---|']
    for sid,row in sorted(rows['1281'].items(),key=lambda t:(t[1]['store']['city'] or '',t[1]['store']['name'])):
        store=row['store']; statuses=[rows[code][sid]['geographic_evidence'] for code in ('1281','1280')]
        lines.append(f"| {sid} | {store['name']} | {store['address']}, {store['city']} | {statuses[0]['status']}: {statuses[0]['reason']} | {statuses[1]['status']}: {statuses[1]['reason']} | {store['online_shopping']} |")
    for r in inventories['1281']['unresolved_registry_rows']:
        lines.append(f"| {r['source_store_id']} | Okänd registerrad {r['row_index']} | Saknas | unknown: {r['reason']} | unknown: {r['reason']} | Ej verifierat |")
    (HERE/'ALL-STORES.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    (HERE/'decision-evidence.json').write_text(json.dumps({'checked_at':datetime.now(UTC).isoformat(),'municipalities':summaries,'sources':sources,'own_by_store':own,'price_universe_by_store':pu,'activation':False},ensure_ascii=False,indent=2),encoding='utf8')
    patch=[];changed=[]
    for backup in sorted((HERE/'backups').rglob('*')):
        if not backup.is_file():continue
        name=backup.relative_to(HERE/'backups').as_posix();current=ROOT/name
        if backup.read_bytes()==current.read_bytes():continue
        changed.append(name)
        patch.extend(difflib.unified_diff(backup.read_text(encoding='utf8').splitlines(True),current.read_text(encoding='utf8').splitlines(True),fromfile='a/'+name,tofile='b/'+name))
    new=['grocery_data/app/connectors/willys/municipality_inventory.py','grocery_data/app/services/willys_municipal_scope.py','grocery_data/tests/test_willys_municipality.py','backend/tests/test_willys_municipal_provider.py','docs/willys_municipality.md','deploy/willys-municipality.override.yaml']
    for name in new:
        patch.extend(difflib.unified_diff([], (ROOT/name).read_text(encoding='utf8').splitlines(True),fromfile='/dev/null',tofile='b/'+name))
    (HERE/'incremental-changes.patch').write_text(''.join(patch),encoding='utf8')
    files=changed+new+['grocery_data/tests/fixtures/willys-municipality-20260922.json.gz']
    (HERE/'final-files.json').write_text(json.dumps({'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'files':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in files}},indent=2))
    print(json.dumps({'files':len(files),'municipalities':summaries,'source_rows':{k:v['row_count'] for k,v in sources.items()}},ensure_ascii=False))


if __name__=='__main__':main()

from pathlib import Path
import hashlib,json,shutil,subprocess
r=Path(__file__).parent
paths=['grocery_data/app/connectors/willys/parser.py','grocery_data/app/connectors/willys/connector.py','grocery_data/app/services/source_artifact.py','grocery_data/source_cli.py','grocery_data/local_relay.py','backend/app/providers/own.py','backend/app/services/production_price_universe_build.py','grocery_data/__main__.py','deploy/scripts/run_daily_refresh.py','docs/HANDOFF.md']
rows=[]
for p in paths:
    target=r/'backups'/p; target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists(): raise RuntimeError('backup exists')
    shutil.copyfile(p,target); rows.append({'path':p,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
(r/'initial-state.json').write_text(json.dumps({'branch':subprocess.check_output(['git','branch','--show-current'],text=True).strip(),'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'files':rows,'status':subprocess.check_output(['git','status','--short'],text=True)},indent=2),encoding='utf-8')
p=Path(paths[0]);s=p.read_text(encoding='utf-8');s=s.replace('        area: GeographicArea,\n    ) -> list[SourceStore]:','        area: GeographicArea,\n        *,\n        filter_locality: bool = True,\n    ) -> list[SourceStore]:',1)
s=s.replace('                if (town_key and town_key != city) or (not town_key and not name_has_city):','                if filter_locality and ((town_key and town_key != city) or (not town_key and not name_has_city)):')
s=s.replace('                    raw_reference=f"{reference}#storeId={external_id}",','                    raw_reference=f"{reference}#storeId={external_id}",\n                    source_fields={"coordinate_source": {"url": document.url,\n                        "sha256": document.payload_hash, "observed_at": document.fetched_at.isoformat()}},')
p.write_text(s,encoding='utf-8')

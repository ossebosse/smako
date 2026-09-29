from pathlib import Path
p=Path('reports/offer-expansion-20260924/verify_lidl_recovery.py')
s=p.read_text().replace("before=R/'lidl-v2-1281'","before=R/'final/lidl-1281'").replace("now=datetime.now(UTC)","now=datetime(2026,9,24,15,tzinfo=UTC)").replace("R.parent/'offer-nutrition-20260924/live-lidl-source'","R.parent/'offer-coverage-20260924/lidl-live-source'").replace("row['own']==26","row['own']==28").replace('new_actual_capture_replay','immutable_capture_requalified_by_final_collector').replace('old_actual_capture_replay','immutable_qualified_OWN_replay')
Path('reports/purchase-planning-20260925/verify_lidl_recovery.py').write_text(s,encoding='utf-8')

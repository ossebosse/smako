"""Municipal source selection using existing campaign policy; no installed job."""
import hashlib
import json
from datetime import UTC, datetime, timedelta

from grocery_data.app.services.area_membership import approved_municipal_stores
from grocery_data.app.services.campaign_refresh_policy import campaign_schedule


def update_selection(inventory, outcomes=None, *, previous=None, now=None):
    now=now or datetime.now(UTC);outcomes=outcomes or {};previous=previous or {}
    code=inventory["area"]["municipality_code"]
    if previous and previous.get("municipality_code")!=code:
        raise ValueError("update state belongs to another municipality")
    inventory_version=hashlib.sha256(json.dumps(inventory,sort_keys=True,default=str).encode()).hexdigest()
    next_inventory_check=(previous.get("next_inventory_check")
                          if previous.get("inventory_version")==inventory_version else None)
    approved=approved_municipal_stores(inventory,concepts=("Coop","Stora Coop","X:-tra"))
    old={r["store_id"]:r for r in previous.get("stores",[])};rows=[]
    for item in inventory["stores"]:
        store=item["store"];identity=store["external_id"];fields=store["source_fields"]
        signature=hashlib.sha256(json.dumps({k:fields.get(k) for k in ["concept","official_store_url","offers_url","ledger_account_number"]},sort_keys=True).encode()).hexdigest()
        row={"store_id":identity,"name":store["name"],"concept":fields["concept"],
             "municipality_status":item["geographic_evidence"]["status"],
             "source_signature":signature,"selected":identity in approved,"due":False}
        if identity not in approved:
            row.update(status="not_selected",reason="municipality_or_identity_not_verified")
        elif identity in outcomes:
            result=outcomes[identity];failed=result["status"] not in {"partial_candidate","partial_text_candidate","confirmed_no_qualified_rows"}
            count=(old.get(identity,{}).get("failed_attempts",0)+1) if failed else 0
            schedule=campaign_schedule(result.get("windows",[]),now=now,failed_attempts=count)
            row.update(**schedule,status=result["status"],failed_attempts=count,
                       last_success=old.get(identity,{}).get("last_success") if failed else result.get("observed_at"),
                       last_fetch_at=result.get("last_fetched_at") or result.get("observed_at") or old.get(identity,{}).get("last_fetch_at"),
                       source_version=result.get("source_version"),last_attempt=now.isoformat())
            # ICA's campaign-only age exception does not apply to Coop/X:-tra.
            # Preserve failed-fetch backoff, but successful sources must be
            # checked before their unchanged 36 h warning / 48 h hard stop.
            if row.get("last_success"):
                observed=datetime.fromisoformat(row["last_success"])
                row["price_hard_stop_at"]=(observed+timedelta(hours=48)).isoformat()
                deadline=max(now,observed+timedelta(hours=35))
                if not failed and deadline<datetime.fromisoformat(row["next_fetch_at"]):
                    row.update(next_fetch_at=deadline.isoformat(),reason="coop_35h_source_check_before_48h_stop")
        elif identity in old and old[identity].get("source_signature")==signature:
            row.update({k:v for k,v in old[identity].items() if k not in {"selected","due","municipality_status"}})
            row["due"]=datetime.fromisoformat(row["next_fetch_at"])<=now if row.get("next_fetch_at") else True
        else:
            row.update(status="new_or_changed_source",next_fetch_at=now.isoformat(),reason="new_or_changed_source",due=True)
        rows.append(row)
    return {"municipality_code":code,"area":inventory["area"],"production_activation":False,
            "inventory_version":inventory_version,
            "next_inventory_check":next_inventory_check or (now+timedelta(hours=72)).isoformat(),"stores":rows,
            "due_store_ids":[r["store_id"] for r in rows if r["selected"] and r["due"]]}

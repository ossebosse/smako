"""Ordinary HTTP planning and lossless read checks on the transition COPY."""

import hashlib
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

import httpx

root = Path(os.environ.get("PROBE_DATA_ROOT", "/work"))
phase = sys.argv[1]
sqlite_suffix = "?mode=ro&immutable=1" if phase.startswith("recovery") else "?mode=ro"


def save(name, value):
    p = Path(os.environ.get("PROBE_OUTPUT_ROOT", str(root))) / (name + ".json")
    p.write_text(json.dumps(value, indent=2) + "\n")
    p.chmod(0o600)


def records():
    with sqlite3.connect((root / "plans.sqlite").as_uri() + sqlite_suffix, uri=True) as db:
        return {
            f"{p}:{r}": hashlib.sha256(s.encode()).hexdigest()
            for p, r, s in db.execute(
                "SELECT plan_id,revision,response_json FROM consumer_plan_revisions"
            )
        }


before = records()
cookies = json.loads((root / "ops-cookies.json").read_bytes())
report = {"phase": phase, "before_revisions": len(before), "cases": []}
with httpx.Client(base_url="http://127.0.0.1:8000", timeout=900, cookies=cookies) as client:
    assert client.get("/ready").status_code == 200
    if phase == "create":
        save("transition-original-revisions", before)
        cases = [
            (
                "profile-15-20",
                json.loads((root / "http-results.json").read_bytes())["cases"][0]["request"],
            )
        ]
        cases.extend(
            (x["case"], x["request"])
            for x in json.loads((root / "representative-bdc9-results.json").read_bytes())["cases"]
            if x["case"] in {"ica-approx-laxsida", "hemkop-open-pizza"}
        )
        active = json.loads((root / "price-universes/active/city-lund.json").read_bytes())
        products = json.loads((root / "price-universes" / active["artifact_file"]).read_bytes())[
            "universe"
        ]["products"]
        created = []
        for name, request in cases:
            if name == "hemkop-open-pizza":
                matches = [
                    p
                    for p in products
                    if p["chain"] == "hemkop"
                    and p["name"].casefold() == "pizza"
                    and p["store_id"] in request["allowed_store_ids"]
                    and p.get("purchase_terms", {}).get("variant_selection") == "required"
                    and p["purchase_terms"]["complete_group_size"] == 2
                ]
                assert len(matches) == 1
                p = matches[0]
                key = hashlib.sha256(
                    repr(("context_product", p["store_id"], p["product_id"])).encode()
                ).hexdigest()[:32]
                request["personal"]["extras"][0]["product_key"] = key
                search = client.post(
                    "/api/product-search",
                    json={"query": p["name"], "product_key": key, "memberships": ["HEMKOP_MEMBER"]},
                )
                assert search.status_code == 200 and search.json()["results"]
            request["personal"]["pantry_revision"] = client.get("/api/personal/state").json()[
                "revision"
            ]
            response = client.post("/api/plans", json=request)
            assert response.status_code == 201, (name, response.status_code, response.text[:500])
            created.append(
                {"case": name, "status": response.status_code, "response": response.json()}
            )
            save("transition-created", created)
            report["cases"].append(
                {
                    "case": name,
                    "status": response.status_code,
                    "plan_id": response.json()["plan_id"],
                }
            )
            save("transition-" + phase, report)
            time.sleep(9)
        save("ops-cookies", dict(client.cookies))
    else:
        created = json.loads((root / "transition-created.json").read_bytes())
        older = json.loads((root / "older-created.json").read_bytes())
        for row in created + older:
            if row["status"] != 201:
                continue
            original = row["response"]
            pid = original["plan_id"]
            revision = original["revision"]
            with sqlite3.connect((root / "plans.sqlite").as_uri() + sqlite_suffix, uri=True) as db:
                saved, request = db.execute(
                    "SELECT response_json,request_json FROM consumer_plan_revisions WHERE plan_id=? AND revision=?",
                    (pid, revision),
                ).fetchone()
            response = client.get("/api/plans/" + pid, params={"revision": revision})
            assert response.status_code == 200, (
                row["case"],
                response.status_code,
                response.text[:300],
            )
            value = response.json()
            if phase.startswith("recovery"):
                assert value["plan"] == json.loads(saved), row["case"]
                assert value["request"] == json.loads(request)
            else:
                # Normal app adds live freshness annotations outside the saved result.
                assert value["plan"] == original["plan"], row["case"]
            report["cases"].append(
                {
                    "case": row["case"],
                    "older": row in older,
                    "plan_id": pid,
                    "revision": revision,
                    "status": 200,
                    "plan_identical": True,
                    "saved_sha256": hashlib.sha256(saved.encode()).hexdigest(),
                }
            )
        if phase.startswith("recovery"):
            pid = created[0]["response"]["plan_id"]
            with httpx.Client(base_url="http://127.0.0.1:8000") as stranger:
                assert stranger.get("/api/plans/" + pid).status_code == 403
            report["wrong_owner_status"] = 403
            report["disabled"] = {}
            for route in (
                "/api/plans",
                "/api/plan",
                "/api/personal/plans/" + pid + "/change",
                "/api/plans/" + pid + "/replace-product",
                "/api/plans/" + pid + "/replace-recipe",
                "/api/admin/reload-price-universe",
                "/api/internal/price-universe/reload",
            ):
                r = client.post(route, json={})
                assert r.status_code == 503 and r.json()["code"] == "recovery_read_only"
                report["disabled"][route] = 503
    after = records()
    report["all_previous_revisions_unchanged"] = all(after.get(k) == v for k, v in before.items())
    assert report["all_previous_revisions_unchanged"]
    report["after_revisions"] = len(after)
    save("transition-" + phase, report)
    print(json.dumps(report))

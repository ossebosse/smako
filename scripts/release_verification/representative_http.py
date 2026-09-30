"""Current source-backed weight, multibuy and open-variant HTTP purchases.

Run in a frozen isolated data copy with the retained evaluation ``job.py`` and
``http_job.py`` on PYTHONPATH. Products are selected from the active artifact;
no historical price or source row is fabricated or forced into serving.
"""

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from job import configure, save

image_build_id = os.environ.get("BUILD_ID")
configure()
if image_build_id:
    os.environ["BUILD_ID"] = image_build_id
os.environ["PLAN_PREWARM_ENABLED"] = "false"
from app.services.personal_policy import interpretation
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

from grocery_data.app.services.prepared_universe_activation import PreparedUniverseArtifactStore

P = Path("/work")
artifact = PreparedUniverseArtifactStore(P / "price-universes").resolve_active_artifact(
    "Lund", verify_hash=True
)
prepared = PreparedPriceUniverseArtifact.model_validate_json(artifact.read_bytes()).restore()
products = prepared.universe.products
keys = {i: k for k, indices in prepared.product_search_index.groups.items() for i in indices}


def pick(chain, predicate):
    return next(
        (i, p)
        for i, p in enumerate(products)
        if p.chain == chain
        and p.price_context_type == "physical_store"
        and p.purchase_terms
        and predicate(p)
    )


targets = [
    (
        "ica-approx-laxsida",
        *pick(
            "ica",
            lambda p: (
                "laxsida" in p.name.casefold() and p.purchase_terms.approximate_package_g == 1200
            ),
        ),
        200,
        "g",
        "estimated",
        True,
    ),
    (
        "ica-loose-weight",
        *pick("ica", lambda p: p.purchase_terms.purchase_form == "loose_weight"),
        350,
        "g",
        "estimated",
        False,
    ),
    (
        "ica-whole-three-pack",
        *pick(
            "ica",
            lambda p: (
                "krossade tomater" in p.name.casefold()
                and p.purchase_terms.complete_group_size == 3
                and p.purchase_terms.variant_selection != "required"
            ),
        ),
        390,
        "g",
        "exact",
        True,
    ),
    (
        "hemkop-open-pizza",
        *pick(
            "hemkop",
            lambda p: (
                p.name.casefold() == "pizza"
                and p.purchase_terms.variant_selection == "required"
                and p.purchase_terms.complete_group_size == 2
            ),
        ),
        1,
        "st",
        "exact",
        True,
    ),
]
# A fixed multibuy is requested in its documented package unit, never a fabricated piece conversion.
targets = [
    (
        name,
        i,
        p,
        p.usable_quantity or p.package_quantity,
        p.usable_unit or p.package_unit,
        mode,
        member,
    )
    if name == "ica-whole-three-pack"
    else (name, i, p, q, u, mode, member)
    for name, i, p, q, u, mode, member in targets
]
save("representative-bdc9-products", [p.model_dump(mode="json") for _, _, p, *_ in targets])


def start():
    process = subprocess.Popen(
        [sys.executable, "/evaluation/http_job.py", "--serve"],
        stdout=(P / "representative-app.log").open("a"),
        stderr=subprocess.STDOUT,
    )
    for _ in range(1800):
        if process.poll() is not None:
            raise RuntimeError("private app startup failed")
        try:
            if httpx.get("http://127.0.0.1:8000/ready", timeout=1).status_code == 200:
                return process
        except httpx.TransportError:
            pass
        time.sleep(0.1)
    raise RuntimeError("startup timed out")


def stop(server):
    server.terminate()
    server.wait(30)


report = {
    "at": datetime.now(UTC).isoformat(),
    "network": "Docker network none; retained source observations",
    "source_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
    "cases": [],
}
server = start()
try:
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=600) as client:
        state = client.get("/api/personal/state").json()
        for name, i, p, q, u, mode, member in targets:
            programs = {"ica": "ICA_STAMMIS", "coop": "COOP_MEMBER", "hemkop": "HEMKOP_MEMBER"}
            search = client.post(
                "/api/product-search",
                json={
                    "query": p.name,
                    "product_key": keys[i],
                    "memberships": [programs[p.chain]] if member else [],
                },
            )
            assert search.status_code == 200, (name, search.text)
            request = {
                "postal_code": "22350",
                "recipes": 0,
                "max_stores": 1,
                "allowed_store_ids": [p.store_id],
                "memberships": {p.chain: member},
                "purchase_planning_mode": mode,
                "personal": {
                    "meals": [],
                    "pantry_revision": client.get("/api/personal/state").json()["revision"],
                    "extras": [
                        {
                            "kind": "campaign"
                            if p.purchase_terms.variant_selection == "required"
                            else "exact",
                            "query": p.name,
                            "quantity": q,
                            "unit": u,
                            "product_key": keys[i],
                            "properties": interpretation(p.name),
                            "confirmed": True,
                        }
                    ],
                },
            }
            time.sleep(9)
            response = client.post("/api/plans", json=request)
            row = {
                "case": name,
                "source_product": p.product_id,
                "request": request,
                "search": search.json(),
                "http_status": response.status_code,
                "response": response.json(),
            }
            if response.status_code == 201:
                row["roundtrip_identical"] = (
                    client.get("/api/plans/" + response.json()["plan_id"]).json() == response.json()
                )
            report["cases"].append(row)
            save("representative-bdc9-results", report)
            print(name, response.status_code, flush=True)
            # Same source with prohibited mode / cap / membership, keeping every other choice identical.
            if name == "ica-approx-laxsida":
                negative = json.loads(json.dumps(request))
                negative["purchase_planning_mode"] = "exact"
                negative["personal"]["pantry_revision"] = client.get("/api/personal/state").json()[
                    "revision"
                ]
                time.sleep(9)
                r = client.post("/api/plans", json=negative)
                report["cases"].append(
                    {
                        "case": name + "-blocked-control",
                        "http_status": r.status_code,
                        "request": negative,
                        "response": r.json(),
                    }
                )
        after = client.get("/api/personal/state").json()
        report["pantry_stock_unchanged"] = (
            after["items"] == state["items"] and after["ledger"] == state["ledger"]
        )
        report["profile_unchanged"] = after["profile"] == state["profile"]
        stop(server)
        server = start()
        report["restart_roundtrips"] = [
            {
                "case": row["case"],
                "identical": client.get("/api/plans/" + row["response"]["plan_id"]).json()
                == row["response"],
            }
            for row in report["cases"]
            if row["http_status"] == 201
        ]
        save("representative-bdc9-results", report)
finally:
    stop(server)

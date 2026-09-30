"""Probe actual old/new images without changing application code or source times.

Mount an isolated consistent data copy at /work and run with --network none.
Private cookies and test-only keys are mode 0600 and never printed. A report
records semantic field loss even if the old HTTP endpoint returns 200.
"""

import argparse
import hashlib
import json
import os
import secrets
import sqlite3
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path("/work")
ORIGINAL = (
    "context:coop:23eaae11c9661e68,context:hemkop:3288e04edd97e349,"
    "context:ica:46850f1523580803,context:ica:979e70ce1f577bc4,"
    "context:willys:383650ec6ff5a636,context:willys:4a671428fc484e43"
)


def save(name, value):
    path = ROOT / name
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    path.chmod(0o600)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def differences(a, b, path="plan"):
    if isinstance(a, dict) and isinstance(b, dict):
        result = []
        for key in sorted(a.keys() | b.keys()):
            if key not in a or key not in b:
                result.append(path + "." + key + (":missing" if key not in b else ":added"))
            else:
                result.extend(differences(a[key], b[key], path + "." + key))
        return result
    if isinstance(a, list) and isinstance(b, list):
        result = [path + ":length"] if len(a) != len(b) else []
        for i, (left, right) in enumerate(zip(a, b, strict=False)):
            result.extend(differences(left, right, f"{path}[{i}]"))
        return result
    return [] if a == b else [path + ":changed"]


def configure(args):
    secret_file = ROOT / "ops-private.json"
    if not secret_file.exists():
        save(secret_file.name, {"key": secrets.token_hex(32), "admin": secrets.token_hex(32)})
    private = json.loads(secret_file.read_bytes())
    policy = json.loads((ROOT / "policy.json").read_bytes())
    os.environ.update(
        APP_ENV="development",
        SECRET_KEY=private["key"],
        BETA_ADMIN_TOKEN=private["admin"],
        PYTHON_DOTENV_DISABLED="1",
        PLAN_STORE_PATH="/work/plans.sqlite",
        GROCERY_DATABASE_URL="sqlite:////work/grocery.sqlite",
        GROCERY_RAW_SNAPSHOT_ROOT="/work/raw",
        PRICE_UNIVERSE_CACHE_ROOT=args.price_root,
        PRICE_UNIVERSE_REQUIRED="false" if args.read_only else "true",
        OWN_SOURCES_ONLY="false" if args.policy == "original" else "true",
        PRICE_UNIVERSE_REQUIRED_CONTEXT_IDS=ORIGINAL
        if args.policy == "original"
        else ",".join(policy["required_context_ids"]),
        PRICE_UNIVERSE_PREWARM_ENABLED="false",
        PLAN_PREWARM_ENABLED="false",
        ALLOW_PROVIDER_FALLBACK="false",
        ALLOW_MOCK_FALLBACK="false",
        MAX_PRICE_AGE_HOURS="48",
        PRICE_AGE_WARNING_HOURS="36",
        DEMAND_REFRESH_ENABLED="false",
        PUBLIC_BASE_URL="http://127.0.0.1:8000",
    )
    os.environ.pop("OPENAI_API_KEY", None)


def records():
    with sqlite3.connect(f"file:{ROOT}/plans.sqlite?mode=ro", uri=True) as db:
        return {
            f"{row[0]}:{row[1]}": hashlib.sha256(row[2].encode()).hexdigest()
            for row in db.execute(
                "SELECT plan_id, revision, response_json FROM consumer_plan_revisions"
            )
        }


def start(label):
    with (ROOT / f"{label}-app.log").open("a") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
                "--log-level",
                "warning",
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    for _ in range(1800):
        if process.poll() is not None:
            return process, False
        try:
            if httpx.get("http://127.0.0.1:8000/health", timeout=1).status_code == 200:
                return process, True
        except httpx.TransportError:
            pass
        time.sleep(0.1)
    process.terminate()
    process.wait(30)
    return process, False


def stop(process):
    if process.poll() is None:
        process.terminate()
        process.wait(30)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["create", "create-open", "read", "recalculate"])
    parser.add_argument("--label", required=True)
    parser.add_argument("--policy", choices=["five", "original"], required=True)
    parser.add_argument("--read-only", action="store_true")
    parser.add_argument("--price-root", default="/work/price-universes")
    args = parser.parse_args()
    configure(args)
    before_records = records()
    report = {
        "at": datetime.now(UTC).isoformat(),
        "phase": args.phase,
        "label": args.label,
        "image_build_id": os.getenv("BUILD_ID"),
        "policy": args.policy,
        "price_universe_required": not args.read_only,
        "price_root": args.price_root,
        "network": "Docker network none",
        "original_records": len(before_records),
        "cases": [],
    }
    process, started = start(args.label)
    report["startup"] = started
    if not started:
        report["app_exit_code"] = process.returncode
        save(args.label + ".json", report)
        print(json.dumps(report))
        return 2
    try:
        cookie_file = ROOT / "ops-cookies.json"
        cookies = json.loads(cookie_file.read_bytes()) if cookie_file.exists() else {}
        with httpx.Client(base_url="http://127.0.0.1:8000", timeout=900, cookies=cookies) as client:
            report["ready"] = client.get("/ready").status_code
            status = client.get("/api/price-universe/status")
            report["serving_status"] = (
                status.json() if status.status_code == 200 else status.status_code
            )
            if args.phase in {"create", "create-open"}:
                assert report["ready"] == 200
                original = json.loads((ROOT / "http-results.json").read_bytes())["cases"][0]
                purchases = json.loads((ROOT / "representative-bdc9-results.json").read_bytes())[
                    "cases"
                ]
                selected = [("profile-15-20", original["request"])]
                selected.extend(
                    (r["case"], r["request"])
                    for r in purchases
                    if r["case"] in {"ica-approx-laxsida", "hemkop-open-pizza"}
                )
                created = []
                if args.phase == "create-open":
                    previous = json.loads((ROOT / "ops-created.json").read_bytes())
                    save(args.label + "-previous.json", previous)
                    created = [row for row in previous if row["status"] == 201]
                    selected = [
                        (label, req) for label, req in selected if label == "hemkop-open-pizza"
                    ]
                    manifest = json.loads(
                        (ROOT / "price-universes/active/city-lund.json").read_bytes()
                    )
                    artifact = ROOT / "price-universes" / manifest["artifact_file"]
                    content = json.loads(artifact.read_bytes())
                    candidates = [
                        p
                        for p in content["universe"]["products"]
                        if p["chain"] == "hemkop"
                        and p["name"].casefold() == "pizza"
                        and p["store_id"] in selected[0][1]["allowed_store_ids"]
                        and p.get("purchase_terms")
                        and p["purchase_terms"]["variant_selection"] == "required"
                        and p["purchase_terms"]["complete_group_size"] == 2
                    ]
                    assert len(candidates) == 1, "unique current source-bound campaign required"
                    product = candidates[0]
                    assert not product.get("gtin"), (
                        "must resolve GTIN key via ordinary product search"
                    )
                    key = hashlib.sha256(
                        repr(
                            ("context_product", product["store_id"], product["product_id"])
                        ).encode()
                    ).hexdigest()[:32]
                    selected[0][1]["personal"]["extras"][0]["product_key"] = key
                    search = client.post(
                        "/api/product-search",
                        json={
                            "query": product["name"],
                            "product_key": key,
                            "memberships": ["HEMKOP_MEMBER"],
                        },
                    )
                    assert search.status_code == 200 and search.json()["results"], (
                        "current campaign missing in ordinary search"
                    )
                    report["current_campaign"] = {
                        "product_id": product["product_id"],
                        "source_provenance": product["source_provenance"],
                        "purchase_terms": product["purchase_terms"],
                        "search": search.json(),
                    }
                for label, request in selected:
                    request = json.loads(json.dumps(request))
                    request["personal"]["pantry_revision"] = client.get(
                        "/api/personal/state"
                    ).json()["revision"]
                    response = client.post("/api/plans", json=request)
                    row = {
                        "case": label,
                        "status": response.status_code,
                        "response": response.json(),
                    }
                    created.append(row)
                    save("ops-created.json", created)
                    save(cookie_file.name, dict(client.cookies))
                    report["cases"].append({"case": label, "status": response.status_code})
                    save(args.label + ".json", report)
                    assert response.status_code == 201, (label, response.text[:250])
                    time.sleep(9)
            else:
                created = json.loads((ROOT / "ops-created.json").read_bytes())
                for generation in range(2 if args.phase == "read" else 1):
                    if generation:
                        stop(process)
                        process, started = start(args.label)
                        assert started, "restart failed"
                    for row in created:
                        old = row["response"]
                        if args.phase == "read":
                            response = client.get("/api/plans/" + old["plan_id"])
                        else:
                            state = client.get("/api/personal/state")
                            payload = {
                                "action": "recalculate",
                                "revision": old["revision"],
                                "pantry_revision": state.json()["revision"],
                            }
                            response = client.post(
                                "/api/personal/plans/" + old["plan_id"] + "/change", json=payload
                            )
                        result = {
                            "case": row["case"],
                            "after_restart": bool(generation),
                            "status": response.status_code,
                        }
                        try:
                            value = response.json()
                        except ValueError:
                            value = {"detail": response.text[:200]}
                        if args.phase == "read" and response.status_code == 200:
                            diff = differences(old["plan"], value["plan"])
                            result.update(
                                plan_identical=not diff,
                                difference_count=len(diff),
                                difference_paths=diff[:80],
                                original_plan_sha256=digest(old["plan"]),
                                returned_plan_sha256=digest(value["plan"]),
                                source_version_retained=value["price_universe_id"]
                                == old["price_universe_id"],
                                recalculation_available=value.get("recalculation_available"),
                                saved_request_identical=value.get("request") == old.get("request"),
                            )
                        else:
                            result["detail"] = str(
                                value.get(
                                    "detail", value.get("code", "response retained privately")
                                )
                            )[:600]
                        report["cases"].append(result)
                        save(args.label + ".json", report)
            after_records = records()
            report["preexisting_records_preserved"] = all(
                after_records.get(k) == v for k, v in before_records.items()
            )
            report["records_after"] = len(after_records)
            save(args.label + ".json", report)
            print(json.dumps(report))
            return 0
    finally:
        stop(process)


if __name__ == "__main__":
    raise SystemExit(main())

"""External, provider-free smoke test for one deployed beta origin."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_urlsafe
from time import perf_counter
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

_SCHEMA_VERSION = "public-beta-production-smoke-v2"


def _safe_origin(value: str, *, allow_http: bool = False) -> str:
    parsed = urlsplit(value.strip())
    allowed = {"https"} | ({"http"} if allow_http else set())
    if parsed.scheme not in allowed or not parsed.netloc:
        protocol = "HTTPS" if not allow_http else "HTTP(S)"
        raise ValueError(f"base URL requires a complete {protocol} origin")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("base URL cannot contain credentials, query or fragment")
    if parsed.path not in {"", "/"}:
        raise ValueError("base URL must not contain a path")
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


def _json_object(response: httpx.Response, *, endpoint: str) -> dict[str, Any]:
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise TypeError(f"{endpoint} did not return a JSON object")
    return payload


def _validate_plan(saved: dict[str, Any], *, max_stores: int) -> dict[str, Any]:
    plan = saved.get("plan")
    if not isinstance(plan, dict):
        raise TypeError("saved-plan response lacks plan")
    plan_id = saved.get("plan_id")
    if not isinstance(plan_id, str) or not plan_id:
        raise ValueError("saved-plan response lacks plan_id")
    recipes = plan.get("recipes")
    if not isinstance(recipes, list) or len(recipes) != 5:
        raise ValueError("production smoke did not produce exactly five recipes")
    for recipe in recipes:
        if not isinstance(recipe, dict):
            raise TypeError("production smoke contains a malformed recipe")
        if not isinstance(recipe.get("ingredients"), list) or not recipe["ingredients"]:
            raise ValueError("production smoke recipe lacks ingredient detail")
        if not isinstance(recipe.get("instructions"), list) or not recipe["instructions"]:
            raise ValueError("production smoke recipe lacks instruction detail")
    basket = plan.get("optimized_basket")
    if not isinstance(basket, dict):
        raise TypeError("production smoke lacks optimized basket")
    stores = basket.get("stores")
    if not isinstance(stores, list) or not 1 <= len(stores) <= max_stores:
        raise ValueError("optimized basket violates the requested store cap")
    total = basket.get("total")
    if not isinstance(total, (int, float)) or total <= 0:
        raise ValueError("optimized basket lacks a positive total")
    quality = plan.get("quality")
    basket_audit = quality.get("basket_audit") if isinstance(quality, dict) else None
    if not isinstance(basket_audit, dict) or basket_audit.get("status") != "PASS":
        raise ValueError("BasketAuditor did not pass")
    price_data = plan.get("data")
    if not isinstance(price_data, dict):
        raise TypeError("plan lacks PriceUniverse provenance")
    universe_id = price_data.get("price_universe_id")
    if not isinstance(universe_id, str) or not universe_id:
        raise ValueError("plan lacks PriceUniverse ID")
    if price_data.get("live_chain_requests") != 0:
        raise ValueError("planner made a live grocery-provider request")
    if price_data.get("status") in {"stale", "broken"}:
        raise ValueError("planner used an unusable PriceUniverse")

    online_contexts = 0
    shopping_lines = 0
    for store in stores:
        if not isinstance(store, dict):
            raise TypeError("optimized basket contains malformed store group")
        items = store.get("items")
        if not isinstance(items, list) or not items:
            raise ValueError("grouped shopping list contains an empty store group")
        shopping_lines += len(items)
        for item in items:
            if not isinstance(item, dict):
                raise TypeError("optimized basket contains malformed item")
            if not str(item.get("product_name") or "").strip():
                raise ValueError("grouped shopping list contains an unnamed product")
            context_type = str(item.get("price_context_type") or "").casefold()
            if context_type == "online_fulfillment":
                online_contexts += 1
                store_name = str(item.get("store_name") or "").casefold()
                if "online" not in store_name:
                    raise ValueError("online fulfillment price lacks an online scope label")
    return {
        "plan_id": plan_id,
        "price_universe_id": universe_id,
        "recipes": len(recipes),
        "recipe_details_checked": len(recipes),
        "stores": len(stores),
        "shopping_groups_checked": len(stores),
        "shopping_lines_checked": shopping_lines,
        "total_sek": round(float(total), 2),
        "online_price_items": online_contexts,
    }


def run_smoke(
    base_url: str,
    *,
    timeout_seconds: float = 45.0,
    request_cold_target_seconds: float = 10.0,
    allow_http: bool = False,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Run health, readiness, PWA, plan and saved-provenance checks."""

    origin = _safe_origin(base_url, allow_http=allow_http)
    own_client = client is None
    session = client or httpx.Client(
        base_url=origin,
        timeout=timeout_seconds,
        follow_redirects=False,
    )
    owner_headers = {"X-Anonymous-Session-ID": f"production-smoke-{token_urlsafe(24)}"}
    try:
        health = _json_object(session.get("/health"), endpoint="/health")
        if health.get("status") not in {"ok", "healthy"}:
            raise ValueError("health endpoint is not healthy")
        ready = _json_object(session.get("/ready"), endpoint="/ready")
        if ready.get("status") not in {"ready", "ok"}:
            raise ValueError("readiness endpoint is not ready")
        manifest = session.get("/manifest.webmanifest")
        manifest.raise_for_status()
        if "application/manifest+json" not in manifest.headers.get("content-type", ""):
            raise ValueError("PWA manifest has the wrong content type")
        unauthenticated_admin = session.get("/api/admin/status")
        if unauthenticated_admin.status_code not in {401, 403}:
            raise ValueError("unauthenticated admin status access was not rejected")

        request = {
            "postal_code": "22350",
            "recipes": 5,
            "servings": 4,
            "max_stores": 2,
            "diet_preference": "mixed",
            "diversity_mode": "balanced",
            "membership_programs": [],
            "optimization_iterations": 0,
            "strategy": "optimized",
            "candidate_recipe_count": 80,
            "beam_width": 30,
            "debug": False,
        }
        started = perf_counter()
        saved = _json_object(
            session.post("/api/plans", json=request, headers=owner_headers),
            endpoint="/api/plans",
        )
        planner_seconds = perf_counter() - started
        facts = _validate_plan(saved, max_stores=2)
        reloaded = _json_object(
            session.get(f"/api/plans/{facts['plan_id']}", headers=owner_headers),
            endpoint="/api/plans/{id}",
        )
        if reloaded.get("price_universe_id") != facts["price_universe_id"]:
            raise ValueError("saved plan lost its PriceUniverse provenance")
        reloaded_plan = reloaded.get("plan")
        if not isinstance(reloaded_plan, dict):
            raise TypeError("reloaded saved plan lacks plan payload")
        reloaded_basket = reloaded_plan.get("optimized_basket")
        if not isinstance(reloaded_basket, dict) or round(
            float(reloaded_basket.get("total", -1)),
            2,
        ) != facts["total_sek"]:
            raise ValueError("saved plan was silently repriced")
        cross_session = session.get(
            f"/api/plans/{facts['plan_id']}",
            headers={"X-Anonymous-Session-ID": "production-smoke-other-session"},
        )
        if cross_session.status_code != 403:
            raise ValueError("a different anonymous session could read the saved plan")

        return {
            "schema_version": _SCHEMA_VERSION,
            "generated_at": datetime.now(UTC).isoformat(),
            "origin": origin,
            "status": "PASS",
            "request_cold_target_seconds": request_cold_target_seconds,
            "planner_seconds": round(planner_seconds, 4),
            "request_cold_target_met": planner_seconds < request_cold_target_seconds,
            "recipes": facts["recipes"],
            "recipe_details_checked": facts["recipe_details_checked"],
            "stores": facts["stores"],
            "shopping_groups_checked": facts["shopping_groups_checked"],
            "shopping_lines_checked": facts["shopping_lines_checked"],
            "total_sek": facts["total_sek"],
            "price_universe_id": facts["price_universe_id"],
            "provider_calls_during_planning": 0,
            "basket_auditor": "PASS",
            "saved_plan_provenance": "PASS",
            "saved_plan_session_isolation": "PASS",
            "unauthenticated_admin_rejected": True,
            "online_price_items_checked": facts["online_price_items"],
        }
    finally:
        if own_client:
            session.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Provider-free production smoke against a deployed HTTPS beta origin."
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=45.0)
    parser.add_argument("--request-cold-target-seconds", type=float, default=10.0)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--allow-http",
        action="store_true",
        help="Local rehearsal only; never evidence of production HTTPS readiness.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    report = run_smoke(
        args.base_url,
        timeout_seconds=args.timeout_seconds,
        request_cold_target_seconds=args.request_cold_target_seconds,
        allow_http=args.allow_http,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["request_cold_target_met"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

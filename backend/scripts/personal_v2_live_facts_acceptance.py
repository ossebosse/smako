"""Selected production source constraints, synthetic guest; no external source calls."""
import json
from pathlib import Path

import httpx

base = "https://beta.smako.nu"
with httpx.Client(base_url=base, timeout=180, headers={"Origin": base}) as client:
    def current():
        return client.get("/api/personal/state").json()["revision"]

    recipe = {"name": "Syntetisk deklarationskontroll", "servings": 1, "ingredients": [{"name": "ris", "quantity": 100, "unit": "g"}], "instructions": ["Deklarationsprov av 100 g ris."]}
    nutrition_req = {"recipes": 0, "max_stores": 2, "personal": {"pantry_revision": current(), "meals": [{"meal_type": "snack", "count": 1, "servings": 1, "limits": {"min_protein_g": 1, "max_kcal": 1000}}], "slots": [{"id": "snack", "day": 1, "meal_type": "snack", "recipe": recipe}]}}
    response = client.post("/api/plans", json=nutrition_req)
    assert response.status_code == 201, response.text
    nutritional = response.json()["plan"]
    eco_req = {"recipes": 0, "max_stores": 2, "personal": {"pantry_revision": current(), "organic_percent": 100, "meals": [], "extras": [{"query": "mjölk", "quantity": 1000, "unit": "ml", "confirmed": True}]}}
    response = client.post("/api/plans", json=eco_req)
    assert response.status_code == 201, response.text
    eco = response.json()["plan"]
    assert eco["personal"]["checks"]["organic_cost_percent"] == 100
    blocked = {**nutrition_req, "personal": {**nutrition_req["personal"], "pantry_revision": current(), "profile": {"allergies": ["jordnötter"]}}}
    response = client.post("/api/plans", json=blocked)
    assert response.status_code == 422 and response.json()["code"] == "DATA_BLOCKED"
    result = {"status": "PASS", "nutrition": nutritional["personal"]["checks"]["nutrition"], "nutrition_cost": nutritional["optimized_basket"]["total"], "organic_cost_percent": eco["personal"]["checks"]["organic_cost_percent"], "organic_cost": eco["optimized_basket"]["total"], "hard_allergy_unknown": "DATA_BLOCKED", "live_requests": nutritional["data"]["live_chain_requests"] + eco["data"]["live_chain_requests"]}
    Path("reports/personal-v2-gaps/live-facts.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))

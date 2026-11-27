"""Owner request 2026-11-27: search recipes and add them to the plan or the shopping list."""
from app.services.recipe_search import recipe_by_id, search, shopping_rows
from fastapi.testclient import TestClient


def test_search_finds_by_name_and_ingredient_one_result_per_dish():
    found = search("köttfärssås", 4)
    assert found and found[0]["name"].startswith("Köttfärssås") and found[0]["servings"] == 4
    assert len({r["base_id"] for r in found}) == len(found)
    by_ingredient = search("kycklinglever", 2)
    assert by_ingredient and all(any("kycklinglever" in i["name"] for i in r["ingredients"]) or "kycklinglever" in r["name"].casefold()
                                 for r in by_ingredient)
    assert search("   ", 2) == []


def test_popular_dishes_come_first_among_equal_matches():
    rows = search("kyckling", 2, "dinner")
    scores = [r["popularity"] for r in rows]
    assert scores[0] == 5 and scores == sorted(scores, reverse=True)


def test_a_found_recipe_gives_the_full_recipe_and_shopping_rows():
    row = search("köttfärssås", 4)[0]
    recipe = recipe_by_id(row["recipe_id"], 4)
    assert recipe and recipe.servings == 4
    rows = shopping_rows(recipe)
    assert rows and not any(r["query"] in {"salt", "svartpeppar", "vatten"} for r in rows)
    assert all(r["unit"] in {"g", "ml", "st"} and r["quantity"] > 0 for r in rows)


def test_the_endpoints(monkeypatch):
    from app.main import app

    client = TestClient(app)
    found = client.get("/api/recipe-search", params={"q": "lasagne", "servings": 3}).json()["results"]
    assert found and found[0]["servings"] == 3
    one = client.get(f"/api/recipe-library/{found[0]['recipe_id']}", params={"servings": 3}).json()
    assert one["recipe"]["name"] == found[0]["name"] and one["shopping_rows"]
    assert client.get("/api/recipe-library/nope:1.0.0:x", params={"servings": 3}).status_code == 404

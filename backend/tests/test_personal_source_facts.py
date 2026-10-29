"""Known raw catalog schemas, with synthetic contents and exact source joins."""

import hashlib
import json
import os
import sqlite3

import pytest
from app.models.personal import ExtraNeed, MealSettings, MealSlot, PortionLimits
from app.services.personal_policy import PolicyConflict
from app.services.personal_source_facts import load_retained_facts, project_raw_facts

from backend.tests.test_personal_planning_v2 import prepared, product, recipe, request, run


def label(**overrides):
    return {
        "id": "source-milk",
        "listOfIngredients": "MJÖLK, vatten",
        "accreditedTags": [{"code": "EU_ORGANIC_FARMING"}],
        "nutrientInformation": [
            {
                "header": {
                    "nutrientBasisQuantity": 100,
                    "nutrientBasisQuantityType": "BY_MEASURE",
                    "nutrientBasisQuantityUnit": {"code": "MLT", "value": "Milliliter"},
                }
            }
        ],
        "nutrientLinks": [
            {"description": name, "unit": unit, "amount": [str(value)]}
            for name, unit, value in [
                ("Energi", "Kilokalori", 45),
                ("Protein", "Gram", 3.5),
                ("Fett", "Gram", 1.5),
                ("Kolhydrat", "Gram", 4.8),
            ]
        ],
        **overrides,
    }


def fact(raw, chain="coop", identity="mjölk"):
    return project_raw_facts(
        raw,
        chain=chain,
        product_id=identity,
        snapshot_id="v2-frozen",
        source_reference="synthetic retained source declaration",
    )


def test_declarations_map_without_certifying_allergen_absence_or_cooked_yield():
    f = fact(label())
    assert f.organic is True and f.nutrition == {
        "kcal": 45,
        "protein_g": 3.5,
        "fat_g": 1.5,
        "carbs_g": 4.8,
    }
    assert f.nutrition_unit == "ml" and "Produktdeklaration" in f.nutrition_basis
    assert not f.ingredients_complete and not f.allergens_checked and f.animal is True
    assert fact({"accreditedTags": [{"code": "EU_ECO_LABEL"}]}).organic is None
    assert fact({"labels": ["eu_ecological"], "nonEkoProduct": False}, "willys").organic is True
    assert fact({"labels": ["eu_ecological"], "nonEkoProduct": True}, "willys").organic is None


def test_explicit_frozen_source_form_is_independent_of_flattened_category_and_allergens():
    raw = {"id": "7340191151833", "name": "Majs", "consumerInformationText": ["Fryst"],
           "claimReportingInformations": {"description": [{"languageCode": "sv", "value": "Djupfryst"}]},
           "listOfIngredients": "INGREDIENSER: Majskorn (Ungern)."}
    f = fact(raw, identity="corn")
    assert f.product_classification == ("frozen",)
    evidence = f.field_sources["product_classification"][0]
    assert evidence["product_id"] == "corn" and evidence["snapshot_id"] == "v2-frozen"
    assert evidence["raw_fields"]["consumerInformationText"] == ["Fryst"]
    assert not f.ingredients_complete and not f.allergens_checked
    assert not fact({"maxStorageTemperature": "-18"}).product_classification
    assert not fact({"consumerInformationText": ["Frys ej"]}).product_classification
    assert fact({"labels": [], "nonEkoProduct": True}, "hemkop").organic is False
    assert fact({"labels": [], "nonEkoProduct": False}, "hemkop").organic is None
    assert not fact({"energyDeclaration": {"value": "G"}}, "willys").nutrition


@pytest.mark.parametrize("amount", ["<0.5", "unknown", "nan", "-1", "inf"])
def test_unknown_conflicting_or_less_than_values_are_not_point_estimates(amount):
    raw = label()
    raw["nutrientLinks"][1]["amount"] = [amount]
    assert "protein_g" not in fact(raw).nutrition


def test_verified_product_nutrition_affects_product_selection():
    p = prepared(
        product("mjölk", 1000, "ml", 20), product("mjölk", 1000, "ml", 1, identity="cheap-unknown")
    )
    from app.models.recipe import RecipeIngredient

    req = request(
        slots=[
            MealSlot(
                id="d",
                day=1,
                meal_type="dinner",
                recipe=recipe(
                    ingredients=[RecipeIngredient(name="mjölk", quantity=200, unit="ml")]
                ),
            )
        ],
        meals=[MealSettings(count=1, servings=1, limits=PortionLimits(min_protein_g=6))],
    )
    result = run(p, req, facts={("coop", "mjölk"): fact(label())})
    assert result.optimized_basket.total == 20
    req.personal.meals[0].limits.min_weight_g = 100
    with pytest.raises(PolicyConflict, match="tillagningsutbyte"):
        run(p, req, facts={("coop", "mjölk"): fact(label())})


@pytest.mark.parametrize("driver", ["sqlite", "sqlite+pysqlite"])
def test_hash_snapshot_context_and_exact_product_join(tmp_path, monkeypatch, driver):
    from app.models.provenance import SourceProvenance

    from backend.tests.test_personal_planning_v2 import NOW

    db_path = tmp_path / "grocery.sqlite"
    raw = tmp_path / "raw"
    raw.mkdir()
    content = json.dumps({"results": {"items": [label()]}}).encode()
    (raw / "page.json").write_bytes(content)
    with sqlite3.connect(db_path) as db:
        db.executescript(
            "CREATE TABLE products(id, chain, external_product_id, store_external_id, raw_reference, raw_snapshot_id, catalog_snapshot_id); CREATE TABLE raw_snapshots(id, payload_hash, payload_location, catalog_snapshot_id);"
        )
        db.execute(
            "INSERT INTO products VALUES (?,?,?,?,?,?,?)",
            (
                "mjölk",
                "coop",
                "source-milk",
                "730400",
                "raw:raw-id#results.items[0]",
                "raw-id",
                "v2-frozen",
            ),
        )
        db.execute(
            "INSERT INTO raw_snapshots VALUES (?,?,?,?)",
            ("raw-id", hashlib.sha256(content).hexdigest(), "page.json", "v2-frozen"),
        )
    p = prepared(
        product("mjölk", 1000, "ml", 20).model_copy(
            update={
                "source_provenance": SourceProvenance(
                    source_provider="own",
                    source_channel="catalog",
                    source_snapshot_id="v2-frozen",
                    source_observed_at=NOW,
                    provider_store_id="730400",
                )
            }
        )
    )
    from app.services import personal_source_facts as source_facts
    original_projection = source_facts._project_facts

    def projection_without_global_lock(*args):
        # Projection (the slow part) must not hold the process-wide lock, so a
        # request for another, already cached universe never waits behind it.
        assert not source_facts._LOCK._is_owned()
        return original_projection(*args)

    monkeypatch.setattr(source_facts, "_project_facts", projection_without_global_lock)
    facts = load_retained_facts(p, database=str(db_path), raw_root=raw)
    assert facts[("coop", "mjölk")].organic is True
    assert not source_facts._KEY_LOCKS  # the per-key lock is released after caching
    with sqlite3.connect(db_path) as db:
        db.executescript("CREATE TABLE telemetry(value); INSERT INTO telemetry VALUES (1);")
    # Unrelated activity must not reparse/project unchanged public source data.
    assert load_retained_facts(p, database=str(db_path), raw_root=raw) is facts
    from app.services import personal_source_facts as module

    with monkeypatch.context() as version_patch:
        version_patch.setattr(module, "FACTS_VERSION", module.FACTS_VERSION + "-next-policy")
        requalified = load_retained_facts(p, database=str(db_path), raw_root=raw)
        assert requalified is not facts and requalified.version != facts.version
    assert load_retained_facts(p, database=str(db_path), raw_root=raw) is facts
    metadata = (raw / "page.json").stat()
    (raw / "page.json").write_bytes(content.replace(b"source-milk", b"wrong--milk"))
    os.utime(raw / "page.json", ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
    # Even preserved size/timestamps cannot hide corrupted source content.
    assert load_retained_facts(p, database=str(db_path), raw_root=raw) == {}
    (raw / "page.json").write_bytes(content)
    assert load_retained_facts(p, database=str(db_path), raw_root=raw) is facts
    from sqlalchemy.engine import URL

    monkeypatch.setenv(
        "GROCERY_DATABASE_URL",
        URL.create(
            driver, database=str(db_path), query={"check_same_thread": "false"}
        ).render_as_string(),
    )
    assert load_retained_facts(p, raw_root=raw)[("coop", "mjölk")].organic is True
    other = tmp_path / "other"
    other.mkdir()
    (other / "page.json").write_text("{}")
    assert load_retained_facts(p, database=str(db_path), raw_root=other) == {}
    with sqlite3.connect(db_path) as db:
        db.execute("UPDATE products SET external_product_id='wrong-product'")
    assert load_retained_facts(p, database=str(db_path), raw_root=raw) == {}


def test_organic_mapping_changes_real_basket_and_unknown_stays_unknown():
    p = prepared(product("mjölk", 1000, "ml", 20))
    req = request(
        extras=[ExtraNeed(query="mjölk", quantity=100, unit="ml", confirmed=True)],
        organic_percent=100,
    )
    result = run(p, req, facts={("coop", "mjölk"): fact(label())})
    assert result.optimized_basket.total == 20
    with pytest.raises(PolicyConflict):
        run(p, req, facts={})


def test_prepared_nutrition_cannot_be_used_as_purchased_raw_ingredient():
    raw = label()
    raw["nutrientInformation"][0]["header"]["preparationState"] = {
        "code": "PREPARED",
        "value": "Tillagad",
    }
    assert fact(raw).nutrition == {} and fact(raw).nutrition_basis is None


def test_retained_ingredient_text_blocks_positive_compound_conflict():
    from app.models.personal import TasteProfile

    p = prepared(product("bröd", 500, "g", 20))
    req = request(
        extras=[ExtraNeed(query="bröd", quantity=100, unit="g", confirmed=True)],
        profile=TasteProfile(allergies=["jordnötter"]),
    )
    f = fact(label(listOfIngredients="Vete, jordnötter, vatten"), identity="bröd")
    with pytest.raises(PolicyConflict, match="produktdeklarationen anger jordnötter"):
        run(p, req, facts={("coop", "bröd"): f})


def test_vegan_claim_is_animal_evidence_but_never_allergy_absence():
    f = fact(
        label(
            accreditedTags=[{"code": "EUROPEAN_V_LABEL_VEGAN"}],
            listOfIngredients="Soja, vatten. Kan innehålla spår av MJÖLK.",
        )
    )
    assert f.animal is False and not f.allergens_checked and not f.ingredients_complete
    conflicting = fact(label(accreditedTags=[{"code": "EUROPEAN_V_LABEL_VEGAN"}]))
    assert conflicting.animal is None and "animal" in conflicting.conflicts


def test_ambiguous_drained_basis_is_retained_but_not_eligible_as_sold():
    f = fact(label(name="Mozzarella", listOfIngredients="MJÖLK, vatten, salt"))
    assert f.nutrition and f.nutrition_preparation == "draining_unknown"


def test_conflicting_duplicate_values_are_marked_not_selected():
    raw = label()
    raw["nutrientLinks"].append({"description": "Protein", "unit": "Gram", "amount": ["8"]})
    f = fact(raw)
    assert "protein_g" not in f.nutrition and "nutrition.protein_g" in f.conflicts
    assert f.nutrition["kcal"] == 45


def _single_label_store(root):
    import hashlib
    import sqlite3

    from app.models.provenance import SourceProvenance

    from backend.tests.test_personal_planning_v2 import NOW, prepared, product

    raw = root / "raw"
    raw.mkdir()
    db_path = root / "grocery.sqlite"
    content = json.dumps({"results": {"items": [label()]}}).encode()
    (raw / "page.json").write_bytes(content)
    with sqlite3.connect(db_path) as db:
        db.executescript("CREATE TABLE products(id,chain,external_product_id,store_external_id,raw_reference,"
                         "raw_snapshot_id,catalog_snapshot_id); CREATE TABLE raw_snapshots(id,payload_hash,"
                         "payload_location,catalog_snapshot_id);")
        db.execute("INSERT INTO products VALUES (?,?,?,?,?,?,?)", ("mjölk", "coop", "source-milk", "730400",
                   "raw:raw-id#results.items[0]", "raw-id", "v2-frozen"))
        db.execute("INSERT INTO raw_snapshots VALUES (?,?,?,?)",
                   ("raw-id", hashlib.sha256(content).hexdigest(), "page.json", "v2-frozen"))
    db.close()
    universe = prepared(product("mjölk", 1000, "ml", 20).model_copy(update={"source_provenance": SourceProvenance(
        source_provider="own", source_channel="catalog", source_snapshot_id="v2-frozen", source_observed_at=NOW,
        provider_store_id="730400")}))
    return universe, db_path, raw


@pytest.mark.parametrize("fault", [None, "destination", "source", "snapshot", "namespace", "scope", "hash"])
def test_stora_coop_source_aliases_keep_exact_raw_facts_for_each_destination(tmp_path, fault):
    from dataclasses import replace

    from app.models import Store
    from app.services.personal_source_facts import _load_retained_catalog_facts

    original, database, raw = _single_label_store(tmp_path)
    source_id = "a886e74ad0e74a0e991f903cdebc2180"
    with sqlite3.connect(database) as db:
        db.execute("UPDATE products SET id=?", (source_id,))
        if fault == "snapshot":
            db.execute("UPDATE products SET catalog_snapshot_id='other'")
    base = original.universe.products[0]
    rows, stores = [], []
    for identity in ["3850", "3853"]:
        provenance = base.source_provenance.model_copy(update={
            "source_role": "owner_assigned_base_price", "price_context": "online_fulfillment",
            **({"provider_store_id": "other"} if fault == "source" else {}),
        })
        product_id = source_id + (":other:" if fault == "namespace" else ":stora-syd:") + identity
        rows.append(base.model_copy(update={
            "product_id": product_id, "store_id": identity, "chain": "coop",
            "price_context_type": "online_fulfillment" if fault == "scope" else "physical_store",
            "source_provenance": provenance,
        }))
        stores.append(Store(store_id=identity, name=identity, city="Malmö", chain="coop",
            price_context_type="physical_store",
            physical_store_external_id="other" if fault == "destination" else identity))
    if fault == "hash":
        (raw / "page.json").write_bytes(b"{}")
    target = prepared(*rows)
    target = replace(target, stores=tuple(stores))
    facts = _load_retained_catalog_facts(target, database=database, raw_root=raw)
    if fault is not None:
        assert not facts
        return
    assert len(facts) == 2
    for row in rows:
        fact = facts[(row.store_id, row.product_id)]
        assert fact.organic is True and fact.nutrition["protein_g"] == 3.5
        assert fact.ingredients and fact.observed_at == base.source_provenance.source_observed_at.isoformat()
        assert fact.source_product_id == row.product_id and fact.source_snapshot_id == "v2-frozen"
        assert row.price == base.price


@pytest.mark.parametrize("fault", ["read_error", "changed_between_hashes"])
def test_failed_projection_is_never_persisted_and_the_retry_recovers(tmp_path, monkeypatch, fault):
    """Review 2026-10-18 P2: a projection that hit a read fault must not reach the disk cache."""
    from pathlib import Path

    from app.services import personal_source_facts as source_facts

    universe, db_path, raw = _single_label_store(tmp_path)
    monkeypatch.setenv("RECIPE_PREPARATION_CACHE_ROOT", str(tmp_path / "cache"))
    source_facts._CACHE.clear()
    read = Path.read_bytes

    def faulty(path):
        if path == raw / "page.json":
            if fault == "read_error":
                raise OSError("injected transient read failure")
            return read(path) + b" "  # differs from the hashed evidence
        return read(path)

    monkeypatch.setattr(Path, "read_bytes", faulty)
    first = source_facts._load_retained_catalog_facts(universe, database=db_path, raw_root=raw)
    monkeypatch.setattr(Path, "read_bytes", read)
    assert len(first) == 0 and not source_facts._CACHE
    assert not list((tmp_path / "cache").rglob("*.json"))
    retry = source_facts._load_retained_catalog_facts(universe, database=db_path, raw_root=raw)
    assert len(retry) == 1
    source_facts._CACHE.clear()

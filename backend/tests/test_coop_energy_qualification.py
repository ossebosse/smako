"""Energy integrity contracts, using synthetic/minimal retained-source shapes.

The two reproduced pairs were observed in hash-bound 2026-10-02 Coop sources.
They are not corrected declarations, manufactured catalogue data or menu prices.
"""

from copy import deepcopy
from dataclasses import replace

import pytest
from app.models.personal import MealSettings, MealSlot, PortionLimits
from app.models.recipe import RecipeIngredient
from app.services import personal_source_facts as module
from app.services.nutrition_reference import product_reference
from app.services.personal_policy import PolicyConflict

from backend.tests.test_personal_planning_v2 import prepared, product, recipe, request, run
from backend.tests.test_personal_source_facts import fact, label


def declaration(kcal, kj=None, *, amount=100, unit="GRM"):
    raw = label()
    raw["nutrientInformation"][0]["header"].update({
        "nutrientBasisQuantity": amount,
        "nutrientBasisQuantityUnit": {"code": unit},
    })
    raw["nutrientLinks"] = [
        {"description": "Energi", "unit": "Kilokalori", "amount": [kcal]},
        *([{"description": "Energi", "unit": "Kilojoule", "amount": [kj]}]
          if kj is not None else []),
        *raw["nutrientLinks"][1:],
    ]
    return raw


@pytest.mark.parametrize("identity,kcal,kj,protein,fat,carbs", [
    ("7392055078800", "1100", "250", "17", "20", "0"),
    ("7300156594488", "1000", "240", "8.2", "1.7", "47"),
])
def test_reproduced_retained_energy_conflicts_preserve_raw_pair_and_source(
    identity, kcal, kj, protein, fat, carbs,
):
    raw = declaration(kcal, kj)
    raw["id"] = identity
    for row, value in zip(raw["nutrientLinks"][2:], [protein, fat, carbs], strict=True):
        row["amount"] = [value]
    f = fact(raw, identity=identity)
    assert {"nutrition.kcal", "nutrition.energy"} <= set(f.conflicts)
    assert "kcal" not in f.nutrition
    assert f.nutrition["protein_g"] == float(protein)  # retained, not itself recast as energy
    proof = f.field_sources["nutrition.energy"][0]
    assert proof["source_product_id"] == identity and proof["snapshot_id"] == "v2-frozen"
    assert proof["source"] == "synthetic retained source declaration"
    assert proof["raw_fields"]["nutrientLinks"] == raw["nutrientLinks"][:2]
    assert "energy_pair_mismatch" in proof["reasons"]
    assert f.field_sources["nutrition.kcal"] == (proof,)
    raw["nutrientLinks"][0]["amount"][0] = "rewritten"
    assert proof["raw_fields"]["nutrientLinks"][0]["amount"] == [kcal]


@pytest.mark.parametrize("kcal,kj", [(250, 1100), (900, 3700), (200, 800), (1, 10), (0, 0)])
def test_conservative_pair_screen_allows_separate_energy_factors_and_rounding(kcal, kj):
    f = fact(declaration(kcal, kj))
    assert not f.conflicts and f.nutrition["kcal"] == kcal
    assert f.field_sources["nutrition.energy"][0]["status"] == "no_conflict_detected"


def test_kcal_alone_does_not_require_a_kj_value_or_a_macro_energy_equation():
    f = fact(declaration(450))  # deliberately not 4/4/9 of this test's other fields
    assert not f.conflicts and f.nutrition["kcal"] == 450
    raw = declaration(450, 1800)
    del raw["nutrientLinks"][0]
    f = fact(raw)
    assert not f.conflicts and "kcal" not in f.nutrition
    assert "nutrition.kcal" not in f.field_sources  # kJ never synthesizes kcal


@pytest.mark.parametrize("amount", [25, 100, 200])
def test_mass_ceiling_is_normalized_but_pair_rounding_stays_on_original_basis(amount):
    f = fact(declaration(1100 * amount / 100, amount=amount))
    assert "nutrition.energy" in f.conflicts and "kcal" not in f.nutrition
    assert "kcal_above_conservative_mass_ceiling" in f.field_sources["nutrition.energy"][0]["reasons"]
    f = fact(declaration(1000 * amount / 100, amount=amount))
    assert not f.conflicts and f.nutrition["kcal"] == 1000
    # 1 kcal and 10 kJ differ by <8 kJ on each original declared basis, even
    # where normalization would amplify that difference beyond 8 kJ/100g.
    assert not fact(declaration(1, 10, amount=amount)).conflicts


def test_mass_ceiling_is_not_applied_to_volume_without_density():
    assert not fact(declaration(1100, unit="MLT")).conflicts


@pytest.mark.parametrize("energy_unit", ["Kilokalori", "Kilojoule"])
@pytest.mark.parametrize("bad", [["nan"], ["inf"], ["-1"], [True], ["bad"], [10**400], [], [1, 2], "45", None])
def test_invalid_energy_values_veto_the_declaration(energy_unit, bad):
    raw = declaration(45, 188)
    next(row for row in raw["nutrientLinks"] if row["unit"] == energy_unit)["amount"] = bad
    f = fact(raw)
    assert "nutrition.energy" in f.conflicts and "kcal" not in f.nutrition


@pytest.mark.parametrize("energy_unit", ["Kilokalori", "Kilojoule"])
def test_duplicate_energy_entries_are_ambiguous_even_when_they_agree(energy_unit):
    raw = declaration(45, 188)
    raw["nutrientLinks"].append(deepcopy(next(row for row in raw["nutrientLinks"] if row["unit"] == energy_unit)))
    f = fact(raw)
    assert "nutrition.energy" in f.conflicts and "kcal" not in f.nutrition


@pytest.mark.parametrize("energy_unit", ["Kilokalori", "Kilojoule"])
def test_nonexact_energy_threshold_is_preserved_without_a_point_value(energy_unit):
    raw = declaration(45, 188)
    row = next(row for row in raw["nutrientLinks"] if row["unit"] == energy_unit)
    row.update(amount=["10000"], amountAccuracy={"code": "LESS_THAN", "value": "Mindre än"})
    f = fact(raw)
    assert not f.conflicts
    if energy_unit == "Kilokalori":
        assert "kcal" not in f.nutrition
        assert "nutrition.kcal" not in f.field_sources
    else:
        assert f.nutrition["kcal"] == 45
    proof = f.field_sources["nutrition.energy"][0]
    assert row in proof["raw_fields"]["nutrientLinks"] and proof["pair_check"] is None


@pytest.mark.parametrize("estimates", [False, True])
def test_normal_planner_selects_qualified_alternative_and_cannot_estimate_past_conflict(estimates):
    good = product("mjölk", 1000, "ml", 20)
    bad = product("mjölk", 1000, "ml", 1, identity="cheap-energy-conflict")
    facts = {("coop", good.product_id): fact(declaration(45, 188, unit="MLT")),
             ("coop", bad.product_id): fact(declaration(1100, 250, unit="MLT"), identity=bad.product_id)}
    req = request(
        slots=[MealSlot(id="d", day=1, meal_type="dinner", recipe=recipe(
            ingredients=[RecipeIngredient(name="mjölk", quantity=200, unit="ml")]))],
        meals=[MealSettings(count=1, servings=1, limits=PortionLimits(min_protein_g=6))],
        allow_nutrition_estimates=estimates,
    )
    result = run(prepared(bad, good), req, facts=facts)
    assert result.optimized_basket.total == 20
    assert result.personal.checks["nutrition"][0]["values"]["protein_g"] == 7
    with pytest.raises(PolicyConflict):
        run(prepared(bad), req, facts=facts)


def test_conflicting_energy_cannot_acquire_a_generic_reference():
    p = product("Potatis", 1000, "g", 20).model_copy(update={"category": "Frukt & grönsaker"})
    raw = declaration(1100, 250)
    raw["listOfIngredients"] = "Potatis"
    conflict = fact(raw)
    assert product_reference(p, "potatis", None) is not None
    assert product_reference(p, "potatis", conflict) is None


def test_source_merge_cannot_erase_energy_only_conflict_or_raw_evidence(monkeypatch):
    from app.services import lidl_product_facts, official_product_facts

    p = product("mjölk", 1000, "ml", 20)
    raw = declaration(1100, 250)
    raw["nutrientLinks"] = raw["nutrientLinks"][:2]
    prior = fact(raw)
    assert not prior.nutrition
    source = replace(fact(declaration(45, 188)), source="synthetic official declaration")
    monkeypatch.setattr(module, "_load_retained_catalog_facts", lambda *a, **k: module.FactsCollection({("coop", p.product_id): prior}))
    monkeypatch.setattr(lidl_product_facts, "reviewed_facts", lambda *a, **k: {})
    monkeypatch.setattr(official_product_facts, "declared_facts", lambda *a, **k: {("coop", p.product_id): source})
    result = module.load_retained_facts(prepared(p))[("coop", p.product_id)]
    assert {"nutrition.kcal", "nutrition.energy"} <= set(result.conflicts)
    assert prior.field_sources["nutrition.energy"][0] in result.field_sources["nutrition.energy"]


def test_exact_identity_completion_preserves_energy_conflict_and_its_raw_source():
    from backend.tests.test_personal_qualified_facts import GTIN

    a = product("mjölk", 1000, "ml", 20, gtin=GTIN)
    b = product("mjölk", 1000, "ml", 11, store="willys", gtin=GTIN)
    prior = fact(declaration(1100, 250, unit="MLT"))
    result = module.complete_identity_facts(prepared(a, b), {("coop", "mjölk"): prior})
    for f in result.values():
        assert {"nutrition.energy", "nutrition.kcal"} <= set(f.conflicts)
        assert "kcal" not in f.nutrition
        assert prior.field_sources["nutrition.energy"][0] in f.field_sources["nutrition.energy"]
        assert prior.field_sources["nutrition.kcal"][0] in f.field_sources["nutrition.kcal"]


def test_conflicted_donor_cannot_qualify_a_physical_coop_offer():
    from backend.tests.test_coop_nutrition_facts import connect, pair

    donor, target, original = pair()
    raw = declaration(1100, 250)
    raw["id"] = donor.gtin
    conflict = module.project_raw_facts(
        raw, chain="coop", product_id=donor.product_id,
        snapshot_id=original.source_snapshot_id, source_reference="synthetic energy conflict",
        observed_at=original.observed_at,
    )
    assert (target.store_id, target.product_id) not in connect(donor, target, conflict)


def test_exact_supplier_supplement_does_not_clear_prior_energy_conflict():
    from app.services.official_product_facts import supplement_catalog_facts

    from grocery_data.app.services.product_declarations import declarations

    row = next(r for r in declarations() if r.get("parser") == "dabas-base-quantity-v2")
    p = product("synthetic supplement target", row["package_quantity"], row["package_unit"],
                20, gtin=row["gtin"], brand=row["brand"])
    raw = declaration(1100, 250)
    raw["nutrientLinks"] = raw["nutrientLinks"][:2]
    prior = fact(raw, identity=p.product_id)
    result = supplement_catalog_facts([p], {("coop", p.product_id): prior})[("coop", p.product_id)]
    assert "supplier_declaration" in result.field_sources  # the real supplement path ran
    assert {"nutrition.energy", "nutrition.kcal"} <= set(result.conflicts)
    assert prior.field_sources["nutrition.energy"][0] in result.field_sources["nutrition.energy"]


def test_fact_version_binds_policy_and_even_rejected_raw_energy(monkeypatch):
    f = fact(declaration(1100, 250))
    version = module.facts_version({("coop", "mjölk"): f})
    assert version.startswith("retained-catalog-facts-v9-ready-baked-bread:")
    different_raw = fact(declaration(1100, 240))
    assert version != module.facts_version({("coop", "mjölk"): different_raw})
    monkeypatch.setattr(module, "FACTS_VERSION", "test-future-policy")
    assert version != module.facts_version({("coop", "mjölk"): f})

"""Source-bound culinary bread form, separate from nutrition/allergen assurance."""

from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest
from app.models.personal import TasteProfile
from app.services.complete_recipes import product_form_compatible
from app.services.personal_policy import PolicyConflict, check_product
from app.services.personal_source_facts import project_raw_facts

FORMULA = ("VETEmjöl, vatten, sirap, fullkornsRÅGmjöl 10 %, fullkornsVETEmjöl 6 %, "
           "klippta RÅGkärnor, jäst, malt av KORN, rapsolja, VETEgluten, salt, grovt VETEmjöl, "
           "fermenterat VETEmjöl, surdegspulver av VETE, mjölbehandlingsmedel (askorbinsyra).")


def raw_bread():
    # Minimal factual schema reproduction from retained Skogaholm bread. It is
    # not a synthetic replacement for a priced product in acceptance testing.
    return {
        "id": "7312200016945", "name": "Bröd Varsågod Skivad",
        "listOfIngredients": FORMULA,
        "description": "Ett färdig skivat bröd som passar lika bra att rosta som att äta precis som den är.",
        "navCategories": [{"name": "Mörkt & grovt bröd", "superCategories": [
            {"name": "Matbröd", "superCategories": [{"name": "Bröd & Bageri"}]}]}],
    }


def prepared(raw=None, *, name=None, form="as_sold"):
    raw = raw or raw_bread()
    f = project_raw_facts(raw, chain="coop", product_id="bread", snapshot_id="snapshot",
                          source_reference="coop:synthetic-minimal-retained-shape")
    p = SimpleNamespace(name=name or raw["name"], product_id="bread", canonical_name="bröd", category="Bröd & Bageri",
        purchase_terms=None, source_provenance=SimpleNamespace(source_snapshot_id="snapshot"))
    r = SimpleNamespace(design=True, preparation=SimpleNamespace(input_forms={"bröd": form}),
                        ingredients=[SimpleNamespace(name="bröd", product_requirements=None)])
    return r, p, f


def test_explicit_ready_cereal_bread_qualifies_with_a_product_line_name():
    r, p, f = prepared()
    assert product_form_compatible(r, "bröd", p, f)
    assert f.product_classification == ("ready_baked_bread",)
    proof = f.field_sources["product_classification"][0]
    assert proof["product_id"] == "bread" and proof["snapshot_id"] == "snapshot"
    assert proof["raw_fields"]["listOfIngredients"] == FORMULA
    assert proof["raw_fields"]["navCategories"] == raw_bread()["navCategories"]
    assert not f.ingredients_complete and not f.allergens_checked
    assert f.ingredients == (FORMULA,) and not f.nutrition


def test_already_baked_and_optional_toasting_are_not_mandatory_preparation():
    raw = raw_bread()
    raw["description"] = "Färdiggräddat bröd som kan ätas som det är. Gott att rosta."
    r, p, f = prepared(raw)
    assert product_form_compatible(r, "bröd", p, f)


@pytest.mark.parametrize("missing", ["description", "navCategories", "listOfIngredients"])
def test_brand_name_cannot_replace_missing_ready_form_or_composition(missing):
    raw = raw_bread()
    del raw[missing]
    r, p, f = prepared(raw)
    assert not product_form_compatible(r, "bröd", p, f)


@pytest.mark.parametrize("description", [
    "Ett saftigt matbröd.",
    "Färdigskivat bröd som bakas hemma. Efter gräddning kan brödet ätas som det är.",
    "Brödet kan inte ätas som det är.",
    "Brödet måste rostas först och kan sedan ätas som det är.",
    "Brödet kan ätas som det är efter upptining.",
    "Bake-off. Brödet kan ätas som det är efter tillagning.",
    "Brödet är halvgräddat. Brödet kan ätas som det är när det gräddas färdigt.",
])
@pytest.mark.parametrize("name", ["Bröd Varsågod Skivad", "Rostbröd"])
def test_negative_or_conditional_preparation_never_becomes_ready(description, name):
    raw = raw_bread()
    raw.update(description=description, name=name)
    r, p, f = prepared(raw)
    if description == "Ett saftigt matbröd." and name == "Rostbröd":
        # The old narrow explicit whole-label path remains valid. An unknown
        # marketing name cannot use that path without the new source proof.
        assert product_form_compatible(r, "bröd", p, f)
    else:
        assert not product_form_compatible(r, "bröd", p, f)


@pytest.mark.parametrize("name", ["Brödmix", "Bröd Bake-off", "Bröd Fyllda", "Bröd Fyllt", "Bröd Brioche", "Muffins", "Kaffebröd"])
def test_incompatible_bakery_identity_is_not_rehabilitated_by_a_ready_sentence(name):
    raw = raw_bread()
    raw["name"] = name
    r, p, f = prepared(raw)
    assert not product_form_compatible(r, "bröd", p, f)


@pytest.mark.parametrize("addition", ["vitlök", "rosmarin", "chili", "russin", "kanel", "choklad", "ost", "skinka", "okänd ingrediens", "E621"])
@pytest.mark.parametrize("name", ["Bröd Varsågod Skivad", "Rostbröd"])
def test_filling_flavour_sweet_pastry_and_unknown_formula_do_not_qualify(addition, name):
    raw = raw_bread()
    raw.update(name=name, listOfIngredients=FORMULA + ", " + addition)
    r, p, f = prepared(raw)
    assert not product_form_compatible(r, "bröd", p, f)


@pytest.mark.parametrize("formula", ["Socker, vetemjöl, vatten, jäst", "Vetemjöl, vatten", "Vatten, jäst", "Vetemjöl, jäst"])
def test_reviewed_formula_requires_cereal_water_and_fermentation(formula):
    raw = raw_bread()
    raw["listOfIngredients"] = formula
    r, p, f = prepared(raw)
    assert not product_form_compatible(r, "bröd", p, f)


@pytest.mark.parametrize("mismatch", ["product", "snapshot", "source", "name", "formula"])
def test_ready_declaration_cannot_be_reused_for_another_identity(mismatch):
    r, p, f = prepared()
    if mismatch == "product":
        p.product_id = "another-product"
    elif mismatch == "snapshot":
        p.source_provenance.source_snapshot_id = "another-snapshot"
    elif mismatch == "source":
        f = replace(f, source="another-source")
    elif mismatch == "name":
        p.name = "Bröd Smakvariant"
    else:
        f = replace(f, ingredients=("Vetemjöl, vatten, jäst, salt",))
    assert not product_form_compatible(r, "bröd", p, f)


def test_ready_does_not_mean_frozen_raw_dry_or_allergen_safe():
    raw = raw_bread()
    raw["consumerInformationText"] = ["Fryst"]
    r, p, f = prepared(raw)
    assert "frozen" in f.product_classification and "ready_baked_bread" not in f.product_classification
    assert not product_form_compatible(r, "bröd", p, f)
    for form in ("raw_edible", "dry", "cooked_drained"):
        r, p, f = prepared(form=form)
        assert not product_form_compatible(r, "bröd", p, f)
    r, p, f = prepared()
    r.ingredients[0].product_requirements = ("frozen",)
    assert not product_form_compatible(r, "bröd", p, f)


@pytest.mark.parametrize("name", ["Rostbröd", "Bröd Varsågod Skivad"])
@pytest.mark.parametrize("source_field", ["consumerInformationText", "claimReportingInformations"])
def test_explicit_frozen_evidence_vetoes_both_bread_identity_paths(name, source_field):
    raw = raw_bread()
    raw["name"] = name
    raw[source_field] = (["Fryst"] if source_field == "consumerInformationText" else
                         {"description": [{"languageCode": "sv", "value": "Djupfryst"}]})
    r, p, f = prepared(raw)
    assert "frozen" in f.product_classification
    assert "ready_baked_bread" not in f.product_classification
    assert not product_form_compatible(r, "bröd", p, f)


@pytest.mark.parametrize("name", ["Rostbröd", "Bröd Varsågod Skivad"])
@pytest.mark.parametrize("text", ["Halvgräddat", "Gräddas före servering"])
@pytest.mark.parametrize("source_field", ["consumerInformationText", "claimReportingInformations"])
def test_mandatory_preparation_in_each_retained_text_field_vetoes_ready_claim(name, text, source_field):
    raw = raw_bread()
    raw["name"] = name
    raw[source_field] = ([text] if source_field == "consumerInformationText" else
                         {"description": [{"languageCode": "sv", "value": text}]})
    r, p, f = prepared(raw)
    assert "not_ready_plain_bread" in f.product_classification
    assert "ready_baked_bread" not in f.product_classification
    assert not product_form_compatible(r, "bröd", p, f)
    proof = f.field_sources["product_classification"][0]["raw_fields"]
    if source_field == "claimReportingInformations":
        assert proof["claimReportingInformations.description"] == raw[source_field]["description"]
    else:
        assert proof[source_field] == [text]


def test_evidence_is_copied_and_allergy_formula_remains_separate():
    raw = raw_bread()
    raw["listOfIngredients"] += " Kan innehålla spår av SESAM."
    r, p, f = prepared(raw)
    assert product_form_compatible(r, "bröd", p, f)
    assert "SESAM" in f.ingredients[0] and not f.ingredients_complete and not f.allergens_checked
    for profile in (TasteProfile(allergies=["sesam"]), TasteProfile(exclusions=["sirap"])):
        with pytest.raises(PolicyConflict):
            check_product(p, profile, f)
    original = deepcopy(f.field_sources["product_classification"])
    raw["navCategories"][0]["name"] = "Muterat"
    assert f.field_sources["product_classification"] == original

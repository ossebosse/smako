"""Owner decision 2026-11-20: every recipe ingredient must resolve."""
import json
from types import SimpleNamespace

import pytest

from app.services import intake_product_links as L


def product(**fields):
    base = dict(name="Mynta Klass 1", brand="Garant", category="Frukt & grönt", package_quantity=25.0,
                package_unit="g", sale_model="fixed_package", store_id="context:willys:x")
    return SimpleNamespace(**{**base, **fields})


EVIDENCE = dict(name="Mynta Klass 1", brand=None, category="Frukt & grönt", package_quantity=25.0,
                package_unit="g", sale_model="fixed_package", store_id="context:hemkop:y")


def test_a_brand_published_after_review_needs_a_new_review():
    assert not L.same_label(EVIDENCE, product(), global_identity=True)
    assert L.same_label(EVIDENCE, product(brand=None), global_identity=True)
    assert not L.same_label(EVIDENCE, product(brand=None, package_quantity=50.0), global_identity=True)


def test_rereviewed_cured_pork_declarations_are_bound_to_their_text():
    accepted = L.composition_rereviews()["d1c1e7ae3d540a2e848d4338204998251d8ba4ebbf73332c12f0d8b5aa60c83c"]
    fact = SimpleNamespace(ingredients=["Ingredienser: Svenskt sidfläsk (92%), vatten, salt, glykossirap, "
                                        "antioxidationsmedel (E301), konserveringsmedel (E250). Stekfläsk är en "
                                        "rå produkt som ska tillagas före användning."],
                           ingredients_complete=False, ingredient_evidence_kind=None)
    assert L.composition_signature(fact) in accepted
    fact.ingredients = ["Ingredienser: Svenskt sidfläsk (80%), vatten, salt, socker."]
    assert L.composition_signature(fact) not in accepted


def test_a_rereview_whose_text_was_edited_is_refused(tmp_path, monkeypatch):
    doc = json.loads(L.REREVIEW_PATH.read_text(encoding="utf-8"))
    doc["rereviews"][0]["accepted"][0]["ingredients"] = ["Svenskt sidfläsk, salt."]
    path = tmp_path / "rereviews.json"
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(L, "REREVIEW_PATH", path)
    L.composition_rereviews.cache_clear()
    try:
        with pytest.raises(ValueError):
            L.composition_rereviews()
    finally:
        monkeypatch.undo()
        L.composition_rereviews.cache_clear()

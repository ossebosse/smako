"""Missed retailer names must reach review without granting food identity."""
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from app.models import Product
from app.services.intake_product_links import compatible


def test_research_finds_kornris_and_starch_without_approving_substitutions(tmp_path, monkeypatch):
    scripts = Path(__file__).parents[2] / "scripts/recipe_layer"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("existing_store_discovery", scripts / "discover_full_coverage.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    products = [
        Product(product_id="barley", name="Kornris Svenskt", brand="Frebaco Kvarn", canonical_name="kornris", category="Gryn",
                store_id="existing", store_name="Selected store", chain="citygross", price=29.95,
                package_quantity=1000, package_unit="g", usable_quantity=1000, usable_unit="g"),
        Product(product_id="starch", name="Majsstärkelse", brand="Maizena", canonical_name="majsstärkelse", category="Mjöl",
                store_id="existing", store_name="Selected store", chain="hemkop", price=19.50,
                package_quantity=400, package_unit="g", usable_quantity=400, usable_unit="g"),
        Product(product_id="bread", name="Guldkorn", brand="Pågen", canonical_name="guldkorn", category="Bröd",
                store_id="existing", store_name="Selected store", chain="willys", price=24.9,
                package_quantity=500, package_unit="g", usable_quantity=500, usable_unit="g"),
    ]
    before = [p.model_dump(mode="json") for p in products]
    prepared = SimpleNamespace(universe=SimpleNamespace(products=products))
    monkeypatch.setattr(module, "load_reference", lambda _: (prepared, {}, [], [], {"fixture": True}))
    monkeypatch.setattr(module, "verify_release", lambda _: {})
    args = SimpleNamespace(output=tmp_path / "research.json", archive=tmp_path)
    module.main(args)
    groups = json.loads(args.output.read_bytes())["groups"]
    assert [r["product"]["product_id"] for r in groups["pärlkorn"]] == ["barley"]
    assert [r["product"]["product_id"] for r in groups["masa harina"]] == ["starch"]
    assert groups["pärlkorn"][0]["facts"] is None
    assert [p.model_dump(mode="json") for p in products] == before
    # Research names alone never grant the exact issued ingredient contract.
    assert not compatible("intake_all_5eb0592304bd", products[0])
    from app.services.intake_product_links import entries
    masa = next(k for k, row in entries().items() if row["name"] == "masa harina")
    assert not compatible(masa, products[1])

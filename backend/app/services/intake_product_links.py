"""Reviewed exact public product identities; never price or personal approval."""
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType

from app.services.ingredient_normalizer import _search_text

PATH = Path(__file__).parents[1] / "data/ingredients/intake-all-20261026.json"


@lru_cache(maxsize=1)
def entries():
    rows = json.loads(PATH.read_bytes())["ingredients"]
    return {row["requirements"][0].removeprefix("pack:"): row for row in rows}


def compatible(key, product, fact=None):
    row = entries().get(key)
    if row is None:
        return False
    if row["kind"] == "definition_only":
        return declared_definition(row, product, fact)
    if fact is not None and row["kind"] in {"plain", "dry"}:
        composition = " ".join(fact.ingredients).casefold().split("kan innehålla")[0]
        excluded = r"\b(?:salt|socker|olja|smör|sirap|sugar|oil)\b"
        if re.search(excluded, composition) or (row["kind"] == "dry" and "vatten" in composition):
            return False
    # GTIN alone cannot hide a changed label, unit or package. Snapshot, price,
    # source qualification, edible forms and personal facts remain live gates.
    def identity(evidence):
        if evidence.get("gtin"):
            return str(getattr(product, "gtin", "")) == evidence["gtin"]
        provenance = getattr(product, "source_provenance", None)
        return (product.product_id == evidence["product_id"] and product.store_id == evidence["store_id"]
                and provenance is not None and provenance.source_snapshot_id
                == evidence["source_provenance"]["source_snapshot_id"])

    return any(identity(evidence)
               and _search_text(product.name) == _search_text(evidence["name"])
               and _search_text(getattr(product, "brand", None) or "") == _search_text(evidence.get("brand") or "")
               and product.package_unit == evidence["package_unit"]
               and product.package_quantity == evidence["package_quantity"]
               and product.usable_unit == row["unit"]
               and product.usable_quantity == product.package_quantity
               and getattr(product, "quantity_confidence", None) == evidence.get("quantity_confidence", "exact")
               for evidence in row["evidence"])


def declared_definition(row, product, fact):
    """A reviewed definition supplies no product evidence by itself.

    Reuse the ordinary, exact supplier declaration gate. The declaration must
    additionally state this input's usable mass/volume and basis, including
    edible-only or drained contents where required. A label, invented form tag,
    generic nutrition reference or net whole-fruit weight cannot supply that.
    """
    from types import SimpleNamespace

    from app.services.complete_recipes import _supplier_classification

    if (fact is None or getattr(fact, "conflicts", ())
            or product.usable_unit != row["unit"]
            or getattr(product, "quantity_confidence", None) != "exact"):
        return False
    basis = {"raw_edible": "edible_as_sold", "dry": "dry",
             "cooked_drained": "cooked_drained", "preserved_drained": "preserved_drained",
             "as_sold": "as_sold"}[row["form"]]
    for proof in fact.field_sources.get("product_classification", ()):
        if (proof.get("kind") != "manufacturer_culinary_declaration"
                or proof.get("declared_usable_quantity") != product.usable_quantity
                or proof.get("declared_usable_unit") != row["unit"]
                or proof.get("declared_quantity_basis") != basis):
            continue
        view = SimpleNamespace(product_classification=fact.product_classification,
            field_sources={"product_classification": (proof,)})
        if _supplier_classification(product, view, row["required_classification"]):
            return True
    return False


def gross_purchase_input(recipe, name):
    """Gross bone/pod/shell/cob mass has no supported edible nutrition yield."""
    for ingredient in recipe.ingredients:
        if ingredient.canonical_name == name:
            for requirement in ingredient.product_requirements or ():
                row = entries().get(requirement.removeprefix("pack:"), {})
                if row.get("gross_inedible_mass"):
                    return True
    return False


def recipe_product(recipe, name, product, fact=None):
    from app.services.ingredient_normalizer import canonicalize_ingredient_name

    canonical = canonicalize_ingredient_name(name)
    for ingredient in recipe.ingredients:
        if ingredient.canonical_name != canonical:
            continue
        if ingredient_product(canonical, ingredient.form, ingredient.product_requirements or (), product, fact):
            return True
    return False


def ingredient_product(canonical, form, requirements, product, fact=None):
    for requirement in requirements:
        if requirement.startswith("pack:intake_all_"):
            key = requirement.removeprefix("pack:")
            row = entries().get(key)
            if row and row["name"] == canonical and row["form"] == form and compatible(key, product, fact):
                return True
    return False


@lru_cache(maxsize=1)
def reference_version():
    return hashlib.sha256(json.dumps(entries(), ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def search_positions(prepared):
    """Index exact public identifiers once per existing prepared universe.

    Ingredient query spelling does not have to match a retailer's spelling.
    These positions are retrieval only; all request gates run after retrieval.
    """
    def compute():
        gtins, scoped = {}, {}
        for row in entries().values():
            if row["kind"] == "definition_only":
                continue
            for evidence in row["evidence"]:
                if evidence.get("gtin"):
                    gtins.setdefault(evidence["gtin"], set()).add(row["name"])
                else:
                    key = (evidence["store_id"], evidence["product_id"], evidence["source_provenance"]["source_snapshot_id"])
                    scoped.setdefault(key, set()).add(row["name"])
        positions = {}
        for n, product in enumerate(prepared.universe.products):
            provenance = product.source_provenance
            key = (product.store_id, product.product_id, provenance.source_snapshot_id if provenance else None)
            for name in gtins.get(getattr(product, "gtin", None), set()) | scoped.get(key, set()):
                positions.setdefault(name, set()).add(n)
        return MappingProxyType({name: frozenset(values) for name, values in positions.items()})

    return prepared.product_search_cache.get_or_compute("reviewed-intake-exact:" + reference_version(), compute)

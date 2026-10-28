"""Reviewed exact public product identities; never price or personal approval."""
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType

from app.models.product import QuantityConfidence
from app.services.ingredient_normalizer import _search_text

PATH = Path(__file__).parents[1] / "data/ingredients/intake-all-20261026.json"


@lru_cache(maxsize=1)
def entries():
    rows = json.loads(PATH.read_bytes())["ingredients"]
    rows.extend(json.loads(PATH.with_name("recipe-shapes-20261026.json").read_bytes())["ingredients"])
    return {row["requirements"][0].removeprefix("pack:"): row for row in rows}


def compatible(key, product, fact=None):
    row = entries().get(key)
    if row is None:
        return False
    if row["kind"] == "definition_only":
        return reviewed_definition(row, product, fact) or declared_definition(row, product, fact)
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


def composition_signature(fact):
    """Reviewed composition, independent of a catalogue's price generation.

    The caller separately verifies the current fact's product/snapshot binding.
    A new price document or UUID must not invalidate identical food content.
    """
    value = {name: getattr(fact, name, None) for name in (
        "ingredients", "ingredients_complete", "ingredient_evidence_kind")}
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _review_identity(evidence, product, fact):
    provenance = getattr(product, "source_provenance", None)
    original = evidence.get('source_provenance', {})
    article = (getattr(provenance, 'retailer_product_id', None)
               or getattr(fact, 'retailer_product_id', None))
    # Stable, exact food identity; the live price, qualification and request
    # scope remain downstream gates. Unidentified rows retain the snapshot gate.
    if evidence.get('gtin'):
        identified = evidence['gtin'] == getattr(product, 'gtin', None)
    elif evidence.get('retailer_product_id'):
        identified = evidence['retailer_product_id'] == article
    else:
        identified = (evidence['product_id'] == product.product_id and provenance
                      and evidence['source_snapshot_id'] == provenance.source_snapshot_id)
    if (not provenance or not evidence.get("review") or not evidence.get("source_sha256")
            or evidence["store_id"] != product.store_id
            or not identified
            or any(getattr(provenance, field, None) != original.get(field) for field in (
                'source_provider', 'source_channel', 'source_role', 'chain', 'provider_store_id',
                'price_context', 'retailer_id_namespace'))
            or evidence.get("gtin") != getattr(product, "gtin", None)
            or any(getattr(product, field, None) != evidence.get(field)
                   for field in ("name", "brand", "category", "package_quantity", "package_unit", "sale_model"))):
        return False
    if fact is not None:
        from app.services.complete_recipes import identity_conflicts
        from app.services.official_product_facts import _mass_blocking

        if (_mass_blocking(fact.conflicts) or identity_conflicts(fact)
                or fact.source_product_id != product.product_id
                or fact.source_snapshot_id != provenance.source_snapshot_id):
            return False
    if evidence.get("composition_sha256"):
        return bool(fact and fact.source_product_id == product.product_id
                    and fact.source_snapshot_id == provenance.source_snapshot_id
                    and composition_signature(fact) == evidence["composition_sha256"])
    return (evidence.get("identity_basis") == "whole_fresh_produce"
            and not (fact and fact.ingredients))


def reviewed_definition(row, product, fact):
    """Independent identity/form and quantity review; no personal fact approval."""
    for proof in row.get("reviewed_links", ()):
        if not _review_identity(proof, product, fact):
            continue
        quantity = proof["quantity"]
        if (quantity["unit"] == row["unit"] == product.usable_unit
                and quantity["usable_quantity"] == product.usable_quantity
                and quantity["confidence"] == product.quantity_confidence
                and quantity["basis"] == row["form"]):
            return True
    return False


@lru_cache(maxsize=1)
def _quantity_reviews():
    result = {}
    for row in entries().values():
        for proof in row.get("reviewed_links", ()):
            if proof["quantity"].get("method") in {
                "usda_sr28_refuse_v1", "matvaretabellen_edible_fraction_v1",
                "reviewed_declared_drained_mass_v1",
            }:
                key = (('gtin', proof['store_id'], proof['gtin']) if proof.get('gtin')
                       else ('article', proof['store_id'], proof['retailer_product_id'])
                       if proof.get('retailer_product_id') else ('product', proof['store_id'], proof['product_id']))
                result.setdefault(key, []).append(proof)
    return result


def project_reviewed_quantity(product, fact, *, allow_estimates=False, required_unit=None):
    """Project edible mass on a copy; retain gross package mass and source time.

    Declared drained contents are exact; population edible yields need consent.
    Every review retains the exact source product, context and gross package.
    """
    if required_unit != "g":
        return product
    article = (getattr(product.source_provenance, 'retailer_product_id', None)
               or getattr(fact, 'retailer_product_id', None))
    keys = [('gtin', product.store_id, getattr(product, 'gtin', None)),
            ('article', product.store_id, article), ('product', product.store_id, product.product_id)]
    proofs = [proof for key in keys for proof in _quantity_reviews().get(key, ())]
    for proof in proofs:
        q = proof["quantity"]
        if q.get('method') == 'reviewed_declared_drained_mass_v1':
            quantity = q.get('usable_quantity')
            if (_review_identity(proof, product, fact)
                    and product.sale_model == 'fixed_package' and product.package_unit == 'g'
                    and product.purchase_terms is None
                    and q.get('confidence') == 'exact'
                    and q.get('basis') in {'preserved_drained', 'cooked_drained'}
                    and q.get('unit') == 'g' and q.get('declared_net_quantity') == product.package_quantity
                    and isinstance(quantity, (int, float)) and not isinstance(quantity, bool)
                    and 0 < quantity <= product.package_quantity
                    and q.get('source', {}).get('sha256')
                    and q.get('label_source', {}).get('sha256')):
                return product.model_copy(update={'usable_quantity': quantity, 'usable_unit': 'g',
                                                   'quantity_confidence': QuantityConfidence.EXACT})
            continue
        if (not _review_identity(proof, product, fact)
                or not allow_estimates
                or product.sale_model not in {"fixed_package", "variable_weight_package"} or product.package_unit != "g"
                or product.purchase_terms is not None
                or q.get("confidence") != "estimated" or q.get("basis") != "raw_edible"
                or q.get("source", {}).get("sha256") is None
                or not 0 < q.get("edible_fraction", 0) < 1
                or q["usable_quantity"] != round(product.package_quantity * q["edible_fraction"], 8)):
            continue
        return product.model_copy(update={"usable_quantity": q["usable_quantity"], "usable_unit": "g",
                                          "quantity_confidence": "estimated"})
    return product


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


def ingredient_product(canonical, form, requirements, product, fact=None, *, reviewed_only=False):
    for requirement in requirements:
        if requirement.startswith("pack:intake_all_"):
            key = requirement.removeprefix("pack:")
            row = entries().get(key)
            if row and row["name"] == canonical and row["form"] == form:
                if reviewed_only:
                    if row["kind"] == "definition_only" and reviewed_definition(row, product, fact):
                        return True
                elif compatible(key, product, fact):
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
            for evidence in row.get("reviewed_links", ()):
                key = (evidence["store_id"], evidence["product_id"], evidence["source_snapshot_id"])
                scoped.setdefault(key, set()).add(row["name"])
                if evidence.get('gtin'):
                    gtins.setdefault(evidence['gtin'], set()).add(row['name'])
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

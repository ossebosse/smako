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
    rows.extend(json.loads(PATH.with_name("expansion-20261101.json").read_bytes())["ingredients"])
    rows.extend(json.loads(PATH.with_name("expansion-round2-20261101.json").read_bytes())["ingredients"])
    rows.extend(json.loads(PATH.with_name("expansion-round4-20261102.json").read_bytes())["ingredients"])
    return {row["requirements"][0].removeprefix("pack:"): row for row in rows}


# Authored recipes ask for fresh leaves ("raw_edible"); the reviewed registry
# so far only listed frozen chopped packs. A plain fresh bunch of the same herb
# is the same food. Owner decision 2026-11-07: accept it by identity, but only
# on its own exact published package mass (no density, yield or per-piece
# estimate) and only from a fresh-produce shelf, so dried jars stay out.
FRESH_HERBS = {"koriander": r"koriander", "gräslök": r"gräslök"}
FRESH_HERB_DESCRIPTORS = r"(?:eko|ekologisk|ekologiska|svensk|svenska|sverige|klass [12]|krav|färsk|färska|knippe|i knippe|i ask|ask|blad)"
# Cut-herb bunches weigh grams to tens of grams. A larger "package" on a fresh
# herb row is a source quantity we cannot trust as edible leaves.
FRESH_HERB_MAX_GRAMS = 150.0


def fresh_herb_alternative(row, product, fact=None):
    canonical = row["name"]
    if row["kind"] != "frozen_edible" or row["form"] != "raw_edible" or canonical not in FRESH_HERBS:
        return False
    label = " ".join(product.name.casefold().replace(",", " ").split())
    brand = " ".join((getattr(product, "brand", None) or "").casefold().split())
    if brand and brand != canonical and label.startswith(brand + " "):
        label = label[len(brand) + 1:]
    label = re.sub(r"\b\d+(?:[,.]\d+)?\s*(?:g|gr)\b", "", label)
    label = " ".join(label.split())
    descriptor = FRESH_HERB_DESCRIPTORS
    if not re.fullmatch(rf"(?:{descriptor} )*{FRESH_HERBS[canonical]}(?: {descriptor})*", label):
        return False
    category = (getattr(product, "category", None) or "").casefold()
    if not re.search(r"frukt|grönt|grönsak|kryddväxt", category) or re.search(r"fryst|skafferi|torkad", category):
        return False
    composition = " ".join(fact.ingredients).casefold().split("kan innehålla")[0] if fact else ""
    if re.search(r"\b(?:salt|socker|olja|smör|grädde|vitlök)\b", composition):
        return False
    return (product.sale_model == "fixed_package" and product.purchase_terms is None
            and product.package_unit == product.usable_unit == row["unit"] == "g"
            and product.usable_quantity == product.package_quantity
            and 0 < product.usable_quantity <= FRESH_HERB_MAX_GRAMS
            and getattr(product, "quantity_confidence", None) == QuantityConfidence.EXACT)


# Owner decision 2026-11-07: where an authored identity has no supplier
# declaration of edible/drained mass, Smako may plan with the exact published
# package mass instead. This only covers the identities listed here; for fresh
# avocado that mass includes peel and stone, so the recipe gets somewhat less
# flesh than written. Identity, shelf, composition and exact quantity remain.
PACKAGE_WEIGHT_IDENTITIES = {
    # Firm whole avocados for wedges/sticks; diced, frozen and ready-to-eat
    # (soft) fruit are other authored forms.
    ("avokado", "raw_edible"): (
        r"(?:\d+-pack )?(?:avokado|avocado)(?: (?:hass|eko|ekologisk|ekologiska|klass [12]|stor|\d+-pack))*",
        r"frukt|grönt", r"tärn|fryst|guacamole|kräm|mogen|olja", r"\b(?:salt|socker|olja|kryddor)\b|citron|syra"),
    # Cheese without brine: shredded mozzarella is sold and used by its net mass.
    ("mozzarella", "as_sold"): (
        r"(?:riven )?mozzarella(?: (?:riven|familjefavoriter|laktosfri|eko|ekologisk|\d+%))*",
        r"riven ost", r"pizza|sticks|paj|gnocchi|burrata|bufala|\blag\b|mini|kul|boll", r"\b(?:lag|vatten|kryddor|örter|vitlök)\b"),
}


def package_weight_alternative(row, product, fact=None):
    entry = PACKAGE_WEIGHT_IDENTITIES.get((row["name"], row["form"]))
    if entry is None or row["kind"] != "definition_only" or row["unit"] != "g":
        return False
    pattern, shelf, excluded, composition_excluded = entry
    label = " ".join(re.sub(r"\b\d+(?:[,.]\d+)?\s*(?:kg|g)\b", "", product.name.casefold()).split())
    category = (getattr(product, "category", None) or "").casefold()
    if re.search(excluded, label) or re.search(excluded, category) or not re.search(shelf, category + " " + label):
        return False
    if not re.fullmatch(pattern, label):
        return False
    composition = " ".join(fact.ingredients).casefold().split("kan innehålla")[0] if fact else ""
    if re.search(composition_excluded, composition):
        return False
    return (product.sale_model == "fixed_package" and product.purchase_terms is None
            and product.package_unit == product.usable_unit == "g"
            and product.usable_quantity == product.package_quantity and product.usable_quantity > 0
            and getattr(product, "quantity_confidence", None) == QuantityConfidence.EXACT)


def _article(product, fact):
    provenance = getattr(product, "source_provenance", None)
    article = getattr(provenance, "retailer_product_id", None) if provenance else None
    if article:
        return article
    if (fact is not None and provenance is not None
            and getattr(fact, "source_product_id", None) == product.product_id
            and getattr(fact, "source_snapshot_id", None) == provenance.source_snapshot_id):
        return getattr(fact, "retailer_product_id", None) or None
    return None


def compatible(key, product, fact=None):
    row = entries().get(key)
    if row is None:
        return False
    if fresh_herb_alternative(row, product, fact) or package_weight_alternative(row, product, fact):
        return True
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
        if (evidence.get("retailer_product_id") and product.store_id == evidence["store_id"]
                and _article(product, fact) == evidence["retailer_product_id"]):
            # The retailer article id is the global identity that lets a
            # reviewed link survive a new collection. It must come from this
            # product's own provenance or from facts bound to this exact
            # product and snapshot; never from its name.
            return True
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


def reviewed_drained_quantity(canonical, form, requirements, product, fact):
    """A source-bound declared drained mass can also live in the review registry."""
    for requirement in requirements:
        row = entries().get(requirement.removeprefix('pack:'), {})
        if row.get('name') != canonical or row.get('form') != form:
            continue
        for proof in row.get('reviewed_links', ()):
            quantity = proof['quantity']
            if quantity.get('method') == 'reviewed_source_already_drained_mass_v1':
                source, label = quantity.get('source', {}), quantity.get('label_source', {})
                if (quantity.get('form_evidence_location') == 'review_registry'
                        and quantity.get('source_quantity_basis') == 'declared_drained'
                        and _review_identity(proof, product, fact)
                        and product.sale_model == 'fixed_package' and product.purchase_terms is None
                        and product.package_unit == product.usable_unit == quantity['unit'] == 'g'
                        and 0 < quantity.get('declared_drained_quantity', 0)
                        == quantity['usable_quantity'] == product.usable_quantity == product.package_quantity
                        <= quantity.get('declared_net_quantity', 0)
                        and quantity['basis'] == form and form in {'preserved_drained', 'cooked_drained'}
                        and product.quantity_confidence == quantity['confidence'] == 'exact'
                        and all(s.get('sha256') and s.get('url')
                                and s.get('evidence_kind') == 'reviewed_manufacturer_drained_mass'
                                and s.get('declared_net_g') == quantity['declared_net_quantity']
                                and s.get('declared_drained_g') == quantity['declared_drained_quantity']
                                for s in (source, label))):
                    return True
                continue
            if (quantity.get('method') == 'reviewed_declared_drained_mass_v1'
                    and quantity.get('form_evidence_location') == 'review_registry'
                    and _review_identity(proof, product, fact)
                    and product.sale_model == 'fixed_package' and product.purchase_terms is None
                    and product.package_unit == product.usable_unit == quantity['unit'] == 'g'
                    and quantity.get('declared_net_quantity') == product.package_quantity
                    and 0 < quantity['usable_quantity'] == product.usable_quantity <= product.package_quantity
                    and quantity['basis'] == form and form in {'preserved_drained', 'cooked_drained'}
                    and product.quantity_confidence == quantity['confidence'] == 'exact'
                    and quantity.get('source', {}).get('sha256')
                    and quantity.get('label_source', {}).get('sha256')):
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
                "reviewed_declared_piece_count_v1",
            }:
                key = (('gtin', proof['store_id'], proof['gtin']) if proof.get('gtin')
                       else ('article', proof['store_id'], proof['retailer_product_id'])
                       if proof.get('retailer_product_id') else ('product', proof['store_id'], proof['product_id']))
                result.setdefault(key, []).append(proof)
    return result


def project_reviewed_quantity(product, fact, *, allow_estimates=False, required_unit=None):
    """Project reviewed usable quantity; retain gross package and source time.

    Declared drained contents are exact; population edible yields need consent.
    Every review retains the exact source product, context and gross package.
    """
    if required_unit not in {"g", "st"}:
        return product
    article = (getattr(product.source_provenance, 'retailer_product_id', None)
               or getattr(fact, 'retailer_product_id', None))
    keys = [('gtin', product.store_id, getattr(product, 'gtin', None)),
            ('article', product.store_id, article), ('product', product.store_id, product.product_id)]
    proofs = [proof for key in keys for proof in _quantity_reviews().get(key, ())]
    for proof in proofs:
        q = proof["quantity"]
        if q.get('method') == 'reviewed_declared_piece_count_v1':
            quantity = q.get('usable_quantity')
            source = q.get('source', {})
            if (required_unit == 'st' and _review_identity(proof, product, fact)
                    and fact is not None and fact.ingredients_complete
                    and product.sale_model == 'fixed_package' and product.package_unit == 'g'
                    and product.quantity_confidence == 'exact' and product.purchase_terms is None
                    and q.get('confidence') == 'exact' and q.get('basis') == 'as_sold'
                    and q.get('unit') == 'st' and q.get('declared_net_quantity') == product.package_quantity
                    and isinstance(quantity, int) and not isinstance(quantity, bool) and 0 < quantity < 100000
                    and source.get('evidence_kind') == 'reviewed_manufacturer_count_declaration'
                    and source.get('sha256') and source.get('url')
                    and source.get('consumer_gtin') == proof.get('gtin') == product.gtin
                    and product.gtin is not None and source.get('declared_piece_count') == quantity
                    and source.get('declared_net_g') == product.package_quantity):
                return product.model_copy(update={'usable_quantity': quantity, 'usable_unit': 'st',
                                                   'quantity_confidence': QuantityConfidence.EXACT})
            continue
        if required_unit != 'g':
            continue
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


def search_positions(prepared, facts=None):
    """Index exact public identifiers once per existing prepared universe.

    Ingredient query spelling does not have to match a retailer's spelling.
    These positions are retrieval only; all request gates run after retrieval.
    Retailer article ids come from each product's provenance or from facts
    bound to that exact product and snapshot, so reviewed links keep finding
    the same article after a new collection.
    """
    def compute():
        gtins, scoped, articles = {}, {}, {}
        for row in entries().values():
            for evidence in row.get("reviewed_links", ()):
                if evidence.get("retailer_product_id"):
                    articles.setdefault((evidence["store_id"], evidence["retailer_product_id"]), set()).add(row["name"])
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
                    if evidence.get("retailer_product_id"):
                        articles.setdefault((evidence["store_id"], evidence["retailer_product_id"]), set()).add(row["name"])
                    key = (evidence["store_id"], evidence["product_id"], evidence["source_provenance"]["source_snapshot_id"])
                    scoped.setdefault(key, set()).add(row["name"])
        positions = {}
        for n, product in enumerate(prepared.universe.products):
            provenance = product.source_provenance
            key = (product.store_id, product.product_id, provenance.source_snapshot_id if provenance else None)
            names = gtins.get(getattr(product, "gtin", None), set()) | scoped.get(key, set())
            if articles:
                fact = facts.get((product.store_id, product.product_id)) if facts is not None else None
                article = _article(product, fact)
                if article:
                    names = names | articles.get((product.store_id, article), set())
            for name in names:
                positions.setdefault(name, set()).add(n)
        return MappingProxyType({name: frozenset(values) for name, values in positions.items()})

    version = "" if facts is None else ":" + str(getattr(facts, "version", None) or id(facts))
    return prepared.product_search_cache.get_or_compute("reviewed-intake-exact:" + reference_version() + version, compute)

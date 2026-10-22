"""Bind declarations to already qualified offers; never borrow their prices."""

import hashlib
import json
import re

from app.models.product import QuantityConfidence
from app.services.personal_policy import ProductFacts

from grocery_data.app.services.product_declarations import exact_declaration


def declared_facts(products):
    result = {}
    for p in products:
        prov = p.source_provenance
        if (
            (p.purchase_terms and p.purchase_terms.identity_scope == "campaign_group")
            or not prov
            or not prov.source_snapshot_id
            or prov.source_role != "offers"
            or prov.retailer_id_namespace not in {"willys:flyer-document-ad", "lidl:public-product"}
            or not p.offers
            or not all(o.campaign_evidence for o in p.offers)
            or p.usable_unit != p.package_unit
            or p.usable_quantity != p.package_quantity
        ):
            continue
        qualifiers = None
        if p.purchase_terms and p.purchase_terms.purchase_form == "variable_package":
            fat = {
                float(v.replace(",", "."))
                for o in p.offers
                for v in re.findall(
                    r"Fetthalt:\s*(\d+(?:[,.]\d+)?)\s*%", o.description, re.IGNORECASE
                )
            }
            if len(fat) != 1 or p.purchase_terms.approximate_package_g != p.package_quantity:
                continue
            qualifiers = {
                "fat_percent": fat.pop(),
                "package_basis": p.purchase_terms.quantity_basis,
            }
        row = exact_declaration(
            p.name,
            p.brand,
            p.package_quantity,
            p.package_unit,
            gtin=p.gtin,
            identity_qualifiers=qualifiers,
        )
        if not row:
            continue
        basis_unit = row.get('basis_unit', 'g')
        source = {
            "kind": "product_declaration",
            "url": row["source"]["url"],
            "document_sha256": row["source"]["sha256"],
            "retrieved_at": row["source"]["observed_at"],
            "supplier_gtin": row["gtin"],
            "target_gtin": p.gtin,
            "identity_method": "exact_gtin_complete_variant_pack"
            if p.gtin
            else (
                "unique_complete_brand_variant_fat_source_approximate_pack"
                if qualifiers
                else "unique_exact_complete_brand_variant_fixed_pack"
            ),
            "identity_qualifiers": qualifiers,
            "declaration_sha256": hashlib.sha256(
                json.dumps(row, sort_keys=True).encode()
            ).hexdigest(),
            "basis_quantity": 100,
            "basis_unit": basis_unit,
            "preparation": "as_sold",
        }
        result[(p.store_id, p.product_id)] = ProductFacts(
            source="verified_official_product_declaration",
            source_product_id=p.product_id,
            source_snapshot_id=prov.source_snapshot_id,
            retailer_product_id=prov.retailer_product_id,
            ingredients_complete=True,
            ingredient_evidence_kind="product_declaration",
            ingredients=(row["ingredients"],),
            nutrition=row["nutrition"],
            nutrition_unit=basis_unit,
            nutrition_basis=f"Officiell produktdeklaration per 100 {basis_unit} som såld",
            nutrition_preparation="as_sold",
            observed_at=row["source"]["observed_at"],
            field_sources={
                **{f"nutrition.{k}": (source,) for k in row["nutrition"]},
                "ingredients": (source,),
                "nutrition_preparation": (source,),
            },
        )
    return result


def declaration_matches_product(product, fact):
    return fact == declared_facts([product]).get((product.store_id, product.product_id))


def _supplement_named_catalog_facts(products, original):
    """Strict existing name/brand/fixed-pack rule for official catalog facts.

    No GTIN is synthesized and no price, identity or stock field is changed.
    The parser requires linked official identity documents or one manufacturer
    declaration with explicit GS1 identity, complete name/category and pack.
    """
    from dataclasses import replace

    from grocery_data.app.domain.identifiers import InvalidGtinError
    from grocery_data.app.services.product_declarations import declarations

    rows = [r for r in declarations() if r.get("parser") in {"gogreen-linked-product-declaration-v1", "zeinas-explicit-juice-declaration-v1"}
            or (r.get("parser") == "garant-explicit-gs1-declaration-v1"
                and r.get("binding_requirement") == "unique_exact_complete_brand_variant_fixed_pack")]
    image_bound_rows = [r for r in declarations()
                        if r.get("parser") == "supplier-validoo-exact-gtin-v1"]
    result = dict(original)
    for p in products:
        prov = p.source_provenance
        if (not prov or not prov.source_snapshot_id or p.sale_model != "fixed_package"
                or not p.package_quantity or p.package_unit not in {"g", "ml"}
                or (p.purchase_terms and p.purchase_terms.identity_scope != "product")):
            continue
        key = (p.store_id, p.product_id)
        prior = result.get(key)
        row = exact_declaration(p.name, p.brand, p.package_quantity, p.package_unit,
                                gtin=p.gtin, rows=rows)
        image_source = None
        if row is None and prior and image_bound_rows:
            sources = prior.field_sources.get("retailer_image_gtin", ())
            valid = [source for source in sources if source.get("snapshot_id") == prov.source_snapshot_id
                     and source.get("product_id") == p.product_id and source.get("gtin")]
            if len(valid) == 1 and (not p.gtin or p.gtin.zfill(14) == valid[0]["gtin"].zfill(14)):
                image_source = valid[0]
                try:
                    row = exact_declaration(p.name, p.brand, p.package_quantity, p.package_unit,
                                            gtin=image_source["gtin"], rows=image_bound_rows)
                except InvalidGtinError:
                    continue
        if row is None:
            continue
        prior = prior or ProductFacts(source="verified_supplier_catalog_supplement",
            source_product_id=p.product_id, source_snapshot_id=prov.source_snapshot_id)
        basis_unit = row.get('basis_unit', 'g')
        source = {**row["source"], "source": row["source"]["url"],
                  "identity_method": row["binding_requirement"], "supplier_gtin": row["gtin"],
                  "declared_name": row["name"], "declared_brand": row["brand"],
                  "identity_source": row["identity_source"], "kind": "supplier_declaration",
                  "bound_product_id": p.product_id, "bound_store_id": p.store_id,
                  "bound_snapshot_id": prov.source_snapshot_id,
                  "source_package_quantity": p.package_quantity, "source_package_unit": p.package_unit,
                  "basis_unit": basis_unit, "preparation": "as_sold", "original_nutrition": row["nutrition"]}
        if image_source:
            source["retailer_image_identity"] = image_source
        fields = dict(prior.field_sources)
        fields["supplier_declaration"] = (*fields.get("supplier_declaration", ()), source)
        changes = {}
        if prior.nutrition and (prior.nutrition_unit != basis_unit or any(
                prior.nutrition[k] != row["nutrition"][k] for k in prior.nutrition.keys() & row["nutrition"].keys())):
            changes["conflicts"] = (*prior.conflicts, "supplier_nutrition_conflict")
            fields["supplier_nutrition_conflict"] = (source,)
        else:
            changes.update(nutrition=dict(row["nutrition"]), nutrition_unit=basis_unit,
                           nutrition_basis=f"Officiell produktdeklaration per 100 {basis_unit} som såld")
            for key_name in row["nutrition"]:
                fields["nutrition." + key_name] = (*fields.get("nutrition." + key_name, ()), source)
        if not prior.ingredients:
            changes.update(ingredients=(row["ingredients"],), ingredients_complete=True,
                           ingredient_evidence_kind="product_declaration")
            fields["ingredients"] = (source,)
        if row.get("culinary_forms"):
            changes["product_classification"] = tuple(dict.fromkeys((*prior.product_classification, *row["culinary_forms"])))
            fields["product_classification"] = (*fields.get("product_classification", ()), source)
        result[(p.store_id, p.product_id)] = replace(prior, **changes, field_sources=fields)
    return result


def _supplement_culinary_attributes(products, original):
    """Attach source-bound attributes without replacing any prior declaration.

    This uses the existing complete brand/variant/fixed-package identity rule;
    a culinary document cannot certify nutrients, allergens or campaign scope.
    """
    from dataclasses import replace

    from grocery_data.app.services.product_declarations import culinary_declarations

    rows = culinary_declarations()
    result = dict(original)
    for p in products:
        prior = result.get((p.store_id, p.product_id))
        prov = p.source_provenance
        if (prior is None or prior.conflicts or not prov or not prov.source_snapshot_id
                or p.sale_model != 'fixed_package'
                or (p.purchase_terms and p.purchase_terms.identity_scope != 'product')):
            continue
        # A matching GTIN is not needed for a unique complete named pack, but
        # no absent supplier GTIN may veto the retailer's independent GTIN.
        row = exact_declaration(p.name, p.brand, p.package_quantity, p.package_unit, rows=rows)
        if row is None or row.get('parser') != 'santa-maria-explicit-culinary-v1':
            continue
        source = {**row['source'], 'source': row['source']['url'],
            'kind': 'manufacturer_culinary_declaration', 'identity_method': row['binding_requirement'],
            'declared_name': row['name'], 'declared_brand': row['brand'],
            'declared_forms': row['culinary_forms'], 'raw_fields': row['evidence'],
            'bound_product_id': p.product_id, 'bound_store_id': p.store_id,
            'bound_snapshot_id': prov.source_snapshot_id,
            'source_package_quantity': p.package_quantity, 'source_package_unit': p.package_unit}
        fields = dict(prior.field_sources)
        fields['product_classification'] = (*fields.get('product_classification', ()), source)
        result[(p.store_id, p.product_id)] = replace(prior, field_sources=fields,
            product_classification=tuple(dict.fromkeys((*prior.product_classification, *row['culinary_forms']))))
    return result


def _retained_supplier_identity(product, fact):
    """A retained Axfood image key corroborates identity, never price or mass.

    Keep the original label/brand/display quantity bound to the same snapshot.
    Package compatibility is checked independently against the supplier below.
    """
    prov = product.source_provenance
    if (not fact or not prov or product.chain not in {"willys", "hemkop"}
            or prov.source_provider != 'own' or prov.source_channel != 'catalog'
            or prov.store_id != product.store_id
            or product.sale_model != "fixed_package"
            or fact.source_product_id != product.product_id
            or fact.source_snapshot_id != prov.source_snapshot_id):
        return None
    sources = fact.field_sources.get("retailer_image_gtin", ())
    if len(sources) != 1:
        return None
    source = sources[0]
    raw = source.get("raw_fields", {})
    if (source.get("method") != "checksum_valid_exact_retained_product_image_key"
            or source.get("source") != fact.source
            or source.get("product_id") != product.product_id
            or source.get("snapshot_id") != prov.source_snapshot_id
            or raw.get("name") != product.name or raw.get("manufacturer") != product.brand):
        return None
    return source


def _supplier_package_matches(product, row, image_source):
    exact_package = (row['package_quantity'], row['package_unit']) == (product.package_quantity, product.package_unit)
    if not image_source:
        return exact_package
    label = image_source.get('raw_fields', {}).get('displayVolume')
    amount = re.fullmatch(r'(\d+(?:[.,]\d+)?)\s*(kg|g|ml|cl|dl|l)', label or '')
    if amount:
        factor, unit = {'kg': (1000, 'g'), 'g': (1, 'g'), 'ml': (1, 'ml'),
                        'cl': (10, 'ml'), 'dl': (100, 'ml'), 'l': (1000, 'ml')}[amount[2]]
        return (exact_package and unit == product.package_unit
                and float(amount[1].replace(',', '.')) * factor == product.package_quantity)
    # Existing Axfood rows project 380/230g to the stated 230g. Recover the
    # supplier link only when BOTH printed quantities agree with that exact
    # supplier's net and drained masses. Never interpret a slash alone as proof.
    if row.get('comparison_basis') != 'Per avrunnen vikt':
        return False
    match = re.fullmatch(r'(\d+(?:[.,]\d+)?)/(\d+(?:[.,]\d+)?)\s*g', label or '')
    return bool(match and row['package_unit'] == row['net_unit'] == row['comparison_unit'] == product.package_unit == 'g'
                and float(match[1].replace(',', '.')) == row['package_quantity'] == row['net_quantity']
                and float(match[2].replace(',', '.')) == row['comparison_quantity']
                and product.package_quantity in {row['package_quantity'], row['comparison_quantity']}
                and 0 < row['comparison_quantity'] < row['net_quantity'])


def supplement_catalog_facts(products, original):
    """Exact-GTIN supplier fields, retaining every conflicting declaration.

    Prices, campaigns and allergens are untouched. A drained quantity does not
    certify the nutrient table's draining basis. Gross transport weight is never
    a purchasable/edible quantity.
    """
    from dataclasses import replace

    from grocery_data.app.domain.identifiers import InvalidGtinError, normalize_gtin
    from grocery_data.app.services.product_declarations import declarations, identity_text

    rows = [r for r in declarations() if r.get("parser") in {
        "dabas-consumer-quantity-v1", "dabas-base-quantity-v2",
        "garant-explicit-gs1-declaration-v1"}]
    result = _supplement_culinary_attributes(products, _supplement_named_catalog_facts(products, original))
    for p in products:
        if not p.source_provenance or (p.purchase_terms and p.purchase_terms.identity_scope != "product"):
            continue
        key = (p.store_id, p.product_id)
        image_source = _retained_supplier_identity(p, result.get(key))
        identity = p.gtin or (image_source or {}).get('gtin')
        if not identity:
            continue
        try:
            gtin = normalize_gtin(identity).normalized_gtin
            if image_source and normalize_gtin(image_source['gtin']).normalized_gtin != gtin:
                continue
        except InvalidGtinError:
            continue
        matches = [r for r in rows if r['gtin'].zfill(14) == gtin.zfill(14)
                   and identity_text(r['brand']) == identity_text(p.brand or '')
                   and _supplier_package_matches(p, r, image_source)]
        if len(matches) != 1:
            continue
        row = matches[0]
        prior = result.get(key) or ProductFacts(source='verified_supplier_catalog_supplement',
            source_product_id=p.product_id, source_snapshot_id=p.source_provenance.source_snapshot_id)
        source = {**row['source'], 'source': row['source']['url'], 'gtin': gtin, 'document_version': row.get('document_version'),
                  'identity_method': 'exact_checksum_gtin_brand_fixed_package',
                  'kind': 'supplier_declaration', 'basis_unit': row['basis_unit'],
                  'original_nutrition': row['nutrition'], 'preparation': row['preparation'],
                  'bound_product_id': p.product_id, 'bound_store_id': p.store_id,
                  'bound_snapshot_id': p.source_provenance.source_snapshot_id,
                  'source_package_quantity': p.package_quantity, 'source_package_unit': p.package_unit}
        if image_source:
            source['retailer_image_identity'] = image_source
            source['supplier_package_quantity'] = row['package_quantity']
            source['supplier_package_unit'] = row['package_unit']
        fields = dict(prior.field_sources)
        fields['supplier_declaration'] = (*fields.get('supplier_declaration', ()), source)
        changes = {}
        nutrition = dict(row['nutrition'])
        unit = row['basis_unit']
        # Two explicit quantities for THIS consumer package support arithmetic;
        # neither a universal density nor the logistics gross weight is used.
        if row['package_unit'] == 'ml' and row.get('net_unit') == 'g':
            ratio = row['package_quantity'] / row['net_quantity']
            if unit == 'ml':
                nutrition = {k: v * ratio for k, v in nutrition.items()}
                unit = 'g'
                source = {**source, 'operation': 'declared_per_100_ml * source_package_ml / source_net_g',
                          'package_ml': row['package_quantity'], 'net_g': row['net_quantity']}
            fields['usable_quantity'] = ({**source, 'quantity': row['net_quantity'],
                                          'unit': 'g', 'basis': 'source_net_mass'},)
        elif row.get('comparison_basis') == 'Per avrunnen vikt':
            if row['comparison_unit'] != 'g' or not 0 < row['comparison_quantity'] <= row['net_quantity']:
                continue
            fields['usable_quantity'] = ({**source, 'quantity': row['comparison_quantity'],
                                          'unit': 'g', 'basis': 'drained'},)
            changes['nutrition_preparation'] = 'draining_unspecified'
        overlap_conflict = bool(prior.nutrition and (
            prior.nutrition_unit != unit or any(prior.nutrition[k] != nutrition[k]
                for k in prior.nutrition.keys() & nutrition.keys())))
        # A later official table never silently replaces a contradictory one.
        # The offline importer binds these to the exact complete product and pack.
        contradictions = [r for r in row.get('corroborating_declarations', ())
            if (r['basis_unit'] != row['basis_unit'] or any(
                r['nutrition'][k] != row['nutrition'][k]
                for k in r['nutrition'].keys() & row['nutrition'].keys()))]
        if overlap_conflict or contradictions:
            changes['conflicts'] = (*prior.conflicts, 'supplier_nutrition_conflict')
            fields['supplier_nutrition_conflict'] = (source, *(
                {**source, **r['source'], 'source': r['source']['url'],
                 'identity_method': r['identity_method'], 'identity_source': r['identity_source'],
                 'original_nutrition': r['nutrition'], 'basis_unit': r['basis_unit']}
                for r in contradictions))
        else:
            changes.update(nutrition=nutrition, nutrition_unit=unit,
                           nutrition_basis=f"Leverantörsdeklaration per 100 {unit}; se dokumenterad mängdgrund")
            for k in nutrition:
                fields['nutrition.' + k] = (*fields.get('nutrition.' + k, ()), source)
        if not prior.ingredients and row['ingredients']:
            changes.update(ingredients=(row['ingredients'],), ingredients_complete=True,
                           ingredient_evidence_kind='product_declaration')
            fields['ingredients'] = (source,)
        result[key] = replace(prior, **changes, field_sources=fields)
    return shell_egg_quantity_proofs(products, result)


# Owner decisions 2026-10-17 and 2026-10-22: every pack of whole shell eggs
# counts. M and L use the class mid-weight with shell (58 g and 68 g) minus
# about 12 % shell. S (under 53 g) uses 48 g with shell. XL uses the L weight
# and a pack without a size class the S weight: lower bounds, so a recipe is
# never left short of egg.
EGG_STANDARD_EDIBLE_G = {'s': 42.0, 'm': 51.0, 'l': 60.0, 'xl': 60.0}
_EGG_CLASS_WORDS = {'small': 's', 's': 's', 'medium': 'm', 'm': 'm', 'large': 'l', 'l': 'l',
                    'x-large': 'xl', 'xl': 'xl'}


_PLAIN_EGG_WORDS = frozenset({'ingredienser', 'ingrediens', 'krav', 'ekologisk', 'ekologiska', 'ekologiskt',
                              'ägg', 'hönsägg', 'från', 'frigående', 'höns', 'inomhus', 'utomhus', 'svenska',
                              'svenskt', 'sverige', 'av'})
# Whole-egg words in shelf names. Compounds ending in "ägg" are listed
# explicitly: underlägg, fläsklägg and chokladägg also end in "ägg".
_SHELL_EGG_NAMES = frozenset({'ägg', 'hönsägg', 'skåneägg', 'brunchägg', 'utehönsägg', 'västgötaägg'})
_SHELL_EGG_DESCRIPTORS = frozenset({
    'p', 'st', 'pack', 'pac', 'x', 'small', 'medium', 'large', 'x-large', 's', 'm', 'l', 'xl',
    'frigående', 'inomhus', 'utomhus', 'inne', 'ute', 'eko', 'ekologisk', 'ekologiska', 'ekologiskt',
    'produktion', 'krav', 'klimat', 'svenska', 'svenskt', 'sverige', 'skåne', 'skånska',
    'bruna', 'stora', 'små', 'familj', 'familjens', 'färska', 'från', 'höns'})


def is_plain_shell_egg(name, brand=None, ingredients=()):
    """True for a pack of whole raw shell eggs, never a product made from egg.

    Every word in the shelf name must be an egg word, a pack count, a size
    class, a production method or a word of the published brand. A declared
    ingredient list may only name plain egg.
    """
    text = name.casefold().replace('/', ' ').replace(',', ' ')
    text = re.sub(r'\d+(?:[,.]\d+)?', ' ', text)
    words = re.findall(r'x-large|[^\W\d_]+', text)
    brand_words = set(re.findall(r'[^\W\d_]+', (brand or '').casefold()))
    if not words or not set(words) & _SHELL_EGG_NAMES:
        return False
    if any(w not in _SHELL_EGG_NAMES | _SHELL_EGG_DESCRIPTORS | brand_words for w in words):
        return False
    declared = re.split(r'kan innehålla', ' '.join(ingredients).casefold())[0]
    return set(re.findall(r'[a-zåäö]+', declared)) <= _PLAIN_EGG_WORDS


def egg_standard_weight(name):
    """Standard edible weight per egg (the smallest stated class wins)."""
    words = re.findall(r'x-large|[a-z]+', name.casefold().replace('/', ' '))
    classes = {_EGG_CLASS_WORDS[w] for w in words if w in _EGG_CLASS_WORDS}
    return min(EGG_STANDARD_EDIBLE_G[c] for c in classes or {'s'})


def _mass_blocking(conflicts):
    """Conflicts that make a usable-mass proof unsafe; nutrient ones do not."""
    return {c for c in conflicts if c != 'supplier_nutrition_conflict' and not c.startswith('nutrition')}


def shell_egg_quantity_proofs(products, result):
    """Usable-mass proofs for plain shell eggs.

    A source-stated package mass gives the population estimate (estimated mode
    only). A counted pack gets count x the standard edible egg weight of its
    size class, or of the smallest class when the name states none.
    """
    from dataclasses import replace
    from pathlib import Path
    reference = json.loads((Path(__file__).parents[1] / 'data/nutrition/edible-yield-references.json').read_bytes())['shell_egg']
    for p in products:
        key = (p.store_id, p.product_id)
        # A shelf without any declaration still sells whole eggs; the mass
        # proof then stands alone and claims nothing about ingredients.
        fact = result.get(key) or (ProductFacts(
            source=f'{p.chain}:shelf_name', source_product_id=p.product_id,
            source_snapshot_id=p.source_provenance.source_snapshot_id) if p.source_provenance else None)
        if (not fact or not p.source_provenance or _mass_blocking(fact.conflicts) or p.package_unit != 'st'
                or not p.package_quantity or p.sale_model != 'fixed_package'
                # Production-method words describe the egg itself ("ÄGG från
                # frigående höns inomhus"); any other word means a composite.
                or not is_plain_shell_egg(p.name, getattr(p, 'brand', None), fact.ingredients)):
            continue
        weight = egg_standard_weight(p.name)
        proof = {'basis': 'standard_egg_weight', 'unit': 'g',
                 'quantity': round(p.package_quantity * weight, 1),
                 'eggs': p.package_quantity, 'edible_g_per_egg': weight,
                 'source_snapshot_id': p.source_provenance.source_snapshot_id,
                 'bound_product_id': p.product_id, 'bound_store_id': p.store_id,
                 'identity_method': 'plain_shell_egg_count_standard_weight'}
        result[key] = replace(fact, field_sources={**fact.field_sources, 'usable_quantity': (proof,)})
    for p in products:
        key = (p.store_id, p.product_id)
        fact = result.get(key)
        if (not fact or not p.source_provenance or _mass_blocking(fact.conflicts) or p.package_unit != 'g' or not p.package_quantity
                or p.sale_model != 'fixed_package' or not fact.ingredients
                or not is_plain_shell_egg(p.name, getattr(p, 'brand', None), fact.ingredients)):
            continue
        proof = {**reference, 'basis': 'estimated_edible', 'unit': 'g',
                 'quantity': p.package_quantity * reference['edible_fraction'],
                 'purchased_shell_mass_g': p.package_quantity,
                 'source_snapshot_id': p.source_provenance.source_snapshot_id,
                 'identity_method': 'plain_shell_egg_source_mass_documented_edible_estimate'}
        result[key] = replace(fact, field_sources={**fact.field_sources, 'usable_quantity': (proof,)})
    return result


def project_usable_quantity(product, fact, *, allow_estimates=False, required_unit=None):
    """Request-local quantity projection; immutable source price stays intact."""
    if required_unit is not None and required_unit != "g":
        return product
    if not fact or not product.source_provenance:
        return product
    # A nutrient disagreement cannot invalidate independently sourced drained
    # mass. Other/unknown conflicts remain blocking; nutrition keeps its guard.
    if _mass_blocking(fact.conflicts):
        return product
    proofs = fact.field_sources.get('usable_quantity', ())
    if len(proofs) != 1:
        return product
    proof = proofs[0]
    quantity = proof.get('quantity')
    if (allow_estimates and proof.get('basis') == 'estimated_edible'
            and proof.get('identity_method') == 'plain_shell_egg_source_mass_documented_edible_estimate'
            and proof.get('purchased_shell_mass_g') == product.package_quantity
            and proof.get('source_snapshot_id') == product.source_provenance.source_snapshot_id
            and proof.get('sha256') and proof.get('unit') == 'g'
            and isinstance(quantity, (int, float)) and 0 < quantity < product.package_quantity):
        return product.model_copy(update={'usable_quantity': quantity, 'usable_unit': 'g',
                                           'quantity_confidence': QuantityConfidence.ESTIMATED})
    if (proof.get('identity_method') == 'plain_shell_egg_count_standard_weight'
            and proof.get('basis') == 'standard_egg_weight' and proof.get('unit') == 'g'
            and proof.get('bound_product_id') == product.product_id
            and proof.get('bound_store_id') == product.store_id
            and proof.get('source_snapshot_id') == product.source_provenance.source_snapshot_id
            and product.package_unit == 'st' and proof.get('eggs') == product.package_quantity
            and isinstance(quantity, (int, float)) and 0 < quantity < 100000):
        return product.model_copy(update={'usable_quantity': quantity, 'usable_unit': 'g',
                                           'quantity_confidence': QuantityConfidence.DERIVED})
    if (proof.get('identity_method') != 'exact_checksum_gtin_brand_fixed_package'
            or proof.get('bound_product_id') != product.product_id
            or proof.get('bound_store_id') != product.store_id
            or proof.get('bound_snapshot_id') != product.source_provenance.source_snapshot_id
            or proof.get('source_package_quantity') != product.package_quantity
            or proof.get('source_package_unit') != product.package_unit
            or proof.get('basis') not in {'drained', 'source_net_mass'}
            or proof.get('unit') != 'g' or not isinstance(quantity, (int, float))
            or isinstance(quantity, bool) or not 0 < quantity < 100000
            or not proof.get('sha256')):
        return product
    return product.model_copy(update={'usable_quantity': quantity, 'usable_unit': 'g'})


def facts_for_quantity_unit(product, fact, unit):
    """Keep native volume use available alongside a source-proven mass projection."""
    from dataclasses import replace

    if not fact or fact.conflicts or unit != 'ml' or fact.nutrition_unit != 'g':
        return fact
    projected = project_usable_quantity(product, fact)
    proof = fact.field_sources.get('usable_quantity', ())
    if (projected == product or product.package_unit != 'ml' or len(proof) != 1
            or proof[0].get('basis') != 'source_net_mass'):
        return fact
    mass_per_volume = projected.usable_quantity / product.package_quantity
    values = {k: v * mass_per_volume for k, v in fact.nutrition.items()}
    source = {**proof[0], 'operation': 'per_100_g * source_net_g / source_package_ml',
              'requested_basis_unit': 'ml'}
    return replace(fact, nutrition=values, nutrition_unit='ml',
                   nutrition_basis='Supplier quantities for this exact package; per 100 ml',
                   field_sources={**fact.field_sources,
                                  **{'nutrition.'+k: (*fact.field_sources.get('nutrition.'+k, ()), source)
                                     for k in values}})

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
            "basis_unit": "g",
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
            nutrition_unit="g",
            nutrition_basis="Officiell produktdeklaration per 100 g som såld",
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
    The parser requires two official documents for the same unique linked item.
    """
    from dataclasses import replace

    from grocery_data.app.services.product_declarations import declarations

    rows = [r for r in declarations() if r.get("parser") == "gogreen-linked-product-declaration-v1"
            or (r.get("parser") == "garant-explicit-gs1-declaration-v1"
                and r.get("binding_requirement") == "unique_exact_complete_brand_variant_fixed_pack")]
    result = dict(original)
    for p in products:
        prov = p.source_provenance
        if (not prov or not prov.source_snapshot_id or p.sale_model != "fixed_package"
                or not p.package_quantity or p.package_unit != "g"
                or (p.purchase_terms and p.purchase_terms.identity_scope != "product")):
            continue
        row = exact_declaration(p.name, p.brand, p.package_quantity, p.package_unit,
                                gtin=p.gtin, rows=rows)
        if row is None:
            continue
        key = (p.store_id, p.product_id)
        prior = result.get(key) or ProductFacts(source="verified_supplier_catalog_supplement",
            source_product_id=p.product_id, source_snapshot_id=prov.source_snapshot_id)
        source = {**row["source"], "source": row["source"]["url"],
                  "identity_method": row["binding_requirement"], "supplier_gtin": row["gtin"],
                  "declared_name": row["name"], "declared_brand": row["brand"],
                  "identity_source": row["identity_source"], "kind": "supplier_declaration",
                  "bound_product_id": p.product_id, "bound_store_id": p.store_id,
                  "bound_snapshot_id": prov.source_snapshot_id,
                  "source_package_quantity": p.package_quantity, "source_package_unit": p.package_unit,
                  "basis_unit": "g", "preparation": "as_sold", "original_nutrition": row["nutrition"]}
        fields = dict(prior.field_sources)
        fields["supplier_declaration"] = (*fields.get("supplier_declaration", ()), source)
        changes = {}
        if prior.nutrition and (prior.nutrition_unit != "g" or any(
                prior.nutrition[k] != row["nutrition"][k] for k in prior.nutrition.keys() & row["nutrition"].keys())):
            changes["conflicts"] = (*prior.conflicts, "supplier_nutrition_conflict")
            fields["supplier_nutrition_conflict"] = (source,)
        else:
            changes.update(nutrition=dict(row["nutrition"]), nutrition_unit="g",
                           nutrition_basis="Officiell produktdeklaration per 100 g som såld")
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


def supplement_catalog_facts(products, original):
    """Exact-GTIN supplier fields, retaining every conflicting declaration.

    Prices, campaigns and allergens are untouched. A drained quantity does not
    certify the nutrient table's draining basis. Gross transport weight is never
    a purchasable/edible quantity.
    """
    from dataclasses import replace

    from grocery_data.app.domain.identifiers import InvalidGtinError, normalize_gtin
    from grocery_data.app.services.product_declarations import declarations, identity_text

    rows = [r for r in declarations() if r.get("parser") in {"dabas-consumer-quantity-v1", "dabas-base-quantity-v2"}]
    result = _supplement_culinary_attributes(products, _supplement_named_catalog_facts(products, original))
    for p in products:
        if not p.gtin or not p.source_provenance or (p.purchase_terms and p.purchase_terms.identity_scope != "product"):
            continue
        try:
            gtin = normalize_gtin(p.gtin).normalized_gtin
        except InvalidGtinError:
            continue
        matches = [r for r in rows if r['gtin'].zfill(14) == gtin.zfill(14)
                   and identity_text(r['brand']) == identity_text(p.brand or '')
                   and (r['package_quantity'], r['package_unit']) == (p.package_quantity, p.package_unit)]
        if len(matches) != 1:
            continue
        row = matches[0]
        key = (p.store_id, p.product_id)
        prior = result.get(key) or ProductFacts(source='verified_supplier_catalog_supplement',
            source_product_id=p.product_id, source_snapshot_id=p.source_provenance.source_snapshot_id)
        source = {**row['source'], 'source': row['source']['url'], 'gtin': gtin, 'document_version': row['document_version'],
                  'identity_method': 'exact_checksum_gtin_brand_fixed_package',
                  'kind': 'supplier_declaration', 'basis_unit': row['basis_unit'],
                  'original_nutrition': row['nutrition'], 'preparation': row['preparation'],
                  'bound_product_id': p.product_id, 'bound_store_id': p.store_id,
                  'bound_snapshot_id': p.source_provenance.source_snapshot_id,
                  'source_package_quantity': p.package_quantity, 'source_package_unit': p.package_unit}
        fields = dict(prior.field_sources)
        fields['supplier_declaration'] = (*fields.get('supplier_declaration', ()), source)
        changes = {}
        nutrition = dict(row['nutrition'])
        unit = row['basis_unit']
        # Two explicit quantities for THIS consumer package support arithmetic;
        # neither a universal density nor the logistics gross weight is used.
        if row['package_unit'] == 'ml' and row['net_unit'] == 'g':
            ratio = row['package_quantity'] / row['net_quantity']
            if unit == 'ml':
                nutrition = {k: v * ratio for k, v in nutrition.items()}
                unit = 'g'
                source = {**source, 'operation': 'declared_per_100_ml * source_package_ml / source_net_g',
                          'package_ml': row['package_quantity'], 'net_g': row['net_quantity']}
            fields['usable_quantity'] = ({**source, 'quantity': row['net_quantity'],
                                          'unit': 'g', 'basis': 'source_net_mass'},)
        elif row['comparison_basis'] == 'Per avrunnen vikt':
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
            changes['ingredients'] = (row['ingredients'],)
            fields['ingredients'] = (source,)
        result[key] = replace(prior, **changes, field_sources=fields)
    # A population estimate is separate from supplier declarations. Only a
    # source-stated shell-egg package mass can use it; counts never become grams.
    from pathlib import Path
    reference = json.loads((Path(__file__).parents[1] / 'data/nutrition/edible-yield-references.json').read_bytes())['shell_egg']
    for p in products:
        key = (p.store_id, p.product_id)
        fact = result.get(key)
        if (not fact or not p.source_provenance or fact.conflicts or p.package_unit != 'g' or not p.package_quantity
                or p.sale_model != 'fixed_package'
                or not re.match(r'^(?:ägg|skåneägg|bruna ägg)\b', p.name.casefold())
                or re.search(r'kokt|pulver|ersättning|vita|choklad', p.name.casefold())):
            continue
        words = set(re.findall(r'[a-zåäö]+', ' '.join(fact.ingredients).casefold()))
        if not words or not words <= {'ingredienser', 'krav', 'ekologiska', 'ägg'}:
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
    if set(fact.conflicts) - {'supplier_nutrition_conflict'}:
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

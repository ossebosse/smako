"""Exact declaration classification, independent of retailer prices and campaigns."""
import re


def document_classification(text):
    # Published Dabas classification breadcrumb, not prose mentioning an ingredient.
    match = re.search(r'Dabas produktklassificering\s+\d+\s*/\s*(.+?)(?=\s+(?:Märkning|Förvaring|Ursprung|Näringsvärde)\b)', text)
    return tuple(part.strip() for part in match.group(1).split('--')) if match else ()


def declaration_food_class(product, fact):
    if not fact or not fact.product_classification or not fact.field_sources.get('product_classification'):
        return None
    if product.purchase_terms and product.purchase_terms.identity_scope != 'product':
        return None
    # Recheck the authoritative variant-bound declaration, including its hash.
    if fact.source == 'verified_lidl_supplier_declaration':
        from app.services.lidl_product_facts import declaration_matches_product
    elif fact.source == 'verified_official_product_declaration':
        from app.services.official_product_facts import declaration_matches_product
    else:
        return None
    if not declaration_matches_product(product, fact):
        return None
    # A food-class rule, never a brand/product/campaign allowlist. Only the
    # explicit Matbröd branch establishes generic bread; pastry/cake does not.
    if 'Matbröd' in fact.product_classification:
        return 'bröd'
    return None


def project_declared_class(product, food_class):
    projections = {
        "bröd": {"canonical_food": "brod", "food_family": "grain", "product_role": "bread",
                 "product_form": "ready", "semantic_confidence": "exact"},
    }
    return product.model_copy(update=projections[food_class])

"""Edition-independent exact compound identity from official PDF text.

No product registry and no fuzzy join. Typography delimits the complete branded
caption; a unique structured identity, literal package, price typography,
comparison arithmetic, page dates and local conditions must agree separately.
Unsupported captions remain outside purchase import.
"""
from __future__ import annotations

import hashlib
import html
import re
from decimal import Decimal

import pymupdf

METHOD = "lidl-exact-compound-document-text-v4"


def normalized(text):
    # Publisher line wrapping, apostrophe glyphs and whitespace only. No fuzzy
    # synonym, token subset, word-order or price-based identity matching.
    text = re.sub(r"-\s*\n\s*", "", text)
    return re.sub(r"\s+", "", text.casefold().translate(str.maketrans({"‘": "'", "’": "'"})))


def national_metadata(publication, pdf=None):
    flyer = publication.json_payload()["flyer"]
    national = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m[1], 16)), flyer.get("subcategory", ""))
    if (publication.http_status != 200
            or publication.url != "https://endpoints.leaflets.schwarz/v4/flyer"
            or publication.query.get('flyer_identifier') != flyer.get('id')
            or not flyer.get("isActive") or flyer.get("countryCode") != "SE"
            or flyer.get("status") != "current"
            or national != "Reklamblad för samtliga butiker i Sverige"
            or not flyer.get("pdfUrl", "").startswith("https://assets.leaflets.schwarz/leaflets/pdfs/")):
        raise ValueError("current_national_document_scope_unverified")
    return {"publication_id": flyer["id"], "pdf_url": flyer["pdfUrl"],
            "pdf_sha256": hashlib.sha256(pdf).hexdigest() if pdf is not None else None,
            "products": [], "offer_start": flyer["offerStartDate"], "offer_end": flyer["offerEndDate"]}


def qualify(publication, pdf, products, source_rows):
    metadata = national_metadata(publication, pdf)
    proofs, decisions = [], []
    with pymupdf.open(stream=pdf, filetype="pdf") as document:
        for page in document:
            spans = [s for b in page.get_text("dict")["blocks"] if b["type"] == 0
                     for line in b["lines"] for s in line["spans"]]
            prices = [s for s in spans if s["font"].startswith("LidlFontPrice-") and s["size"] >= 30
                      and s['text'].strip()]
            captions = []
            for block in page.get_text("dict")["blocks"]:
                if block["type"] != 0:
                    continue
                bs = [s for line in block["lines"] for s in line["spans"]]
                title = []
                for s in bs:
                    if s["font"] != "LidlFontCondPro-Bold" or not 9 <= s["size"] <= 11:
                        break
                    title.append(s["text"])
                if not title:
                    continue
                captions.append((block, "\n".join(title), bs))
            for block, title, bs in captions:
                decision = {"page": page.number + 1, "title": title, "bbox": list(block["bbox"]),
                            "status": "review", "reason": "exact_compound_identity_missing_or_nonunique"}
                decisions.append(decision)
                first_body = next((s['text'] for s in bs if s['font'] == 'LidlFontCondPro-Book'), '')
                matches = [p for p in products if ((p.brand and
                           any(normalized(p.brand) == normalized(''.join(title.splitlines()[:n]))
                               for n in range(1, len(title.splitlines()))) and
                           normalized(p.brand + p.name) in {normalized(title), normalized(title + first_body)})
                           or (not p.brand and normalized(p.name) == normalized(title)))]
                if len(matches) != 1:
                    continue
                p = matches[0]
                decision["product_id"] = p.external_product_id
                try:
                    descriptor = first_body if normalized((p.brand or '') + p.name) != normalized(title) else ''
                    proof = qualify_caption(page, block, bs, captions, prices, p, source_rows, metadata,
                                            identity_descriptor=descriptor)
                except ValueError as exc:
                    decision["reason"] = str(exc)
                    continue
                proofs.append(proof)
                decision.update(status="qualified", reason=None)
    # Repeated or conflicting document bindings are review cases, not best-price selection.
    duplicates = {p["product_id"] for p in proofs if sum(q["product_id"] == p["product_id"] for q in proofs) != 1}
    shared_prices = {p['product_id'] for p in proofs if sum(
        (q['page_number'], q['price_bbox']) == (p['page_number'], p['price_bbox']) for q in proofs) != 1}
    for decision in decisions:
        if decision.get("product_id") in duplicates:
            decision.update(status="review", reason="repeated_document_product_binding")
        elif decision.get('product_id') in shared_prices:
            decision.update(status='review', reason='price_assigned_to_multiple_captions')
    return [p for p in proofs if p["product_id"] not in duplicates | shared_prices], decisions


def detached_package(page, block, captions):
    """One explicit quantity label directly above exactly one caption column.

    Never choose a quantity by matching a desired price or source package.
    Unclear image-overlay quantities remain unbound.
    """
    choices = []
    for b in page.get_text('dict')['blocks']:
        if b['type'] != 0:
            continue
        ss = [s for line in b['lines'] for s in line['spans']]
        if len(ss) != 1 or ss[0]['font'] != 'LidlFontPro-Bold':
            continue
        s = ss[0]
        if not re.fullmatch(r'\d+(?:[,.]\d+)?\s*(?:kg|g|ml|l)', s['text'].strip()):
            continue
        owners = [c for c, _, _ in captions if abs(c['bbox'][0]-s['bbox'][0]) <= 35
                  and 0 <= c['bbox'][1]-s['bbox'][3] <= 100]
        if len(owners) == 1 and owners[0] is block:
            choices.append(s)
    if len(choices) != 1:
        raise ValueError('detached_package_caption_relation_not_unique')
    return choices[0]


def qualify_caption(page, block, spans, captions, prices, product, source_rows, metadata, *, identity_descriptor=''):
    p = product
    rows = source_rows.get(p.external_product_id, [])
    if len(rows) != 1 or "Mat och nära mat" not in p.category_path:
        raise ValueError("unique_food_source_identity_required")
    row = rows[0]
    if normalized(row.get('fullTitle', '')) != normalized((p.brand or '') + p.name):
        raise ValueError('structured_complete_identity_conflict')
    if re.search(r'\b(?:gäller|endast|kupong|aktivera|personlig)\b', page.get_text(), re.IGNORECASE):
        raise ValueError('page_critical_condition_requires_review')
    piece = (p.package_text == '/st' and p.sale_unit == 'st' and p.package_quantity is None
             and 'Frukt & grönsaker' in p.category_path)
    weight = p.sale_unit == "kg" and p.package_quantity is None
    if (len(p.offers) != 1 or p.offers[0].quantity or not (piece or weight) and (not p.package_quantity
            or p.package_unit not in {"g", "kg", "ml", "l"})):
        raise ValueError("fixed_single_package_required")
    if p.package_unit in {'ml', 'l'} and not any(category in p.category_path for category in
            ('Oljor, kryddor och såser', 'Färdigrätter')):
        raise ValueError('liquid_deposit_applicability_requires_review')
    offer = p.offers[0]
    body = " ".join(s["text"] for s in spans if s["font"] == "LidlFontCondPro-Book")
    body = re.sub(r'\s+', ' ', body).strip()
    approximate = None
    if weight:
        approximate_match = re.search(r'\bCa (\d+(?:[,.]\d+)?) kg\b', body)
        if approximate_match:
            approximate = float(approximate_match[1].replace(',', '.')) * 1000
            if p.average_weight_kg is None or abs(float(p.average_weight_kg)*1000 - approximate) > .001:
                raise ValueError('source_document_approximate_weight_conflict')
            body = body.replace(approximate_match[0], '')
        elif 'Lösvikt' in body and 'Frukt & grönsaker' in p.category_path and p.package_text == '/kg':
            body = body.replace('Lösvikt', '')
        else:
            raise ValueError('weight_purchase_form_not_verified')
    if piece:
        if body.count('Styckpris') != 1:
            raise ValueError('explicit_piece_price_missing')
        body = body.replace('Styckpris', '')
    if identity_descriptor:
        if not body.startswith(identity_descriptor.strip()):
            raise ValueError('identity_descriptor_not_first')
        body = body[len(identity_descriptor.strip()):].strip()
    description = html.unescape(re.sub("<[^>]+>", " ", row.get("keyfacts", {}).get("description", "")))
    drained = re.findall(r'Avrunnen vikt:\s*(\d+)\s*g\b', body)
    source_drained = re.findall(r'Avrunnen vikt:\s*(\d+)\s*g\b', description)
    if drained != source_drained or len(drained) > 1:
        raise ValueError('document_source_drained_quantity_conflict')
    drained_quantity = Decimal(drained[0]) if drained else None
    if drained_quantity is not None:
        if p.package_unit != 'g' or not 0 < drained_quantity < p.package_quantity:
            raise ValueError('drained_quantity_unit_or_bounds_unverified')
        body = re.sub(r'Avrunnen vikt:\s*\d+\s*g\b', '', body)
    pack = re.findall(r"(?<![\w.,])(\d+(?:\s*[×x]\s*\d+)?(?:[,.]\d+)?\s*(?:kg|g|ml|l))\b", body)
    package_label = None
    if not pack and not (piece or weight):
        package_label = detached_package(page, block, captions)
        pack = [package_label['text'].strip()]
    if not (piece or weight) and (len(pack) != 1 or normalized(pack[0].replace('×', 'x')) != normalized((p.package_text or "").replace('×', 'x'))):
        raise ValueError("literal_single_package_mismatch")
    if (piece or weight) and pack:
        raise ValueError('piece_weight_or_package_conflict')
    remaining = body if piece or weight else body.replace(pack[0], "")
    comparison = re.search(r"Jfr\s+(\d+[,.]\d{2})\s+kr/(kg|l)", remaining)
    if comparison and weight:
        raise ValueError("weight_rate_comparison_requires_explicit_basis")
    if comparison:
        quantity = (drained_quantity or p.package_quantity) / (1000 if p.package_unit in {"g", "ml"} else 1)
        if comparison[2] != ("kg" if p.package_unit in {"g", "kg"} else "l") or abs(
                Decimal(comparison[1].replace(",", ".")) * quantity - offer.price) > Decimal(".005") * quantity + Decimal(".005"):
            raise ValueError("document_comparison_price_conflict")
        remaining = remaining.replace(comparison[0], "")
    # Preserve every non-identity descriptor; only this complete closed grammar
    # is understood. Flavour lists, drained weight, deposits, coupons stop here.
    for origin in re.findall(r'(?:Ursprung|Odlingsland):?\s*(?:se förp\.|se i butik|[A-ZÅÄÖ][a-zåäö]+)', remaining):
        if normalized(origin) not in normalized(description):
            raise ValueError('document_source_origin_conflict')
        remaining = remaining.replace(origin, '')
    remaining = re.sub(r'Lägsta 30-dgrs pris:?\s*\d+(?:[.:]\d{2}|:-)', '', remaining)
    limits = re.findall(r'Max\s+(\d+)\s+förp\./hushåll', remaining, re.IGNORECASE)
    source_limits = re.findall(r'Max\s+(\d+)\s+förp\./hushåll', description, re.IGNORECASE)
    if len(limits) > 1 or limits != source_limits:
        raise ValueError('document_source_purchase_limit_conflict')
    remaining = re.sub(r'Max\s+\d+\s+förp\./hushåll', '', remaining, flags=re.IGNORECASE)
    for fat in re.findall(r'Fetthalt: \d+(?:[,.]\d+)?%', remaining):
        if normalized(fat) not in normalized(description):
            raise ValueError('fat_content_source_conflict')
        remaining = remaining.replace(fat, '')
    # Composition is retained, and must be confirmed by the exact structured
    # identity. This does not turn it into a full ingredients declaration.
    for descriptor in re.findall(r'Av (?:nöt|fläsk|kyckling)(?:, kötthalt: \d+%)?', remaining):
        if normalized(descriptor) not in normalized(description):
            raise ValueError('composition_source_conflict')
        remaining = remaining.replace(descriptor, '')
    if remaining.strip():
        raise ValueError("unclassified_caption_condition_or_variant")
    start, end = metadata["offer_start"], metadata["offer_end"]
    header = page.get_text(clip=pymupdf.Rect(0, 0, page.rect.width, 42))
    dates = re.findall(r"\b(?:Mån|Tis|Ons|Tors?|Fre|Lör|Sön)\s+(\d{1,2})/(\d{1,2})", header)
    if len(dates) != 2:
        raise ValueError("page_period_missing_or_not_full_campaign")
    window = [f'{start[:4]}-{int(m):02d}-{int(d):02d}' for d, m in dates]
    if not start <= window[0] <= window[1] <= end:
        raise ValueError('page_period_outside_publication')
    start, end = window
    x0, y0, _, y1 = block["bbox"]
    nearby = [s for s in prices if x0 - (s['bbox'][2]-s['bbox'][0])*.5 <= s["bbox"][0] <= x0 + page.rect.width * .30
              and y0 - 15 <= s["bbox"][1] <= y1 + 85]
    # Another caption between the text and price makes its tile ambiguous.
    nearby = [s for s in nearby if not any(b is not block and x0 - 5 <= b["bbox"][0] <= s["bbox"][0]
               and y0 <= b["bbox"][1] <= s["bbox"][1] for b, _, _ in captions)]
    if len(nearby) != 1:
        raise ValueError("price_caption_relation_not_unique")
    price = nearby[0]
    token = price["text"].strip().replace(":-", ".00")
    if not re.fullmatch(r"\d+\.\d{2}", token) or Decimal(token) != offer.price:
        raise ValueError("document_structured_price_conflict")
    region = pymupdf.Rect(min(x0, price['bbox'][0]) - 3, min(y0, price["bbox"][1] - 65),
                         max(block["bbox"][2], price["bbox"][2]) + 3,
                         max(y1, price["bbox"][3]) + 3)
    text = page.get_text(clip=region)
    if weight and '/kg' not in text:
        raise ValueError('weight_rate_label_not_in_same_tile')
    if piece and '/st' not in text:
        raise ValueError('piece_price_label_not_in_same_tile')
    local_conditions = re.sub(r'Max\s+\d+\s+förp\./hushåll', '', text, flags=re.IGNORECASE)
    # A "from" callout is qualified only when this exact closed single variant
    # independently states a comparison price yielding precisely this amount.
    # Open variant groups and unequal prices still fail the source/parser gates.
    if comparison:
        local_conditions = re.sub(r'\bFrån:', '', local_conditions, flags=re.IGNORECASE)
    if re.search(r"max|kupong|aktiver|personlig|från:|pant|\bför:", local_conditions, re.IGNORECASE):
        raise ValueError("local_critical_condition_requires_review")
    if ("Med Lidl Plus" in text) != offer.member_only:
        raise ValueError("document_member_context_conflict")
    source_conditions = re.sub(r'Max\s+\d+\s+förp\./hushåll', '', description, flags=re.IGNORECASE)
    if re.search(r"välj|olika|sorter|max|kupong|aktiver|personlig|pant", source_conditions, re.IGNORECASE):
        raise ValueError("source_variant_or_condition_requires_review")
    from grocery_data.app.domain.purchase_terms import PurchaseTerms
    terms = PurchaseTerms(source_reference='document-ad:' + hashlib.sha256(text.encode()).hexdigest(),
        purchase_form=('variable_package' if approximate else 'loose_weight') if weight else 'piece' if piece else 'fixed_package',
        approximate_package_g=approximate,
        quantity_basis='source_approximation' if approximate else 'requirement' if weight else 'source_exact',
        limit_scope='household_campaign')
    return {"purchase_terms": terms.model_dump(mode='json'), "price_basis_unit": 'kg' if weight else 'package',
            "product_id": p.external_product_id, "gtin": p.gtin, "source_name": p.name,
            "package_label": package_label,
            "explicit_piece_purchase": piece,
            "full_title": row["fullTitle"], "brand": p.brand, "package_text": p.package_text,
            "page_number": page.number + 1, "bbox": list(region), "text": text,
            "price_bbox": list(price['bbox']),
            "text_sha256": hashlib.sha256(text.encode()).hexdigest(), "price": str(offer.price),
            "member_only": offer.member_only, "max_packages_per_household": int(limits[0]) if limits else None,
            "drained_quantity_g": str(drained_quantity) if drained_quantity is not None else None,
            "deposit_status": "not_applicable_verified_non_beverage_package",
            "identity_method": METHOD, "required_source_text": [], "price_token": price["text"],
            "valid_from": start, "valid_to": end, "reviewed_source_description": description,
            "binding_checks": ["exact_complete_branded_caption", "unique_source_identity",
                "literal_single_package", "price_typography_geometry", "closed_caption_grammar",
                "document_price_equals_source", "explicit_page_dates", "national_publication_scope"]}

"""Conservative, edition-independent Willys text rules. No product/edition list.

PDF text positions and typography establish the local price/caption relation;
the separately printed comparison price checks its arithmetic. Unclassified
caption conditions and ambiguous relations remain review cases.
"""
import hashlib
import re
from collections import Counter
from datetime import date
from decimal import Decimal

RULES = 'willys-document-text-rules-v6-purchase-terms'
COUNTRIES = {'sverige', 'danmark', 'spanien', 'italien', 'frankrike', 'kina', 'brasilien',
             'nederländerna', 'tyskland', 'norge', 'finland', 'belgien', 'polen', 'portugal', 'marocko', 'irland'}


def flat(text):
    return re.sub(r'\s+', ' ', text).strip()


def text_bag(text):
    # The viewer and PDF have different reading orders, but preserve the same
    # page characters, including amounts, letters and duplicate occurrences.
    return Counter(c for c in text.casefold() if c.isalnum())


def blocks(page):
    result = []
    for b in page.get_text('dict')['blocks']:
        if b['type'] != 0:
            continue
        spans = [s for line in b['lines'] for s in line['spans']]
        text = '\n'.join(''.join(s['text'] for s in line['spans']) for line in b['lines']) + '\n'
        result.append({'bbox': list(b['bbox']), 'text': text, 'spans': spans})
    return result


def period(text):
    matches = re.findall(r'Priserna gäller[^\n]*?från\s+\w+\s+(\d{1,2})/(\d{1,2})\s+t\s*o\s*m\s+\w+\s+(\d{1,2})/(\d{1,2})\s+(20\d{2})', flat(text), re.IGNORECASE)
    windows = set()
    for d, m, ed, em, y in matches:
        end = date(int(y), int(em), int(ed))
        start = date(int(y) - ((int(m), int(d)) > (int(em), int(ed))), int(m), int(d))
        if not 0 <= (end-start).days <= 13:
            raise ValueError('document_period_outside_supported_window')
        windows.add((start.isoformat(), end.isoformat()))
    if len(windows) != 1:
        raise ValueError('document_period_missing_or_conflicting')
    return next(iter(windows))


def near_label(label, price):
    x0, y0, x1, y1 = price['bbox']
    lx0, ly0, lx1, ly1 = label['bbox']
    return (lx0 <= x1 and lx1 >= x0 and y0 - (y1-y0)*.55 <= ly0 <= y1
            and ly1 >= y0-(y1-y0)*.6)


def price_blocks(rows):
    prices = []
    for block in rows:
        spans = [s for s in block['spans'] if s['font'].endswith('Serif-Price')]
        if not spans:
            continue
        digits = [s['text'].strip() for s in spans]
        if len(digits) != 2 or not all(s.isdecimal() for s in digits) or len(digits[1]) != 2:
            prices.append({**block, 'error': 'unrecognized_price_typography'})
            continue
        labels = [b for b in rows if near_label(b, block)]
        text = flat('\n'.join(b['text'] for b in labels))
        units = {unit.casefold() for unit in re.findall(r'Per\s+(förp|st|kg)\b', text, re.IGNORECASE)}
        multibuys = set(re.findall(r'\b(\d+)\s+FÖR\b', text))
        audience = [b for b in labels if 'För dig med' in flat(b['text'])]
        x0, y0, x1, y1 = block['bbox']
        deposit_near = any(re.search(r'\bpant\b', b['text'], re.IGNORECASE)
            and b['bbox'][0] <= x1 and b['bbox'][2] >= x0
            and y0-(y1-y0)*.6 <= b['bbox'][1] <= y1+(y1-y0)*.6 for b in rows)
        if (len(units) > 1 or len(multibuys) > 1 or units and multibuys
                or not (units or multibuys) or any('WillysPlus' not in re.sub(r'\s', '', b['text']) for b in audience)):
            error = 'price_unit_or_audience_ambiguous'
        else:
            error = None
        prices.append({**block, 'price': str(Decimal(digits[0])+Decimal(digits[1])/100),
            'unit': next(iter(units), None), 'required_packages': int(next(iter(multibuys), 1)),
            'deposit_unknown': deposit_near,
            'member_only': bool(audience), 'labels': [b['text'] for b in labels], 'error': error})
    return prices


def caption_fields(ad, window):
    text = flat(ad['text'])
    title = ad['title']
    unknown_deposit = bool(re.search(r'\bpant\b|\+pant', text, re.IGNORECASE))
    variant_text = re.sub(r'Gäller endast \d+[-–]\d+ \w+', '', text, flags=re.IGNORECASE)
    # A historical reference-price range is not a package/variant range.
    variant_text = re.sub(r'Lägsta\s+30-dgrspris\s+\d+[,:]\d{2}(?:[-–]\d+[,:]\d{2})?\s*kr(?:/kg)?', '', variant_text, flags=re.IGNORECASE)
    names = [title.capitalize()]
    shared_form = re.fullmatch(r'(EKOLOGISKA )?(PASSERADE),\s*(KROSSADE) (TOMATER)', title)
    if shared_form:
        names = [flat(' '.join(filter(None, (shared_form[1], shared_form[i], shared_form[4])))).capitalize()
                 for i in (2, 3)]
    elif ',' in title:
        alternatives = [p.strip() for p in title.split(',')]
        if not all(re.fullmatch(r'[A-ZÅÄÖ]+(?: [A-ZÅÄÖ]+)*(?: \d+-PACK)?(?: \d+G)?', p) for p in alternatives):
            raise ValueError('variant_range_or_approximate_quantity_requires_review')
        names = [re.sub(r' \d+G$', '', p).capitalize() for p in alternatives]
    approximate = bool(re.search(r'\bCa\s+\d+(?:[,.]\d+)?\s*kg\b', variant_text, re.IGNORECASE))
    if len(names) > 1:
        variant_text = re.sub(r'Olika sorter', '', variant_text, flags=re.IGNORECASE)
    quantity_range = re.search(r'(?<![\w.,])(\d+(?:[,.]\d+)?)\s*[-–]\s*(\d+(?:[,.]\d+)?)\s*(g|kg|ml|l)\b', variant_text, re.IGNORECASE)
    open_group = bool(re.search(r'Olika sorter', variant_text, re.IGNORECASE)) or bool(quantity_range)
    if quantity_range:
        if not re.search(r'Olika sorter', text, re.IGNORECASE):
            raise ValueError('quantity_range_meaning_requires_review')
        variant_text = variant_text.replace(quantity_range[0], '')
        variant_text = re.sub(r'Jämförpris\s+\d+[,:]\d{2}[-–]\d+[,:]\d{2}\s*kr/(?:kg|l)', '', variant_text, flags=re.IGNORECASE)
    variant_text = re.sub(r'Olika sorter', '', variant_text, flags=re.IGNORECASE)
    if re.search(r'Olika|\d\s*[-–/]\s*\d', variant_text, re.IGNORECASE):
        raise ValueError('variant_range_or_approximate_quantity_requires_review')
    if open_group:
        names = [title.capitalize()]
    body = text[len(title):].strip()
    parts = [p.strip() for p in body.split('•')]
    if len(parts) < 2:
        raise ValueError('caption_structure_requires_review')
    brand = parts[0]
    body = ' • '.join(parts[1:])
    body = re.sub(r'\+\s*pant\b|\bexkl\.?\s*pant\b|\bpant tillkommer\b', '', body, flags=re.IGNORECASE)
    # Critical conditions are parsed completely, rather than silently dropped.
    limits = re.findall(r'Max\s+(\d+)\s+(?:köp|förp)/hushåll', body, re.IGNORECASE)
    if len(set(limits)) > 1 or ('Max' in body and not limits):
        raise ValueError('purchase_limit_unit_requires_review')
    start, end = window
    short = re.search(r'Gäller endast (\d+)[-–](\d+) (\w+)', body, re.IGNORECASE)
    if short:
        months = ['januari','februari','mars','april','maj','juni','juli','augusti','september','oktober','november','december']
        if short[3].casefold() not in months:
            raise ValueError('short_period_month_unknown')
        month = months.index(short[3].casefold())+1
        start, end = (date(int(window[0][:4]), month, int(short[i])).isoformat() for i in (1, 2))
        if not window[0] <= start <= end <= window[1]:
            raise ValueError('short_period_outside_document')
        body = body.replace(short[0], '')
    comparison = re.search(r'Jämförpris\s+(\d+[,:]\d{2})(?:[-–](\d+[,:]\d{2}))?\s*kr/(kg|l|st)\b', body, re.IGNORECASE)
    if not comparison:
        raise ValueError('independent_comparison_price_missing')
    comparison_price = Decimal(comparison[1].replace(':','.').replace(',','.'))
    comparison_unit = comparison[3].casefold()
    comparison_high = Decimal(comparison[2].replace(':','.').replace(',','.')) if comparison[2] else None
    if bool(quantity_range) != bool(comparison_high):
        raise ValueError("quantity_and_comparison_range_mismatch")
    body = body.replace(comparison[0], '')
    body = re.sub(r'Lägsta\s+30-dgrspris\s+\d+[,:]\d{2}(?:[-–]\d+[,:]\d{2})?\s*kr(?:/kg)?', '', body, flags=re.IGNORECASE)
    body = re.sub(r'Max\s+\d+\s+(?:köp|förp)/hushåll', '', body, flags=re.IGNORECASE)
    if approximate:
        body = re.sub(r'\bCa\s+(?=\d)', '', body, flags=re.IGNORECASE)
    if len(names) > 1 or open_group:
        body = re.sub(r'Olika sorter', '', body, flags=re.IGNORECASE)
    minimum, maximum, range_unit = None, None, None
    if quantity_range:
        minimum, maximum = (Decimal(quantity_range[i].replace(',', '.')) for i in (1, 2))
        range_unit = quantity_range[3].casefold()
        factor = 1000 if range_unit in {'kg', 'l'} else 1
        minimum, maximum = minimum*factor, maximum*factor
        range_unit = 'g' if range_unit in {'g', 'kg'} else 'ml'
        if minimum >= maximum:
            raise ValueError('invalid_variant_quantity_range')
        body = body.replace(quantity_range[0], '')
    pack_pattern = r'(?<!\w)(\d+(?:[,.]\d+)?)\s*(kg|g|ml|cl|dl|l|p)\b'
    packs = list(re.finditer(pack_pattern, body, re.IGNORECASE))
    if not packs:
        packs = list(re.finditer(pack_pattern, title, re.IGNORECASE))
    if len(packs) > 1:
        raise ValueError('multiple_package_quantities_require_review')
    quantity, unit = None, None
    if packs:
        p = packs[0]
        quantity = Decimal(p[1].replace(',','.'))
        unit = p[2].casefold()
        factors = {'kg':(1000,'g'), 'g':(1,'g'), 'ml':(1,'ml'), 'cl':(10,'ml'), 'dl':(100,'ml'), 'l':(1000,'ml'), 'p':(1,'st')}
        factor, unit = factors[unit]
        quantity *= factor
        body = body.replace(p[0], '')
    # A single explicit descriptor can be supported without guessing variants.
    descriptors = []
    # Closed descriptive grammar, retained in the product name. These words
    # never establish ingredients, nutrition, or unspecified variety membership.
    for pattern in (r'\b\d+(?:[,.]\d+)?%', r'\b\d+\s+månader\b', r'\bskivad\b', r'\bdjupfrysta\b',
                    r'\bItaliensk\b', r'\bExtra virgin\b', r'\bSqueezy\b', r'\bKrispiga\b', r'\bGlutenfria\b'):
        descriptors.extend(m[0] for m in re.finditer(pattern, body, re.IGNORECASE))
        body = re.sub(pattern, '', body, flags=re.IGNORECASE)
    # Explicit alternatives within one descriptor dimension, never an open
    # "different varieties" group or a package/price interval.
    variant_groups = (('Normalsaltat', 'Extrasaltat'), ('Enrisrökt', 'Alspånsrökt'),
                      ('Original', 'Tryffel'), ('Vanilj', 'Kladdkaka'))
    for group in variant_groups:
        if all(re.search(r'\b'+word+r'\b', body, re.IGNORECASE) for word in group):
            if len(names) != 1:
                raise ValueError('multiple_variant_dimensions_require_review')
            names = [names[0]+' '+word for word in group]
            for word in group:
                body = re.sub(r'\b'+word+r'\b', '', body, flags=re.IGNORECASE)
    # A descriptor identical to the complete headline carries no new variant.
    body = re.sub(r'(?<!\w)'+re.escape(title)+r'(?!\w)', '', body, flags=re.IGNORECASE)
    if re.search(r'\bOriginal\b', body, re.IGNORECASE):
        descriptors.append('Original')
        body = re.sub(r'\bOriginal\b', '', body, flags=re.IGNORECASE)
    if re.search(r'\bgäller ej ekologisk(?:a)?\b', body, re.IGNORECASE):
        descriptors.append('ej ekologisk')
    for word in [*COUNTRIES, 'nya zeeland', 'djupfryst', 'tillfälligt parti', 'klass 1', 'gäller ej ekologisk', 'gäller ej ekologiska']:
        body = re.sub(r'\b'+re.escape(word)+r'\b', '', body, flags=re.IGNORECASE)
    exclusions = []
    if open_group:
        exclusion = re.search(r'Gäller ej ([A-Za-zÅÄÖåäö ,]+)(?=•|$)', body, re.IGNORECASE)
        if exclusion:
            exclusions = [exclusion[1].strip()]
            body = body.replace(exclusion[0], '')
        if re.search(r'Gäller ej', body, re.IGNORECASE):
            raise ValueError('open_group_exclusion_scope_requires_review')
    residual = re.sub(r'[\s•.\ue000-\uf8ff]', '', body)
    if residual and len(names) == 1 and quantity:
        from grocery_data.app.services.product_declarations import exact_declaration

        # A manufacturer can prove that an apparent slash is one complete
        # compound variant. This does not authorize its price or another pack.
        declaration = exact_declaration(' '.join([*names, *descriptors, body]),
                                        brand, quantity, unit)
        if declaration:
            names, descriptors, residual = [declaration['name'].capitalize()], [], ''
    if residual:
        raise ValueError('unclassified_caption_condition_or_variant:' + residual[:80])
    return {'brand': '' if brand.casefold() in COUNTRIES else brand, 'names': [' '.join([name, *descriptors]) for name in names],
        'package_quantity': float(quantity) if quantity and not approximate else None,
        'package_unit': unit if not approximate else None,
        'approximate_package_quantity_g': float(quantity) if approximate else None,
        'open_variant_group': open_group, 'exclusions': exclusions,
        'variant_package_minimum': float(minimum) if minimum else None,
        'variant_package_maximum': float(maximum) if maximum else None,
        'variant_package_unit': range_unit,
        'comparison_price_maximum': str(comparison_high) if comparison_high else None,
        'max_quantity': int(limits[0]) if limits else None, 'valid_from': start, 'valid_to': end,
        'comparison_price': str(comparison_price), 'comparison_unit': comparison_unit,
        'deposit_status': 'unknown' if unknown_deposit else 'not_applicable', 'short_period_explicit': bool(short)}


def geometry_relation(ad, price, page_width, page_height, captions, *, tight=False):
    x0, y0, x1, _ = ad['bbox']
    px0, _, px1, py1 = price['bbox']
    center = (px0+px1)/2
    # Caption below its price, horizontally in the same limited column/tile.
    width, padding = (.20, .02) if tight else (.30, .10)
    if not x0-8 <= center <= max(x1, x0+page_width*width)+page_width*padding:
        return False
    # Price and caption may overlap vertically in compact tiles, but a quote
    # from the preceding tile row is not a candidate. Arithmetic still checks
    # the independent comparison price; ambiguous matches remain blocked.
    if not -(price['bbox'][3]-price['bbox'][1])*.7 <= y0-py1 <= page_height*.22:
        return False
    return not any(other['index'] != ad['index'] and py1 < other['bbox'][1] < y0 and other['bbox'][0] <= center <= other['bbox'][2] for other in captions)


def relation(ad, price, page_width, page_height, captions):
    if price.get('error') or not geometry_relation(ad, price, page_width, page_height, captions):
        return False
    q, unit = ad['package_quantity'], ad['package_unit']
    if ad.get('variant_package_minimum'):
        if price['unit'] == 'kg' or ad['comparison_unit'] != {'g':'kg','ml':'l'}[ad['variant_package_unit']]:
            return False
        total = Decimal(price['price'])
        factor = Decimal(price['required_packages']) / 1000
        return all(abs(Decimal(str(amount))*factor*Decimal(rate) - total) <= Decimal('.005')*(Decimal(str(amount))*factor+1)
            for amount,rate in [(ad['variant_package_minimum'],ad['comparison_price_maximum']),
                                (ad['variant_package_maximum'],ad['comparison_price'])])
    if price['unit'] == 'kg' and q is None:
        return ad['comparison_unit'] == 'kg' and Decimal(ad['comparison_price']) == Decimal(price['price'])
    if q is None:
        return price['unit'] == 'st'  # Explicit per-piece quote, never kg → piece.
    if price['unit'] == 'kg':
        return False
    comp_unit = {'g':'kg', 'ml':'l', 'st':'st'}[unit]
    if ad['comparison_unit'] != comp_unit:
        return False
    amount = Decimal(str(q)) / (1000 if unit in {'g','ml'} else 1) * price['required_packages']
    return abs(Decimal(ad['comparison_price'])*amount-Decimal(price['price'])) <= Decimal('.005')*amount+Decimal('.005')


def qualify_document(doc, listing):
    if len(doc) != len(listing['pages']) or len(doc) != len(listing['pageTexts']):
        raise ValueError('publication_page_count_mismatch')
    mismatched_pages = {i for i,(page,text) in enumerate(zip(doc, listing['pageTexts'], strict=True),1)
                        if text_bag(page.get_text()) != text_bag(text)}
    window = period('\n'.join(p.get_text() for p in doc))
    if period('\n'.join(listing['pageTexts'])) != window:
        raise ValueError('viewer_document_period_conflict')
    ads, page_reports = [], []
    for number, page in enumerate(doc, 1):
        rows = blocks(page)
        captions = []
        caption_styles = {(b['spans'][0]['font'], round(b['spans'][0]['size'], 2))
                          for b in rows if b['spans'] and ('•' in b['text'] or 'Jämförpris' in b['text'])
                          and b['text'].splitlines()[0].strip().isupper()}
        for row in rows:
            lines = row['text'].strip().splitlines()
            style = (row['spans'][0]['font'], round(row['spans'][0]['size'], 2)) if row['spans'] else None
            if not lines or not ('•' in row['text'] or 'Jämförpris' in row['text'] or style in caption_styles):
                continue
            # Known publisher's product-caption typography. An unknown font is
            # not silently treated as an approved layout.
            title = lines[0].strip()
            if not title.isupper() or not any('Bold' in s['font'] or 'Black' in s['font'] for s in row['spans'][:1]):
                continue
            heading = []
            for span in row['spans']:
                if span['font'] != row['spans'][0]['font'] or span['size'] != row['spans'][0]['size']:
                    break
                heading.append(span['text'])
            title = flat(' '.join(heading))
            ad = {k: row[k] for k in ('bbox', 'text')}
            ad.update(page=number, index=len(ads)+len(captions), title=title,
                status='quarantine', qualification_method=RULES)
            try:
                ad.update(caption_fields(ad, window))
            except ValueError as exc:
                ad['reason'] = str(exc)
            captions.append(ad)
        prices = price_blocks(rows)
        unbound_conditions = [b for b in rows if re.search(r'\b(max|kupong|aktivera|personlig|endast)\b', b['text'], re.IGNORECASE)
            and not any(a['bbox'] == b['bbox'] for a in captions)]
        matches = {a['index']: [i for i,p in enumerate(prices) if relation(a,p,page.rect.width,page.rect.height,captions)]
                   for a in captions if 'reason' not in a}
        # Resolve adjacent equal-price tiles by the caption's own column before
        # enforcing the one-to-one relation. Never use amount as a tie-breaker.
        for ad in captions:
            candidates = matches.get(ad['index'], [])
            local = [i for i in candidates if geometry_relation(ad, prices[i], page.rect.width,
                     page.rect.height, captions, tight=True)]
            if local:
                matches[ad['index']] = local
        use = Counter(i for candidates in matches.values() for i in candidates)
        short_banner = bool(re.search(r'Gäller\s+(?:mån|tis|ons|tor|fre|lör|sön)\b', page.get_text(), re.IGNORECASE))
        for ad in captions:
            if number in mismatched_pages:
                ad['reason'] = 'page_viewer_pdf_text_mismatch'
            if unbound_conditions:
                ad['reason'] = 'unbound_critical_condition_on_page'
            if 'reason' in ad:
                continue
            candidates = matches[ad['index']]
            if any(p.get('error') and geometry_relation(ad,p,page.rect.width,page.rect.height,captions,tight=True) for p in prices):
                ad['reason'] = 'unrecognized_nearby_price_requires_review'
            elif short_banner and not ad['short_period_explicit']:
                ad['reason'] = 'short_day_banner_scope_requires_review'
            elif len(candidates) != 1 or use[candidates[0]] != 1:
                ad['reason'] = 'price_caption_relation_not_unique'
            else:
                p = prices[candidates[0]]
                rate_only = p['unit'] == 'kg'
                ad.update(status='qualified', price=p['price'], required_packages=p['required_packages'],
                    member_only=p['member_only'], price_bbox=p['bbox'], price_text=p['text'],
                    package_quantity=None if rate_only or ad.get('variant_package_minimum') else ad['package_quantity'] or 1,
                    package_unit=None if rate_only or ad.get('variant_package_minimum') else ad['package_unit'] or 'st',
                    price_basis_unit='kg' if rate_only else 'package',
                    exact_checkout_supported=not rate_only and not ad.get("open_variant_group") and ad.get("deposit_status") != "unknown" and not p.get("deposit_unknown"),
                    text_sha256=hashlib.sha256(ad['text'].encode()).hexdigest(),
                    binding_checks=['same_page_geometry','unique_price_caption','explicit_price_unit',
                        'complete_caption_grammar','viewer_pdf_text_equal','explicit_period'],
                    price_labels=p['labels'])
                from grocery_data.app.domain.purchase_terms import PurchaseTerms
                form = ('variable_package' if ad.get('approximate_package_quantity_g') else 'loose_weight') if rate_only else 'fixed_package' if ad['package_unit'] != 'st' else 'piece'
                ad['purchase_terms'] = PurchaseTerms(
                    source_reference='document-ad:' + ad['text_sha256'], purchase_form=form,
                    complete_group_size=p['required_packages'],
                    approximate_package_g=ad.get('approximate_package_quantity_g'),
                    quantity_basis='source_approximation' if ad.get('approximate_package_quantity_g') else 'requirement' if rate_only else 'source_interval' if ad.get('variant_package_minimum') else 'source_exact',
                    variant_package_minimum=ad.get('variant_package_minimum'),
                    variant_package_maximum=ad.get('variant_package_maximum'),
                    variant_package_unit=ad.get('variant_package_unit'),
                    identity_scope='campaign_group' if ad.get('open_variant_group') else 'product',
                    variant_selection='required' if ad.get('open_variant_group') else 'resolved',
                    exclusions=tuple(ad.get('exclusions', ())), limit_scope='household_campaign',
                    deposit_status='unknown' if p.get('deposit_unknown') or ad.get('deposit_status') == 'unknown' else 'not_applicable',
                ).model_dump(mode='json')
        ads.extend(captions)
        page_reports.append({'page':number, 'text_binding_verified':number not in mismatched_pages,
            'identified_captions':len(captions), 'price_blocks':len(prices),
            'unbound_critical_conditions':[b['text'] for b in unbound_conditions],
            'unrecognized_price_blocks':sum(bool(p.get('error')) for p in prices),
            'unclassified_text_blocks':[{'bbox':b['bbox'],'text':b['text']} for b in rows
                if ('•' in b['text'] or 'Jämförpris' in b['text']) and not any(a['bbox']==b['bbox'] for a in captions)]})
    seen = {}
    for ad in ads:
        if ad['status'] != 'qualified':
            continue
        key = tuple(str(ad[k]) for k in ('title','brand','package_quantity','package_unit','price','required_packages','member_only','max_quantity','valid_from','valid_to'))
        if key in seen:
            ad.update(status='duplicate', reason='duplicate_advertisement', duplicate_of=seen[key])
        else:
            seen[key] = ad['index']
    if not ads:
        raise ValueError('unsupported_document_caption_layout')
    return {'ads':ads, 'pages':len(doc), 'valid_from':window[0], 'valid_to':window[1],
        'review_method':RULES, 'page_reports':page_reports, 'image_content':'not_interpreted'}

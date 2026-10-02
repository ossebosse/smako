"""Conservative mappings to imported SLV foods, never branded declarations.

Only named plain foods and their evidenced form qualify. No density, yield,
allergen absence, price, fresh/dried or fresh/frozen equivalence is inferred.
The planner independently requires the existing nutrition-estimate opt-in.
"""
import re

from app.services.ingredient_normalizer import canonicalize_ingredient_name


def reviewed_reference(product, name, facts):
    if facts and facts.conflicts:
        return None
    canonical = canonicalize_ingredient_name(name)
    label = ' '.join(product.name.casefold().split())
    category = (getattr(product, 'category', None) or '').casefold()
    composition = ' '.join(facts.ingredients).casefold() if facts else ''
    # This prefix/suffix cleanup never removes variant or cooking information.
    label = re.sub(r'^(?:ekologisk |färsk )', '', label)
    label = re.sub(r'\s+(?:eko|ekologisk|klass 1|i ask)$', '', label)
    label = re.sub(r'\s+\d+(?:[,.]\d+)?\s*g$', '', label)
    fresh_category = any(x in category for x in ('frukt', 'grönsak', 'grönt', 'svamp', 'blomkål', 'broccoli'))
    frozen = bool(re.search(r'\b(?:fryst|frysta|djupfryst|djupfrysta)\b', label) or 'fryst' in category)
    forbidden = r'konserv|inlagd|saltlag|kryddblandning|marinerad|sås|soppa|stuvad|stekt|torkad|pulver|dipp|chips'
    produce = {
        'zucchini': (362, None, r'(?:zucchini|squash)'),
        'aubergine': (372, None, r'aubergine'),
        'spenat': (4941, 361, r'(?:babyspenat|spenat)(?: blad| hackad)?'),
        'blomkål': (322, 323, r'blomkål(?: buketter)?'),
        'champinjoner': (333, 383, r'champinjoner(?: skivade)?'),
        'pepparrot': (291, None, r'pepparrot'),
        'dill': (377, None, r'dill(?: i knippe)?'),
        'persilja': (352, None, r'(?:bladpersilja|persilja)(?: blad| i knippe)?'),
        'basilika': (379, None, r'basilika'),
    }
    if canonical in produce:
        raw_id, frozen_id, pattern = produce[canonical]
        simple = re.sub(r'\s+(?:fryst|frysta|djupfryst|djupfrysta)$', '', label)
        if (not re.fullmatch(pattern, simple) or re.search(forbidden, label + ' ' + category)
                or composition and re.search(r'\b(?:olja|smör|grädde|socker|salt|vatten|ättika)\b', composition)):
            return None
        if frozen:
            return frozen_id
        return raw_id if fresh_category else None
    dry = {
        'spiskummin': (7199, r'spiskummin(?: malen| hel| burk| påse)?'),
        'gurkmeja': (7198, r'gurkmeja(?: malen| burk| påse)?'),
        'kanel': (2306, r'kanel(?: malen| burk| påse)?'),
        'havregryn': (702, r'havregryn(?: fullkorn)?'),
        'vetemjöl': (1941, r'(?:vetemjöl|kärnvetemjöl)'),
        'salt': (1975, r'(?:salt|hushållssalt|finkornigt salt)(?: med jod| utan jod| fint| finkornigt)?'),
    }
    if canonical in dry:
        identity, pattern = dry[canonical]
        if (re.fullmatch(pattern, label) and
                not re.search(r'blandning|smaksatt|kryddsalt|flingsalt|mineral|badsalt', label)):
            # Grain/spice form is conveyed by its exact whole-product name.
            return identity
    return None

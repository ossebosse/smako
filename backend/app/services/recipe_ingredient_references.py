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
    if canonical == 'oliver':
        return _black_oiled_drained_olive_reference(product, facts, label, composition)
    # This prefix/suffix cleanup never removes variant or cooking information.
    label = re.sub(r'^(?:ekologisk |färsk )', '', label)
    label = re.sub(r'\s+(?:eko|ekologisk|klass 1|i ask)$', '', label)
    label = re.sub(r'\s+\d+(?:[,.]\d+)?\s*g$', '', label)
    fresh_category = any(x in category for x in ('frukt', 'grönsak', 'grönt', 'svamp', 'blomkål', 'broccoli', 'zucchini', 'aubergine', 'selleri', 'potatis', 'rotsaker', 'färska örter', 'kryddväxt')) or bool(re.search(r'\bkruka\b', label))
    frozen = bool(re.search(r'\b(?:fryst|frysta|djupfryst|djupfrysta)\b', label) or 'fryst' in category)
    if canonical == 'äpple':
        from app.services.nutrition_reference import MAPPINGS
        # Raw apple with skin, measured edible grams. Neither a named cultivar
        # declaration nor a piece yield; preserve the separate quantity gate.
        return 588 if (588 in MAPPINGS and fresh_category and not frozen and not composition
            and re.fullmatch(r'(?:äpple|äpplen)(?: röda| gröna| svenska| ekologiska| klass [12])*', label)) else None
    forbidden = r'konserv|inlagd|saltlag|kryddblandning|marinerad|sås|soppa|stuvad|stekt|torkad|pulver|dipp|chips'
    produce = {
        'gurka': (339, None, r'gurka(?: sverige| svensk| ofilmad)?'),
        'zucchini': (362, None, r'(?:zucchini|squash)'),
        'aubergine': (372, None, r'aubergine'),
        'selleri': (321, None, r'(?:stjälkselleri|blekselleri|bladselleri|selleri)'),
        'rödbeta': (294, None, r'(?:rödbeta|rödbetor)'),
        'sötpotatis': (3765, None, r'sötpotatis'),
        'spenat': (4941, 361, r'(?:babyspenat|spenat)(?: blad| hackad)?'),
        'blomkål': (322, 323, r'blomkål(?: buketter)?'),
        'champinjoner': (333, 383, r'champinjoner(?: skivade)?'),
        'pepparrot': (291, None, r'pepparrot'),
        'dill': (377, None, r'dill(?: i knippe)?'),
        'persilja': (352, None, r'(?:bladpersilja|persilja)(?: blad| krus| kruka| i kruka| i knippe)*'),
        'basilika': (379, None, r'basilika(?: kruka| i kruka| blad)*'),
    }
    if canonical == 'paprika' and fresh_category:
        match = re.fullmatch(r'paprika(?: (röd|grön|gul))?', label)
        if match:
            return {'röd': 351, 'grön': 350, 'gul': 381, None: 392}[match.group(1)]
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
        'kanel': (2306, r'kanel(?: cassia)?(?: malen| burk| påse)?'),
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


def _black_oiled_drained_olive_reference(product, facts, label, composition):
    """SLV 402: black, oil-coated, pitted and drained; not every preserved olive.

    SLV report 3/2016 pp. 8, 18, 44 and LanguaL C0139/K0026/Z0219
    document the reviewed preparation. The source is a generic composite sample,
    never the exact branded declaration. Actual drained package proof is separate.
    """
    if not facts or facts.conflicts or not composition:
        return None
    label = re.sub(r'\s+(?:eko|ekologisk|ekologiska)$', '', label)
    if not re.fullmatch(r'(?:svarta oliver|oliver (?:svarta|kalamata|kalamon))'
                        r' (?:urkärnade|utan kärna|utan kärnor)', label):
        return None
    words = set(re.findall(r'[a-zåäö]+', composition))
    allowed = {'ingredienser', 'vatten', 'urkärnade', 'svarta', 'oliver', 'kalamataoliver',
               'kalamonoliver', 'av', 'sorten', 'kalamata', 'kalamon', 'vinäger', 'extra',
               'virgin', 'olivolja', 'havssalt', 'salt', 'ekologiskt', 'ekologiska',
               'certifierad', 'ingrediens'}
    if (not words <= allowed or 'olivolja' not in words or 'urkärnade' not in words
            or not words & {'svarta', 'kalamata', 'kalamon', 'kalamataoliver', 'kalamonoliver'}):
        return None
    if (getattr(product, 'usable_unit', None) != 'g'
            or not any(e.get('basis') == 'drained' and e.get('unit') == 'g'
                       and e.get('quantity', 0) > 0
                       and e.get('quantity') == getattr(product, 'usable_quantity', None)
                       and e.get('source')
                       for e in facts.field_sources.get('usable_quantity', ()))):
        return None
    return 402

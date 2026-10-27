"""Build the full remaining worklist; retrieval is never product approval.

The explicit group notes describe the unresolved proof, not a new food fact.
Original references come from the previous complete 2,200-variant report.
"""
import argparse
import hashlib
import json
from pathlib import Path

NOTES = {
    'mynta': ('quantity', '25/100-g cut herb packs need a leaf-only yield; reject rooted 429-g pots. Inspect retained 101599969_ST and queued 101391698_ST.'),
    'tamarindpasta': ('assortment', '435-ml Chua Hah Seng concentrate has unproved strength and mass. Find a priced seedless unsweetened paste; do not equate concentrate to paste.'),
    'masa harina': ('assortment', 'PAN precooked cornmeal is not verified nixtamalised masa. Search approved catalogues for exact Maseca/Minsa/nixtamalised SKU.'),
    'citrongräs': ('quantity', '50-g whole stems exist. Need tender trimmed-core yield; tea, powder and seasoned dumplings are excluded.'),
    'nötkött': ('product_relation', 'Inspect authored cut/cooking requirements and exact boneless beef candidates (strips, steak, stewing cuts); do not substitute mince or a slow cut in a quick preparation.'),
    'pärlkorn': ('assortment', 'Urtekram 1012040/400 g polished barley is a source lead without a priced exact SKU. Cut GoGreen korngryn is not the same form.'),
    'klibbigt ris': ('product_relation', 'Search glutinous/sticky rice aliases; verify rice variety from composition. Jasmine and sushi rice are negative controls.'),
    'bambuskott': ('product_relation', 'Search bambuskott/bambuskotts aliases; bind plain shoots and source-declared drained grams.'),
    'räkor': ('product_relation', 'Existing 400/200-g and 870/500-g packs need exact cooked, peeled and drained source binding. Shell-on and raw shrimp are separate.'),
    'tapiokastärkelse': ('assortment', 'Search tapioca/tapioka/cassava starch; require pure starch rather than pearls or cassava flour.'),
    'äggula': ('preparation', 'Whole hen eggs can supply separated yolk through a sourced estimated partition. Joint yolk/white demand must share eggs and account for shell and unused fractions.'),
    'äggvita': ('preparation', 'Liquid-white candidate is sold in ml while recipe uses g. Evaluate sourced egg partition, sharing eggs with yolk, or exact supplier mass; never ml=g.'),
    'rimmat fläsk': ('product_relation', 'Scan/Tulip gram packs exist. Verify raw cured boneless pork, not smoked/cooked bacon, with exact composition and package.'),
    'gelatinblad': ('quantity', 'Dr Oetker 5701073066478 is catalogued as 12 sheets; source the exact net gram quantity and retain sheet package identity.'),
    'klibbigt rismjöl': ('assortment', 'Require glutinous rice flour identity; plain rice flour cannot satisfy it.'),
    'tapiokapärlor': ('assortment', 'Need small dry tapioca pearls, with size/form evidence; starch and ready boba are excluded.'),
    'breda risnudlar': ('product_relation', 'Search rice-noodle labels including pad thai. Verify broad flat dry rice form and full composition.'),
    'kronärtskocka': ('product_relation', 'Monte Castello 400/240-g hearts are a candidate. Require plain drained hearts; marinated spreads are not equivalent.'),
    'makrill': ('assortment', 'Observed tomato tins cannot supply raw boneless fillets. Search exact unseasoned raw/frozen fillet SKU.'),
    'mango': ('quantity', 'Review fresh gram packs and preserved preparation constraints for frozen flesh. Whole fruit needs sourced edible yield; juice/chutney excluded.'),
    'rispapper': ('product_relation', 'Search rice paper/spring-roll sheets; source rice composition and dry sheet mass. The two authored forms denote purchased dry sheets.'),
    'sardiner': ('product_relation', 'Existing oil tins need drained fish weight and matching preparation; net sauce/oil weight cannot be used.'),
    'uradlinser': ('assortment', 'Require split peeled Vigna mungo (urad dal), not mung beans, beluga or chana dal.'),
    'vinblad': ('product_relation', 'Sevan 620/350-g leaves in brine are a candidate. Verify drained leaf quantity; filled dolmas excluded.'),
    'bittergurka': ('assortment', 'Need priced bitter melon and edible flesh yield excluding seeds; cucumber is not equivalent.'),
    'chana dal': ('assortment', 'Require split peeled chana chickpeas; whole chickpeas and chickpea flour excluded.'),
    'gröna mungbönor': ('preparation', 'Eldorado 800-g dry beans exist. Need sourced soak/cook/drain yield and instructions, waiting/active time and cooked nutrition basis.'),
    'surkål': ('product_relation', 'Stollenwerk 680/650-g and Rolnik 850/500-g candidates need plain fermented cabbage composition and drained-weight source.'),
    'vattenkastanjer': ('product_relation', 'Search vattenkastanj aliases and source peeled drained canned mass, not full can weight.'),
    'avokado': ('quantity', 'Hass fixed packs and frozen cubes exist. Bind a sourced edible yield or verified peeled flesh; keep frozen handling requirements.'),
    'silkestofu': ('assortment', 'Search silken/silk tofu; firm tofu cannot silently replace soft silken texture.'),
    'kefir': ('quantity', 'Observed plain packs are in g; recipes require ml. Need exact supplier volume/density or separately reviewed authored revision; no numeric unit rewrite.'),
    'varmrökt lax': ('quantity', 'Falkenberg plain hot-smoked packs exist. Verify skinless boneless edible mass; seasoned/glazed products do not prove plain fish.'),
    'bläckfisk': ('assortment', 'Observed breaded rings are not raw cleaned squid. Search unbreaded cleaned raw/frozen product.'),
    'fjälster': ('authored_scope', 'Recipe uses drained grams but casing is normally specified by length/calibre. Inspect original sausage design and source conversion; any redesign must be explicit.'),
    'fläsklever': ('product_relation', 'Search pork liver aliases; exact raw trimmed gram pack required, not liver paste.'),
    'fläsksida med svål': ('product_relation', 'Search fresh pork belly, verify boneless with rind and authored cut/timing; cured side is different.'),
    'groddade mungbönor': ('product_relation', 'Search mung bean sprouts and verify species; other sprouts are excluded.'),
    'gröna linser': ('product_relation', 'GoGreen/Zeta cooked 380/230-g candidates; source plain cooked drained basis before considering dry-to-cooked preparation.'),
    'kaffe': ('preparation', 'Recipe requires measured unsweetened brewed coffee. Source instant/brew preparation with dose, final volume and time; concentrate is not automatically equivalent.'),
    'kalvlägg med ben': ('product_relation', 'Search ossobuco/veal shank. Authored as-sold grams include bone; do not certify edible nutrition from gross mass.'),
    'kokta ägg': ('preparation', 'Need sourced cooked peeled egg yield and cooking/cooling time. Raw edible egg estimate alone does not certify cooked mass.'),
    'mangold': ('assortment', 'Observed beet/chard mix does not prove plain chard. Search exact plain leaves and stalks with trimmed mass/yield.'),
    'matbanan': ('assortment', 'Search plantain/kokbanan, verify authored ripeness and peeled yield; dessert banana excluded.'),
    'matjessill': ('product_relation', 'Eldorado 200/125-g candidate needs declared drained fillet weight; Abba net mass alone is insufficient.'),
    'mungbönsstärkelse': ('assortment', 'Require pure mung-bean starch, not bean flour or glass noodles.'),
    'musslor': ('product_relation', 'Separate live shell-on as-sold from cooked drained meat. Existing water tin and fresh bag require distinct exact source bindings and nutrition restrictions.'),
    'pomelo': ('quantity', '875-g honey pomelo candidate needs rind/membrane/seed-excluding edible yield; do not borrow orange yield.'),
    'risvermicelli': ('product_relation', 'Search thin rice vermicelli and verify rice composition, dry mass and thin shape; mung glass noodles excluded.'),
    'runda risnudlar': ('assortment', 'Require round rice noodles and diameter/form evidence; broad flat noodles are not the same ingredient.'),
    'råa räkor': ('product_relation', 'Ullmo 7315638231041 is labelled raw peeled. Verify deglazed edible gram mass and unchanged frozen preparation handling.'),
    'sattu': ('assortment', 'Require roasted chickpea flour; raw gram flour is not interchangeable without an explicitly authored preparation.'),
    'svart te': ('product_relation', 'Search plain black loose-leaf tea with gram mass; Earl Grey/flavoured teas and counted teabags do not establish this input.'),
    'svarta linser': ('preparation', 'Search cooked black/beluga lentils or a sourced dry cooking chain; do not replace with urad.'),
    'vegansk smördeg': ('product_relation', 'Search ordinary puff pastry too; complete composition must prove vegan ingredients rather than relying on product name.'),
    'vetegluten': ('assortment', 'Need vital wheat gluten flour for seitan; wheat flour and finished seitan excluded.'),
    'apelsinskal': ('preparation', 'Need a separate sourced zest yield and shared fruit balance if flesh is also used; candied peel cannot replace fresh zest.'),
    'edamame i balja': ('product_relation', 'Search edamame/soybeans in pods. Preserve gross as-sold amount and block unsupported edible nutrition.'),
    'filmjölk': ('quantity', 'Existing packs have gram weights. Obtain supplier volume/density for the authored ml amount or explicit reviewed recipe change.'),
    'grapefrukt': ('quantity', 'Search grapefruit/grape fruit labels and exact pack scope; need specific edible yield rather than soft-drink matches.'),
    'grön matbanan': ('assortment', 'Require explicitly unripe plantain and peeled yield; ripe plantain/dessert banana are different.'),
    'hirs': ('assortment', 'Require food-grade hulled millet grains; bread/bowl ingredients and bird feed excluded.'),
    'kastanjer': ('assortment', 'Require cooked peeled edible chestnuts, with usable mass. Candy called Kastanjer is a negative match.'),
    'kokosolja': ('quantity', 'Observed jars are in ml while recipe uses g. Source exact dual declaration or density with conditions; do not assume water density.'),
    'majskolv': ('product_relation', '400-g corn-on-cob packs are candidates. Bind as-sold gross mass and frozen preparation; no assumed kernel nutrition.'),
    'mozzarella': ('product_relation', 'Two as-sold recipes need plain mozzarella without brine. Review pizza block, not breaded sticks or brined net mass.'),
    'padrónpaprika': ('quantity', '200-g exact Padrón packs exist; need edible trimmed yield or supplier edible declaration, not generic pepper factors.'),
    'pektin': ('product_relation', 'Atair 7350053730205 10-g candidate needs composition/gel-strength evidence; pectin mix or jam sugar is not pure pectin.'),
    'popcornmajs': ('product_relation', 'Search plain popping corn kernels, verify no oil/salt and dry gram pack; microwave mix excluded.'),
    'psylliumfröskal': ('product_relation', 'Search fiberhusk/psyllium husks and require pure food-grade husks, not whole seeds.'),
    'risflingor': ('assortment', 'Require dry rice flakes/poha, not puffed rice or oat flakes.'),
    'rökt makrill': ('quantity', 'Search smoked mackerel fillets with skinless boneless edible weight; whole smoked fish needs specific yield.'),
    'vattenmelon': ('quantity', 'Search whole/cut watermelon packs and edible flesh yield; sweets/drinks are false retrieval matches.'),
    'ägg': ('preparation', 'For cooked_drained require the same sourced boiling/peeling chain as kokta ägg; never treat raw edible mass as cooked mass.'),
}


def main(args):
    previous = Path('docs/reviews/recipe-coverage-followup-20261027')
    coverage = json.loads((previous / 'coverage.json').read_bytes())
    blockers = json.loads((previous / 'blockers.json').read_bytes())
    research = json.loads(args.research.read_bytes())['groups']
    source_review = json.loads((previous / 'source-review.json').read_bytes())['groups']
    assessments = json.loads(args.review.read_bytes())['groups'] if args.review else {}
    after = json.loads(args.after.read_bytes()) if args.after else None
    if assessments:
        assert set(assessments) == set(NOTES)
    acquisitions = []
    if args.acquisitions:
        for folder in ('public', 'public-2', 'public-3', 'public-4'):
            for file in sorted((args.acquisitions / folder).glob('*.json')):
                if file.name == 'index.json':
                    continue
                acquisition = json.loads(file.read_bytes())
                if not isinstance(acquisition, dict) or 'item' not in acquisition:
                    continue
                acquisitions.append({k: acquisition[k] for k in ('item', 'source', 'status', 'reason')
                                     if k in acquisition})
    rows = []
    for key, group in blockers['groups'].items():
        indices = group['affected_indices']['estimated']
        if not indices:
            continue
        name = key.split('|')[0]
        classification, action = NOTES[name]
        candidates = []
        for candidate in research.get(name, []):
            p, f = candidate['product'], candidate.get('facts') or {}
            candidates.append({k: p.get(k) for k in ('store_id', 'product_id', 'name', 'brand', 'gtin', 'package_quantity', 'package_unit')}
                              | {'article': f.get('retailer_product_id') or (p.get('source_provenance') or {}).get('retailer_product_id'),
                                 'source_provenance': p.get('source_provenance'),
                                 'retrieval_only': True})
        rows.append({'group': key, 'original_ids': [coverage['variants'][i]['original_id'] for i in indices],
                     'current_ids': [coverage['variants'][i]['current_id'] for i in indices],
                     'blocked_count': len(indices), 'single_remaining_upper_bound': group['single_remaining_group_upper_bound']['estimated'],
                     'definition': group.get('definition'), 'blocker_class': classification,
                     'action': action, 'retained_candidates': candidates,
                     'previous_review': source_review.get(name), 'status': 'under_review',
                     'verification': 'Exact identity/form/quantity evidence; negative near-match and changed-fact regression; current dependency-bound full checkout in both modes and distinct original-ID delta.',
                     'owner_decision': None,
                     'decision_boundary': 'Only a new source/retailer/allowlist or a culinary/scope change requires a separate decision; missing evidence is not approval.'})
        row = rows[-1]
        if name in assessments:
            row['status'], row['finding'] = assessments[name]
        gtins = {str(p.get('gtin')).zfill(14) for p in candidates if p.get('gtin')}
        row['source_acquisitions'] = [a for a in acquisitions
            if str(a['item'].get('gtin', '')).zfill(14) in gtins
            or a['item'].get('retrieval_group') == name
            or (name == 'gelatinblad' and a['item'].get('kind') == 'oetker_gelatin')
            or (name == 'nötkött' and a['item'].get('kind') == 'scan_ryggbiff')
            or a['item'].get('kind') == {'kaffe': 'coffee_preparation',
                'gröna mungbönor': 'mung_preparation', 'psylliumfröskal': 'fiberhusk_denmark'}.get(name, 'not_a_source_kind')
            or (name in {'ägg', 'äggula', 'äggvita', 'kokta ägg'} and a['item'].get('kind', '').startswith('egg_'))]
        if after:
            row['current_verification'] = {}
            for mode in ('exact', 'estimated'):
                scopes = after['modes'][mode]['input_scopes']
                still_blocked = [v['original_id'] for v in after['variants']
                    if any(scopes[s]['name']+'|'+scopes[s]['form']+'|'+scopes[s]['unit'] == key
                           for s in v['modes'][mode]['blocking_scope_ids'])]
                complete = [after['variants'][i]['original_id'] for i in indices
                            if after['variants'][i]['modes'][mode]['basket'] == 'verified']
                row['current_verification'][mode] = {'remaining_group_original_ids': still_blocked,
                                                   'whole_verified_affected_original_ids': complete}
    rows.sort(key=lambda row: (-row['blocked_count'], row['group']))
    assert len(rows) == 76
    unique = {reference for row in rows for reference in row['original_ids']}
    assert len(unique) == 595
    args.output.mkdir(parents=True, exist_ok=True)
    result = {'schema': 'smako-full-coverage-worklist-v1', 'base_main': '9992d34', 'denominator': 2200,
              'active_variants': 2462, 'remaining_original_ids': 595, 'groups': rows,
              'source_report': str(previous / 'coverage.json'), 'candidate_research': str(args.research),
              'candidate_research_sha256': hashlib.sha256(args.research.read_bytes()).hexdigest(),
              'scope': coverage['scope'], 'counts_are_not_promised_gains': True}
    (args.output / 'work-matrix.json').write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
    lines = ['# Full recepttäckning: arbetsmatris', '',
             'Alla 76 grupper och 595 unika ursprungs-ID:n. Full ID- och kandidatkarta i `work-matrix.json`.',
             'Bas: main 9992d34. 999/1 605 insatslösta; 997/1 605 verifierade tvåbutikskorgar.',
             'Exakt och inklusive uppskattningar är skilda mått. Marginalerna är villkorade, inte utlovade vinster.', '',
             '| Grupp | Berörda | Enda grupp | Status | Granskat fynd / nästa åtgärd |', '| --- | ---: | ---: | --- | --- |']
    lines += [f"| {r['group'].replace('|', ' / ')} | {r['blocked_count']} | {r['single_remaining_upper_bound']} | {r['status']} | {r.get('finding', r['action'])} |" for r in rows]
    (args.output / 'work-matrix.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print({'groups': len(rows), 'unique_original_ids': len(unique)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--research', type=Path, default=Path('.local/recipe-coverage-20261027/source-review.json'))
    parser.add_argument('--output', type=Path, default=Path('docs/reviews/recipe-coverage-full-20261027'))
    parser.add_argument('--review', type=Path)
    parser.add_argument('--after', type=Path)
    parser.add_argument('--acquisitions', type=Path)
    main(parser.parse_args())

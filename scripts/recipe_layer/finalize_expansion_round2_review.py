"""Reconcile immutable delivery IDs, issued stage proofs and remaining blockers."""
import argparse
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from app.services.meal_library_content import (
    ROOT,
    encoded,
    identity,
    load_entries,
    manifest_entries,
)
from app.services.recipe_authoring import library_vocabulary
from app.services.recipe_library import current_recipes
from audit_expansion_queue import SOURCE, audit
from coverage_reference import checked_additive_transition, imported_recipes
from review_product_search import review_search_key, review_search_matches

REPORT = Path('docs/reviews/recipe-unblock-round2-20261101')
BASE = '545dad2a1b78566e0bff0c4ff616c053c038cc58'
STAGE_NUMBERS = (*range(1, 34), *range(35, 60))
REJECTED_STAGES = (34,)
EXTRA_QUERIES = {
    'makrutlimeblad': ['makrut', 'kaffir', 'limeblad', 'lime leaves', 'limblad', 'lime leaf'],
    'räkpasta': ['räkpasta', 'räk pasta', 'shrimp paste', 'gapi', 'kapi', 'belacan', 'trassi', 'terasi'],
    'curryblad': ['curryblad', 'curry leaves'], 'epazote': ['epazote'],
    'thaibasilika': ['thaibasilika', 'thai basil'],
    'tapiokastärkelse': ['tapiok', 'tapioc', 'kassav', 'cassav'],
    'tapiokapärlor': ['tapiok', 'tapioc', 'sago', 'sabud'],
    'risflingor': ['risfling', 'rice flake', 'poha'],
    'bläckfisk': ['bläckfisk', 'squid', 'calamar', 'sepia', 'tioarm'],
    'mangold': ['mangold', 'chard'], 'kastanjer': ['kastanj', 'castagn', 'chestnut'],
    'sattu': ['sattu', 'rostat kikärtsmjöl'], 'chana dal': ['chana', 'delade kikärt'],
    'urad dal': ['urad', 'svart lins'], 'masa harina': ['masa', 'majsmjöl'],
    'torkade räkor': ['torkade räk', 'räkor tork', 'dried shrimp'],
    'guajillochili': ['guajillo'], 'pandanblad': ['pandan'], 'achiotepasta': ['achiote', 'annatto'],
    'toor dal': ['toor', 'tuvar', 'tur dal'], 'kashmirichilipulver': ['kashmir'],
    'fermenterade sojabönor': ['fermenter', 'tao jiao', 'taotjo', 'misopasta', 'miso'],
    'krachai': ['krachai', 'fingerroot'], 'getkött': ['getkött', 'goat'],
    'krabbkött': ['krabb', 'crab', 'surimi'], 'amaretti': ['amarett', 'mandelbiskv'],
    'rucola': ['rucola', 'ruccola'], 'stracchino': ['stracchino', 'crescenza'],
    'fontina': ['fontina', 'fontal'], 'rökt provola': ['provol', 'scamorza'],
    'palmsocker': ['palmsocker', 'palm socker', 'jaggery'],
    'ung jackfrukt': ['jackfrukt', 'jackfruit'], 'lotusrot': ['lotus'],
    'blåmusslor med skal': ['mussl', 'mussel'],
    'klibbigt ris': ['klibb', 'sticky rice', 'glutinous', 'sweet rice'],
}
REASONS = {
    'pavbröd': 'Alla tre vada pav-nivåer har separata granskade versioner med mjukt svenskt hamburgerbröd. Standard/utökad utelämnar uttryckligen curryblad men bevarar senapsfrö och ingefära. Utökad använder redan granskat tamarindkoncentrat med ny dos i ml. Brödet har inte lagts in som pav-alias och ingen gram/ml-konvertering antas.',
    'pandanblad': 'Tvålagers kokosgelé och utökad banan i kokosmjölk har godkända uttryckliga versioner utan pandan; respektive receptkälla anger bladen som valfri arom. Bladen har inte fått ett falskt alias. Kvarvarande rätter behöver annan genomgång: blad som omslag, grön färg eller dominerande arom kan inte tas bort generellt.',
    'achiotepasta': 'Tre separata paprikaversioner av citrusbräserat fläsk i pibilstil och tre ancho-versioner av ugnstacos utan achiote är granskade. Kvarvarande mucbipollo-utkast har även epazote, bananblad och degrelaterade hinder; paprika/ancho är inte registeralias eller lika-smak-konverteringar för achiote.',
    'epazote': 'Separata granskade korianderversioner öppnade papadzules och två arroz a la tumbada-varianter. Kvarvarande krabbsoppa och mucbipollo kräver ytterligare sakgranskning och har även andra hinder; koriander är ingen identitetsalias för epazote.',
    'grön papaya': 'De tre kvarvarande recepten är galouti kebab, där rå grön papaya används för enzymatisk mörning av färs. Ett salladsalternativ som äpple eller gurka löser inte den funktionen. Ingen verifierad grön papaya eller uppmätt alternativ mörningsmetod finns i referensen.',
    'klibbigt ris': 'Khao tom mats granskade bakpappersversion stoppades i fullständigt korgprov: inget verifierat köp av glutinöst ris. Sushiris är en separat rundkornig produkt och har inte bytts in i denna ångade kärna. Den lokalt utfärdade testversionen återkallades med bevarade bytes och felkvitto.',
    'fermenterade sojabönor': 'Bredare misosökning hittar Kikuzuru Miso Pasta 300 g, men referensens fakta saknar innehållsdeklaration. Japansk misopasta är inte automatiskt thailändska fermenterade sojabönor/tao jiao; även kapokblommor eller palmsocker återstår i berörda recept.',
    'färska majskorn': 'Referensen visar förvällda frysta majskolvar och tillagade majskärnor. Ingen kvalificerad färsk rå majskärna eller rå kolv med användbar kärnmängd påvisad. Förvälld majs byts inte in i uchepos råa smet som om stärkelsefunktionen var oförändrad.',
    'makrutlimeblad': 'Särskrivningen Lime Blad Torkade dolde två KRUA 25 g-produkter i den tidigare sökningen. Separat torr identitet har nu granskade källkopplingar; pad prik king och khua kling har godkända infusionsversioner. De kvarvarande utkasten kräver färska blad och har även andra hinder. En torr dos eller metod måste författas och provas separat; ingen automatisk färsk-torr-konvertering. Makrutlimeskal i currypasta är fortfarande inte blad.',
    'räkpasta': 'Ingen separat kvalificerad fermenterad räkpasta påvisad. Currypasta, fisksås och färdig räkmat är inte identiska insatser.',
    'thaibasilika': 'Garant-krukorna har cirka 190 g bruttovikt, City Gross 429 g. Ätlig bladmassa är inte verifierad. Styckdos skulle kräva separat inköpsbevis och ny receptversion; samtliga tio utkast har även andra hinder.',
    'palmsocker': 'Sockertyp, förpackningsmängd och form måste bindas; vanligt socker eller kokossocker blir inte automatiskt palmsocker.',
    'bläckfisk': 'Ingen kvalificerad rå rensad bläckfiskmassa påvisad. Panerade ringar/färdigmat får inte ersätta råa gram utan separat receptgranskning.',
    'krabbkött': 'Surimi är en sammansatt fiskprodukt, inte avrunnet krabbkött. Ingen sådan identitetsalias införs.',
    'masa harina': 'Vanligt majsmjöl är inte verifierat nixtamaliserad masa harina. Färdiga tortillas löser inte deg- eller stärkelsefunktionen.',
    'tapiokastärkelse': 'Tapiokapärlor och sammansatta glutenfria mjölblandningar bevisar inte ren tapiokastärkelse.',
    'tapiokapärlor': 'Stärkelsepulver är inte färdiga tapiokapärlor; storlek och tillagning behöver rätt produkt.',
    'tomatillo': 'Färdig tomatillosalsa är granskad som egen insats. Kvarvarande recept kräver annan egen dos och metod; salsa räknas inte som rå tomatillo.',
    'pecorino romano': 'Lagrad pecorino finns som separat granskad ost, utan Romano-/DOP-påstående. Kvarvarande varianter har andra hinder och kräver egen receptgranskning.',
    'vitt vin': 'Matlagningsvin finns som separat granskad volyminsats; det byter inte automatiskt ut originalets vin eller löser övriga hinder.',
    'rött vin': 'Matlagningsvin finns som separat granskad volyminsats; det byter inte automatiskt ut originalets vin eller löser övriga hinder.',
    'rucola': 'Motsvarande bladprodukt finns i underlaget men berörda ostfyllda recept har även andra olösta råvaruhinder. Inte importerade.',
    'blåmusslor med skal': 'Fryst musselkött utan skal är separat granskat. Det kan inte användas med levande musslors mängd, öppningskontroll eller långa ugnstid utan en ny innehållsgranskning.',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main(args):
    current = current_recipes()
    queue, _ = audit(SOURCE, library_vocabulary(current))
    original = {r['source_id']: r for r in queue['variants']}
    previous = json.loads(Path('docs/reviews/recipe-unblock-20261101/recipe-review.json').read_bytes())['recipes']
    records, proofs, modes = [], [], {m: Counter() for m in ('exact', 'estimated')}
    common_scope = None
    for stage in STAGE_NUMBERS:
        review = json.loads((REPORT / f'recipe-review-stage{stage}.json').read_bytes())
        receipt = json.loads((REPORT / f'import-stage{stage}.json').read_bytes())
        raw = (REPORT / f'qualification-stage{stage}.json').read_bytes()
        probe = json.loads(raw)
        pack_raw = (ROOT / f'reviewed-expansion-round2-20261101/standardized-stage{stage}.json').read_bytes()
        assert sha(raw) == receipt['qualification_sha256']
        assert receipt['basket_status'] == 'verified_estimated'
        assert probe['pack_sha256'] == receipt['pack_sha256'] == review['pack_sha256'] == sha(pack_raw)
        assert not probe['input_only'] and probe['deadline_seconds'] == 20
        stable = {k: probe['scope'][k] for k in ('clock', 'conditions', 'facts_sha256',
            'universe_sha256', 'max_stores', 'pantry', 'servings', 'store_ids',
            'imported_reference_ids_sha256', 'recipe_ids_sha256')}
        if common_scope is None:
            common_scope = stable
        assert stable == common_scope
        expected = {r['runtime_id'] for r in review['recipes']}
        for mode, counts in modes.items():
            rows = probe['modes'][mode]['recipes']
            assert {r['id'] for r in rows} == expected and len(rows) == len(expected)
            for row in rows:
                counts[row['status']] += 1
                if mode == 'estimated':
                    assert row['status'] == 'verified' and row['audit']['passed']
        records.extend(review['recipes'])
        proofs.append({'stage': stage, 'variants': len(expected), 'qualification_sha256': sha(raw),
                       'pack_sha256': sha(pack_raw), 'scope': probe['scope'],
                       'modes': {m: dict(Counter(r['status'] for r in probe['modes'][m]['recipes'])) for m in modes}})
    corrections, new_revocations, correction_proofs = {}, {}, []
    corrected_results = {mode: [] for mode in modes}
    for correction_name in ('portion-corrections', 'lamb-corrections', 'selected-product-corrections', 'alternative-portion-corrections', 'pasta-shape-corrections', 'pindi-portion-corrections', 'date-basis-corrections'):
        review = json.loads((REPORT / f'{correction_name}.json').read_bytes())
        receipt = json.loads((REPORT / f'import-{correction_name}.json').read_bytes())
        raw = (REPORT / f'qualification-{correction_name}.json').read_bytes()
        probe = json.loads(raw)
        pack = (ROOT / f'reviewed-expansion-round2-20261101/standardized-{correction_name}.json').read_bytes()
        assert sha(raw) == receipt['qualification_sha256']
        assert receipt['basket_status'] == 'verified_estimated'
        assert probe['scope']['manifest_sha256'] == receipt['after_manifest_sha256']
        assert probe['pack_sha256'] == receipt['pack_sha256'] == review['pack_sha256'] == sha(pack)
        assert not probe['input_only'] and probe['deadline_seconds'] == 20
        assert {k: probe['scope'][k] for k in common_scope} == common_scope
        batch = {r['previous_id']: r for r in review['recipes']}
        assert len(batch) == len(review['recipes']) and not batch.keys() & corrections.keys()
        assert receipt['new_revocations'].keys() == batch.keys()
        corrections.update(batch)
        new_revocations.update(receipt['new_revocations'])
        expected = {r['runtime_id'] for r in batch.values()}
        for mode in modes:
            rows = probe['modes'][mode]['recipes']
            assert {r['id'] for r in rows} == expected and len(rows) == len(expected)
            corrected_results[mode].extend(rows)
        correction_proofs.append({'name': correction_name, 'variants': len(batch),
                                  'qualification_sha256': sha(raw), 'pack_sha256': sha(pack)})
    corrected_ids = {r['runtime_id'] for r in corrections.values()}
    assert corrections.keys() <= {r['runtime_id'] for r in records} | corrected_ids
    for mode, counts in modes.items():
        rows = corrected_results[mode]
        assert {r['id'] for r in rows} == corrected_ids and len(rows) == len(corrected_ids)
        # Count each latest recipe variant once, excluding superseded versions.
        for stage in STAGE_NUMBERS:
            old_probe = json.loads((REPORT / f'qualification-stage{stage}.json').read_bytes())
            for row in old_probe['modes'][mode]['recipes']:
                if row['id'] in corrections:
                    counts[row['status']] -= 1
        for row in rows:
            if row['id'] not in corrections:
                counts[row['status']] += 1
            if mode == 'estimated':
                assert row['status'] == 'verified' and row['audit']['passed']
    manifest = manifest_entries()
    issued = {identity(r): r for r in load_entries(manifest['current'] + manifest['history'])}
    rejected_versions = []
    for stage in REJECTED_STAGES:
        rejected = json.loads((REPORT / f'rejected-stage{stage}.json').read_bytes())
        receipt = json.loads((REPORT / f'import-stage{stage}.json').read_bytes())
        assert receipt['basket_status'] == 'data_blocked_revoked'
        for row in rejected['recipes']:
            assert issued[row['runtime_id']].design.content_sha256 == row['content_sha256']
            assert manifest['revocations'][row['runtime_id']] == row['reason']
            assert row['qualification_sha256'] == receipt['qualification_sha256']
        rejected_versions.extend(rejected['recipes'])
        new_revocations.update(rejected['new_revocations'])
    for row in records:
        assert issued[row['runtime_id']].design.content_sha256 == row['content_sha256']
    accepted = {}
    for row in previous + records:
        row = dict(row)
        followed = set()
        while row['runtime_id'] in corrections:
            assert row['runtime_id'] not in followed
            followed.add(row['runtime_id'])
            correction = corrections[row['runtime_id']]
            assert row['content_sha256'] == correction['previous_content_sha256']
            row.update({k: correction[k] for k in ('runtime_id', 'content_sha256')})
        accepted[row['source_id']] = row
    assert len(accepted) == len(previous) + len(records) and accepted.keys() <= original.keys()
    active = {identity(r): r for r in current}
    for r in accepted.values():
        assert active[r['runtime_id']].design.content_sha256 == r['content_sha256']
    native_raw = args.native_probe.read_bytes()
    native_probe = json.loads(native_raw)
    assert native_probe['input_only']
    native = {r['id']: r for r in native_probe['modes']['estimated']['recipes']}
    pending_native = {r['source_id'] for r in queue['variants'] if r['source_id'] not in accepted
                      and r['status'] == 'native_compatible_not_approved'}
    assert native.keys() == pending_native
    assert all(r['status'] == 'data_blocked' for r in native.values())
    (REPORT / 'remaining-native-inputs.json').write_bytes(native_raw)
    for row in queue['variants']:
        source_id = row['source_id']
        row['source_native_status'] = row.pop('status')
        if source_id in accepted:
            record = accepted[source_id]
            row.update(status='imported_reviewed_version', runtime_id=record['runtime_id'],
                       content_sha256=record['content_sha256'])
        elif source_id in native:
            row.update(status='pending_qualified_input', input_blocks=native[source_id]['input_blocks'])
        else:
            row['status'] = 'pending_register_or_authoring'
    queue['status'] = dict(Counter(r['status'] for r in queue['variants']))
    pending = [r for r in queue['variants'] if r['source_id'] not in accepted]
    rejected_by_source = {r['source_id']: r for r in rejected_versions}
    for row in pending:
        if row['source_id'] in rejected_by_source:
            rejected = rejected_by_source[row['source_id']]
            probe = json.loads(Path(rejected['qualification_path']).read_bytes())
            result, = [r for r in probe['modes']['estimated']['recipes'] if r['id'] == rejected['runtime_id']]
            row['reviewed_alternative_blockers'] = result['input_blocks']
            row['rejected_alternative_id'] = rejected['runtime_id']
    blockers = defaultdict(set)
    for row in pending:
        for key in row['unknown_ingredients']:
            blockers[key].add(row['source_id'])
        for block in row.get('input_blocks', []):
            blockers[block['identity']].add(row['source_id'])
        for block in row.get('reviewed_alternative_blockers', []):
            blockers[block['identity']].add(row['source_id'])
    queue['ranked_register_blockers'] = [
        {**r, 'source_ids': sorted(set(r['source_ids']) - accepted.keys()),
         'variants': len(set(r['source_ids']) - accepted.keys()),
         'only_register_blocker': sum(p['unknown_ingredients'] == [r['identity']] for p in pending)}
        for r in queue['ranked_register_blockers'] if set(r['source_ids']) - accepted.keys()]
    queue['ranked_register_blockers'].sort(key=lambda r: (-r['variants'], -r['only_register_blocker'], r['identity']))
    (REPORT / 'queue.json').write_bytes(encoded(queue))

    reference = json.loads(Path('ci/coverage-reference.json').read_bytes())
    assert common_scope['universe_sha256'] == reference['files']['universe']['sha256']
    assert common_scope['facts_sha256'] == reference['files']['facts']['sha256']
    universe_raw = args.universe.read_bytes()
    assert sha(universe_raw) == reference['files']['universe']['sha256']
    products = json.loads(universe_raw)['universe']['products']
    texts = [(p, review_search_key(p['name'])) for p in products]
    old_ledger = {r['identity']: r for r in json.loads(Path('docs/reviews/recipe-unblock-20261101/ingredient-blockers.json').read_bytes())['blockers']}
    ledger = []
    for key, ids in blockers.items():
        name = key.split('|')[0]
        old = old_ledger.get(key, {})
        queries = list(dict.fromkeys([name, *old.get('search_queries', []), *EXTRA_QUERIES.get(name, [])]))
        query_keys = [review_search_key(q) for q in queries]
        matches = [p for p, text in texts if review_search_matches(text, query_keys)]
        labels = sorted({(p['name'], p.get('brand') or '', str(p['package_quantity']), p['package_unit']) for p in matches})
        ledger.append({'identity': key, 'variants': len(ids), 'source_ids': sorted(ids), 'search_queries': queries,
            'retrieved_product_rows': len(matches), 'retrieved_labels': labels,
            'status': 'pending_source_form_or_content_review',
            'reason': REASONS.get(name, old.get('reason', 'Ingen kvalificerad insats för denna identitet/form är visad. Namnträffar är endast sökunderlag; andra former och tillagningssätt behöver sakgranskning.')),
            'next_action': 'Granska exakt vara, form, mängd och källfakta i befintliga butikskontexter. Om en kulinarisk ersättning behövs, skapa en separat granskad receptversion; bevara originalet.'})
    ledger.sort(key=lambda r: (-r['variants'], r['identity']))
    (REPORT / 'ingredient-blockers.json').write_bytes(encoded({'scope': reference['source_scope'],
        'universe_sha256': sha(universe_raw), 'products_searched': len(products),
        'note': 'Överlappande variantantal. Sökningar i den frysta referensen; noll träffar bevisar inte frånvaro i handeln. Söklistor är inte godkända produkter.', 'blockers': ledger}))

    raw = subprocess.check_output(['git', 'show', BASE + ':backend/app/data/recipes/library-manifest.json'])
    before = json.loads(raw)
    previous_active = current_recipes(generation=len(before['current']))
    after_raw = (ROOT / 'library-manifest.json').read_bytes()
    after = json.loads(after_raw)
    added_entries = after['current'][len(before['current']):]
    old = {identity(r): r.design.content_sha256 for r in load_entries(before['current'] + before['history'])}
    new = {identity(r): r.design.content_sha256 for r in load_entries(after['current'] + after['history'])}
    assert all(new[k] == value for k, value in old.items())
    transition = {'base_commit': BASE, 'before_manifest_file_sha256': sha(raw),
        'after_manifest_file_sha256': sha(after_raw), 'before_manifest': before, 'after_manifest': after,
        'added_entries': added_entries, 'corrected': [],
        'new_revocations': new_revocations,
        'superseded_new_versions': list(corrections.values()),
        'rejected_new_versions': rejected_versions,
        'added': [{'runtime_id': k, 'content_sha256': v} for k, v in new.items() if k not in old],
        'preserved_issued_variants': len(old), 'preserved_active_variants': len(previous_active)}
    checked_additive_transition(transition)
    assert {r['runtime_id'] for r in transition['added']} == (
        {r['runtime_id'] for r in records} | corrected_ids | {r['runtime_id'] for r in rejected_versions})
    references, _ = imported_recipes()
    assert len(references) == 2200
    (REPORT / 'library-transition.json').write_bytes(encoded(transition))
    received_by_base = defaultdict(set)
    admitted_by_base = defaultdict(set)
    for row in queue['variants']:
        received_by_base[row['base_id']].add(row['source_id'])
        if row['source_id'] in accepted:
            admitted_by_base[row['base_id']].add(row['source_id'])
    ingredient_rows = json.loads(Path('backend/app/data/ingredients/expansion-round2-20261101.json').read_bytes())['ingredients']
    summary = {'received_bases': len(received_by_base), 'received_variants': len(original),
        'newly_imported_variants': len(records), 'newly_imported_bases': len({r.design.base_id for r in current}) - len({r.design.base_id for r in previous_active}),
        'corrected_new_versions': len(corrections),
        'corrected_current_variants': len(corrected_ids - corrections.keys()),
        'rejected_local_versions': len(rejected_versions),
        'batch_limited_variants': sum(bool(r['servings_multiple']) for r in corrections.values()),
        'correction_qualification_sha256': correction_proofs[0]['qualification_sha256'],
        'correction_qualifications': correction_proofs,
        'total_incoming_imported_variants': len(accepted), 'total_incoming_bases_with_import': len(admitted_by_base),
        'whole_incoming_families_imported': sum(ids == admitted_by_base.get(base) for base, ids in received_by_base.items()),
        'partly_imported_incoming_families': sum(ids != received_by_base[base] for base, ids in admitted_by_base.items()),
        'pending_variants': len(pending), 'pending_status': dict(Counter(r['status'] for r in pending)),
        'current_bases': len({r.design.base_id for r in current}), 'current_variants': len(current),
        'preserved_issued_variants': len(old), 'original_reference_ids': len(references),
        'new_ingredient_definitions': len(ingredient_rows), 'new_reviewed_product_links': sum(len(r['reviewed_links']) for r in ingredient_rows),
        'basket_modes_new_variants': {m: dict(c) for m, c in modes.items()},
        'remaining_native_probe_sha256': sha(native_raw), 'stages': proofs,
        'cooking_test': 'not_cooked', 'beta_activation': False,
        'scope_note': 'Full single-recipe baskets, max two stores, four dinner or one breakfast/snack portion, empty pantry, no extra diet/nutrition/organic/allergy limits. Unknown served nutrition is not approved under hard limits. Not warm-menu timing.'}
    summary['deliveries'] = {delivery: {'received_variants': len(rows),
        'received_bases': len({r['base_id'] for r in rows}),
        'imported_variants': sum(r['source_id'] in accepted for r in rows),
        'pending_variants': sum(r['source_id'] not in accepted for r in rows)}
        for delivery in sorted({r['source_file'].split('/')[0] for r in queue['variants']})
        for rows in [[r for r in queue['variants'] if r['source_file'].split('/')[0] == delivery]]}
    (REPORT / 'summary.json').write_bytes(encoded(summary))
    print({k: v for k, v in summary.items() if k != 'stages'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--universe', type=Path, required=True)
    parser.add_argument('--native-probe', type=Path, required=True)
    main(parser.parse_args())

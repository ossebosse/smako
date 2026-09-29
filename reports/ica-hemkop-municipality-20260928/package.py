import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

P = Path(__file__).parent
ROOT = P.parents[1]
A = json.loads((P / 'acceptance.json').read_bytes())
I = json.loads((P / 'image.json').read_bytes())
assert A['status'] == 'PASS_LUND_MUNICIPAL_CHAIN' and (P / 'RESULTS.md').exists()
handoff = ROOT / 'docs/HANDOFF.md'
old = (P / 'before/docs/HANDOFF.md').read_bytes()
old_text = old.decode('utf-8')
heading = '# Smako – 28 september 2026: ICA/Hemköp kopplade till gemensamt kommunläge'
current = handoff.read_text(encoding='utf-8')
if not current.startswith(heading):
    assert handoff.read_bytes() == old
    introduction = f'''{heading}

[Samlat resultat](../reports/ica-hemkop-municipality-20260928/RESULTS.md),
[butiksrader och nästa uppdatering](../reports/ica-hemkop-municipality-20260928/STORES.md),
[köp och audit](../reports/ica-hemkop-municipality-20260928/OFFERS.md),
[acceptans](../reports/ica-hemkop-municipality-20260928/acceptance.json).

Lund PASS i isolering: samma kommunval genom inventering, källurval, OWN, PriceUniverse och beständig uppdateringsstatus. ICA 12 butiker/277 godkända OWN/275 serverade; Hemköp 3/18/18, inklusive Dalby utan onlinekatalog. Total serving 42 003 → 42 085. Södra Sandby, Genarp och Veberöd inkluderas på verifierad kommuntillhörighet. Fem obligatoriska baser, Coop-v4 och X:-tra bevaras.

Ordinarie publicering/reload, nästa rebuild med synligt frivilligt Hemköp-fel och omstart ger identisk produkthash. Fyra HTTP-profiler 201/445,29 kr, audit och identisk sparning/GET efter omstart. Förfallen ICA-inventering behöll alla prisobservationer och godkännanden utan prisanrop. {A['unique_tests_passed']} tester, Ruff/compileall och 592 runtimefilhashar PASS. Isolerad image `{I['tag']}` (`{I['image'][7:19]}…`); ingen produktionsaktivering, Windows- eller schemaändring.

Malmö: ICA 24 verifierat innanför, 23 insamlade/560 OWN; Hemköp 4/24 OWN. Två identiska PU-kandidater med 580 produkter, men **0 aktiverad serving**: ordinarie kontrollkorg är ofullständig, ingen Lund-baspolicy används. Bunkeflostrand saknar verifierad strukturerad erbjudandelänk; 45 ICA-träffar har okänd kommunstatus. Full Malmö-publicering, äldre PurchaseTerms, komplexa kampanjvillkor, Lidl/Willys-täckning och historisk Lidl-fixture kvarstår separat. Tidigare femmiddagsmilstolpe, originalpolicy/Primat och sparade användarval bevaras.

---

'''
    handoff.write_bytes(introduction.encode('utf-8') + old)
assert handoff.read_bytes().endswith(old)
prior = json.loads((ROOT / 'reports/coop-source-binding-20260928/PACKAGE.json').read_bytes())
bad = [n for n, h in prior['evidence_hashes'].items()
       if n != 'docs/HANDOFF.md' and hashlib.sha256((ROOT / n).read_bytes()).hexdigest() != h]
assert not bad
assert hashlib.sha256(old).hexdigest() == prior['evidence_hashes']['docs/HANDOFF.md']
baseline = json.loads((P / 'baseline.json').read_bytes())['app']['files']
files = {**baseline, **I['changed_files']}
assert all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest for name, digest in files.items())
evidence = [f for f in P.rglob('*') if f.is_file() and f.name != 'PACKAGE.json' and '__pycache__' not in f.parts]
evidence += [ROOT / n for n in I['changed_files']]
evidence += [ROOT / 'docs/HANDOFF.md', *[ROOT / n for n in [
    'grocery_data/tests/test_ica_area_offers.py', 'grocery_data/tests/test_ica_hemkop_municipal_link.py',
    'grocery_data/tests/test_hemkop_municipal_job.py', 'grocery_data/tests/test_hemkop_physical_offers.py',
    'backend/tests/test_ica_hemkop_municipal_provider.py',
    'grocery_data/tests/fixtures/hemkop-physical-20260928.json.gz',
    'grocery_data/tests/fixtures/hemkop-municipal-register-20260928.json.gz']]]
result = {'created_at': datetime.now(UTC).isoformat(), 'image': I, 'acceptance': A,
    'application_source_files': len(files), 'application_file_hashes': files,
    'policy_sha256': hashlib.sha256((P / 'policy.json').read_bytes()).hexdigest(),
    'production_activation': False, 'original_policy_changed': False, 'windows_or_active_schedules_changed': False,
    'prior_evidence': {'unchanged': len(prior['evidence_hashes']) - 1,
        'handoff_only_prepend': True, 'original_handoff_preserved_exactly': True, 'mismatches': bad},
    'isolated_remote_root': '/var/tmp/smako-ica-hemkop-municipality-20260928',
    'rollback_candidate': '/var/tmp/smako-coop-source-binding-20260928',
    'remaining_tasks': ['ICA Bunkeflostrand structured source binding', '45 ICA unknown municipality records',
        'full Malmö base policy and publication', 'older PurchaseTerms binding', 'new complex campaign conditions',
        'Lidl/Willys coverage', 'historical Lidl fixture', 'original-policy Primat blocker'],
    'evidence_hashes': {str(f.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(f.read_bytes()).hexdigest()
                       for f in sorted(set(evidence))}}
(P / 'PACKAGE.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print('Package sealed:', len(result['evidence_hashes']), 'evidence files')

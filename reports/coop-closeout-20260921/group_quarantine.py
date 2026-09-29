"""Read retained evidence; disjoint primary causes plus deduplicated overlaps.

Food/other is a report-only review of the actual advertised group title and
its variant list, not a nutrition qualification or a new import allowlist.
"""
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / 'coop-physical-fix-20260921'
result = json.loads((PRIOR / 'final-acceptance-v2/result.json').read_bytes())
# Reviewed explicit parent titles in these retained official source responses.
OTHER = {'Tvättmedel/Sköljmedel', 'LED-lampor', 'Tandkräm', 'Maskindisktabletter',
         'Kaffekopp', 'Paninigrill', 'Skärbräda 2-pack', 'Digital stektermometer', 'Glitterset'}
FOOD = {'Bregott', 'Färsk kycklingfilé', 'Röda Äpplen', 'Konserverade tomater', 'Läsk',
        'Nötfärs', 'Lagrad ost', 'Chokladkakor', 'Falukorv', 'Spare ribs', 'Blomkål',
        'Svenska päron', 'Färsk pasta fettuccine', 'Vetemjöl', 'Vitkål', 'Salladsmix',
        'Müslibar', 'Kolsyrat vatten', 'Ekologiska rödbetor', 'Färskost', 'Yoghurtkvarg',
        'Frysta bär/frukter', 'Matpaj', 'Tomatketchup', 'Gnocchi', 'Färsk fläskkarré',
        'Bacon 3-pack', 'Glass flerpack', 'Kycklinglårfilé', 'Dressing', 'Hårdost',
        'Läsk 6-pack', 'Kakor', 'Färsk lammrostbiff', 'Te', 'Räkor i lake', 'Makaroner',
        'Kombucha', 'Mjukost', 'Parmigiano Reggiano', 'Fruktdryck 3-pack',
        'Pizza Ristorante', 'Juice', 'Stor kaviar', 'Hela kaffebönor',
        'Vegetariskt protein', 'Kryddiga korvar', 'Olivolja Classico', 'Tex-mex'}
# First applicable cause only in the primary table. This is a reporting order,
# not a relaxation or a claim that repairing this cause fixes all other causes.
PRIORITY = ['purchase_price_role_unverified', 'source_is_pil_requires_review',
            'deposit_amount_unverified',
            'mixed_variant_group_checkout_unsupported_without_ordinary_price',
            'approximate_package', 'fixed_purchase_package_unverified',
            'piece_purchase_contract_not_supported', 'bounded_checkout_contract_unverified']
LABELS = {'purchase_price_role_unverified':'Procentpris utan köpprisgrund',
          'source_is_pil_requires_review':'Oklar isPil-markering',
          'deposit_amount_unverified':'Obelagd pant',
          'mixed_variant_group_checkout_unsupported_without_ordinary_price':'Blandat variantgruppköp utan stödd restprismodell',
          'approximate_package':'Ungefärlig förpackning',
          'fixed_purchase_package_unverified':'Fast köp-/förpackningsmängd obelagd',
          'piece_purchase_contract_not_supported':'Styckkontrakt saknar köpstöd',
          'bounded_checkout_contract_unverified':'Köpavtal ej kvalificerat'}
rows=[]
for store in result['stores']:
    products=json.loads((PRIOR/f"final-acceptance-v2/{store['store']}-extracted.json").read_bytes())['products']
    by_id={p['external_product_id']:p for p in products}
    for decision in store['qualification']['decisions']:
        if not decision['blockers']:
            continue
        p=by_id[decision['source_id']];offer=p['offers'][0]['source_payload']
        title=offer['source_record']['content'].get('parentTitle') or offer['source_record']['content']['title']
        reasons=sorted(set(decision['blockers']))
        primary=next((key for key in PRIORITY if key in reasons),reasons[0])
        rows.append({'store':store['store'],'name':p['name'],'source_id':decision['source_id'],
                     'group_id':offer['group_offer_id'],'group_title':title,
                     'category':'livsmedel' if title in FOOD else 'övrigt' if title in OTHER else 'okänt',
                     'classification_evidence':'reviewed source parentTitle + its actual variant list',
                     'primary_reason':primary,'all_reasons':reasons,
                     'raw_reason_occurrences':len(decision['blockers']),
                     'observed_at':store['observed_at'],'source_hash':store['source_hash'],
                     'source_url':store['official_url']})
assert len(rows)==379 and len({(r['store'],r['source_id']) for r in rows})==379


def aggregate(keys, overlaps=False):
    groups=defaultdict(list)
    for r in rows:
        for reason in r['all_reasons'] if overlaps else [r['primary_reason']]:
            entry={**r,'reason':reason}
            groups[tuple(entry[k] for k in keys)].append(r)
    return [{**dict(zip(keys,k,strict=True)),'variants':len(v),
             'offer_groups':len({(r['store'],r['group_id']) for r in v})}
            for k,v in sorted(groups.items())]


primary=aggregate(['store','category','reason'])
overlap=aggregate(['store','reason'],True)
summary=[]
for account in ['3839','3815']:
    for category in ['livsmedel','övrigt','okänt']:
        selected=[r for r in rows if r['store']==account and r['category']==category]
        summary.append({'store':account,'category':category,'variants':len(selected),
                        'offer_groups':len({r['group_id'] for r in selected})})
combinations=defaultdict(list)
for r in rows:combinations[(r['store'],tuple(r['all_reasons']))].append(r)
combinations=[{'store':k[0],'reasons':list(k[1]),'variants':len(v),
               'offer_groups':len({r['group_id'] for r in v})} for k,v in sorted(combinations.items())]
report={'denominator':379,'classification_scope':'report only, not recipe/nutrition eligibility',
        'primary_order':PRIORITY,'summary':summary,'primary':primary,'overlap':overlap,
        'disjoint_reason_combinations':combinations,'rows':rows}
(HERE/'quarantine-grouped.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
lines=['# Karantän: 379 unika butik–variantposter', '',
       'Underlag: föregående Exakta bortfall, slutacceptans och sparade verkliga källsvar från 21/9 kl. 09:44 Stockholm. Ingen ny hämtning.', '',
       '## Livsmedel / övrigt / okänt per butik', '',
       '| Butik | Klass | Varianter | Erbjudandegrupper |','|---|---|---:|---:|']
for r in summary:lines.append(f"| {r['store']} | {r['category']} | {r['variants']} | {r['offer_groups']} |")
lines+=['','Livsmedel inkluderar drycker och godsaker; det betyder inte recept-/näringsgodkänt. Övrigt omfattar uttryckliga hushållsvaror, hygien och lampor. Klassningen är en rapportgranskning av källtitel och variantlista, inte en ny produktionsregel. Okända titlar skulle hamna i okänt. Alla radbevis och klassningar finns i `quarantine-grouped.json`.','',
        '## En huvudorsak per variant – inga dubbla totalsummor','',
        'Prioritet: procentpris → isPil → pant → variantgruppköp → ungefärlig mängd → obelagd förpackning → styckstöd → övrigt köpavtal. Detta är endast presentationsordning. Att lösa huvudorsaken löser inte automatiskt överlappande hinder.','',
        '| Butik | Klass | Huvudorsak | Varianter | Berörda grupper |','|---|---|---|---:|---:|']
for r in primary:lines.append(f"| {r['store']} | {r['category']} | {LABELS.get(r['reason'],r['reason'])} | {r['variants']} | {r['offer_groups']} |")
lines+=['','Variantkolumnen summerar exakt till 379. Gruppantal får inte summeras mellan huvudorsaker: olika varianter i samma grupp kan ha olika huvudorsak. Gruppnyckeln är fysisk butik + source group-ID; liknande annonser i olika butiker slås inte ihop.','',
        '## Alla felorsaker – överlappande, varje variant högst en gång per orsak','',
        '| Butik | Felorsak | Unika varianter | Grupper |','|---|---|---:|---:|']
for r in overlap:lines.append(f"| {r['store']} | `{r['reason']}` | {r['variants']} | {r['offer_groups']} |")
lines+=['','Den äldre rapporten räknade felkodsförekomster, även när samma felkod fanns två gånger på samma variant. Denna tabell deduplicerar även dessa upprepningar. Alla ömsesidigt uteslutande kombinationer finns i JSON (`disjoint_reason_combinations`); deras variantantal summerar också till 379.','',
        'Stora grupper är inte lika många oberoende fel: Bulltoftas 74 procentposter är EN LED-annons. Blandade gruppköp behöver stöd för gemensam varukorg mellan belagda varianter, inte en text- eller prisjustering. Pant och isPil kräver ytterligare verifierat underlag. Inget av detta släpps genom denna avslutning. Mjölet ingår redan i de 112 radgodkända, inte i karantänens 379.']
(HERE/'QUARANTINE.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps({'summary':summary,'primary':primary},ensure_ascii=False))

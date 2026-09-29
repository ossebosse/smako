"""Render the bounded text-import evidence; no collection or activation."""

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
result = json.loads((ROOT / "final-acceptance/result.json").read_bytes())
coop = json.loads((ROOT / "coop-regression/result.json").read_bytes())
ads = [ad for page in result["pages"] for ad in page["ads"]]
decisions = {d["source_id"]: d["blockers"] for d in result["qualification"]["decisions"]}
reasons = {
    "exact_advertised_variant_unverified": "Flera annonserade varianter; exakt köpvariant inte belagd",
    "fixed_package_unverified": "Fast förpackningsinnehåll saknas eller är intervall/ca/multipack",
    "independent_price_package_check_unavailable": "Oberoende jämförpriskontroll stöds inte eller saknas",
    "comparison_unit_basis_unverified": "Jämförprisets enhet matchar inte belagd förpackningsenhet",
    "container_deposit_applicability_unverified": "Vätska: behållare/panttillämplighet inte kvalificerad av textadaptern",
    "deposit_amount_unverified": "Pant tillkommer men belopp/antal inte belagt",
    "additional_condition_requires_review": "Uttryckligt variant-/behörighetsvillkor ännu inte kvalificerat",
    "weight_price_not_supported_for_concrete_purchase": "Kilopris bevarat; konkret köpmängd saknar stödd kontraktsform",
    "printed_comparison_conflicts_with_purchase": "Tryckt jämförpris motsäger tilldelat köppris/förpackning",
    "purchase_limit_unparsed": "Text med Max ännu inte säkert klassificerad som köpgräns/annan begränsning",
}


def price(ad):
    if ad["required_packages"] > 1:
        return f"{ad['required_packages']} för {ad['purchase_price']} kr"
    return f"{ad['purchase_price']} kr/{ad['sale_unit']}"


def spans(items):
    return ", ".join(f"{s['id']} (block {s['block']})" for s in items)


lines = [
    "# X:-tra Skansvägen – sid- och annonsvis texttäckning",
    "",
    f"Verifiering: **{result['verification_at']}**. Ursprunglig observation: **{result['observed_at']}**, inte föryngrad.",
    "",
    ("[Officiell butik](https://x-tra.se/butiker/skansvaegen) · "
    "[Officiell PDF](https://dr.coop.se/Butik/?store=216525). "
    "Butiks-ID 3658, PDF-konto 216525, Skansvägen 2, Lunds kommun 1281."),
    "",
    (f"PDF SHA-256: `{result['document_sha256']}`. Metadata binder dokumentet till X:-tra Skansvägen. "
    "Tryckt v.39: 21–27 september 2026; varje sidas utgåve-ID cx_2639 verifieras. "
    "Sida 8 begränsas till torsdag 24–söndag 27 september. Alla åtta sidor finns."),
    "",
    ("**Partiell täckning.** 57 identifierade textannonser har klassificerats. "
    "Antalet eventuella ytterligare bildannonser/okända annonser är okänt, inte noll. "
    "Ingen bildanalys, OCR eller extern tjänst används. Textblock, typsnitt och koordinater "
    "återges i JSON; en sida med läsbar text är inte bevis på komplett annonsidentifiering."),
    "",
    "| Sida | Textannonser/priser | OWN | PU nu | Blockerade köp | Okända ytterligare annonser |",
    "|---|---:|---:|---:|---:|---|",
]
for p in result["pages"]:
    lines.append(
        f"| {p['page']} | {len(p['ads'])} | {sum(a['own'] for a in p['ads'])} | "
        f"{sum(bool(a['price_universe_product_ids']) for a in p['ads'])} | "
        f"{sum(not a['own'] for a in p['ads'])} | okänt |"
    )
lines += [
    "",
    ("Totalt 10 importerade i isolerat OWN, 9 i PriceUniverse för 22 september, "
    "1 framtida (Snacktomater), 47 blockerade för köp. Ingen tidigare X:-tra-import finns "
    "i det jämförda kommununderlaget: 0 redan täckta. Förkörningar/replay är inte nya "
    "prisobservationer eller ytterligare nya annonser."),
    "",
    ("Fullständigt snapshotkontrakt: **10/57 = 17,54 %**, under oförändrade 95 %. "
    "Snapshot är BROKEN; det uttryckliga partiella radkontraktet publicerar endast de tio "
    "godkända raderna i isolerad OWN. 57/57 gick att representera som SourceProduct/SourceOffer "
    "med råfält; detta är inte 57 godkända köp. Kvalitetsvarningens kritiska larmnivå 70 % "
    "är separat från snapshotkravet på 95 %."),
    "",
    "## Konkreta köp och källjämförelse",
    "",
    ("Separat kontrollavläsning av originalets textblock finns i testfixturens "
    "`manual-reference.json`. Det är inte extern mänsklig bildgranskning. "
    "Köppris måste tillhöra samma annonskolumn/rad, ha entydiga decimalsiffror/enhet "
    "och dessutom stämma med tryckt jämförpris och belagd förpackning."),
    "",
    "| Annons | Köp | Jämförpris | Referens (inte ordinarie köppris) | Text-/prisspann | Audit |",
    "|---|---|---|---|---|---|",
]
for title in ["Couscous", "Ekologisk tomatpuré", "Gul lök i nät"]:
    a = next(a for a in ads if a["title"] == title)
    lines.append(
        f"| [s{a['page']}a{a['ad']} {title}]({result['source_url']}#page={a['page']}) | "
        f"{price(a)}, {a['package_quantity']} {a['package_unit']}/förpackning | "
        f"{' '.join(a['comparison_text'])} | {' '.join(a['reference_prices']) or 'saknas'} | "
        f"text {spans(a['text_spans'])}; pris {spans(a['price_spans'])} | PASS |"
    )
lines += [
    "",
    ("Alla tre: publika priser utan medlemskrav, 21–27 september, ingen köpgräns "
    "eller pant angiven i respektive annons. Inget ordinarie köppris eller GTIN har skapats. "
    "Tomatpuréns 30 kr gäller två 200 g-förpackningar; ett obelagt köp av en för 15 kr stoppas. "
    "Löken köps som ett helt nät på 3 kg för 19,90 kr. Referensen 19:78 för couscous "
    "respektive 19:77 för tomatpuré används inte som restpris."),
    "",
    ("Tre ingrediensmatchningar och köp/audit PASS, ingen näringsgodkänd helmeny. "
    "Flytande honung når OWN/PU men matchning till ingrediensen honung avvisas "
    "(produktens canonical_name är flytande honung). Ingen ny matchningsregel införs."),
    "",
    "## Samtliga identifierade annonser",
    "",
    ("Varje rad länkar till rätt PDF-sida. Fullständiga koordinater, råtexter, prisdelar, "
    "villkor, källhash, observation, SourceOffer-ID och PU-ID finns i "
    "`final-acceptance/result.json` och `source-products.json`."),
    "",
    "| Sida/ruta | Titel | Annonserat pris | Medlem | Period | OWN/PU/status | Exakt återstående hinder |",
    "|---|---|---|---|---|---|---|",
]
for a in ads:
    state = (
        "importerad OWN + PU"
        if a["price_universe_product_ids"]
        else "importerad OWN; framtida, ej PU nu"
        if a["own"]
        else "extraherad; köp blockerade"
    )
    blocker = (
        "; ".join(reasons.get(b, b) for b in a["blockers"])
        or "inga köphinder i aktuellt textkontrakt"
    )
    lines.append(
        f"| [s{a['page']}a{a['ad']}]({result['source_url']}#page={a['page']}) | {a['title']} | "
        f"{price(a)} | {'ja' if a['member_only'] else 'nej'} | {a['valid_from']}–{a['valid_to']} | {state} | {blocker} |"
    )
lines += [
    "",
    "## Avgränsade kvarstående hinder",
    "",
    ("Bregott s2a12: 49,90 kr, 750 g, tryckt jämförpris 78,67 kr/kg; "
    "49,90/0,75 = 66,53 kr/kg. På s1a4 stämmer 66,53, men variantgruppen är ändå "
    "blockerad. Ingen av sidorna används för att tyst skriva över den andra."),
    "",
    ("Vatten s6a1: 34 kr, medlemspris, 6 × 1,5 liter och ”Pant tillkommer”. "
    "Belopp saknas och multipack/variantgrupp är inte kvalificerade. "
    "Övriga vätskors konservativa behållarspärr är en adapterbegränsning; "
    "den innebär inte ett påstående om att exempelvis olivolja har pant."),
    "",
    ("Kilopriser bevaras som prisuppgifter, men ca-vikt omvandlas inte till en "
    "fast paketvikt. Intervall och blandade varianter får inte en påhittad SKU/GTIN. "
    "Gemensamma villkor och sidans kortare datum finns med källspår i SourceOffer. "
    "Begränsade medlemsköp kräver dessutom ett belagt kampanj-ID över X:-tra-butiker; "
    "en butiksspecifik dokumenthash duger inte för ett gemensamt hushållstak."),
    "",
    ("Parsern är återanvändbar för samma dokumentmall och härleder datum, sidor, "
    "annonskolumner och produkter ur indata. Ändrad/okänd layout spärras; den är "
    "inte en generell parser för alla PDF-mallar. Bildinnehåll kan innehålla uppgifter "
    "som denna textinsats inte identifierar. Full reklambladstäckning är därför inte belagd."),
    "",
    "## Överlappande orsaker (summeras inte till 47)",
    "",
]
counts = Counter(b for a in ads for b in a["blockers"])
for b, n in counts.most_common():
    lines.append(f"- {n}: {reasons.get(b, b)} (`{b}`).")
(ROOT / "COVERAGE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
summary = {
    "xtra": {
        "identified_text_ads": len(ads),
        "unknown_additional_ads": None,
        "pages_expected": 8,
        "pages_read": len(result["pages"]),
        "own": sum(a["own"] for a in ads),
        "price_universe_current": result["price_universe_count"],
        "future_imported": sum(a["own"] and a["period_status"] == "future" for a in ads),
        "blocked": sum(not a["own"] for a in ads),
        "already_covered_before_stage": 0,
        "new_source_observations_this_stage": 0,
        "new_qualified_price_records_vs_previous": 10,
        "runtime_seconds": result["runtime_seconds"],
        "source_observed_at": result["observed_at"],
        "verified_at": result["verification_at"],
        "source_age_hours": result["source_age_hours"],
        "ingredient_checkout_audit_pass": 3,
        "nutrition_qualified_menu": False,
        "blocker_overlaps": dict(counts),
    },
    "coop": {
        "stores": len(coop["stores"]),
        "accepted_source_variants": sum(r["accepted"] for r in coop["stores"]),
        "quarantined": sum(r["rejected"] for r in coop["stores"]),
        "price_universe_current": coop["price_universe_count"],
        "expired_since_previous_verification": 6,
        "replayed_checkout_audit_pass": len(coop["proofs"]),
        "prior_additional_checkout_proofs_preserved": 2,
        "runtime_seconds": coop["runtime_seconds"],
    },
    "production_activation": False,
    "external_calls_this_stage": 0,
}
(ROOT / "coverage-final.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(summary, ensure_ascii=False))

# Kommunparameter genom Coop, Stora Coop och X:-tra

Verifierat 2026-09-22 i den separata Windows-arbetskopian, Python 3.12. Ingen aktivering, serverändring eller schemaändring. Det bestående kravet är även inskrivet i projektets AGENTS.md.

Samma kommando/kod har inventerat och behandlat Lund **1281** och Malmö **1280**. Kommunbeviset är butikens officiella position mot SCB RegSO 2025, version 2025-01-01; position inom 10 meter från gräns förblir osäker. Adressort är inte kommungräns. Genarp, Veberöd och Oxie ingår genom positionen. Tidigare användarprofiler, adressortsläge och butiksval har inte ändrats.

| Resultat | Lund | Malmö |
|---|---:|---:|
| Nationellt upptäckta och redovisade butiker | 778 | 778 |
| Verifierat inom kommunen | 10 | 18 |
| Okänd kommuntillhörighet | 0 | 1 |
| Verifierat utanför kommunen | 768 | 759 |
| Coop/Stora Coop med kvalificerade poster | 9 av 9 | 11 av 16 |
| Strukturerade poster i OWN och isolerat PU | 493 | 532 |
| X:-tra med textimport | 1 av 1 | 1 av 2 |
| X:-tra: OWN / aktuella i isolerat PU | 10 / 9 | 10 / 9 |
| Totalt aktuella butik–produktposter i isolerat PU | 502 | 541 |

Detta är partiell erbjudandetäckning. Nationella publicerade register har följts, men deras fullständighet mot alla verkliga butiker är inte oberoende belagd. Alla 778 rader finns i [Lunds lista](STORES-1281.md) respektive [Malmös lista](STORES-1280.md), inklusive utanför, okända och misslyckade. [COVERAGE.md](COVERAGE.md) visar kommunbutikernas individuella utfall och officiella länkar.

## Ändring och verifierad kedja

1. `--municipality-code` går till befintlig `GeographicArea(mode="municipality")` och `discover`. Ingen handskriven runtime-butikslista.
2. Gemensamma `approved_municipal_stores` räknar om medlemskap mot kod och bundet kommunbevis. En sparad etikett `inside` räcker inte. Fel kommunetikett kan inte importera andra kommunens butiker.
3. Coop/Stora Coop väljs från inventeringen och använder befintlig butiksspecifik browsertransport. X:-tra väljs ur samma inventering och hämtar aktuell officiell butikssida, därifrån dess faktiska `weeklyOffersLink` och ytterligare publicerade dokumentlänkar. ID, konto och adress måste stämma.
4. Befintliga SourceOffer, radvalidering, collector, isolerat OWN och providers används. X:-tra återanvänder textlayoutparsern och importen; varken produktlistor, konton eller kampanjdatum är inbyggda i nya koden.
5. PriceUniverse bygger på respektive kommuns egna godkända produkter och snapshots. Kommunens nyckel ingår i kandidatens versionsidentitet. Inga baspriser fabriceras. Coop Online berörs inte.
6. `update-selection.json` innehåller alla upptäckta butiker, kommunstatus, val, källsignatur, senaste lyckade observation, försök och nästa tid. Förändrad källa blir förfallen; omstart bevarar tidsplan. Befintlig kampanjpolicy återanvänds: kampanjgräns med förberedelse en timme före, högst 72 timmar till kontroll, 12 timmar för tomt/obundet flöde, begränsade felåterförsök från 15 minuter. Förslag till ny inventering efter 72 timmar sparas utan att skjutas fram vid omstart. Ingen ny driftloop har installerats.

En kontroll utan förfallet arbete gör **noll externa prisanrop** och bygger **ingen tom ersättningskandidat**. Om inventering är förfallen ska ordinarie anrop utelämna `--inventory` och därmed hämta nya register. `--inventory` är ett uttryckligt val av bevarat underlag och behåller dess observationer. Nya eller ändrade butiker kommer då med genom samma kod.

## Faktisk nätverifiering respektive återspelning

- Färska officiella register och gränsunderlag: 22 september, cirka **10:28–10:29 Europe/Stockholm**. Sparat under `live/{kod}/inventory`.
- Färsk butiksspecifik strukturerad insamling: **10:36:38–10:40:16**. Alla nio Lundsbutiker och alla sexton verifierade Malmöbutiker försöktes. Körtid för respektive strukturerad insamling: **51,884 s** och **166,027 s**. Sparat under `live/{kod}/pipeline/collection`.
- Slutlig X:-tra-nätinsamling: Skansvägen **10:41:13**, Söderkulla **10:41:21**. Publicerad PDF hämtades från respektive butik; se nedan. Första kontrollen krävde felaktigt en synlig HTML-länk trots att länken finns i officiell strukturerad siddata. Det felet rättades; de första misslyckade kontrollresultaten är bevarade, inte slutresultat.
- `live/{kod}/final` återanvänder dagens oförändrade strukturerade källsvar och gör nya X:-tra-anrop. Det föryngrar inte Coop-observationerna.
- Slutkodens ytterligare `final-code-replay` körs helt utan nätverk på samma sparade källor. Identiska butiksvärden/observationer och **502/541** verifieras i `final-code-verification.json`. X:-tras checkout/audit verifierades igen, cirka **1,9/2,0 s** per import. Det är regression, inte ny prisinsamling.
- 105 unika berörda tester passerade (103 i huvudsuiten; slutlig körning av kommunfilens tio tester omfattar två nytillkomna). Ruff och compileall passerade. JUnit-resultat finns i `tests.xml` och `tests-contract-final.xml`.

Tester omfattar båda kommunerna, X:-tra utan synlig HTML-ankarlänk, ändrad utgåvelänk, fel butik/konto/adress, fel kommun, källbyte, omstart, retry, inget förfallet arbete, okänd layout, befintlig ICA-provider och tidigare Coop-näringskoppling. Pris-/observationsbindning och textlayoutens villkor fortsätter att prövas i de befintliga X:-tra-testerna. Syntetiska mutationer är feltester; faktiska källutfall ovan kommer från nätinsamlingen.

## X:-tra: separat källa och utgåva per butik

| Butik | Upptäcktskälla → faktisk PDF | SHA256 för hämtad PDF | Sidor / textannonser / karantän | Giltighet |
|---|---|---|---|---|
| Skansvägen 3658 | [officiell butik](https://x-tra.se/butiker/skansvaegen) → [utgåva](https://dr.coop.se/Butik/?store=216525) | `d42781fdb753e5b5788ad93ab91f50d72c48239b93419bec5c9145665450e2e1` | 8 / 57 / 47 | 21–27 september; sidan 8: 24–27 september |
| Söderkulla 3646 | [officiell butik](https://x-tra.se/butiker/soederkulla) → [utgåva](https://dr.coop.se/Butik/?store=216532) | `d56feb59d59324211a001797c6c4ade3fb0bb447d7fe520d5a9250e8c3e25105` | 8 / 57 / 47 | 21–27 september; sidan 8: 24–27 september |

Dokumentmetadata anger respektive butik; länkar/konton, titel, sidantal, bytes/hash och verklig observation binds av programmet. Innehåll som råkar vara lika mellan två dokument kopieras inte mellan butikerna. Originalbytes och sidans relevanta publika butiksfält är sparade. Ett upprepat dokument kan endast dedupliceras inom samma butik.

För vardera butiken: Couscous, ekologisk tomatpuré och gul lök går genom befintlig ingrediensmatchning, checkout och audit (PASS). Flytande honung är korrekt prisimporterad men blockeras av ingrediensmatchningen. Exakta annonser, textblock, produkt-ID, köpberäkningar och audit finns i `live/{kod}/final/xtra-{id}/1/import/result.json`. Detta bevisar separata ingrediensköp, inte en näringsgodkänd helmeny.

Nio textposter är aktuella; den tionde börjar 24 september och finns endast framtida i OWN. Inga kampanjdatum, pantbelopp, GTIN eller ordinarie restpriser har skapats. En fungerande textmall för dessa två dokument är **inte stöd för alla utgåvor**. Okänd textlayout får `unsupported_text_layout`, obunden dokument-/butiksgiltighet blockerar hela källan, bildberoende dokument får `image_dependent`. Antalet oidentifierade bildannonser förblir `null`, inte noll. Därför är `complete=false` även när åtta av åtta PDF-sidor har lästs.

## Exakta kvarstående hinder

- **Stora Coop Stadion 3853 och Coop Forum Jägersro 3850:** `invalid offer quantity`, klassat som gemensamt parser-/källfel. Samtliga 535 varianter per källa spärras. Ingen kvalitetsgräns har sänkts och ingen generell karantänutvidgning har gjorts. Namn/koncept från befintligt register bevaras, inklusive det äldre Forum-namnet.
- **Coop Malmö Central 3833, Kornettsgatan 3835 och Djupadal 3831:** `ConnectorFetchError` i `public_offer_fetch`. Befintlig transport rapporterar inte mer detaljerat HTTP-underlag i denna körning; orsaken ska inte gissas till exempelvis 403. Hämtade annonsantal är okända. Inga blockerade anrop har loopats.
- **X:-tra Nydala 3829:** officiell butikssidas strukturerade `weeklyOffersLink` saknas. [Butikssidan](https://x-tra.se/butiker/nydala) återkontrollerades en gång för att bevara just detta råbevis i `nydala-source-evidence/store-page.json`; inga gissade PDF-/prisanrop gjordes. Butiken har inte klassats som erbjudandetom.
- **X:-tra Kirseberg 3548:** kommuntillhörighet osäker vid gräns; finns kvar som okänd och samlas inte in som Malmöpris.
- X:-tra är partiell textimport med 47 avvisade annonser per lyckad butik och okänd möjlig bildtäckning. Övrig närings-/variantkarantän från tidigare leveranser kvarstår. Ingen ny 15/20-jämförelse ingår i denna kommunverifiering; tidigare jämförelse och näringsbevis är bevarade oförändrade.

## Reproducera, endast isolerat

Kör från denna arbetskopia med befintliga beroenden (Python 3.12, Playwright och dess Chromium, httpx, BeautifulSoup, PyMuPDF). Inga nya beroenden installerades. Välj en ny tom output-sökväg varje gång; befintliga resultat skrivs inte över.

```powershell
$env:PYTHONPATH='backend;.'
$env:PYTHONIOENCODING='utf-8'
py -3.12 -m grocery_data.scripts.collect_coop_municipality --municipality-code 1281 --output reports/NEW-LUND-RUN
py -3.12 -m grocery_data.scripts.collect_coop_municipality --municipality-code 1280 --output reports/NEW-MALMO-RUN
# Omstart/kontroll med bevarad inventering; inga prisanrop om inget är förfallet:
py -3.12 -m grocery_data.scripts.collect_coop_municipality --municipality-code 1281 --inventory reports/NEW-LUND-RUN/inventory/inventory.json --previous-state reports/NEW-LUND-RUN/update-selection.json --due-only --output reports/NEW-LUND-CHECK
```

Vanliga collectorns/importens operationslås och isolerade databaser används. Output är frivilliga offers_only-kandidater, aldrig aktiva manifest eller en ersättning för komplett bas. `--structured-input` är endast återvalidering av ett exakt matchande isolerat butiksurval och sparad OWN; det är inte färsk insamling. Förberett för driftintegration är inte en installerad scheduler. Se [RELEASE.md](RELEASE.md) för gränsen mot den tidigare Coop-kandidaten och väntande ICA-release.

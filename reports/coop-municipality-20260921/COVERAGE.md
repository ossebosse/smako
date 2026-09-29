# Butikstäckning – Lunds kommun 1281

Färsk insamling 21 september 2026 kl. 19:55–19:58 Europe/Stockholm.
Nationell Coop-karta: 720 poster. X:-tra: 58 poster, kontrollerade mot samtliga
butikslänkar i samma officiella register. Alla 778 poster prövades: tio inom
Lunds kommun, 768 utanför, noll okända i detta källmaterial. En komplett publicerad
registerlista är inte oberoende bevis för att varje verklig butik finns med.
Inga misslyckade butiker har tagits bort. [Alla 778 rader](ALL_STORES.md).

Position från respektive officiellt register prövas mot SCB RegSO 2025, som
följer kommunindelningen 2025-01-01. Kommun-ID verifieras mot befintligt SCB-register.
Källversion, koordinater, hash och observation sparas. Inom tio meter från
någon delområdesgräns blir status okänd. Ingen ny radie/postnummerlikhet.
Genarp och Veberöd tillkommer jämfört med adressorten Lund: tio kommunbutiker
mot åtta adressortsbutiker, inklusive X:-tra i båda. Adressortsläget är oförändrat.
Registrets positionsnoggrannhet och gränsändringar efter 2025 är begränsningar;
Trollebergsvägens registerposition ligger misstänkt nära Flöjtvägen. Båda ligger
inom Lund, men positionerna är inte verifierade för avståndsberäkning/ruttning.

Varje Coop-butik har ett eget kontrollerat StorePageType-ID och konto samt ett
separat faktiskt strukturerat svar. De gemensamma priserna har inte kopierats.

| Butik / ID / koncept | Kommunstatus | Officiell källa | Insamling | Grupper / varianter | Godkända / karantän | OWN / PU | Verifierade ingrediensköp | Beta |
|---|---|---|---|---|---|---|---|---|
| Coop Värpinge Lund / 3659 / Coop | inside; official_position_in_scb_municipality | [butik](https://www.coop.se/butiker-erbjudanden/coop/coop-varpinge-lund/) | structured_success_partial_rows | 47 / 322 | 55 / 267 | 55 / 55 | 3 | ej aktiverad här |
| Stora Coop Lund / 2696 / Stora Coop | inside; official_position_in_scb_municipality | [butik](https://www.coop.se/butiker-erbjudanden/stora-coop/stora-coop-lund/) | structured_success_partial_rows | 78 / 540 | 77 / 463 | 77 / 77 | 3 | ej aktiverad här |
| Coop Veberöd / 1158 / Coop | inside; official_position_in_scb_municipality | [butik](https://www.coop.se/butiker-erbjudanden/coop/coop-veberod/) | structured_success_partial_rows | 56 / 356 | 68 / 288 | 68 / 68 | 3 | ej aktiverad här |
| Coop Trollebergsvägen / 3837 / Coop | inside; official_position_in_scb_municipality | [butik](https://www.coop.se/butiker-erbjudanden/coop/coop-trollebergsvagen/) | structured_success_partial_rows | 22 / 135 | 44 / 91 | 44 / 44 | 3 | ej aktiverad här |
| Coop Flöjtvägen / 3839 / Coop | inside; official_position_in_scb_municipality | [butik](https://www.coop.se/butiker-erbjudanden/coop/coop-flojtvagen/) | structured_success_partial_rows | 22 / 135 | 44 / 91 | 44 / 44 | 3 | ej aktiverad här |
| Coop Klostergården / 3820 / Coop | inside; official_position_in_scb_municipality | [butik](https://www.coop.se/butiker-erbjudanden/coop/coop-klostergarden/) | structured_success_partial_rows | 47 / 322 | 55 / 267 | 55 / 55 | 3 | ej aktiverad här |
| Coop Mårtenstorget / 3813 / Coop | inside; official_position_in_scb_municipality | [butik](https://www.coop.se/butiker-erbjudanden/coop/coop-martenstorget/) | structured_success_partial_rows | 56 / 356 | 68 / 288 | 68 / 68 | 3 | ej aktiverad här |
| Coop Genarp / 3841 / Coop | inside; official_position_in_scb_municipality | [butik](https://www.coop.se/butiker-erbjudanden/coop/coop-genarp/) | structured_success_partial_rows | 22 / 135 | 44 / 91 | 44 / 44 | 3 | ej aktiverad här |
| Coop Vildgåsen Lund / 3656 / Coop | inside; official_position_in_scb_municipality | [butik](https://www.coop.se/butiker-erbjudanden/coop/coop-vildgasen-lund/) | structured_success_partial_rows | 22 / 135 | 44 / 91 | 44 / 44 | 3 | ej aktiverad här |
| X:-Tra Skansvägen / 3658 / X:-tra | inside; official_position_in_scb_municipality | [butik](https://x-tra.se/butiker/skansvaegen) | document_text_unintegrated | ? / ? | 0 / ? | 0 / 0 | 0 | ej aktiverad här |

Godkända/karantän avser butik–produktvariant, inte oberoende kampanjer.
Totalt 372 butikskampanjer, 2 436 variantposter, 499 godkända och 1 937 i karantän.
Samtliga nio fulla snapshotkontrakt är fortsatt underkända; 95%-krav och hela
nämnaren är oförändrade. Endast det uttryckliga partiella radkontraktet publiceras
inom testdatabasen. Blockerare per variant och överlapp finns i
[quarantine-final.json](quarantine-final.json); fulla kvalitetsmått i
[coverage-final.json](coverage-final.json). Ingen karantän har tappats bort.

”Verifierade ingrediensköp” är tre konkreta produkter per Coop-butik som passerat
matcher, checkout och audit. Det är inte ett fullständigt antal planeringsbara
produkter. Näringsbegränsad planering har inte kvalificerats för dessa 499 poster;
inget nytt verifierat näringsunderlag har lagts till. Ingen vinnande meny eller
besparing påstås. Äldre Bulltofta-underlag hör till Malmö och är bevarat separat.

X:-tra Skansvägen 3658 / konto 216525 är upptäckt och dess butikslänk leder till
åtta PDF-sidor. Samtliga åtta har hämtats och text extraherats. Status är
`document_text_unintegrated`, inte ”saknar erbjudanden” och inte enbart bildberoende.
Ingen strukturerad produktpost exponerades i butikens publicerade data; PDF-texten
saknar ännu verifierad koppling annons–pris–variant–villkor för befintligt köpavtal.
Sista sidan gäller först torsdag 24–söndag 27 september; den får inte bli måndagspris.
Noll importer, okänt fullständigt annons-/karantänantal. Därför är prisinsamlingen
9 av 10 upptäckta kommunbutiker och täckningen uttryckligen partiell.

Första körningen stoppades av sträng/heltal vid jämförelse av samma butikskonto;
rättad med strikt ID-regression. Stora Coop hade nya uttryckliga åldersvillkor:
de sparas nu och 23 berörda varianter karantänsätts. Okända schemafält stoppar
fortfarande hela berörda källan. Stora hämtades på nytt efter rättningen.
Övriga färska källbatcher verifierades oförändrade med slutparsern; deras tider
har inte flyttats. Misslyckade förkörningar ligger kvar som separat evidens.

Kommuninsamlingen använder inventeringens `selected_store_ids`. Den gamla
OWN-postnummerhjälpen stöder fortfarande bara 20/21/22-prefix: den används inte
som kommungräns. Den isolerade verifieringen hämtar befintliga OWN-/stores-rader
per belagd adressort och exakt käll-ID och använder vanliga OWN get_offers.
En framtida betaexpansion måste koppla detta explicita kommunurval till användarens
butiksval; befintliga profiler har inte fått ett tyst utvidgat sökområde.

Samma kod på Malmö 1280 med sparade verkliga källor: {'outside': 759, 'inside': 18, 'unknown': 1}; 16 Coop-butiker valda. Ingen Malmö-prisinsamling genomförd här.

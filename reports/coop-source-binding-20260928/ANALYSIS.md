# Coop: aktuell strukturerad butikskälla, 28 september 2026

Status: **PASS i isolerad kandidat**. Se [RESULTS.md](RESULTS.md) för faktisk serving, rebuild, omstart och profilprov. Ingen produktionsaktivering.

## Fastställd konflikt

Den verifierade femkällorskandidaten `lund-own-five-base-20260928-v1` och dess originalimage `32e838155b0e…` bevaras. Före ändring verifierades samtliga 589 kodfiler mot kandidatens manifest (`verified-baseline.json`). Originalpolicyn, Primat och tidigare releaser har inte ändrats.

De lyckade svaren 2026-09-27 16:15 UTC och avvisade svaren 2026-09-28 07:03 UTC har exakt samma förväntade och observerade butiksbindning för samtliga nio Coop/Stora Coop. `binding-comparison.json` visar varje värde, tidpunkt, dokumenthash och tillgänglig kampanjidentitet:

| Fysisk butik (ID) | Källbutik/ledger, förväntat = observerat |
|---|---:|
| Coop Veberöd (1158) | 106595 |
| Stora Coop Lund (2696) | 105760 |
| Coop Vildgåsen Lund (3656) | 216523 |
| Coop Värpinge Lund (3659) | 216526 |
| Coop Mårtenstorget (3813) | 106430 |
| Coop Klostergården (3820) | 106435 |
| Coop Trollebergsvägen (3837) | 106444 |
| Coop Flöjtvägen (3839) | 106445 |
| Coop Genarp (3841) | 106447 |

Förväntad/observerad API-källa är i varje fall `https://external.api.coop.se/dke/offers/sorting-groups/{ledger}`. Butikssida, dokumentets butik, kuvertets butik/sökväg och API-bindning stämmer. HTTP är 200. Det avvikande fältet är `structured_offers.error`: förväntat frånvarande, observerat `public_structured_schema_unrecognized`; `data` saknas. `parse_structured` lade tidigare detta schemafel i samma villkor som verkliga identitetskonflikter och gav därför den missvisande texten **Coop shared structured store/source evidence mismatch**.

De ursprungliga avvisade kuverten innehåller inte produktdelen: transportens sanitizer hade redan kastat bort den. Därför går deras exakta kampanj-ID/produktlista inte att återskapa från dessa kuvert. Detta är en begränsning i det sparade beviset, inte bevis för fel butik.

En begränsad ny faktisk hämtning av Veberöds officiella butikssida 10:43 UTC med oförändrad spärr identifierade två nya fält (`results/schema-diagnostic.json`):

* `content.dealOfferRulesText`: **Handla andra varor för 200:- så får du köpa:**.
* `priceInformation.steps`: faktiska prissteg, exempelvis 3/25 kr, 5/35 kr och 10/50 kr för Kanelbullar. En annan rad har 2/90 kr och 4/149 kr. `termStyle` och `dealType` är **Ladder Deal**; något vanligt `discountValue` finns inte på översta prisnivån.

Det är verkliga villkor i den nya kampanjutgåvan, inte en ny butik eller en ändrad dokumenthash som felaktigt ärvts. Den äldre transporten avvisar dessa okända fält. Ingen gammal dokumenthash jämförs med den nya vid identitetskontrollen. Färsk Chromium-session används per butik och officiell StorePageType återkontrolleras före varje hämtning. Varje butik hämtas mot sitt eget ledger; inget gemensamt svar kopieras mellan butiker.

## Gemensam rättning

`grocery_data/app/connectors/coop/structured_offers.py` bevarar de två granskade fälten, med fortsatt stängt schema för okända affärsfält och okända fält inne i prisstegen. HTTP-/schemafel skiljs från verkliga butik-/källkonflikter. Nästa okända schemafält redovisas med fältnamn utan att spara obearbetad feltext eller sessionsuppgifter.

Köpkrav spärras per rad med `additional_purchase_rules_requires_review`; prissteg spärras med `tiered_price_steps_requires_review`. Villkor hos kampanjföräldern kan inte försvinna hos barnvarianten. Prissteg bevaras som `other`, utan pris eller mängd som inte finns angiven som ett enda köp. Övriga rader måste fortfarande klara samma befintliga produkt-, butik-, period-, förpacknings-, medlems- och villkorskontroller. Inga generella identitetsspärrar eller trösklar har sänkts. Parser- och radgranskningsproveniens versionssätts till `coop-parser-v4`; ordinarie publiceringskontrakt är oförändrat.

Den första fullständiga nya hämtningen 10:51 UTC behålls också som mellanresultat. Den exponerade att Ladder Deal saknar direktpris; det gav då fortfarande ett helt dokumentfel. Den kompletta rättningen prövades därefter mot samtliga nio sparade svar: inga gemensamma fel, 254 kvalificerade rader, samtliga övriga i karantän (`replay-new-captures.json`). Detta är **replay**, inte ytterligare en insamling eller en föryngring av observationer.

## Avgränsningar och återställning

Ny image byggs ovanpå verifierad image och används endast i `/var/tmp/smako-coop-source-binding-20260928`. Den tidigare alternativa instansen ligger kvar. Privat SQLite-kopia och käll-/PriceUniverse-träd har kopierats under befintligt operationslås; råfiler och faktiska observationstider bevaras. Rollback är att återgå till den tidigare isolerade kandidaten; produktion har inte växlats.

Ordinarie CLI/import/rebuild/publicering/reload används. Testharnessen avstår uttryckligen från orelaterade kedjors nya nätinsamling men deras befintliga källor importeras genom oförändrade providers. X:-tra har egen status och hämtas inte om när det inte är förfallet. Baskällorna är fortfarande giltiga; deras observationer ändras inte.

ICA/Hemköps kommunluckor, äldre PurchaseTerms-kopplingar, Lidl/Willys nya kampanjbortfall, Malmö-publicering och historisk Lidl-fixture är separata kvarstående uppgifter. Tillkomna köpkrav/prissteg är specificerade kvarstående radblockerare, inte återställda köppriser. Stöd för dem kräver verifierad villkors-/prismodell; ingen extern information behövs för att lösa den här hela-butikskällans schemaavvisning.


### Gränsen OWN → serving

Första faktiska reloadprovet visade korrekt godkända 254 OWN-rader men noll nya serving-rader. Den befintliga kommunprovidern hade en explicit versionskontroll för enbart `coop-parser-v3`. Vid versionssättningen till v4 måste även denna befintliga kontroll följa med: den medger nu exakt de granskade versionerna v3/v4, medan X:-tra fortsatt endast medger `xtra-pdf-text-v1`. Övriga krav på fysisk butik, källsnapshots, köpblockerare och kampanjbevis ändras inte. Regressionen prövar v3, v4, okänd version och fel butik genom verklig OWN/providerväg. Mellanresultatet med uteblivna serving-rader är sparat och räknas inte som slutacceptans.

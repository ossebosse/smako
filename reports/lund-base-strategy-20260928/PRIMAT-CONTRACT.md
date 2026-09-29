# Primats kontrakt – Lund, 28 september 2026

En verklig `/stores/resolve`-hämtning 07:04:22 UTC återger Clemenstorget 1004409 med `tier=offers_only`, `selected=false`. Identitetsfingeravtrycket stämmer med den verifierade kopplingen. Gunnesbo 1088004 har `tier=full`, `selected=true`. Underlaget finns i `results/primat-contract.json`; inga produktpriser hämtades i detta identitetsprov.

| Fält | Ursprung och faktisk betydelse |
|---|---|
| tier | Källans fält, kopieras av `PrimatPriceProvider._parse_resolved_store`. Nu offers_only för 1004409. |
| coverage | Normaliserad lokal klassning i `primat_store_discovery_export._coverage`; full blir full_catalog. Parsern kan ta explicit källfält coverage, annars används tier. I dagens råsvar finns inget coverage-fält för dessa butiker. |
| selected | Urval från källans default_selection, förenat med butiker vars eget selected är true. Det är inte ett kvalitets- eller täckningsbevis. |
| full_catalog-krav | Lokal publiceringspolicy för obligatoriska baskontexter. Revalideraren kontrollerar identitet, kanal och täckning; selected=false är inte i sig ett avslag. |

Dagens råsvar saknar också price_context_type. Exportens physical_store kommer i dessa två fall från den äldre lokala standardtolkningen, inte ett nytt bevis på fysiskt hyllpris. Alternativet använder inga Primat-priser.

Ingen belagd parser-/mappningsdefekt hittades. Identiteten är oförändrad men det deklarerade källkontraktet har ändrats. Att kalla den aktuella källan full_catalog skulle strida mot råsvaret. Inga källfält eller produktionskrav har ändrats.

## Historiskt bevis och begränsning

Bevarade discovery-exporter från 24 och 30 augusti visar Clemenstorget `tier=full`, normaliserad `coverage=full_catalog`, `selected=true`; Gunnesbo full/full_catalog men selected=false. Kopiorna i denna rapport är oförändrade, med SHA-256 i paketmanifestet. Båda anger råsvarshash `7d75ee2fe9840693490289354e7abdf291d109ab2c58f3a4ebbd961be8ea00fe`.

Fullständigt ursprungligt HTTP-råsvar har inte återfunnits. De bevarade projektionerna innehåller direkt tier och råsvarshash, men medger ingen ny parsning av hela det gamla svaret. `docs/lund_primat_phase_c_export.md` visar underlaget för den gamla policyn: verifierad butiksidentitet, källans full-klassning och ett begränsat produkt-/prisprov, 48 sökfrågor med 32 produkter från Clemenstorget och 1 831 från Gunnesbo. Detta var inte en oberoende genomräkning av hela sortimentet. Även senare bounded proof med 24 respektive 1 864 produkter är ett urval.

Det går därför att belägga ändrad deklarerad täckning, men inte hur mycket ett tidigare fullständigt sortiment faktiskt har krympt. Den tidigare klassningen var källdeklarerad, inte oberoende fullsortimentsverifierad.

## Återställning av originalstrategin

Originalpolicyn kräver fortfarande sina sex obligatoriska kontexter, inklusive Primat 1004409 full_catalog. Återställning kräver aktuell, verifierbart butiksspecifik bas från denna källa, godkänd identitets-/kanal-/täckningsrevalidering, färska prisobservationer och komplett originalfederation samt nya planerings- och driftprov. Ett ändrat tier-fält ensamt ersätter inte pris- och täckningsprovet. Andra butikers priser eller offers_only får inte fylla luckan.

Den alternativa policyn `lund-own-five-base-20260928-v1` är ett separat beslutsspår. Den återställer inte originalpolicyn och utgör inte en godkänd release enligt denna. Clemenstorget bidrar enbart med kvalificerade egna butikserbjudanden där aktuell giltighet är belagd.

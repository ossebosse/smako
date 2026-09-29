# City Gross kommunstöd – 23 september 2026

City Gross är anslutet till den gemensamma kommunfunktionen, befintlig
onlineconnector, OWN, PriceUniverse och ordinarie behovsstyrda driftväg.
Willys tidigare delresultat och releaseunderlag bevaras. Ingen aktivering ingår.

| Kommun / butik | Kommunstatus | Kanal | Hämtade / godkända OWN | Karantän | PriceUniverse |
|---|---|---|---:|---:|---:|
| Lund 1281 | Verifierat noll butiker av 38 i officiellt register | Ingen vald källa | 0 / 0 | 0 | 0 |
| Malmö 1280: Hyllie 3211, site169 | Inom kommun | Butiksspecifik onlinekatalog | 13 523 / 13 523 | 0 | 13 523 |
| Staffanstorp 1230: 3229, site11 | Inom kommun, positiv kontroll | Butiksspecifik onlinekatalog | 13 780 / 13 780 | 0 | 13 780 |

[Officiellt butiksregister](https://www.citygross.se/api/v1/PageData/stores)
och [site-register](https://www.citygross.se/api/v1/sites?siteTypeId=3)
ligger till grund för identitet; gemensam SCB-geometri avgör kommun.
Malmö Stora Bernstorp 3203/site59 ligger utanför Malmö och lånas inte in.
Alla 38 rader per kommun bevaras i [Lund](CITYGROSS-STORES-1281.md),
[Malmö](CITYGROSS-STORES-1280.md) och [Staffanstorp](CITYGROSS-STORES-1230.md).

De fulla katalogerna är promoverade i separata OWN-databaser. Slutparser v4
återspelar originalen utan nya nätanrop eller föryngrade observationer.
Noll produktkarantän betyder inte att alla rabattvillkor stöds: elva
minimiköpsbeloppskampanjer per butik spärras, med belagt ordinarie pris kvar.
PriceUniverse- och köpkvitton redovisas separat nedan.

## Resultat och underlag

- [Inventering, faktisk insamling och replay](INVENTORY-COLLECTION.md).
- [Prisroller, sex butiksspecifika aktuella erbjudandeexempel och officiella länkar](PRICE-SEMANTICS.md).
- [Produkt-/receptköp genom matcher, checkout och audit](PURCHASES.md).
- [Ordinarie isolerad drift, omstart, nollbehov, förfall, fel och återhämtning](RUNTIME.md).
- [Testresultat, bevarandekontroll och inkrementpaket](TESTS.md).
- [Exakt Willys-lucka per butik och kvarstående Malmö-prov](WILLYS-GAPS.md).
- [Separat City Gross-releaseunderlag](RELEASE-CITYGROSS.md).
- [Driftintegration och beständig konfiguration](../../docs/citygross_municipality.md).

Aktuella erbjudanden verifierades separat i respektive butik den 23 september:
Barilla Lasagneplattor 2 × 500 g för 42 kr och Garant Eko Basmatiris 1 kg för
44,95 kr till och med 4 oktober; Zeta Spaghetti 2 × 400 g för 22 kr till och
med 27 september. Publika kampanjer, inget medlemskrav/minsta köpbelopp,
separat varukorgstak 25 försäljningsenheter. Flerköpspris kräver angivet antal.
Onlinepriserna belägger inte fysisk hyllkant. Produkt, variant, källtid,
kampanj-ID och butikens eget råsvar finns i [exempeldata](offer-examples.json).

## Provets räckvidd

Verklig insamling: 136 kataloganrop för Hyllie och 138 för Staffanstorp,
sex registeranrop och tre SCB-anrop. Övriga avgränsade källprober redovisas
i respektive evidensfil. Driftprov använder uttryckligt OWN-only och märkt
replay/felinjektion, med extern nätåtkomst spärrad. Det är inte ett fullständigt
federerat Malmö-prov med aktuell Primat-bas.

Den [frysta basinspektionen](base-current.json) från 23 september 08:09 UTC
visade aktuellt Primat-underlag för Lund men ingen verifierad Malmö-kontext;
Coops onlineobservation hade passerat 48 timmar. Underlaget kopierades under
befintligt operationslås och lästes isolerat. Det uppdaterades inte och används
inte som Malmö-bas eller aktuellt rollbackunderlag.

Lidls nästa konkreta steg är officiell kommuninventering och exakt
butiksgiltighet för aktuella regionala/nationella erbjudanden genom befintlig
offers-only-validering. Ingen Lidl-ombyggnad har påbörjats.

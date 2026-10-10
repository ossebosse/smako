# Viktvaror och kampanjjämförelse – kandidat, inte aktiverad

Runtime `0e7c20dfa91183b622cce340093a8a6cca93a5a9`, gren
`fix/weight-offers-20261010`, ovanpå aktuell sammanhängande kod `2ec813973b0c`.
Beta har inte ändrats. Ingen push, insamling, reläändring eller prispublicering.

## Vad felet var och vad som ändrats

Produktsökningen krävde fast förpackningspris även för produkter med belagt
kilopris. Dessa fick därför **Inte jämförd**. Den befintliga korgmotorn kunde
redan beräkna dem i uppskattningsläge. I exakt läge uteslöts de med ett
allmänt felmeddelande, medan valet för uppskattningar låg under Mina val.

- Jämförelsen använder nu befintlig pris-, mängd- och köpgränskontroll för
  viktpriser. Visningen säger kr/kg eller kr/l, aldrig ett påhittat paketpris.
  `best_price`/`effective_price` för hela paket förblir null på viktvaror;
  `display_price` och dess enhet bär den nya visningen.
- Inköpslistan har ett synligt, frivilligt val för uppskattad vikt och kostnad.
  Det gäller också recept i samma korg. Exakt läge ändras aldrig automatiskt.
- Ett stopp på grund av inköpsläget förklarar vilket val användaren kan göra.
- Ett uttryckligt byte av inköpsläge vid omräkning följer ordinarie audit,
  ägarskydd och ny revision. Misslyckad omräkning bevarar tidigare plan.
- Prisdatum, medlemskap, butik/kanal, kampanjgrupper, mängder och näringsregler
  är bevarade. Ingen ny prismotor eller receptdefinition införs.

## Användarens två exempel

Samma hashkontrollerade prisartefakt används före/efter. Observationer från
9 oktober; isolerad replayklocka 10 oktober 12:00 UTC. Detta är inte en ny offert.

| Vara | Belagt underlag | Resultat |
|---|---|---|
| Coop Satsumas, GTIN 2317302900005 | 29,90 kr/kg offentligt; 20 kr/kg Coop-medlem, 4–11 oktober | Nu synligt och jämförbart kilopris. 1 000 g behov ger källans 8 × cirka 140 g, uppskattat 22,40 kr och 120 g rest. Exakt läge stoppas tydligt. |
| Scan Fläskytterfilé, GTIN 2320321600009, cirka 950 g | Coop Online Syd 105 kr/kg; inga aktiva kampanj-ID:n i råsvaret | 105 kr/kg visas. Bladets 65 kr/kg kan **inte** kopplas till denna onlineprodukt med befintligt underlag. |
| Generisk fläskytterfilé 1 000 g | Fri befintlig korg väljer Nybergs Deli Holland cirka 1 100 g, 59 kr/kg | Uppskattat 64,90 kr före/efter. Detta är en annan produkt och inte bevis för Scan-kampanjen. |

Satsumas 22,40 och generisk fläskytterfilé 64,90 fungerade redan i uppskattningsläge
i förekoden. Rättningen förbättrar tillgången till och förståelsen av det läget;
ingen besparing från ändrad prismotor påstås. Användarens smörbild visar 45 kr
för 500 g; fasta förpackningars befintliga jämförelse bevaras.

## Övriga produkter

Offlinegenomgång av alla 42 492 rader i det faktiskt publicerade underlaget:
40 100 fasta prisrader, **1 002 jämförbara viktprisrader**, 1 390 fortsatt
utan säker fullständig jämförelse. Rader är inte unika butiksoavhängiga produkter.

Viktprisrader: Coop 167, Hemköp 277, Willys 520, ICA 34, Lidl 4.
Inventeringen använder samtliga kedjemedlemskap och samma replaydatum;
enskilda användares pris beror fortfarande på deras val.

Kvarstående grupper:

- 957 med okänd köpmodell i äldre kontrakt. Ingen säker enhet/mängd får antas.
- 404 kräver val av kampanjvariant. Ett grupppris styrker inte en exakt SKU,
  dess näring eller allergenegenskaper.
- 29 viktvarurader har köpgräns vars enhet inte stöds säkert av det äldre
  kontraktet. Kampanjen finns kvar som metadata; inget obegränsat kampanjpris
  används. Exakta produkter och stopp finns i `WEIGHT-BLOCKERS.json`.

## Verifiering

- 166 lokala riktade backendtester PASS; slutliga 15 vikttester PASS.
- 167 relevanta tester passerar mot leveransimagen över två körningar.
  Första körningen saknade en gammal näringsfixture i testmounten (166 PASS,
  ett FileNotFoundError). Det återstående testet passerade när rätt bevarad
  fixture monterades. Runtimekällkod monterades aldrig in.
- Prisvisningsregressionen fallerar på föregående 205-image och passerar på
  kandidaten. Ursprungliga generiska stopp finns i bevarad före-replay.
- Chromium och WebKit, mobil layout: medlemspris 20 kr/kg, riktig knapp,
  exakt stopp, uttrycklig uppskattning, en start vid dubbelklick, korg/audit,
  reload, sparad GET, ny revision, äldre revision och annan ägare 403 PASS.
  Misslyckat byte tillbaka till exakt läge bevarar hela revisionen.
- Inga oväntade pageerror, requestfailed eller 5xx i slutproven. Två inledande
  fel i testskriptets navigation/selektor bevaras som FAIL. Ingen fysisk iPhone.
- Gemensam veckokorg provas med ett kontrollerat receptbehov och egen varurad
  som delar samma viktförpackning. Befintligt källbundet näringsprov passerar;
  inga saknade näringsvärden för Satsumas eller Scan har hittats på.
- Två CPU, 3 GiB. Containerobservation efter prov cirka 992 MiB, inte minnestopp.
  Ingen ny prestanda- eller storskalig menysökning ingår.
- Ruff, compileall och 10 paketerade filhashar + fyra HTTP-filhashar PASS.

Fulla råa prov ligger på D: under `.local/weight-offers-20261010/`, utanför Git.
Sanerat versionsbundet underlag: `EVIDENCE.json`. Paket och separat framtida
aktiveringsväg: `ACTIVATION.md`. Konkreta källluckor: `RESEARCH.md`.

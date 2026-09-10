# Smako V2 – leveransrapport 2026-09-10

Ingång: https://beta.smako.nu/personal, länkad från startsidan.
[R1–R9 och återupptagbara delsteg](../docs/product/personal-planning-v2.md).
Allergi-/eko-/näringsverifiering och kontosynk saknar produktionsacceptans.

## Levererade flöden

**Min plan:** dag/måltid, separata middags-/måltids-/portionsantal, full köpkostnad,
butikssummor och snabbt öppna/redigera/byta/ta bort/fylla recept. Färre butiker
jämförs för samma recept, extrabehov och skafferibidrag. Tekniska ID:n ligger under
detaljer. **Inköpslista:** noll recept, bekräftade generiska egenskaper, exakt
produktlåsning, hela förpackningar, faktiskt använda prisvillkor och överskott.
Andra källregistrerade erbjudanden visas separat och påstås inte användas.

**Skafferi:** manuellt/sök/scanner, generiskt/exakt, mängd/enhet/obrukbar. Verkligt,
reserverat och disponibelt saldo. Generering bokför inget inköp. Bekräftat inköp
och förbrukning är atomiska/idempotenta, också med gammal dubbelklicksrevision.
Reservationer kan frigöras utan att verkligt lager raderas. Restförslag visar
nya köp och kostnader innan val; förhandsgranskning skriver aldrig lager/korg.

**Sök varor:** befintlig sökmotor/scanner återanvänds utan live-prisanrop.
**Mina val:** granskad svensk smakprofil, mjukt/hårt, separata måltidstypsval,
fördelning, eko och näringsgränser. Profilsparande för återanvändning kräver
uttrycklig knapp. Bekräftade plankrav följer privata revisioner.

Feedback ligger i dokumentflödet på den äldre sidan och i footer på V2.
Ingen flytande feedbackkontroll täcker innehåll, tangentbord eller safe-area.
Mobilprov: 390 × 844 samt 24 px grundtext. Fysisk iPhone/Safari-krom och verklig
kameraskanning är inte accepterade; emulering ska inte beskrivas som telefonprov.

## Beräkning och arkitektur

`PersonalPlanner` komponerar befintlig generator, `MenuOptimizer`, `BasketOptimizer`,
`BasketCalculator`, matcher och `ProductSearchIndex`. Inga parallella prisregler.
Recept + uttryckliga extra behov − tillåtet reserverat skafferi blir EN korg med
gemensamt butikstak 1/2/3 och medlems-/prisunderlag. Kompatibla behov delar paket;
exakta olika varianter byts inte ut. "Ska köpas" använder inte gammalt skafferi
utan valt medgivande. g/ml/st blandas inte utan verifierad omräkning.

Kandidatval och slutkontroll använder samma hårda krav. Balanserad och Varierad
använder befintliga variationsregler. Varierad jämförs mot faktisk Balanserad
referens, strukturell förändring och dess valda budget. Middagar dupliceras inte;
frukost/mellanmål kan upprepas. Den befintliga generatorn har tre nya recept per
övrig måltidstyp, inte omdöpta middagar.

Strategiska flerköp kräver läget som tillåter större köp. Sökningen tillåter högst
10 % extra radutlägg och kräver minst 10 % lägre paketpris. Behov, faktisk mängd,
merkostnad och överskott särredovisas. Vanlig avrundning kan ge överskott i båda
lägena. Ingen hållbarhet/bäst-före uppfinns. Ekoalternativsökningen är begränsad
till 256 delmängder och kandidatstrålen till åtta; misslyckad sökning är inte ett
matematiskt bevis på att varje möjlig kombination är omöjlig.

## Kombinerat fryst exempel

Integrationstestet har middag + frukost + mellanmål med sammanlagt 600 ml mjölk
och 240 g bröd. En uttrycklig extrarad kräver ytterligare 600 ml mjölk. Befintligt
skafferi har 300 ml, som reserveras mot recepten. Köpbehov: 900 ml + 240 g.

| Inköp | Hel förpackning | Radkostnad | Beräknat överskott |
|---|---:|---:|---:|
| Mjölk | 1 000 ml | 20,00 kr | 100 ml |
| Bröd | 500 g | 25,00 kr | 260 g |
| Totalt | 2 förpackningar | **45,00 kr** | 100 ml + 260 g |

Detta är förenklade frysta testpriser, inte ett aktuellt butikserbjudande.
Planen lämnar verkligt lager på 300 ml tills inköp bekräftas. Ett inköp ger
1 300 ml mjölk + 500 g bröd; upprepad bekräftelse ger ingen ny mängd. Bekräftad
förbrukning lämnar 100 ml + 260 g. Gammalt lager får inget påhittat kronvärde.

## Datatäckning och kvarstående hinder

Artefakten har 42 622 produktobservationer, sju butikskontexter och ID
`price-universe:46b7fa8ce02ef396819aad2f40384fce95aab594a443677db1c40f1da15ad5fe`.
Byggtid 2026-09-10 17:08:55 UTC; äldsta observation 2026-09-08 19:56:07 UTC.
Inga observationstider, färskhetsgränser eller aktiva manifestpekare har flyttats.

- **R1 PARTIAL/DATA_BLOCKED:** fullständiga spårbara ingrediens-/allergendeklarationer
  saknas. Kontroll kräver källa och specifik produkt-/snapshot-identitet. Okänd
  allergi eller information blockeras, även vid byten/skafferianvändning.
  Etikettpåminnelse ersätter aldrig verifiering. Frysta deklarationsfixturer
  verifierar motorn, men utgör inte en produktionsdatakälla.
- **R4 DATA_BLOCKED:** kostnadsandel efter rabatt inkluderar alla köpta livsmedel,
  även mat-extras; skafferi/icke-mat/avgifter undantas. Unknown räknas inte som eko.
  Animaliskt krav omfattar ägg/mejeri/sammansatta varor. Verifierad produktstatus
  saknas, så valt krav stoppar beräkningen i produktion utan att sänkas.
- **R5 DATA_BLOCKED:** full produktnäring med enhet/grund och spårbart tillagnings-
  utbyte saknas. Den äldre generiska approximationen intygar inte nya gränser.
  Per portion, ändrade mängder/portioner och negativa/NaN/inf-värden kontrolleras.
  Även skafferiets näringsdeklaration saknas. En produktionskoppling för verklig
  evidens behöver tillkomma; inga källinsamlingar har ändrats här.
- **R2 PARTIAL:** gästskafferi är fungerande och privat; verklig kontosynk är inte
  accepterad. Flytt stöds endast till tomt verifierat konto. Befintliga kontodata
  skrivs aldrig över. Katalogkoppling krävs även för fullt skafferitäckta behov.
- **R6 PARTIAL:** öppna/redigera/ta bort/fylla/byta fungerar i planeringen. Efter
  bokfört inköp/förbrukning krävs ny plan; ändring av redan bokförd plan återstår.
- **R9 PARTIAL:** befintliga kampanj-/medlems-/flerköpskontrakt används. Källstödda
  mix-and-match-grupper saknas och gissas inte. Onlinepris intygar inte fysisk
  hyllkostnad. Okänd ordinarie kostnad ger ingen uppfunnen besparing.

## Konto och operatörssteg

[Authlib/OIDC](https://docs.authlib.org/en/v1.5.0/client/starlette.html), låst till
1.8.0, sköter PKCE S256, state, nonce och signerad ID-token. Ingen egen lösenords-
hantering eller e-postbaserad ägarkoppling. Endast HMAC av verifierad issuer och
subject finns i signerad Secure/HttpOnly-cookie; ingen e-post/token i profilen.

Samtliga OIDC-inställningar är **saknade på VPS**. Nästa steg:

1. Registrera klient hos en befintlig etablerad OIDC-leverantör, med callback
   `https://beta.smako.nu/api/account/callback` och authorization-code/PKCE.
2. Sätt `SMAKO_OIDC_ISSUER_URL`, `SMAKO_OIDC_CLIENT_ID`, `SMAKO_OIDC_CLIENT_SECRET`
   direkt i `/opt/smako/production.env` (0600). Hemligheter ska aldrig till chat,
   repo eller rapport. Befintlig stark `SECRET_KEY` och HTTPS krävs. Ingen tjänst
   eller betald prenumeration har beställts.
3. Återskapa endast appen. Kör verklig acceptans för inloggning, fel state/nonce,
   utloggning, ägarisolering, uttrycklig gästflytt, revisionskonflikt och radering.
   Gästflödet ska fortsätta fungera; inga konto-ready-påståenden före provet.
4. Ordna spårbar produkt-/allergen-/eko-/näringsdata och tillagningsunderlag innan
   dessa krav kan verifieras. ICA OWN-research är fortsatt uppskjuten och får
   inte användas som en oannonserad insamlingsändring.

## Privat lagring, cache och restore

`personal_private_state` ligger i befintlig plan-SQLite, bundet till HttpOnly
gästägare eller verifierat konto. Ingenting personligt hamnar i PriceUniverse.
Optimistiska revisioner och `BEGIN IMMEDIATE` skyddar lager. Planrevision och
reservation skrivs i samma transaktion. Fel bevarar historik/senast fungerande
resultat. Servern kontrollerar också exakt skafferiprodukt och dess enhet.

Privata cacheidentiteter inkluderar ägare/tillståndsrevision, profil, skafferi,
korg, recept, policy, medlemskap, prisversion och färskhet. Ändringar använder
befintlig planner-kö. Personliga API-svar är `private, no-store`; inga privata
fält går till generell analytics. Radering tar bort privat tillstånd och lägger
slumpmässigt rad-ID i aktuell raderingsledger. Backup omfattar hela databasen.
Restore undertrycker raderna och kontrollerar att de inte återkommer.
En icke-tom sådan ledger testas med frysta data; verklig ledger hade noll poster.

## Tester och tidsmätningar

- `personal-v2/regression-release-c.xml`: **381/381** berörda tester. V2, äldre
  planner/API, prismotor/audit, revisioner, variation, generator, sökning,
  radering/restore, admission, säkerhet, statiskt UI och deployment.
- `personal-v2/membership-scanner.xml`: **56/56** ytterligare medlems-/kampanj-/
  scannerkontroller. `test_personal_planning_v2.py`: 28 kombinerade frysta tester.
- Chromium/WebKit: **18 per motor**, riktig lokal ASGI/SQLite och frysta produkter;
  inga mockade personliga handlers. Bilder: `personal-v2/browser-final-b/`.
- Verklig HTTPS: **22 per motor**, nya syntetiska gäster, exakt nollreceptskorg,
  skafferi, frukost/mellanmål, extravara, redigering, dataspärr och ägarisolering.
  Inget köpt lager från generering, noll live-prisanrop, inga JavaScript-fel.
  Slutversion/resultat: `personal-v2/https-browser/results.json`.
  B-verifiering: exakt korg 7,05 kr, frukost + mellanmål + extra 38,44 kr,
  200 ml skafferibidrag, samma resultat i båda motorerna.
- Ruff, compileall och berörd JavaScript-syntax passerar.
- En UI-strängassertion misslyckades även i originalträdet. Den uppdaterades
  för befintlig signerad delta-visning; `app.js` och prisgoldens är oförändrade.
  Saknad `.dockerignore` kopierades från originalet för deploymentkontrollen.

Identisk gammal 5-middagsförfrågan mot samma frysta artefakt gav samma fem recept
och **244,49 kr** före/efter. Kall lokal körning **18,170 → 18,820 s (+3,6 %)**;
varm **1,136 → 1,070 s (−5,8 %)**. Separata processer, ett stickprov, ingen
statistisk prestandagaranti. Första HTTPS-anrop efter första omstart: 14,031 s,
sedan 1,333 s. Tidigare redan varm VPS 3,009/1,415 s är ingen kall kontrollgrupp.
Kall planneromskrivning är uttryckligen uppskjuten.
Slutversion B: HTTPS 13,936 s efter omstart och 1,348 s varmt, fortfarande
244,49 kr och noll live-anrop (`personal-v2/after-https-b.json`).

Tre nya personliga lägen mot verkligt fryst underlag: Billigast **139,04 kr**,
Balanserad **163,92 kr**, Varierad **167,90 kr**, tre middagar × fyra portioner.
Varierad har testad strukturell skillnad och ligger inom 25 % av Balanserad.
Detta är olika menyer, ingen samma-meny-besparing. Tider 23,789/18,584/32,882 s
är V2-funktionsprov och inte jämförbara med äldre 5-middagsbaslinjen.

## Deployment och rollback

Endast appen byttes. Första V2: `personal-v2-20260910`, image
`sha256:9623bb6940eff5370ce189870e4395030caf80af012f786c7bdfebd99a7a32fb`.
Slutversion: `personal-v2-20260910c`, image
`sha256:4e967681b4c6015f3b8c1505784de5cfa7173a43fe98f2bc9f89e1f6bc859467`.
Föregående verifierade B-image: `sha256:1438783a8fcada0e06e722645e221bf9b163208a077bf8d41e8bafe5de1c09d3`.
Källa `/opt/smako/releases/personal-v2-20260910c`, via `/opt/smako/current`.
29 kontrollerade app-/driftfiler ovanpå faktiskt installerad release, följt av
tre kompletteringsfiler och ett avslutande serverkravsfelsskydd. Baseline/hash kontrollerades före kopiering. Befintlig
VPS-skillnad för valfri ACME_EMAIL bevarades. Inga lokala relayändringar paketerades.

Backup före release **20260910T191841Z**. Backup med första V2-data
**20260910T192800Z**, validerad och återläst till separat
`/srv/smako/restore/personal-v2-20260910` med aktuell raderingsledger. Databas-
integritet, paketets hash och PriceUniverse semantiska/filhash verifierades.
64 gamla revisioners fullständiga rad-hashar oförändrade vid första release;
alla 70 revisioner bevarade vid B. Bara syntetiska acceptansrevisioner tillkom.
Scheduler-container och aktiva prismanifest är oförändrade. Ingen användardata raderad.
Efter B:s acceptansprov fanns 76 revisioner; samtliga bevarades vid C.
Slutliga radantal och hashkontroll finns (`personal-v2/personal-v2-deployment.json`).

Rollback från C går till den verifierade B-versionen som behåller privat
schema och raderingsstöd. Återgå inte till pre-V2-imagen för privat drift:

```sh
ssh smako 'python3 /opt/smako/evidence/personal_v2_activate_remote.py rollback personal-v2-20260910c'
```

Scriptet återställer app-symlink/version, behåller databaser och återskapar bara
appen. Readiness, tidigare revisionshashar, prismanifest och scheduler kontrolleras.
Hemliga env-backuper stannar på servern med 0600. Historisk databasrestore behövs
inte vid appbyte. Verklig datarestore måste använda aktuell raderingsledger och
nya privata suppressionregler, enligt befintligt runbook.
En isolerad kompatibilitetsrepetition läste 68 ägda planer och två privata tillstånd
från backupkopian med både första V2-imagen och B-imagen. Produktionsdata monterades
inte skrivbart och appen rullades inte bakåt under användartrafik. Evidens:
`personal-v2/personal-v2-rollback-rehearsal.json`.

Willys-task/relay, ICA/Primat-normalisering, källinsamling, scheduler och Caddy är
orörda. Kall prestanda och ICA OWN-research är fortsatt uppskjutna. Tidigare
operatörsprov kvarstår enligt [bevarad HANDOFF](handoff-before-personal-v2-20260910.md).

C:s enda kodändring spärrar det äldre globala vegetariska/veganska kostfältet
tills användaren uttryckligen anger V2:s måltidsspecifika kostval. Kravet kunde
annars skickas via API utan effekt. Fryst regression och verklig HTTPS verifierar
HTTP 422 med konkret konflikt; inget hårt krav ignoreras tyst.

Slutlig C-acceptans 19:56 UTC: 381/381 regressionstester, båda HTTPS-motorerna
22/22, 82 revisioner totalt och samtliga tidigare 76 oförändrade. Prismanifest
och scheduler oförändrade. C:s äldre referensmeny: 244,49 kr, 14,021 s efter
omstart och 1,229 s varmt, noll live-prisanrop (`after-https-c.json`).

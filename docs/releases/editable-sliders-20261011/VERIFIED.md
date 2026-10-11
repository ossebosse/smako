# Redigerbara reglage och fast fördelningsskala

Appkod: `7987bd5bc5d129a023f37569a4626ca847abdb72`.
Build: `editable-sliders-7987bd5bc5d1`.

Fördelningens skala är alltid det valda måltidsantalet. När en kategori ändras
begränsas den till återstående antal utan att andra kategorier flyttas.
Ändrat måltidsantal normaliserar summan; vegetariskt/veganskt kostval fördelar
alla tillfällen till vegetariskt enligt API-kontraktet.

Alla reglagens siffervärden går att redigera med tangentbord. Enter eller
fokusbyte tillämpar värdet, Escape avbryter en pågående redigering, och tomma
frivilliga gränser återställer standard. Decimaler med komma stöds för
portionsvikt och näringsgränser. Manuell inmatning respekterar samma
fördelningsbudget, skalgränser och min/max-ordning som reglagen.

Proteinets skala är 0–100 g och kolhydraternas 0–400 g. Tidigare sparade krav
utanför den nya skalan visas uttryckligen och bevaras tills användaren ändrar
dem. Noll och ingen gräns förblir skilda värden. Medlemsprisavsnittet under
Extraval är borttaget; befintlig `all_advertised`-prissättning består.

## Lokal verifiering

- 18 testfall i `backend/tests/test_personal_choices_browser.py` passerar,
  inklusive Chromium och WebKit, API-validerad nyttolast, fasta skalor,
  tangentbordsinmatning, faktiska drag med mus, kostval, mobilbredd och gamla krav.
- Berörda fall kördes igen efter slutjusteringarna av äldre gränser och fältbredd.
- Ruff, compileall och `git diff --check` passerar.
- Tidigare backendverifiering återanvänds: endast tre statiska appfiler ändras.

## Paketering och återgång

Den aktiva förälderns tre filer jämfördes med Git-hashar före paketering.
Image byggdes utan nätåtkomst ovanpå exakt befintlig appimage.

- Ny image: `sha256:78edde2cc66dc16300edf9b8de62fc378ea44aef20d6e3ebb9d7c0fca3d651f7`.
- Förälder/återgång: `sha256:81501a07c22e49f1e889f89a6f1f0d3cdd1879172c64fe30b5498ad10be938b2`,
  build `postcode-meals-93c4f9ac4505`.
- Serverbevis: `/opt/smako/evidence/editable-sliders-7987bd5bc5d1`.

Vid återgång används driftlåset och sparad compose-wrapper med förälderns
appimage. Återställ aldrig en äldre databas över senare användararbete.
Scheduler, källprofiler, prismanifest och Windowsuppgift ingår inte i ändringen.

## Aktivering

Aktiverad 2026-10-11 19:24 UTC (21:24 svensk tid), se `ACTIVATED.json`.
Endast appimage och BUILD_ID ändrades under befintligt driftlås. Privat
PlanStore säkerhetskopierades och integritetskontrollerades; samtliga 258
tidigare planrevisioner och 84 privata tillstånd bevarades med oförändrade
radhashar. Prismanifest, mounts, övrig miljö och andra containrar bevarades.

Isolerad slutkandidat skapade en riktig plan, verifierade checkout-audit och
identisk GET, räknade om och återläste sparad plan: 88,6 sekunder. Chromium
kontrollerade fasta fördelningsskalor, manuell inmatning och de nya näringstaken.
WebKit kontrollerade mobilvy och Malmöval. De tre publicerade filernas hashvärden
matchar paketet. Skärmbilder granskades och fältbredden justerades så att även
tomma värdens hjälptexter ryms.

Driftstatus efter bytet: ready med rätt build, samma publicerade/laddade
prismanifest och fem kvalificerade baskällor publicerade och laddade.
Det lokala reläet hade ingen väntande leverans. Observation 19:24 UTC;
färskhetsgränserna 36/48 timmar är oförändrade.

Det första publika planprovet gav en 500 under `product_facts`:
`sqlite3.OperationalError: database is locked` vid den befintliga katalogläsningen
i `personal_source_facts.py:703`. Exakt incident hämtades med ordinarie
`smako_ops.py app-incident` och bevarades lokalt; efterföljande separat läsprov
av samma tabell lyckades. Driftstatus och WebKit-kontroll hade körts samtidigt
med första planprovet; den exakta låsägaren är inte fastställd. Ingen käll- eller
databasinställning ändrades för att kringgå felet.

Det separata publika omprovet passerade på 65,2 sekunder: rätt build, manuellt
angivna måltidsvärden, uppskattade köp och näring, godkänd checkout-audit,
identisk sparad GET och återläsning i gränssnittet. Inga JavaScript-fel.
Det belägger återhämtad planberäkning, inte en åtgärdad generell låskonflikt.
Testcontainrarna är stoppade och tunneln stängd; inga aktiveringsväntare finns kvar.

# En gemensam sökmeny för inköpslistan

Implementerad och isolerat verifierad. **Inte aktiverad på beta.**

- De två tilläggsknapparna ersätts av **Lägg till vara** och en sökruta.
- Förslagen visas som en meny under rutan medan användaren skriver.
  Generiska förslag kommer först; ”Kaffe” börjar med ”Bryggkaffe · 500 g”.
  Därefter kommer konkreta produkter. Det interna generiska registret styr
  vilken betydelse som prioriteras; både närmare och ursprungliga matchningar
  hämtas med befintligt produktindex. Ingen kandidat tas bort ur korgsökningen.
- Inga butiksväljare, butiksnamn eller priser i dessa förslag. Varumärken
  som Coop kan fortfarande ingå i en produkts namn. Butik väljs i korgberäkningen.
- Ofullständig förpackning visas sist med tydlig text och kan inte väljas
  genom denna snabbmeny. Ingen falsk ”null”-text eller påhittad förpackning.
- **Tillbaka till generisk vara** finns i produktdialogen. En tillagd generisk
  rad har **Ändra vara** för namn, mängd och enhet; samma rad ersätts vid sparning.
- Menyn stöder tangentbord, Escape och klick utanför. Gamla planer och privata
  sparade val använder samma modeller och lagring som före ändringen.

## Produktidentitet

Verifierad GTIN/förpackning fortsätter att ge en exakt produktkoppling.
Identiskt namn, varumärke och förpackning utan gemensamt identitetsbevis
slås inte ihop till en påstått verifierad produkt. Förslaget visas en gång;
användaren bekräftar de uttryckliga varuvalen i produktdialogen, utan att välja
butik. De sparas med sina egna nycklar via befintlig one_of-väg. Andra varianter
läggs aldrig till automatiskt. Maximalt åtta alternativ kvarstår.

## Testat

59 backendtester lokalt och samma 59 mot den paketerade imagen PASS.
Både Chromium och WebKit i mobil layout PASS: kaffemenyn och ordningen,
frånvaro av butiksval/priser, mängd-/enhetsredigering utan dubblettrad,
återgång till generiskt val, gruppval med bevarade exakta produktnycklar,
omladdning, dubbelklick med ett jobb, riktig korgberäkning, audit, sparad GET
samt annan ägares nekade åtkomst. Inga pageerrors, nätfel eller server-5xx i slutproven.
Ruff och compileall PASS. Serverad HTML/JS/CSS hashmatchar paketet.

Två CPU och 3 GiB; appkoden kommer från imagen utan källkodsmount.
Pris-/faktaunderlaget är samma historiska replay som i föregående kandidat,
inte en liveoffert eller fysisk telefontestning. Inga insamlingar eller
produktionsändringar. Tidigare omstarts-/revisionsbevis för oförändrad
lagringskod återanvänds, inte redovisade som nya omstartsprov.

Ett prov startades för tidigt under bygget och träffade föregående utvecklingsapp.
Det avbröts korrekt av en assertion och bevaras som FAIL. Slutverktyget kräver
rätt BUILD_ID före knappflödet. De slutliga proven använder rätt identifierad image.

## Leverans

Runtime `6b10628f22d8315ba9758ae6e5381cb711365478`.
Image `sha256:a5b678ca483135037c8a4d20cb61738861b544bfbcc21c58e8389b9f022bae32`.
BUILD_ID `shopping-list-6b10628f22d8`.
Paket `smako-shopping-list-6b10628f22d8.zip`, 131100 byte,
SHA-256 `14ccb4780572d50e1a7331ed5e60b99366fc6029060a698e3db554bd71803bfc`.
Paketet ligger på D: under `.local/shopping-quick-menu-20261009/package/`.

Separat framtida aktivering följer [inköpslistans app-only-anvisning](../shopping-list-20261008/ACTIVATION.md),
med **ovanstående nya identiteter**. Gamla paketet ska inte installeras för att
få den här menyn. Övriga skydd, backup, aktuell appkontroll och begränsningar
för binär-/flagga-återgång gäller fortsatt. Ingen aktivering gjord i denna etapp.

Reproduktion mot isolerad app med exakt denna image och replayunderlag:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/release_verification/shopping_quick_menu_browser.py --expected-build shopping-list-6b10628f22d8 --output .local/shopping-menu-new-proof
```

Kontoinloggningens tidigare konfigurationsbegränsning kvarstår. Detta är en
rättning av varuvalens gränssnitt och förslagsordning, ingen ny inloggningsrelease.

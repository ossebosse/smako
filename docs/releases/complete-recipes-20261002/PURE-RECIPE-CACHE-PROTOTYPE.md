# Avgränsad prototyp: återanvänd rena receptberäkningar

Utgår från runtime `38ee1aa5ecbc64045801a4f40f9c0302ed0e4a09` i egen
arbetsgren `perf/recipe-quote-reuse`. Ingen fjärrberäkning, integration,
paketändring eller produktionsaktivering har gjorts i detta delprov.

Den autentiska breda Varierad-körningen på 2 CPU/3 GiB gav ett giltigt resultat
men tog cirka 17,6 minuter. Befintlig rapport har mycket veckosöktid utanför
förpacknings-, närings- och auditstegen. Lokal profilering bekräftar upprepad
normalisering, innehålls-ID, proteinklassning och full versionsvalidering.
Detta förklarar en konkret onödig kostnad, men mikroproven nedan visar inte
hur stor andel av hela den autentiska körningen som kan tas bort.

Ändringen omfattar:

- Exakt receptnyckel med oförändrade, orundade mängder, full fryst design och
  snapshots av ingrediens-/instruktionslistor samt beredningens formordbok.
  Även formordbokens ordning bevaras eftersom äldre innehålls-ID använder den.
- Högst 512 rena beräkningsresultat per cache och planering. Recept-ID,
  proteinklass och standardnormalizerns receptprofil återanvänds. Priser,
  butiksvillkor, skafferi och näringsbeslut ligger kvar i sina befintliga vägar.
- Befintlig innehållscache i `clean_recipe` får träffa före upprepad validering.
  Valen för kompletta recept ingår nu uttryckligen i dess nyckel. Ändrat
  innehåll eller ändrade val valideras på nytt.
- Anpassade normalizers och MenuOptimizer-underklasser behåller tidigare
  profilberäkningsbeteende. Sökbredd, retry, ordning, tie-breaks, kostnadstak,
  recept-/produktkandidater, offertcache och kvalitetsgrindar är oförändrade.

Lokala Windows-mikroprov med bibliotek
`smako-complete-dinners-v1:1c623aa7e4a8e8f9cde292807198c59d6f191f0dd3030462a254893995e7e90c`:

| Ren beräkning | Före, median | Prototyp, median | Kontroll |
| --- | ---: | ---: | --- |
| 200 femrättsförslag över alla 104 kandidater | 1,797 s | 0,281 s | Exakt samma ID, klassning, acceptans och preferenspoäng |
| 100 000 fulla receptnycklar inklusive hash | 2,660 s | 0,950 s | Alla receptfält samt muterbara behållare ingår |

Tre repetitioner per väg, sekventiellt på den lokala utvecklingsdatorn.
Tiderna är inte jämförbara med serverns resursbegränsade hela planering.
Råprofil, körskript och mikroresultat finns i arbetskopians ignorerade `.local`.
Ingen uppmätt förbättring av hela Varierad-flödet påstås här.

Verifierat: 322 relevanta tester över de fokuserade körningarna, Ruff och
compileall. Detta inkluderar alla 104 kandidatprofiler, exakta mängdändringar
på `1e-10`, instruktioner, formordbok, design, portionsantal, namn, ändrade
receptval, cachelivslängd, anpassad normalizer, oförändrad sökordning och trace,
samt normal personlig planering med näring, köp och audit jämfört med samma
kodväg utan den nya rena beräkningscachen.

Första breda körningen saknade en ignorerad historisk testartefakt och fick
13 setup-fel. Oförändrad fil återanvändes från projektroten, SHA-256
`9a66691dd5cefc4fd9bf53a72037948bf7e4c939558fd21be760d5a3c2ab5afa`;
alla 15 berörda erbjudandeprov passerade sedan. Ingen fixture eller faktisk
produkt har handändrats. Befintliga serializer-varningar gäller en äldre
syntetisk fixtures enumfält, inte avvikande resultat.

Nästa verifiering är samma autentiska breda Varierad-begäran med oförändrat
fryst prisunderlag, resursnivå, medlemskap och val. Full meny, audit, kostnad,
ordning och sökdiagnostik behöver jämföras innan eventuell integration.

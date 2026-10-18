# Granskad betarelease: planering, uppstart och recept

Användaren beställde 2026-10-18 att uppgiften till Claude skulle skrivas och
committas, därefter betan aktiveras. Uppgiften finns i
[CLAUDE-RECIPE-SCALING.md](../../CLAUDE-RECIPE-SCALING.md), commit `540b123`.

## Paketets omfattning

Pinnad Git-kandidat: `bac0fc15ca9a5dffe2cde80d8c977d238fa40028`.
Runtimekoden för planeringen är densamma som granskade `a70f3af`/`90ddeeb`.
Intervallet sedan senast aktiverade appkod `e041451` omfattar också tidigare
granskade uppstarts-, faktalås-, recept-, ägg- och sökrättningar.
Biblioteket har 222 recept (125 grundrecept och 97 variationer).
De 20 prototyperna från tillväxtprovet ingår inte.

Kandidatens BUILD_ID är `app-bac0fc15ca9a-512ef3ea` och image
`sha256:574025c92df8ffc6dec47d0200c20750eb863fe6b69e214710bd56abdfffb79d`.
Den bygger ovanpå faktiskt aktiv image
`sha256:93bbfd2ebe3764cddd559422ed1fce53197359b6f0aabde50619dfc6a81cd8f7`.
26 runtimefiler ändras. Bygget sker utan nätverk och verifierar varje
ursprunglig/ny filhash, compileall och att andra runtimefiler är oförändrade.

## Uttryckligt granskat undantag från vanlig app-paketering

Den vanliga paketeraren stoppade korrekt en skillnad i `config.py`: betan har
sedan tidigare stöd för `BETA_ADMIN_PASSWORD_HASH` som saknas i main. Att
skriva main-filen direkt skulle ta bort stödet för betans inloggning.

Ett separat granskat paket bevarar exakt de tre befintliga tilläggen:
settingsfältet, formatvalideringen och miljöinläsningen. Se
[exakt bevarad differens](preserved-config.patch). Paketbyggaren kontrollerar
att aktiv config är Git-basen plus just dessa tillägg, och att sammanslagningen
ger samma bytes oavsett vilken ändring som appliceras först. Alla övriga 25
ändrade filer är byteidentiska med vald Git-commit. Inga lösenord, hashvärden
för verkliga lösenord eller miljöhemligheter finns i paketet eller rapporten.

Main-configens SHA-256: `af931604e6a3f71024493657d952b7da13049b75f5c552468839ccac494893bd`.
Kandidat-configens SHA-256: `925db7e7a7ab6aa048f839b1663dcda0db072e249ccaba0028b31171ed58ccf0`.
Aktiv admin-autentisering, dashboard och andra oförändrade filer behålls från
basimagen. Detta är en exakt dokumenterad patchrelease, inte ett påstående om
att hela serverimagen kan byggas från enbart main. Full konsolidering av
tidigare serverändringar kvarstår separat.

Ordinarie build- och aktiveringsworkers används oförändrade. De kontrollerar
pinnad basimage, paket-/filhashar, oförändrad övrig miljö, driftlås, lugn
menytrafik, verifierade databasbackuper, databevarande och rollback vid fel.
Den vanliga paketerarens krav på exakt Git-matchning har inte tagits bort.

Separat verktygsrättning `bac0fc1`: en appmodul som heter
`content_pack_requirements.py` klassas inte längre som ett beroendemanifest;
`deploy/.env.production.example` behandlas som dokumentation och installeras
aldrig. 16 paketeringstester passerar, inklusive spärrar för riktiga beroenden
även under appkatalogen, schema, compose, deploy-skript och felaktig lineage.
Ruff och compileall passerar. Serverns miljö ändras inte av exemplet.

## Verifiering före aktivering

- [Full granskning av planeringsoptimeringen](../../reviews/planner-exact-speed-20261018.md):
  2 835 lokala backendtester passerade med 10 kända XFAIL och 2 SKIP.
- [CI för releasecommit bac0fc1](https://github.com/ossebosse/smako/actions/runs/39156892674)
  är grön, inklusive webbläsartester. Admin-undantaget kontrolleras separat
  mot den byggda imagen; det ingår inte i main-CI:n.
- Den faktiska imagen klarar appimport, full strukturell biblioteksvalidering
  och settingskontroller med ett syntetiskt lösenord. Direkt prov av dess
  autentisering accepterar rätt lösenord och drift-token samt avvisar fyra
  obehöriga fall, inklusive försök att använda drift-token som lösenord när
  lösenordshash är konfigurerad.
- Separata frysta planeringsprov körs mot den faktiska imagen, med dess egna
  appfiler och bibliotek. Endast testharness och frysta publika indata monteras;
  inga produktionsdatabaser eller användarprofiler används.

Samtliga fyra prov PASS, identisk full resultathash mot tidigare granskad
222-receptsreferens och godkänd checkout-audit:

| Stad | Kall tid | Varm tid | Pris i båda körningar |
| --- | ---: | ---: | ---: |
| Lund | 42,46 s | 35,91 s | 548,76 kr |
| Malmö | 54,96 s | 47,74 s | 534,92 kr |

Detta är funktionsverifiering, inte en ny jämförande hastighetsstudie. Det
ordinarie prisbygget pågick samtidigt. De fyra hashverifierade indatafilerna
per stad och tillfälliga förberedelsecachefiler togs bort efter proven;
originalarkiv och rapporter behölls.

Byggkvitton, separat paketbyggare och verifieringsunderlag finns lokalt under
`.local/beta-planner-20261018` och på servern under
`/opt/smako/evidence/app-bac0fc15ca9a-512ef3ea`. Aktiveringsutfallet och de
publika proven journalförs separat efter genomförd aktivering.

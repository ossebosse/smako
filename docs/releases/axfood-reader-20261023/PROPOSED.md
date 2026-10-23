# Axfood-reader: förberedd, inte aktiverad

Kandidat `c981d757b081f79f3926d9bcb6349c9918fcfb4d`, BUILD_ID `source-ops-c981d757b081`:

`sha256:92be15f2efa053f7c85bc398782d10618e9e1d06dbef24625528862753e6ffbf`

Bas: aktiv `sha256:dc23ba03be3ca2370d28d6230d392160a63fb278a56f5b0171ebe91947713072`, BUILD_ID `app-c253cbd9ef93-9940259d`.
Paket `smako-source-ops-c981d757b081.zip`, SHA-256 `d31850a6df5862a45ca8b5566d821406875408465ea13ac2b5574370381cdd6a`.
Exakt tre runtimefiler ändras; deras SHA och verifierad oförändrad konfiguration
finns i [manifest.json](manifest.json). Planner, receptbibliotek, databasschema,
ICA och scheduler ingår inte. Den aktiva bildens äldre admin-inställning bevaras.

## Verifierat

- Immutable v3-release `16410fb3d4e21746a75cb6c34072bb4bcc159c20ceefec2ba1187bb883ac233a`: 103 verifierade dokument, 18 negativa svar.
  Fulla kodlistor/täckningsbortfall finns i [arbetsrapporten](../../reviews/verified-reference-axfood-20261023.md).
- Bildens native bibliotek har 222 recept. Två städer × sju profiler × två
  faktaversioner × tre upprepningar gav 78 slutkontrollerade menyer och sex
  oförändrat blockerade Malmö/vegan-anrop. Alla par behöll utfall och kassasumma.
  För varje giltig, stabil gammal meny gjordes separat ny audit mot berikade fakta.
- Native-provet körde föregående reader-image `2f2f8b8`. Återanvändningen binds
  till verifierat byteidentisk planner/modeller/bibliotek och exakt samma färska
  faktaprojektion i slutimagen för båda städerna. Endast reader/projektor skiljer;
  gränsvärden och felaktig precision har dessutom riktade prov i slutkodens fulla CI.
- Production-klon med temporära databaser och syntetiska nycklar: bas → kandidat
  → återgång ger readiness 200 för 22350 och 21120. Alla prispekare är oförändrade.
  Kandidatens cgroup-peak var 2789945344 byte med 3 GiB-gräns.
  Basens peak var 3035136000 byte; detta är inga jämförbara
  latens- eller kall-diskmätningar. Önskad marginal på 2,5 GiB nåddes inte.
- Inga produktionsdatabaser användes. Bakgrundspreparering av källfakta stängdes
  av i readiness-klonen; färsk faktaladdning verifierades separat ovan. Provet
  bevisar inte produktionens fulla bakgrunds-prewarm eller total cachekapacitet.
  Befintliga aging/degraded-varningar redovisas; pris-/kvalitetskrav sänktes inte.
- [Full app-CI](https://github.com/ossebosse/smako/actions/runs/40019613139):
  3 094 PASS, 10 XFAIL, 53 SKIP inklusive Chromium/WebKit. Riktade arkiv-, reader-,
  protokoll-, kö- och integritetsprov samt Ruff/compileall passerar.

## Konkret driftförslag

[compose.proposed.yaml](compose.proposed.yaml) väljer exakt image/BUILD_ID och
monterar endast den pinnade releasen read-only. `AXFOOD_PRODUCT_DETAIL_ROOT`
pekar på samma exakta katalog i containern. Filen har inte installerats eller
lagts till i den aktiva Compose-listan. Övriga image-/miljö-/volymvärden bevaras.
Paket och data finns redan på servern under evidensroten i manifestet.

Vid ett separat godkänt appbyte används befintligt driftlås, kontroll av lugn
menytrafik och roterande fullbackup enligt BETA.md. Bekräfta att basbilden och
Compose-listan fortfarande matchar manifestet; annars krävs ny verifiering.
Aktivering ändrar inte PriceUniverse-manifest, observationstider eller priser.
Den installerar inte den nya sökpolicyn eller någon automatisk detaljinsamling.

Rollback återställer manifestets exakta tidigare Compose-lista, basimage och
BUILD_ID, tar bort det tillagda mount/env-override och startar en ny appprocess.
Föregående faktakonfiguration återkommer och härledda processcacher återskapas;
inga produktionsdatabaser eller prismanifest återställs. Samma två readiness-
anrop och prispekarnas SHA kontrolleras igen. Klonprovet verifierade detta
förfarande med separata data, utan ett produktionsbyte.

## Retention och kommande uppdatering

[retention.proposed.json](retention.proposed.json) är ett framtida referensregister,
inte ett påstående att releasen redan är aktiv. Befintlig retention har stöd för
aktiv/rollback/evidens, minst två senaste, högst åtta/32 GiB och sju dygns marginal.
Utan register bevaras alla releaser. Okända/korrupta kataloger och staging bevaras.
Inget Axfood-register eller scheduler-env har installerats i detta steg.

Godkända katalograder utgör insamlingskön via `--approved-snapshot` i main;
befintlig journal styr 30-dygnsomprövning, sju dygn efter 404/410 och retry/stopp.
En framtida automatisk uppdatering måste väljas separat, använda samma befintliga
driftlås och staging/validering/atomisk publicering, samt behålla LKG och dess
verkliga ålder. Nytt katalogscope eller högre hämtningstakt ingår inte.

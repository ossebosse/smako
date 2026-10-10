# Aktiverat på beta 10 oktober 2026

**App och källprocess aktiverade 19:28:53 svensk tid (17:28:53 UTC).**
Runtime `5786d5fa6a0febb7a581a70e583e5c876d494da2`.

- App: `comparability-app-5786d5fa6a0f`, image `ca1b35327a55…`.
- Källprocess: `comparability-source-5786d5fa6a0f`, image `63cc251fcc6f…`.
- Paket och fulla imagehashar: [ACTIVATION.md](ACTIVATION.md).
- `/ready` 200. Samma prismanifest publicerat och laddat: `50c0bb0e83de…`.
- Kompletta recept fortsatt aktiverade. Proxy, reläfe795, mounts, miljö utom
  BUILD_ID, behörigheter, scheman och data bevarade. Ingen migration/serverbuild.

## Verifierade liveflöden

Chromium och WebKit, mobil vy, separata nya gäst-/sessionsidentiteter:
prisfri snabbmeny, hela köpförpackningar, kampanjval, riktig korgberäkning,
dubbelklick med ett start-POST, audit, omladdning, omräkning till revision2,
oförändrad revision1 och ägarisolering403. Publik produktsökning PASS i båda.
Ingen fysisk iPhone-testning eller generell verifiering av alla kontoleverantörer.

Publik Chromium-meny PASS: fem enkla middagar för två, butikstak3, uttryckligt
köp-/näringsmedgivande. Faktiskt publicerade data utan replayklocka. Hela korgen
251,95 kr, använd mängd125,26 kr, audit godkänd med redovisade uppskattningar.
143,59 s klick till renderat resultat i detta enda prov; inget nytt prestandalöfte.
Ett jobb, omladdning under beräkningen, receptöppning, inköpslista, sparad GET
och annan ägares avslag. Ingen syntetisk provlagningsfeedback skickades.
Inga pageerrors eller nätfel i de godkända flödena.

24 appfiler och7 källimagefiler kontrollerade i **körande** containrar;
6 verkligt serverade HTML/JS-filer matchar paketet. Alla247 tidigare revisioner
samt79 privata tillstånd är hashbevarade; efter proven252 revisioner/82 tillstånd.
Samtliga251 revisioner som fanns vid den direkta äldre-läsningen materialiserades;
den ytterligare publika revisionen lästes genom ägarkontrollerad GET.

## Backup, begränsat byte och drift

Operationslåset hölls under bytet. Inga plananrop under föregående15 minuter;
CPU0,02/0,04 s under två10s-prover. Detta är ett vilobelägg, ingen direkt
räknare över minnesjobb. Konsistent SQLite-backup110747648 byte,
SHA-256 `55961931e2508f25deda94b9356f9c03463b940d4e317e8970f066d0aada49ca`,
integrity/FK-kontroll PASS. Privat backup/Compose före/efter finns skyddat under
`/opt/smako/evidence/comparability-activation-20261010/`, utanför Git.

Upplöst Compose-diff: endast app.image, app.BUILD_ID, scheduler.image och
scheduler.BUILD_ID. COMPLETE_RECIPES_ENABLED=true bevarades. Tidigare
produktionsresursgränser var osatta och ändrades inte; de isolerade testerna
med två CPU/3GiB ska inte beskrivas som produktionsmiljön.

Den gamla schemaläggaren väntade på den gemensamma900s-stopptiden medan nya
appen var skapad. `docker top` visade enbart cron, inga barninsamlingar.
Just schemaläggaren stoppades med10s timeout under befintligt operationslås,
varpå det ordinarie Compose-bytet slutfördes. Inga databas-/insamlarprocesser
avbröts, inga lås bröts. Bytet var inte ett avbrottsfritt byte.

Serverutrymme:16103006208 byte före staging;15977914368 byte vid efterkontroll.
Behovskalkyl8870685402 byte, marginal godkänd. Ingen rensning gjordes.
Reläets verkliga v3-artefakt05f37497… kvalificerades läsande med nya källimagen:
19108 rader/10587 produkter, utan ny import. Mottagaren omparsar råunderlaget;
ingen ändring av Windowsreläet krävs för dessa parserfält.

Ordinarie behovskontroll `*/15 * * * *`, backup `47 02 * * *` återlästa.
Windowsuppgiften är Ready/enabled, senaste resultat0, nästa start
11 oktober01:30 svensk tid. Inga uppgifter lämnades pausade.

## Viktigt: Scan-kampanjens publicering återstår

**Källfixen är aktiv, men Scan65-raderna är ännu inte publicerade på beta.**
Coops tidigare fel har nästa tillåtna återförsök10 oktober20:00:40 svensk tid.
Med ordinarie15-minuterskontroll väntas första passande kontroll20:15.
Historik/backoff och scheman har inte skrivits om. En framtida körning är
inte verifierad i förväg. Inga nya prisinsamlingar eller manuella publiceringar
startades här; råpriser/observationer har inte föryngrats.

Alla fem obligatoriska baser är fortfarande FRESH, cirka27,2–28,0h vid
19:32-kontrollen. Nästa avgränsade kontroll: `scripts/smako_ops.py status`
och Coops ordinarie källjournal efter att nästa försök slutförts. Bekräfta då
kvalificering → nytt manifest → laddning innan Scan kallas tillgänglig live.

[Sanerade maskinbevis](ACTIVATED.json). [Kandidatens ursprungliga prov](RESULTS.md).
Huvudgrenen är `master`; användaren har godkänt sammanföring och vanlig push.
Ingen historik skrivs om och inga privata driftdata/imagearkiv läggs i Git.

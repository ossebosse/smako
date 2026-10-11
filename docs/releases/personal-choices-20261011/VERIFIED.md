# Mina val: aktiverad på betan

Appcommit: `b48ca5925820bc4eb87c2d46fb5f32104fe1d2f5`.
Build-ID: `personal-choices-b48ca5925820`.

Aktiverad 2026-10-11 15:07:33 UTC (17:07 svensk tid) på
`https://beta.smako.nu/personal#choices`, efter användarens godkännande.
[Maskinläsbart aktiveringsbevis](ACTIVATED.json).

Ändringen samlar huvudreglagen för middagar, 1–6 portioner och butikstak.
Extraval innehåller fler måltider, gemensam smakprofil, näringsreglage och
befintliga övriga inställningar. Nya planer och uttrycklig omräkning tillåter
spårbara näringsuppskattningar och uppskattade köp. Standardgränser bevaras;
variationsbudget är intern (25 %).

51 riktade lokala testfall passerar, inklusive Chromium/WebKit, återläsning av
äldre profiler och skydd av tidigare revisioner. Ruff, compileall och JavaScript-
syntaxkontroller passerar. Fyra statiska filer är hashverifierade över HTTPS.

Kandidaten bygger som en sexfilers appdelta på betans exakta befintliga bild.
Samtliga sex basfiler matchade den testade föräldern. Kandidatens riktiga UI
skapade en middag för två portioner med publicerat Willys-underlag i Lund,
genomförde omräkning och läste tillbaka samma sparade plan. Checkout-audit och
summakontroll passerade. Chromium och WebKit gav inga sidfel. Testet använder
egen gästsessionsdata och separat PlanStore; det är inte en användarprofil.

Paketets SHA-256:
`dd8e9eccd110f53a00d481a9d96251211f14358ac38cb0004094c286058f9827`.
Kandidatbild:
`sha256:8040a97b586b310a48b260012746798eefd87d8d945feee08d1bcf585f9978b5`.

Skyddat serverunderlag:
`/opt/smako/evidence/personal-choices-b48ca5925820`.
Lokala prov och skärmbilder: `.local/choices-deploy/`.

Aktiveraren kräver driftlås, lugn planering, SQLite-backup och exakt Compose-diff
för appbild och BUILD_ID. Den kontrollerar bevarade mountar, miljö, övriga
containrar, tidigare databasrader och aktiva prismanifest. Vid misslyckad
uppstart återställs föregående Compose-wrapper och appbild med senaste data.
Ingen äldre databas återställs.

## Aktivering och publik kontroll

Endast appcontainern byttes. 256 tidigare planrevisioner och 82 privata tillstånd
är hashbevarade. SQLite-integritet, aktiva prismanifest, mountar, miljö (förutom
BUILD_ID), scheduler, proxy och övriga befintliga containrar är verifierade.
Ordinarie Malmöuppdatering höll driftlåset och fick slutföras före aktivering.
Låset är släppt; ingen aktiveringsväntare återstår. Windowsuppgiften är orörd.

På publik beta skapades en ny plan via Chromium med separat verifieringsgäst,
checkout-audit och identisk sparad återläsning (35,5 sekunder inklusive kontroll).
WebKit verifierade mobilreglagen, tillvalen, frånvaro av dubbletter och ingen
horisontell överströmning. Alla fyra statiska filer matchar releasens SHA-256;
båda webbläsarna saknar sidfel. Den isolerade kandidaten verifierade dessutom
uttrycklig omräkning. Detta är inte ett fysiskt iPhone-prov.

Testcontainern är stoppad. Skyddad backup och tidigare appbild är kvar. Vid
återgång ska senaste databas behållas; använd den sparade Compose-wrappern och
föregående appbild under befintligt driftlås. Inga aktuella planer får ersättas
med backupen som normal återgångsåtgärd.

# Publik generering: uppföljning 2 oktober 2026

Utgångspunkt är den faktiskt driftsatta appen `14cc716` och
[Lunds aktiveringsprotokoll](../lund-20260929/ACTIVATION-LIVE-20261001.md).
Detta är en riktad appändring, inte en ny områdesaktivering.

## Belagda fel och avgränsning

Användarens Fel-ID `29f7a372-e1cf-4b51-8195-0db36605e535` motsvarar
POST `/api/plans`, HTTP 503, 1,658 ms, 2 oktober 10:19:01 CEST,
build `14cc716`. Historiska request- och response-bodyer saknas i den
beständiga loggen. Postnumret i detta enskilda försök är ännu inte bekräftat;
det tillskrivs därför inte säkert nedanstående postnummerfel.

Följande har däremot reproducerats:

1. Med 22350, 5 middagar, 2 portioner, högst 3 inköpsställen, exact, mixed,
   Balanserad och de sex faktiska medlemsprogrammen fungerar gamla appen
   i en separat Chromium-session: 201, 3,125 s, request-ID
   `230c7e6d-f659-45b8-9eac-cab537bda945`.
2. Med samma formulär men testpostnumret 22222 svarar publika knappen
   503, `consumer planning requires a matching active local PriceUniverse`,
   request-ID `5f6b151f-df2c-497e-a703-22ade9cb7f10`. Aktiv artefakt har
   endast `22350` i sin postnummernyckel. Frontend beskriver detta felaktigt
   som pågående prisuppdatering och stänger av knappen som vid globalt
   driftstopp. Backendloggen matchar POST, 503 och 1,489 ms.
3. WebKit med mobilvy i en separat testsession bryter en lång menybegäran
   efter 66,485 s med `Timeout was reached`, request-ID
   `1bb9ba07-08df-4423-af6d-56470fabd482`. Servern arbetar fortfarande.
   Chromium-kandidatens kalla beräkning tar 332,781 s och slutförs med 201.
   WebKit är inte ett faktiskt iPhone-prov. Det första avbrottet observerades
   mot isolerad kandidat via HTTP-loopback; slutprovet använder HTTPS.

Uppdateringskontrollen 10:45 CEST var `not_due`, utan externa prisanrop.
Den generiska uppdateringstexten var inte evidens för en prisuppdatering.
Proxyn har ingen accesslogg för att återläsa historiska bodyer. Publik HTTPS,
fångad nätverkstrafik och korrelerade backendposter används som transitbevis.

## Rättning

`4b28304`: ett postnummer utanför aktiverad täckning ger 422 med
`body.postal_code` och aktuell tillåten täckning. Värdet ändras inte åt
användaren. Saknat respektive oanvändbart prisunderlag får separata felkoder;
andra 503-fel beskrivs som tjänstefel. Endast faktisk `/ready`-status kan
stänga av planeringen globalt. Fel-ID, alla val och statusknappen bevaras.

`74c9077`: formulärets POST `/api/plans` skickar `Prefer: respond-async`.
Efter befintlig validering startar samma planner och samma sparning i ett
begränsat jobb. POST returnerar 202; webbläsaren följer en sessionsbunden
GET `/api/plan-jobs/{job_id}` tills resultatet eller ett precist fel finns.
Korta anrop ersätter den långa tysta webbläsaranslutningen. Det ändrar inte
beräkning, antal butiker, medlemskap, köp- eller näringsmedgivanden.

Jobben använder befintlig ägarsession och planner-kö. Annan ägare får 404.
Samma ägares identiska pågående försök återanvänder samma jobb. Antalet
pågående och kvarhållna jobb är begränsat; slutförda transportposter löper
ut efter 15 minuter. Färdiga planer sparas fortsatt i PlanStore. Oavslutade
jobb överlever inte appomstart; en sådan poll får ett uttryckligt fel och
formuläret behåller värdena. Vanliga API-anrop utan Prefer är fortsatt
synkrona, inklusive de separata 15/20-proven.

Ingen ändring av prisområdets täckning, kvalitet, identitet, näringskrav,
färskhetsgränser, relä, scheman eller femkällorspolicy. Ingen användarprofil
har ändrats. Inga cookies, token eller ägaridentiteter ingår i bevisen.

## Verifiering

Nio felregressioner fallerade före första rättningen. Async-regressionen
fallerade före andra rättningen (synkront 503 i stället för snabbt 202).
206 fokuserade tester passerade, inklusive konsumentflöde, kögräns,
ägarisolering, postnummerfält, färskhetsspärr, felpresentation och statusretry.
Efter sista transportjusteringen passerade de 16 direkt berörda testerna
igen. Ruff, compileall och diffkontroll passerar.

Kandidat `74c9077001b3084317f36630fd38ce48e4663473`:
image `sha256:80e8ba59c9b04c8bff668062da2bf1937eae236881472449e2a0180f42387180`.
Serverpaket SHA-256 `5c2b6b36f827a59bd6171443db4a6f036b278ce2a1568070ca0f8bb69d9f994b`.
622 runtimefiler matchar paketet; pip check och offline Chromium-start PASS.
Kandidaten använder isolerad plandatabas och läser produktionspriser read-only.

## Drift och publik knappacceptans

App `74c9077` är driftsatt cirka 11:15 CEST med befintligt driftlås och
app-only-förfarande. Samtliga 188 tidigare planrevisioner och prismanifest
är bevarade, SQLite integrity PASS, miljön är oförändrad förutom appens
BUILD_ID. Scheduler/källjobb är fortsatt `08c1374`; proxy och scheduler
har samma containeridentiteter. Återgångskod och skyddad onlinebackup finns
under `/opt/smako/evidence/public-menu-followup-20261002`.
[Driftsättningsbevis](deployment.json).

Den kalla HTTPS-kandidaten passerade i WebKit efter 336,250 s, och Billigast
efter 3,547 s. Alla kontroller för recept, mängder, inköpslista, kvalitetsmärkning,
kostnadsavstämning, val och sparning/återläsning PASS.
[Kandidatens knappbevis](candidate-webkit.json).

Publika `https://beta.smako.nu`, faktiska knappen i separata sessioner:

| Webbläsarprov | Val | POST → slutresultat | Total tid | Kostnad |
| --- | --- | --- | --- | --- |
| WebKit, 390 × 844 med touch, kall | Balanserad, sex medlemskap | 202 → 201 | 338,359 s | 168,55 kr |
| WebKit, 390 × 844 med touch, varm | Billigast, sex medlemskap | 202 → 201 | 3,563 s | 125,10 kr |
| Chromium, 1280 × 900, ren session | Balanserad, inga medlemskap | 202 → 201 | 314,218 s | 168,55 kr |
| Chromium, 390 × 844 med touch, varm | Balanserad, sex medlemskap | 202 → 201 | 3,046 s | 168,55 kr |
| Chromium, 390 × 844 med touch, varm | Billigast, sex medlemskap | 202 → 201 | 3,515 s | 125,10 kr |

Alla fem har fem middagar × två portioner, tre inköpsställen, fullständiga
instruktioner och ingrediensmängder, verifierad korg, kvalitetskontroller PASS
och identisk sparad plan efter omladdning. Inga JavaScript-fel. Detta är
WebKit-prov och Chromium-prov; ingen fysisk iPhone har provats.
[Samtliga knappbevis och sanerade requests](public-acceptance.json).

308 av 308 start-, status- och resultatanrop matchar backendloggens request-ID,
endpoint, metod, HTTP-status och build. Fördelning: 302 × 202, 5 × 201,
1 × 422 från det avsiktliga fältfelsprovet. Faktiskt serverade app.js,
index.html, personal.js och service-worker.js matchar Git `74c9077`.
Readiness är 200/ready och användbart prisunderlag är fresh.
[Drift- och korrelationsbevis](runtime-after.json).
[Publik inköpslista](public-mobile-shopping.png),
[publika fullständiga recept](public-mobile-recipes.png),
[korrekt postnummerfel](public-postal-error.png).

POST-start och efterföljande GET-statusanrop är separata HTTP-svar, inte
ett förtäckt synkront 201. Kalla publika WebKit-provet krävde 154 korta
statusanrop; längsta observerade HTTP-anropet var 4,932 s. Det tidigare
cirka en minut långa anslutningsproblemet reproduceras därmed inte med
den nya transporten under samma fullständiga beräkning.

Fältfelsprovet gick först via publika knappen med 22222. 422 pekade ut
postnummerfältet, behöll samtliga val och lämnade knappen användbar. Därefter
ändrades enbart postnumret till 22350 i samma testsession och den kalla
Balanserad-menyn skapades. Detta är inte en ändring av användarens profil.
En separat session nekades jobbresultatet med 404 och sparad plan med 403.
[Ägarisolering](owner-isolation.json).

Faktiskt skickade program-ID:n är `CITY_GROSS_PRIO`, `COOP_MEMBER`,
`HEMKOP_MEMBER`, `ICA_STAMMIS`, `LIDL_PLUS`, `WILLYS_PLUS`. Fler val behåller
normal tillgänglighet, inga undvikna ingredienser och 25 procent för Varierad.
Köpläget är exact, kosten mixed, `personal` saknas och inget separat
näringsmedgivande tillförs. Befintlig näringsuppskattning märks som sådan.

Fyra separata synkrona 15/20-regressioner kördes mot samma image i den
isolerade kandidaten, med oförändrade releaseprofiler och produktionspriser
read-only. Det är inte publika knapp-prov. HTTPS-testadressen använder
kandidatens CA och den konfigurerade appens Origin; inga skydd slogs av.

| Profil | HTTP | Tid | Kostnad | Inköpsställen |
| --- | --- | --- | --- | --- |
| Original, exact | 201 | 186,172 s | 440,72 kr | 2 |
| Original, estimated | 201 | 201,891 s | 440,72 kr | 2 |
| Plus, exact | 201 | 176,532 s | 440,72 kr | 2 |
| Plus, estimated | 201 | 197,359 s | 440,72 kr | 2 |

Alla fyra har checkout PASS, avstämda summor, uppfyllda proteinminima och
identisk återläsning. Request-ID:n matchar kandidatens backendposter och
build `74c9077`. [Separata regressioner](personal-regressions.json).

Efter slutproven är alla tidigare 188 revisioner fortfarande oförändrade;
193 finns totalt. Prismanifestet är oförändrat och databasintegriteten är
ok. [Slutinventering](final-inventory.json). Testcontainrar och våra SSH-tunnlar
är stoppade; testdata och bevis är bevarade.

Fullständiga sanerade nätverksbevis finns under
`.local/public-menu-followup-20261002`.

Kall beräkning tar fortfarande flera minuter. Transportändringen gör att
webbläsaren kan invänta resultatet; den påstår inte att optimeringen blivit
snabbare. Ingen Git-push, städning, Malmö-aktivering eller policyändring.

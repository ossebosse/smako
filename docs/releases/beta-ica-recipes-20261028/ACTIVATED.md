# Samlad beta 2026-10-28: server aktiverad, Windowsregistrering återstår

App och första schedulerbilden aktiverades **2026-10-28 18:51:14 UTC** på
https://beta.smako.nu. Slutlig appkomplettering aktiverades **21:04:28 UTC**;
båda kommunernas `/ready` svarar med `app-f596e1102fd7-09770600`.
Ägarens beställning omfattar Malmö ICA,
två insamlingsnätter och hela det integrerade recept-/beräkningsarbetet.

## Pinnar och granskning

- Samlad grundkod: `2b65533af00d6355bd9370a18b9f613337c7ed2d`, main
  `2f033b83aa3f259fe00945425c64780d55164ea1`.
- Slutlig appkod: `f596e1102fd710a262fd834ae431f0d071a4e9d2`, main
  `45fa207b6a2531405e23780d7c5239a54517d80c` efter PR41.
- App: `sha256:d33eafe41e887d3b427ca2c85e0ef95309413b4de989a4eefb3ef170e55f16ac`,
  BUILD_ID `app-f596e1102fd7-09770600`, ovanpå första appbilden
  `sha256:e60cabb6ffcf8d452d5d3071dca634e2bc20bbf4f32ab0990cf6e0d937b8cf73`.
- Slutlig scheduler: `sha256:00d69bd1f4d5d4c6fa5a5fd6dc10d8eab9adef79654fb8669433a3112c37173d`,
  BUILD_ID `beta-scheduler-2b65533af00d-contracts1`, aktiverad 19:43:52 UTC.
- [Grön CI på main](https://github.com/ossebosse/smako/actions/runs/40733422872),
  efter PR37–40 och [grön CI efter PR41](https://github.com/ossebosse/smako/actions/runs/40763603004).
  [Granskning och riktade prov](REVIEW.md).

Bilderna byggdes på de faktiska tidigare driftbilderna. 373 deklarerade
appfiler och 429 schedulerfiler hashkontrollerades; övriga runtimefiler och
tidigare adminfunktioner bevarades. Inga beroenden eller databasscheman ändrades.
Appimport, 2 462 aktiva receptvarianter, 66 granskade ingrediensdeklarationer
och syntetiskt adminlösenord passerade i exakt kandidatimage. Den slutliga
schedulerbilden korrigerar fyra äldre kopior till samma granskade main-träd;
dess övriga runtimefiler och konfiguration hashkontrollerades oförändrade.
Experimentell generationssammanslagning är avstängd;
`LIBRARY_SEARCH_POLICY=smako-current-library-v2` är aktiverad.

## Databevarande och drift

Det befintliga driftlåset hölls genom källprov, förberedelse, full backup och
imagebyte. Ordinarie insamlingar fick avslutas före låstilldelningen.
Den första verifierade, roterande backupen är `20261028T183259Z`. Inför
slutligt schedulerbyte verifierades `20261028T193735Z`, inklusive båda
SQLite-databaserna och båda kommunernas återställningsunderlag. Slutlig
appaktivering verifierade ny backup `20261028T205455Z`. Samtliga
tidigare plan-/profil-/kontorader jämfördes som hashmultimängder och finns kvar.
Mountar, proxy och övrig miljö bevarades. Prismanifesten var oförändrade vid
själva imagebytet. Rollback bevarar föregående bilder och återställer inga databaser.

Gamla schedulerns PID1 svarade inte på vanlig stoppsignal. Före avslut
verifierades exakt gammal image och enbart `cron`, utan barnprocesser eller
insamlingsjobb. Den tomma PID1 avslutades inom den redan låsta aktiveringen;
compose fortsatte med de granskade bilderna. Detta avbröt ingen insamling.

Första prisbygget fann en äldre modellkopia i schedulern. Gamla prismanifest
behölls; appen var redan rätt paketerad. De fyra korrigerade schedulerfilerna
och fullständiga nätverkslösa prisbyggen för båda kommunerna verifierades före
slutligt byte. Lund: 45 673 råprodukter/30 kontexter, 304,05 s. Malmö:
91 384/61, 529,22 s. Båda använde 2 CPU/3 GiB och noll externa nätanrop;
databas och slutna källcacher var oförändrade. Detta mäter prisbygge,
inte menyberäkning. Se [orsak och granskning](REVIEW.md).

Ett första schedulerbyte återställdes när en omedelbar cronkontroll hann
före filens skapande. Kontrollen väntar nu upp till två minuter på exakt
de två korrekta jobben och behåller alla tidigare kontroller. Slutligt byte
bevarade appens faktiska container-ID och samtliga tidigare databasrader.

`PRICE_COLLECTION_CADENCE=mon_thu` och `ICA_PRIMAT_BASE_ENABLED=true` gäller
för båda runtimebilderna. Den faktiska cronfilen har exakt två jobb:

- Daglig backup 02:47 svensk tid.
- Befintlig arbetare minut 2, 17, 32 och 47 för lokala övergångar/publicering.

Nya källhämtningar förfaller måndag/torsdag 03:17 Europe/Stockholm med
begränsade felåterförsök inom tre timmar. Separat dagligt Coop-återförsök är
avstängt. Körplanerna verifierades för onsdag utan källanrop och torsdag med
förfallna källor i båda kommunerna. Basprisernas observationstider, verkliga
kampanjdatum och 36/48-timmarsvarningar bevaras. Se [policyn](../../PRICE-COLLECTION.md).

## ICA och receptunderlag

Malmös 24 godkända fysiska ICA-butiker behåller sina verkliga orter.
Primat gav 11 exakt ID-kopplade kontexter för prisområdet 21120, varav två
fullständiga baskällor: Caroli `1004490` och Maxi Västra Hamnen `1003569`.
Avgränsad slutinsamling gav 2 645 produktposter. Övriga Primat-kontexter är
offers-only; 24 kommunbutiker betyder inte 24 baspriskällor.

Lunds slutinsamling gav 1 964 poster med färska Gunnesbopriser och kvalificerad
LKG för Clemenstorget. Primat anger nu Clemenstorget som offers-only.
Dess tidigare baspriser behåller sin observationstid enligt ordinarie
retain-until-replaced-policy; ingen ny fullständighet påstås för denna källa.
Varje lyckad kommunhämtning använde kontraktets 49 anrop. Separata prov och
en rate-limit-händelse ingår inte i dessa lyckade försöks anropstal.

Det granskade Axfood-detaljarkivet `b11ed75863be1547755ee78be5143ba737d5ea3564acc1cadaa0feb6b4ebf0a8`
är hashverifierat och skyddat i befintlig datavolym. Den vanliga faktaladdningen
använder både detta arkiv och de 66 tidigare utgivna kompositionsgranskningarna.
De två privata kvalificeringsdatabaserna togs bort under driftlåset först
efter godkänd kanonisk backup; 14 420 819 968 byte frigjordes.
Efter slutlig appaktivering verifierades kanoniska aktiva artefakters hash
och identitet igen under driftlåset. Endast den egna diagnostiska SQLite-
kopian och två privata, inaktiva byggartefakter pensionerades: ytterligare
7 495 313 963 byte. Slutlig ordinarie lagringsretention är complete.

## Windows kräver fortfarande administratör

Fullpaket `2b65533af00d` är installerat i den befintliga reläinstallationen.
Integritets-/importkontrollen passerade för 1 017 källfiler, Python 3.12 och
låsta beroenden, utan nätanrop. Den befintliga S4U-uppgiften kunde inte
uppdateras utan administratörsrättighet. UAC avbröts; ingen uppgiftsändring
registrerades. Uppgiften använder fortfarande `2464596b6f07` och sina tre
tidigare dagliga starttider 01:30, 09:30 och 17:30. LastTaskResult är 1.

Kör det förberedda `.local/beta-all-20261028/activate_windows_admin.ps1` i en
administratörsterminal på den befintliga Windowsvärden. Det jämför den sparade
uppgiftsgranskningen och kör paketets `set_price_collection_schedule.ps1` med
`-Apply`: måndag/torsdag 03:17, exakt nytt paket och `-CollectionCadence mon_thu`,
med oförändrat konto, transport och inställningar. En pågående körning stoppas
inte av skriptet. Kontrollera sedan faktisk XML och nästa starttid.
Serverns aktivering får inte beskrivas som slutförd Windowsregistrering.

## Publika prov på första appbilden

Båda nya pris-ID:n bekräftades via publik scoped readiness efter att appens
interna reload-anrop först nått transportens timeout. Ett diskmanifest ensamt
räknades inte som laddning. Lund använder
`price-universe:0c617164ed822450e72b218929fe7c02f6647a2d07f08426c0ee89e0f9b590a2`
och Malmö `price-universe:b756752d4509a2c3597b676c7780e7a2c8a4fb0c2e7c332322d32a433cc5bee9`.
Båda har användbara obligatoriska kontexter.

Gästprovet med fem recept/fyra portioner nekades korrekt med 403 enligt
befintligt medlemskap. Slutproven använder tre middagar/två portioner,
högst två butiker inom tre kilometer och vanliga separata gästidentiteter.
Lund gav 201 på 50,45 s; Malmö gav 201 på 53,02 s. Båda korgarnas revision
passerade, summorna stämde, okända mängder var noll och två återläsningar
gav exakt samma sparade meny. Inga verkliga användarprofiler användes.

Första Malmöförsöket nådde 422/SEARCH_INCOMPLETE efter 60,48 s innan
sökningen hann börja. Det var inte en lyckad meny eller omöjlighetsbevis.
Samma krav passerade efter gemensam förberedelse för portioner 1–4;
inga krav, priser eller receptfilter ändrades. Den nätverkslösa förberedelsen
av alla 2 462 varianter i båda kommunerna klarade 175,33 s med 2 CPU/3 GiB
och minnestopp 2 121 519 104 byte. Tidigare förberedelse 1/4 klarade också
183,48 s, 2 561 286 144 byte. Dessa tider är skilda från API-menyproven.

Ordinarie uppstart laddade tidigare fakta och bibliotek men anropade inte
den gemensamma aktuella källförberedelsen; prisreload schemalade inte heller
denna. PR41 kompletterar den befintliga bakgrundsarbetaren och anropar den
efter godkänd ny runtimeaktivering. Ändringen är aktiverad i slutlig appbild;
två appfiler ändrades och 1 004 andra runtimefiler hashkontrollerades oförändrade.
Scheduler, mountar, priser och övrig miljö bevarades; enbart BUILD_ID ändrades.

Exakt kandidatbild passerade vanlig lifespan-uppstart utan nätverk med
2 CPU/3 GiB: 191,98 s, minnestopp 2 542 624 768 byte. Den automatiska
bakgrundsförberedelsen rapporterade ready för båda pris-ID:n och samtliga
2 462 varianter för portioner 1–4, noll persistensfel och noll syntetiska
plan-/profilrader. Metodsignaturen är
`aaf300e88babbc6fa096c83c62a2ab5eb837a3cf23e12cda1a5ebd6ebbd43967`.
Detta är gemensam receptförberedelse, inte färdiga menyer eller ett bevis
för att alla varianter klarar varje användares krav.

## Slutprov på aktiverad app

Publika gästprov med samma tre middagar/två portioner, högst två butiker inom
tre kilometer, passerade på slutlig BUILD_ID: Lund **201 / 50,89 s**, Malmö
**201 / 52,36 s**. Hela korgrevisionen och avstämningen av summor passerade,
okända mängder var noll och två återläsningar per plan var identiska.
Tidigare gästgränser består: fem recept/fyra portioner gav korrekt 403.

Det första Lundförsöket efter slutligt appbyte gav **422 / SEARCH_INCOMPLETE
vid 64,34 s**, utan slutkontrollerad meny eller utförlig diagnostik. Det
bevaras separat och räknas inte som framgång. Nästa försök använde samma krav
och en ny syntetisk gäst. Ingen manuell källförberedelse kördes efter detta
appbyte. Ett senare godkänt försök bevisar inte latens för det första kalla
anropet. Orsaken till den extra tiden är inte fastställd.

Driftkontroll 21:08 UTC bekräftade laddat/publicerat Lund-ID, ready och
tillräckligt lagringsutrymme. Alla 13 registrerade pipelineincidenter var
recovered; inga HTTP 5xx-metriker fanns i det aktuella dygnsfönstret. Äldre
källor behåller sina synliga åldersvarningar och kan fortfarande ha egna
insamlingsfel; inga kvalitetsgränser ändrades för att göra status grön.

Den frysta referenstäckningen 2 024/2 200 hela uppskattningskorgar,
1 140 hela exakta korgar och 176 kvarvarande blockerade importer är historisk.
Den mäts inte om av dessa två gästprov och är inte ett påstående om full
täckning med dagens priser, alla valkombinationer eller global optimalitet.
Maskinläsbart, sekretessrensat slutunderlag: [EVIDENCE.json](EVIDENCE.json).

Skyddat råunderlag finns i `.local/beta-all-20261028/` och serverns
`/opt/smako/evidence/beta-all-2b65533af00d/` samt
`/srv/app/var/reports/beta-all-20261028/`. Inga privata profiler, cookies,
källnycklar, databaser eller full miljökonfiguration checkas in. Slutlig app
har även `.local/beta-recipes-autoprep-20261028/` och
`/opt/smako/evidence/app-f596e1102fd7-09770600/` som skyddat råunderlag.

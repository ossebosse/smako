# Återstående Coop-källor 2026-10-29

Färsk kontroll av de öppna felen: Coop Malmö Central 3833/106415,
Kornettsgatan 3835/106417 och Djupadal 3831/106443 svarar HTTP 200 med exakt
`{}` från respektive butikskopplade offentliga erbjudandekälla. Officiell
identitet och sidrubrik stämmer; inga produktkort eller produktlänkar finns.
X:-tra Nydala 3829/106413 har uttryckligen tom `weeklyOffersLink` på sin
identifierade officiella sida och ingen alternativ aktuell publikationslänk.

Parser v8 behåller `{}` som verkligt råsvar och kräver samstämmig tom DOM,
exakt källa, butik och status. Saknad feed, null, okända objekt, fel status,
flera svar och korsade identiteter förblir blockerade. X:-tra accepterar bara
uttryckligen tom sträng utan alternativa publikationer; okänd PDF-layout eller
saknat/null fält räknas fortfarande som fel. Normalt tomt resultat rensar bara
den butikens tidigare referenser och behåller observationens verkliga tid.
Dashboarden visar kontrollhistorik även utan en påhittad priskontext.

Online Syd 730400 har incident `source-5bee65424ddcdca6ed78c16d` med signatur
`5bee65424ddcdca6ed78c16d9628051ba492b40a1c4d624eb0529da642777ad8`.
Den äldre avvisade ögonblicksbilden är `875e4d32e7da4aa0a8f4f388edea5747`.
Färskt begränsat API-prov 08:06 UTC visar både kampanjer utan köpgränsfält och
kampanjer med positiva uttryckliga styckgränser. Parser v4 behåller verifierade
B2C-baspriser men undanhåller kampanjpris, medlemspris och effektivt rabattpris
när köpgränsen saknas eller inte kan tolkas säkert. Enbart de fyra exakta
borttagna gränssökvägarna på kategoriytan för 730400 granskas. Nya fält,
typbyten, identitets-/pris-/medlemsvillkor och andra sammanhang spärras.

Befintlig fullkataloggräns, 730400-allowlist, normalisering, hälsokontroller,
LKG och atomisk publicering behålls. Online Syd förblir onlinepris och får
aldrig räknas som fysiskt baspris. Må-/torsdagspolicyn ändras inte.

Apppaketet omfattar 13 granskade käll-/läsarfiler, schedulerpaketet 10.
Scheduler får inga dashboardfiler. Paket baseras på verkligt aktiva
`source-ops-1d092bc85f91`-bilder med exakt filhashkontroll och bevarar övrig
recept-, beräknings-, autentiserings- och driftkod. Aktivering kräver grön CI,
verifierad backup, befintligt gemensamt driftlås och kommunvis runtimekontroll.

Lokalt har fokuserade tester för parser, gränsvillkor, butiksläsare,
schemaavgränsning och dashboard passerat; kompletterande kommun-/jobbtester
journalförs separat. Ruff och compileall passerar. Verklig insamling,
publicering och laddning ska redovisas separat i aktiveringsjournalen.

Appens Coop-katalogparser är i verkligheten v2. Dess tre historiska Git-baser
är explicit hashbundna i paketeraren. Endast Coop-grenen i den äldre gemensamma
collectorn ersätts; Hemköp och Willys behåller exakt sina aktiva bytes. De två
rena Coop-modulerna får granskad v4 inklusive tidigare v3-presentationsgranskning.
Scheduler använder sin befintliga v3-bas utan denna appanpassning.

Slutlig fullkatalog-/gränskomplettering finns i [ONLINE-REVIEW.md](ONLINE-REVIEW.md),
och verklig laddning finns i [ACTIVATED.md](ACTIVATED.md).

# Veckooptimering och receptvarianter aktiverade på betan

Aktiveringen verifierades 2026-10-16T13:22:09.891774+00:00. Kodcommit `e041451`, gren
`feature/joint-week-refinement`, efter användarens beställning att pusha och
aktivera på betan. BUILD_ID: `joint-week-refinement-app-e041451`.

Ändringen omfattar gemensamma veckobyten, inköpsöverskott som sekundärt
urvalskriterium, tidigare prestandaförbättringar och receptvarianter sedan
föregående appaktivering `recipe-nutrition-extras-app-7e402a7`.
Biblioteket har 197 recept och policyn är
`personal-policy-v2-10-joint-week-refinement`.
Se [implementation och frysta mätningar](../../../reports/joint-week-refinement-20261016.md).

## Kontrollerat appbyte

16 granskade runtimefiler lades ovanpå den faktiskt aktiva appbilden.
De är byteidentiska med pinnad Git-kod; övriga 676 runtimefiler är oförändrade.
Bildbygget kördes utan nätverk. Filhashar, compileall, import och strukturell
receptvalidering passerade. Tidigare 460 offlineprov och 19 frysta mätningar
återanvändes för oförändrad kod.

Aktiveringen väntade på den ordinarie kommunuppdateringen. Befintligt
gemensamt driftlås hölls sedan under SQLite-backup och appbyte. Backupkopiorna
klarade quick_check. Ingen databas återställdes. Alla tidigare sparade rader
har hashverifierats både vid bytet och efter HTTP-proven.

Endast appens image och BUILD_ID ändrades. Volymer, övrig miljö, scheduler,
proxy och scheman bevarades. Aktiva prismanifest var oförändrade under bytet.
Lund och Malmö svarade ready med den nya BUILD_ID:n. Befintliga källvarningar
är inte åtgärdade av denna apprelease.
Efter proven överensstämmer publicerat och laddat Lund-manifest; alla fem
obligatoriska baskällor är kvalificerade, användbara och laddade.

## Publik verifiering

Fyra separata gäster skapade och återläste menyer på beta.smako.nu med
butiker inom 3 km från 22225 och högst två inköpsställen. Samtliga fick
HTTP 201, godkänd kassakontroll, avstämda summor, noll okända mängder och
identiska sparade planer vid två återläsningar. De begärda närings- och
viktgränserna verifierades. Inköpsöverskott redovisas utan avdrag från
inköpssumman; veckosökningens budget på högst 32 nya korgberäkningar per
biblioteksökning hölls.

| Prov | Tid | Antal recept | Inköpssumma | Resultat |
| --- | --- | --- | --- | --- |
| protein40 | 533.72 s | 5 | 1113.0 kr | PASS |
| all-macros | 26.98 s | 5 | 1113.0 kr | PASS |
| breakfast-snack-weight | 15.77 s | 2 | 64.06 kr | PASS |
| vegan | 16.28 s | 3 | 473.17 kr | PASS |

Tiderna är enstaka API-prov, inklusive asynkron pollning, och innebär ingen
garanti vid samtidig användning. Första provet kördes efter appomstart och
tog 533,72 s (8 min 54 s), vilket är en tydlig kvarstående svarstidsbegränsning.
Dess interna planerartid var 43,79 s; cirka 490 s låg alltså utanför den
redovisade planerartiden. Appens bakgrundsuppvärmning rapporterade färdigt
under väntan, men underlaget isolerar inte orsaken till hela tidsskillnaden.
Det efterföljande makroprovet tog 26,98 s (intern planerartid 14,72 s).
Uppstart, kö och förberedelser behöver undersökas separat.
Inga nya browserprov behövdes för denna ändring av backend och receptdata.

Slutkontroll: 2026-10-16T13:34:52.333681+00:00. App, scheduler och proxy kör; inga nya
OOM-händelser. [Kompakt evidens](EVIDENCE.json) innehåller image- och
filhashar samt kontrollresultat. Privata HTTP-svar, sessionsuppgifter och
databaskopior ligger utanför Git.

## Kvarstående begränsningar

Sökningen är begränsad och bevisar inte globalt lägsta pris. Tidigare frysta
prov visade mindre överskott i tre profiler men ingen sänkt inköpssumma i
matrisen. Ekokrav kan fortfarande vara långsamma och saknade produkt- eller
näringsuppgifter kan stoppa vissa kombinationer. Detta är inget lasttest.

## Backup arkiverad 2026-10-19

Den avslutade releasebackupen finns nu förlustfritt komprimerad i
`/opt/smako/evidence/joint-week-refinement-e041451/backup-20261016T131323Z.tar.gz`.
Alla filhashar, ägare och behörigheter verifierades före borttagning av den
okomprimerade kopian. Privat inventarium, kvitto och återställningsanvisning
finns intill arkivet. Se [lagringsjournalen](../../storage-maintenance.md).
Aktiva data och denna releases historiska verifieringsresultat är oförändrade.

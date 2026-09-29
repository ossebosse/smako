# Separat releaseförslag: Coops fysiska strukturerade erbjudanden

**Förberett för granskning, inte aktiverat.** Detta förslag ändrar inte den
väntande ICA-releasen eller dess Windows-administratörssteg.

Verifierad del: befintlig Coop-transport med strukturerat publikt svar,
prisroller/variantvillkor och uttryckligt partiell import via collector → OWN
→ PriceUniverse → befintlig checkout/audit. Flöjtvägen och Bulltofta verifierade
på Windows med faktisk nätinsamling 21 september 2026. Isolerat slutunderlag:
44 respektive 68 varianter. Detta är ingen fullständig butikskatalog.

Föreslagen releaseenhet är `incremental.patch` plus dess filmanifest och
regressioner. Patchen utgår från den separata kommunarbetskopians bevarade
förläge, inte från ren HEAD. Den får inte appliceras ovanpå väntande ICA-paket
utan integrationsgranskning. Inga nya runtime-beroenden.

## Grindar före ett separat aktiveringsbeslut

1. Granska ändringarna i gemensam OWN-projektion/radvalidering och bekräfta
   kompatibilitet med då deployad kod. Kör Coop-, ICA- och Online-regressioner.
2. Verifiera samma publika transport i avsedd serverruntime under befintligt lås,
   utan utökad online-allowlist eller cookieöverföring. Windowsprovet bevisar inte
   serveråtkomst. Hämta då nytt underlag; septemberprovet är inte evigt giltigt.
3. Kör aktuell isolerad kandidat med fortsatt karantän, exact fysisk butik,
   datum och oförändrade baser/färskhetsgränser. Inga `isPil`- eller andra
   osäkra rader får släppas genom för att nå ett önskat antal.
4. Före nyttopåstående: samma riktiga 15/20-profil med identiska färska baser,
   oförändrade 40/30/20-krav, max två inköpsställen, medlemskap av/på, checkout
   och audit. Ingen ny sådan fullmenyjämförelse eller besparing hävdas här.
5. Efter uttryckligt godkännande: befintliga backup-/lås-/validerings-/atomiska
   aktiveringsrutiner; frivilligt butikstillskott och verifierad process-reload.
   Uppdateringsschema och aktiva priser förblir oförändrade fram till dess.

## Rollback

Spara kodversion och kompatibelt, fortfarande färskt basmanifest före eventuell
release. Återgå via befintlig atomisk aktivering utan Coop-tillskottet om dess
validering eller import misslyckas. Behåll råbevis och karantän. Återaktivera
aldrig ett utgånget/48h-gammalt basunderlag; samla och validera basen först om
inget giltigt återställningsunderlag finns. Användarprofiler och planer berörs
inte av denna isolerade leverans.

Ingen ändring av produktion, Windows-uppgift, cron, serverkonfiguration,
Primat eller ICA-baspriskatalogens paus. Ingen observerad flerdagarsstabilitet.

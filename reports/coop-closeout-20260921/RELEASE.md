# Separat partiellt Coop-releaseunderlag – avslutning 21 september

**Ingen aktivering.** Behåll föregående Coop-leverans och dess 112 godkända
butik–variantposter. Denna lilla tilläggspatch rättar namnkopplingen för
vetemjöl och verifieringskedjan. Den väntande ICA-releasen berörs inte.

## Verifierat innehåll

- Befintlig fysisk Coop-insamling, källbindning och radgodkänt offers_only-kontrakt.
- Flöjtvägen 44 och Bulltofta 68 kvalificerade poster i isolerad OWN/PriceUniverse.
  Samma 379 karantänposter, nämnare 491 och oförändrad 95%-gräns.
- ”Kärnvetemjöl” → ”vetemjöl” beläggs av annonsens eget föräldra-/variantnamn.
  Ingen generell mappning av ”mjöl”, specialmjöl eller blandningar. Synligt
  motstridigt produktnamn stoppas även om metadata påstår exakt identitet.
- Riktig import → ingrediensmatchning → checkout → audit klarar mjöl i båda
  butikerna: två 2 kg-paket för 26 kr. Ordinarie pris null, inget köp av ett
  paket för 13 kr. Pasta och nötfärs klarar fortsatt samma kedja.
- 324 berörda regressionstester PASS. Ruff och compileall PASS.

## Avgränsningar som kvarstår

Karantänen är 263 livsmedelsvarianter och 116 övriga, fördelade på 51 fysiskt
butiksbundna grupper. Grupper med både godkända och blockerade varianter räknas
som berörda, inte helt underkända. Se `QUARANTINE.md` och radbevis i JSON.
Ingen tolkning av isPil, pant eller variantblandning har gissats.

Mjölet var redan prisimporterat. Ingen ny prisimport eller ny karantänfrisläppning
görs här; två befintliga butiksposter får korrekt ingrediensmatchning. Ingen
näringsinformation har lagts till. Källan saknar verifierat produktbundet
näringsunderlag för mjölet: detta är inte bevis för godkänd 40/30/20-meny.
Ingen 15/20-jämförelse eller besparing påstås.

## Återstår före betaaktivering

1. Separat aktiveringsbeslut för Coop; blanda inte patchen i ICA:s väntande paket.
2. Integrera och regressionsverifiera mot då aktuell deployversion. Patchen
   bygger på den sparade, ocommittade kommun/Coop-arbetskopian, inte ren HEAD.
3. Verifiera tillåten befintlig Coop-transport i serverruntime. Dagens isolerade
   verifiering använde sparade verkliga Windows-svar från kl. 09:44, utan nya
   nätanrop. Ingen observationstid har flyttats. Före aktivering krävs då
   färskt och fortfarande kampanjgiltigt underlag samt aktuella validerade baser.
4. Validera exakt butikskoppling, gemensamma källfel, frivilligt tillskott,
   kvarvarande karantän, medlemskap, köpgränser, 36/48h, kampanjutgång och LKG.
   De 112 självständigt godkända raderna behöver inte vänta på resten av de 491.
5. Kör oförändrad riktig 15/20-profil med lika baser och 40/30/20-krav före
   nyttopåstående. Bekräfta näring där planeringen kräver det och max två butiker.
6. Befintlig backup/lås/atomisk aktivering/reload och isolerad testidentitet i
   betan efter godkännande. Verifiera health/ready, checkout, audit och återläsning.

Rollback: använd kompatibel kod och fortfarande giltigt basunderlag utan
Coop-tillskott; behåll råbevis/karantän. Återaktivera inte gamla priser om
basunderlaget passerat stoppgränsen. Ingen profil eller befintlig plan skrivs över.

Ingen produktion, Windows-uppgift, schema, serverkonfiguration, ny kedja,
bildanalys, betalt API eller ändring av Primat/ICA-baspausen ingår.

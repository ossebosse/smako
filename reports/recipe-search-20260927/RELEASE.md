# Inaktiv releasekandidat — receptsökning 27 september 2026

Verifierade resultat finns i VERIFICATION.md och summary.json. Inget har aktiverats i produktion.

## Omfattning

De nio applikationsfilerna i changed-application-files.json innehåller gemensam sökoptimering, produktspecifik Dabas-mängdkoppling och korrekt råvaruform. Ingen databas- eller schemamigration, inga Windows-uppgifter och inga kommunlistor ändras. Registrerade deklarationer utökas utan att tidigare rader skrivs över. Användarprofil och befintliga recept sparas oförändrade.

## Verifiering

Fyra oförändrade 15/20-profiler, samtliga 84 recept, 29 uttryckligt identifierade referensfall, två HTTP-planer inklusive audit, lagring, omstart och rollback. 700 regressioner samt 32 riktade slutprov. Historisk replay på 24 september med nya tydligt tidsstämplade mängdfakta; inte färska priser.

Målet är endast delvis nått: 32 tidigare godkännanden består och ett nytt har tillkommit. Stekt ris med lax och vitkål har återkallat näringsgodkännande efter upptäckt av fel rå/torkad vitlökskoppling. Gamla rapporter och sparade planer är bevarade som historiska resultat, inte som ett nytt godkännande enligt den korrigerade kontrollen. Ingen automatisk omräkning av användarplaner har genomförts.

## Inför eventuell aktivering

Kontrollera applikations-/källhashar mot PACKAGE.json och bevara hela föregående arbetskopias releasepaket. Kör ordinarie tester i målmiljön. Ta separat ställning till de kvarstående produktionskontrollerna: färsk komplett bas, Malmö-publicering och historisk Lidl-fixture. Historiska kampanjer får inte förlängas. Befintlig behovsstyrd uppdatering och observationstider ska användas utan ombyggnad eller schemaändring.

Kommunstöd, medlems-/butik-/kanalkontrakt och gränsen två inköpsställen är oförändrade. Den nya näringsgränsen är endast ett sökfilter; befintlig radvalidering, varukorg, näringsprövning och audit ger godkännandet. Recept som behöver andra mängder ska få en separat version; ingen sådan version ingår här.

## Rollback

baseline-code/ och baseline-HANDOFF.md återger arbetskopian före denna etapp. Återställ endast de filer som anges i changed-application-files.json till motsvarande tidigare version, ta bort den nya nutrition_search_bounds.py om förekoden används och återställ föregående deklarationsregister. Bevara användarnas plan- och profildata samt andra kedjors filer. Återställning ska göras som en avsiktlig senare releaseåtgärd; den har inte utförts i produktion.

I isolerat rollbackprov kunde förekoden läsa båda nya sparade HTTP-planerna identiskt. Ny omräkning gav 422 när förekoden saknade den nödvändiga mängdkopplingen; de sparade planerna bevarades. Det är en säker vägran, inte bakåtkompatibelt stöd för de nya beräkningarna.

# Recept- och mängdupplösning

Läs **VERIFICATION.md** och **summary.json** för faktiska slutförda körningar.
**recipe-first-stops.json** innehåller alla 84 recept, utan dubbelräkning.
**candidate-review.json** innehåller produktvisa före/efterbeslut.
**RELEASE.md** är separat, inaktivt aktiverings- och rollbackunderlag.

`profile/` är körbevis; `sources/` är verkliga källsvar och importerade fakta.
Underkataloger med `intermediate` är ersatta mellankörningar, inte slutresultat.
`baseline-code/` fryser föregående implementation; ändra inte den.
`PACKAGE.json` binder slutkod, testkod, dokumentation och körbevis med SHA-256.

Slutproven kördes på Python 3.12 i privat native-behållare utan nät, separat
PlanStore, frysta prisartefakter och uttrycklig historisk testklocka. Rapporternas
HTTP-data har egna request-ID:n och tider; körningarna är inte aktuella priser.
Ingen produktion eller aktiv schemaläggning ingår. Kör inte remote.initialize
igen; den skapade isoleringen och tidigare releaser ska bevaras.

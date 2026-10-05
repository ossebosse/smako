# Reproducerbar utgångspunkt

Denna etapp utgår från `feature/recipe-usability-20261005` vid `b8667da72f601040e11645c6186c1f11a635d629`. Där ingår runtime `2816d50e4a14dd118015a4c047f2346435b981ef` och senare test-/dokumentationsarbete. Arbetsgrenen är `feature/package-variation-20261005`; tidigare beta och produktionsdata har inte ändrats.

Den sparade begäran är `saved-main-five-cuisine-4-balanced` från det tidigare leveransunderlaget. Exakta fält finns i [MENUS.json](MENUS.json) och den hashbundna privata replayfilen `.local/next-milestone-20261005/request.json`. Den ber om fem middagar för fyra personer, Balanserad, tillåtna grekiska, italienska, mexikanska, indiska och thailändska kök, 10–15 ingredienser, minst 30 g protein per portion, högst tre inköpsställen, uppskattat köp, separat näringsmedgivande och tomt skafferi. Ingen ny fördelningsregel finns i R0–R2.

Fryst `PriceUniverse` från 4 oktober har SHA-256 `f82d66103e830b82b7d919fe847fd5b3ef85c5e323e0a2133c338f064dfb8768`. Alla dess 2 233 refererade råfiler verifierades mot `grocery.sqlite` med SHA-256 innan någon kodändring. Observationstider, priser, butiks- och kanalkontrakt, receptversioner och mängder har behållits. R0 är en **berikad historisk replay**: äldre frysta priser kombineras med senare hämtade, tidsstämplade fakta. Den är inte en aktuell prisoffert.

Jämförelseleden är:

- **R0:** föregående receptkandidat, dess befintliga fakta och oförändrade begäran.
- **R1:** ny runtime med samma frysta råfiler och föregående deklarationsregister monterat läsbart; samma begäran.
- **R2:** samma runtime och begäran med en ny, separat tidsstämplad leverantörslämnad deklaration.
- **R3:** samma runtime och faktaunderlag som R2, men uttryckligen valda variationsvillkor.

R0:s fasta meny kördes på nytt på dess tidigare image; fri R0 använder den sparade HTTP-replayen från föregående leverans och räknas inte som nykörd. R1/R2 har nya fasta och fria prov, R3 uttryckliga fria variationsprov. R3 jämför andra maträtter och får därför inte kallas besparing för samma mat. Planerade rester är endast upplysning om inköpt mängd minus behov; de läggs inte i faktiskt skafferi eller räknas som framtida värde.

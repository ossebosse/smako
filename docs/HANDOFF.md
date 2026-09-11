# Smako – aktuell status 11 september 2026

Live: https://beta.smako.nu/personal, build `personal-v2-qualified-20260911b`.
Appkod `e1c0db1`; alla fem deployade appfiler hashmatchade.
[R1–R9-matris](product/personal-planning-v2.md) ·
[Full rapport: menyer, fakta, tester och rollback](../reports/smako-qualified-product-data-20260911.md).

- R3/R6/R7/R8 IMPLEMENTED_AND_VERIFIED. R1/R2/R4/R5/R9 PARTIAL.
- R4: ekoandel och animaliskt eko fungerar i begränsade verkliga fall.
  R5: granskad kall frukost med alla fyra makron + eko 30 % kostar 81,96 kr.
- Samma 449 produkter: ingrediensdeklarationer 78→83, eko 45→46, makron 73→78.
  75 har användbar grund som såld vara före recept-/enhetskontroll. Fakta-ID i rapporten.
- Tillagad vikt/förlustgrund, generiskt skafferis näring och fulla allergener DATA_BLOCKED.
  OIDC kräver fortfarande separat operatörskonfiguration och verklig kontoacceptans.
- 175 regressionstester; sista ändringen 28 direkt berörda + 81 fokuserade tester.
  Chromium/WebKit inklusive Mina val→verklig HTTPS passerar; fysisk iPhone återstår.
- Backup/rollback och gemensamt driftlås; 120 revisioner, alla tidigare bevarade.
  Ingen användardata raderad. Prismanifest/scheduler orörda, noll liveleverantörsanrop.
- Basmeny 244,49 kr före/efter. Kall 16,181→16,102 s; varm 0,759→0,875 s.
- Kall prestanda, ICA OWN, Willys-task/relay och fulla R9-livekampanjer fortsatt avgränsade.
  [Tidigare OIDC-/driftåtgärder](../reports/smako-personal-planning-v2-gaps-20260911.md).

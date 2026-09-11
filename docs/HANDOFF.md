# Smako – aktuell status 11 september 2026

Live: https://beta.smako.nu/personal, build `personal-v2-gaps-20260911c`.
[R1–R9-matris och återupptagbara delsteg](product/personal-planning-v2.md) ·
[Full rapport, datatäckning, OIDC och rollback](../reports/smako-personal-planning-v2-gaps-20260911.md).

- R3/R6/R7/R8 IMPLEMENTED_AND_VERIFIED. R1/R2/R4/R5/R9 PARTIAL.
- R6 stöder ändring efter köp/förbrukning, topup och bevarad inköpshistorik.
  R9:s gruppmotor verifierad; kompletta livekampanjer LIVE_DATA_UNAVAILABLE.
- Spårbara eko-/makrofält från sparade källor används. Komplett allergenunderlag,
  animalieklassning, tillagningsutbyte och kontosynk är inte färdiga.
- 413 regressionstester + 56 medlems/scanner; sista kampanjgräns 33 fokuserade tester.
  Chromium/WebKit och faktisk HTTPS passerar. Fysisk iPhone återstår.
- Backup/isolerad restore/framåtkompatibel rollback verifierade. 105 revisioner;
  tidigare revisioner bevarade, ingen användardata raderad. Gemensamt driftlås.
- Samma gamla meny 244,49 kr. Kall 13,888 → 16,360 s (+17,8 %), varm 0,785 → 0,780 s.
  Uppmätt regression, ingen prestandaomskrivning. Prisgoldens oförändrade.
- Nästa operatör: godkänn OIDC-leverantör, konfigurera tre värden privat enligt
  rapporten och kör verklig kontoacceptans. Därefter komplettera verifierad källdata.
- Kall plannerprestanda, ICA OWN-research och Willys-task/relay fortsatt uppskjutna.
  ICA/Primat-normalisering, insamling, scheduler och prismanifest orörda.
- Tidigare Willys MULTI_DAY_RELIABILITY är fortsatt UNOBSERVED; separat operatörsprov
  enligt [bevarad HANDOFF](../reports/handoff-before-personal-v2-gaps-20260911.md).

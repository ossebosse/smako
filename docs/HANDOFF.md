# Smako – aktuell status 10 september 2026, 19:56 UTC

Live: https://beta.smako.nu/personal, build `personal-v2-20260910c`.
[Produktkrav R1–R9, acceptans och tre återupptagbara delsteg](product/personal-planning-v2.md).

- Gemensam korg, extravaror/noll recept, receptredigering, privat gästskafferi,
  reservationer/inköp/förbrukning och måltidstyper är levererade.
- R1/R2/R6/R9 PARTIAL; R4/R5 DATA_BLOCKED. Ingen verifierad kontosynk,
  allergifrihet, full produktnäring eller ekologisk status får påstås färdig.
- 381 + 56 tester passerar; Chromium/WebKit lokalt och via faktisk HTTPS.
  Fysisk iPhone/kamera återstår. Gamla recept/prisgoldens oförändrade.
- Backup/isolerad restore och rollback-kompatibilitet verifierade. 82 revisioner
  efter syntetiska prov; alla tidigare revisioner bevarade. Ingen data raderad.
- Nästa operatörssteg: konfigurera etablerad OIDC privat enligt rapporten och
  kör verklig kontoacceptans; skaffa spårbar allergen-/eko-/näringsdata.
- Kall plannerprestanda och ICA OWN-research fortsatt uppskjutna. Willys-task,
  relay, ICA/Primat-normalisering, källinsamling, scheduler och prismanifest orörda.
- Tidigare Willys-uppföljning kvarstår: kör `deploy/scripts/inspect_willys_relay.ps1`
  nästa morgon; MULTI_DAY_RELIABILITY fortfarande UNOBSERVED.

[Full leveransrapport och rollback](../reports/smako-personal-planning-v2-20260910.md) ·
[Bevarad tidigare HANDOFF](../reports/handoff-before-personal-v2-20260910.md).

# Separat app-only-beslut: weight-offers-0e7c20dfa911

**Inte aktiverad.** Ingen ändring av källprocess, relay, scheduler eller data.

- Runtime: `0e7c20dfa91183b622cce340093a8a6cca93a5a9`.
- Image: `sha256:523caa8ec5b09264738a90942f9e0d4157fe7fb41efc0a59d3e38b2e472f578e`.
- BUILD_ID: `weight-offers-0e7c20dfa911`.
- Paket: `smako-weight-offers-0e7c20dfa911.zip`, SHA-256
  `799ee154a142d7586362cc548a2cc585488cc56486f983cfe6b6144f6ded33cc`.
- Imagearkiv: `smako-weight-offers-0e7c20dfa911.image.tar`, SHA-256
  `f9614a02293f6c5c3872495203626bf67a93a23097852fb06bc8a4d5edb688f2`.

Filer: `D:\Projects\Smako\.local\weight-offers-20261010\package\`.
Byggverktyg: `scripts/build_weight_offers_patch.py --commit 0e7c20dfa911 --output <ny tom katalog>`
via projektets Python. Paketet verifierar 10 basfiler mot den aktiva 205-imagen
och bygger endast appdelta. Leveransimagen har provats utan runtimekällmount.

Vid separat godkänd aktivering:

1. Läs aktuell `smako_ops.py status`, faktisk app/image, pågående jobb, kapacitet,
   Compose-wrapper `/opt/smako/compose`, mounts och användarlagring. Basen vid
   utvecklingen var return-session-205cd8ca0f31/image853d5b98. Skriv inte över
   senare fungerande appändringar. Källprocess04e47c6 ska bevaras.
2. Vänta ut jobb, ta konsistent PlanStore-backup och håll ordinarie operationslås.
   Verifiera arkivhash före docker load; inget serverbygge eller databasbyte.
3. Full upplöst konfigurationsdiff får endast ändra app.image och app.BUILD_ID.
   COMPLETE_RECIPES_ENABLED=true, övriga miljöfaktorer och mounts bevaras.
4. Byt endast appen genom befintlig app-only-väg. Kontrollera /ready, laddat
   prismanifest, image, BUILD_ID och faktiska HTTP-filhashar mot EVIDENCE.json.
5. Kör publik sökning och privat viktvarukorg med separata verifieringsidentiteter
   och aktuellt publicerat underlag. Testa explicit medgivande, audit, revisions-GET
   och ägarskydd. Installera aldrig replayklockan eller testlagringen.

Ingen ny DB-modell eller migration. Senaste planer/revisioner ska alltid behållas.
Ett eventuellt byte tillbaka till 205 behöver eget kompatibilitetsbeslut och
bevarar senaste data. Flagga av för kompletta recept tar inte bort den här
inköpsliste-/prisvisningsfunktionen och är därför inte generell återgång.
Inga påståenden om provad äldre binär mot nya revisioner görs här.

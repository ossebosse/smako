# Separat app-only-beslut: member-prices-f00f5304e544

**Inte aktiverad.** Ingen ändring av källprocess, relay, scheduler eller data.

- Runtime: `f00f5304e5449bd8417f3dab4fcb547e27135de7`.
- Image: `sha256:7635779a3c7640856db031c0104748217bb93576cd57e9311b370cf56c05f75c`.
- BUILD_ID: `member-prices-f00f5304e544`.
- Paket: `smako-member-prices-f00f5304e544.zip`, SHA-256
  `c6477944559caedf497b54d4c26994ef1b77b5bc968181baf048b1e6aab1f9ad`.
- Imagearkiv: `smako-member-prices-f00f5304e544.image.tar`, SHA-256
  `102c9964692da1dd6d03a79dacb420071dbe0009647f498ebfa071bf978aacc6`.

Filer: `D:\Projects\Smako\.local\member-scan-20261010\recovery-package\`.
Byggverktyg: `scripts/build_member_prices_patch.py --commit f00f5304e544 --output <ny tom katalog>`
via projektets Python. Paketet verifierar 14 basfiler mot den verifierade viktvaruimagen 0e7 (som bygger på aktiva 205)
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
   och aktuellt publicerat underlag. Testa tomt medlemsval, synligt medlemskrav, explicit viktmedgivande, audit, revisions-GET
   och ägarskydd. Installera aldrig replayklockan eller testlagringen.

Ingen ny DB-modell eller migration. Senaste planer/revisioner ska alltid behållas.
Ett eventuellt byte tillbaka till 205 behöver eget kompatibilitetsbeslut och
bevarar senaste data. Flagga av för kompletta recept tar inte bort den här
inköpsliste-/prisvisningsfunktionen och är därför inte generell återgång.
Inga påståenden om provad äldre binär mot nya revisioner görs här.

Kandidaten inkluderar viktvaruändringen 0e7 samt medlemsprispolicyn. Den rättar
inte Coops avvisade fysiska kampanjkälla; se SCAN.md. Behåll källprocessen
oförändrad. Gamla planrevisioner läses med sin sparade policy. Nya beräkningar
och personliga omräkningar sparar all_advertised utan att ändra innehavda
medlemskap. Ingen medlemsregistrering eller personlig kupongaktivering sker.

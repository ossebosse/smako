# Privat publiceringsprov och oförändrad beta

Provets validering/atomiska pekare kördes i /work/publication/price-universes,
under samma kanoniska driftlås. Produktionens kataloger var read-only.
Detta är inte en produktionsaktivering eller bevis för drift över flera dagar.

| Kontroll | Utfall |
|---|---|
| baseline_validated | active_from_prebuilt_artifact |
| candidate_validated | active_from_prebuilt_artifact |
| broken_candidate_rejected | True |
| failed_candidate_keeps_lkg | True |
| missing_lineage_rejected | True |
| stale_rollback_rejected | True |
| rollback_and_restart_readback | True |

Tid: 140.08 s. Betans manifest förblev byte-identiskt:
`ff76c9f6bc5c54b778872870b6655050cc74e25e386b62a081663676dfe5b429`.

Giltigt rollbackunderlag (A): `67ebfecdfb4bfed5b72041f369c7e633f51e4b499d7d77bd1d859b091c5d7067`.
Äldsta basobservation: 2026-09-21T01:17:55.407816+00:00.
48-timmarsgräns: **23 september 03:17:55 Europe/Stockholm**.
Varning vid 36 timmar kvarstår. Rollback måste också vara kodkompatibel;
kan inte användas efter gränsen utan nytt riktigt källunderlag.

Isolerad kandidat A: `price-universe:8cfb4f26664c18415b606d55f3075b4ee0d36b5f8f6d8f175e6fe26b2e1127ed`.
Isolerad kandidat B: `price-universe:8fadb32137969f3ec974ffd05976753ee74dd92fac47f397e6c20586fc434b19`.
Fullständiga artefakter och fryst databas ligger i serverns privata provkatalog
/tmp/smako-coop-1520-20260922/data. De byggdes från originalkällorna, inte från
betans begränsade sökprojektion. Inga användarplaner finns i dessa prisartefakter.

Betan avläst 2026-09-22T07:06:11.388071+00:00: health 200, ready 200.
App/scheduler är fortfarande `billigaste-veckomenyn:0.1.0-smako-price-recovery-lund-20260914a`.
Aktivt PriceUniverse: `price-universe:8cfb4f26664c18415b606d55f3075b4ee0d36b5f8f6d8f175e6fe26b2e1127ed`.
Denna ordinarie aktivering skedde före vårt arbete, 22 september 04:49:43 UTC.
Ingen betaprofil eller tidigare plan har ändrats.

141 fokuserade tester omfattar även saknad/korrupt frivillig databas, ofullständig
kandidat, diskbrist, manipulerad artefakt, bevarad LKG, källhistorik, omstart,
36/48 timmar, gruppriser, medlemsvillkor och gemensamma köpgränser.
Felfallen är tester; 332 audit-anrop i B är verkliga planeringskorgar.

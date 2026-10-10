> Uppdatering 2026-10-10 10:04 UTC: denna kandidat är nu aktiverad efter
> återställd prisdrift. [Utfört byte och slutprov](../source-return-recovery-20261010/ACTIVATED.md).
> Texten nedan bevarar läget vid den tidigare leveransen före aktivering.

# Separat app-only-kandidat: return-session-205cd8ca0f31

Inte aktiverad. Se EVIDENCE.json för full runtime, image och pakethash.
Paket på D: `.local/return-session-20261010/package/smako-return-session-205cd8ca0f31.zip`.
Image byggd lokalt med `scripts/build_return_session_patch.py`, nätverk av,
hashkontroll av fyra filer i basimagen. Ingen käll-/reläkod ingår i deltapaketet.

Återanvänd den aktuella app-only-vägen från
`../shopping-quick-menu-20261009/ACTIVATED.md`, med nya konkreta identiteter.
Kopiera inte föregående skripts pinnade hashvärden oförändrat.
Förkontroll måste läsa faktisk app, wrapper, Compose, data/mounts, kapacitet
och pågående jobb; dagens konstaterade bas är shopping-list-6b10628f22d8.
Bevara senare arbete. Vänta ut jobb, ta konsistent PlanStore-backup och håll
befintligt operationslås. Bara app.image och BUILD_ID får skilja;
COMPLETE_RECIPES_ENABLED förblir true. Ingen databasersättning, migration,
ny insamling eller sidotjänstbyte. Ingen serverbuild.

Prisdriften är spärrad enligt RESULTS.md. Kalla inte ett appbyte för prisåterställning.
Återställ tillräcklig kapacitetsmarginal innan installation/backup.
Efter separat aktivering: kontrollera faktiskt serverade filhashar, ägarbundna
sparade revisioner och knappar. Kör endast nya planprov när gällande femkällorsgate
är uppfylld. Ingen replayklocka eller fryst testdata i produktion.

Denna UI-rättning har ingen DB-migration. Återgång till bevarad 6b-image är
begränsad till detta fyra-filers delta och återinför den kända återanslutningsbuggen.
Senaste användarlagring bevaras alltid. Receptflagga av är inte en rättning av
prisblockerings-/statusfelet. Sänk inte färskhetsgränser eller ägarskydd.

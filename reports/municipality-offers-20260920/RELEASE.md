# Separat releaseförslag – inte aktiverat

Föreslagen leveransenhet är enbart opt-in kommunbedömning, geografisk evidens, ICA:s begränsade adresskomplettering och rapportering. Den väntande releasen `ica-structured-lund-20260920a` ska fortsatt använda sitt tidigare granskade innehåll. Dessa ändringar ingår **inte** i dess image eller Windows-export.

Kandidaten ligger på `areas/municipality-audit-20260920`. `incremental.patch` och `changed-files.json` beskriver endast detta delmåls differens mot den bevarade ocommittade basen. Originalbranchens status och 139 ärvda ocommittade kod-/test-/dokumentfiler kontrolleras med hash; releasekällans egna manifest verifieras separat.

Första säkra användning är manuell inventering: `--area-mode municipality --municipality-code 1281|1280 --inventory-only --skip-flyers` med ny isolerad output. Standard är fortsatt locality. Inget användarpostnummer kräver identiskt butikspostnummer. Kommunens datatäckning styr inte användarens butikstak, radie eller butikspreferenser.

Inte verifierat för aktivering: full kommuninventering över alla kedjor, koordinatmatchning utan gränsbehörighet, nya Coop-raders köpavtal, serverdrift för de nya provkontexterna, aktuellt 15/20-utfall och några nya bildbaserade priser. En räknad söklista eller grön parser är inte releasegodkännande. Kommunens `municipality_complete=false` hindrar att sökresultatets fullständighet används som automatisk produktionsgodkänd ICA-ID-lista.

Nästa separata release måste kräva färska geografiska källor och färska kvalificerade priser, replay/regression, explicit geografiskt scopeslut, isolerad kandidat och vanliga promotion-/rollbackkontroller. Ingen källa, basregel (36/48h) eller 95-procentsgrind ändras av denna kod.

Rollback för denna inventeringsfunktion: använd befintligt adressortsläge eller lämna den separata grenen omergad. Ingen produktionsmanifestrollback behövs eftersom inget aktiverades. Kopiera inte den nya arbetskopians hela ärvda diff över den väntande releasen.

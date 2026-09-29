# Nästa uppdateringar – policyförslag, inte installerat schema

| Butik | Senast lyckad källa (Stockholm) | Nästa kontroll | Prisets 48 h-stopp | Skäl |
|---|---|---|---|---|
| Coop Värpinge Lund (3659) | 2026-09-22T11:28:29.389092+02:00 | 2026-09-23T22:28:29.389092+02:00 | 2026-09-24T11:28:29.389092+02:00 | coop_35h_source_check_before_48h_stop |
| Stora Coop Lund (2696) | 2026-09-22T11:28:34.888015+02:00 | 2026-09-23T22:28:34.888015+02:00 | 2026-09-24T11:28:34.888015+02:00 | coop_35h_source_check_before_48h_stop |
| Coop Veberöd (1158) | 2026-09-22T11:28:40.992159+02:00 | 2026-09-23T22:28:40.992159+02:00 | 2026-09-24T11:28:40.992159+02:00 | coop_35h_source_check_before_48h_stop |
| Coop Trollebergsvägen (3837) | 2026-09-22T11:28:46.079226+02:00 | 2026-09-23T22:28:46.079226+02:00 | 2026-09-24T11:28:46.079226+02:00 | coop_35h_source_check_before_48h_stop |
| Coop Flöjtvägen (3839) | 2026-09-22T11:28:50.363456+02:00 | 2026-09-23T22:28:50.363456+02:00 | 2026-09-24T11:28:50.363456+02:00 | coop_35h_source_check_before_48h_stop |
| Coop Klostergården (3820) | 2026-09-22T11:28:54.592275+02:00 | 2026-09-23T22:28:54.592275+02:00 | 2026-09-24T11:28:54.592275+02:00 | coop_35h_source_check_before_48h_stop |
| Coop Mårtenstorget (3813) | 2026-09-22T11:28:59.759972+02:00 | 2026-09-23T22:28:59.759972+02:00 | 2026-09-24T11:28:59.759972+02:00 | coop_35h_source_check_before_48h_stop |
| Coop Genarp (3841) | 2026-09-22T11:29:04.932126+02:00 | 2026-09-23T22:29:04.932126+02:00 | 2026-09-24T11:29:04.932126+02:00 | coop_35h_source_check_before_48h_stop |
| Coop Vildgåsen Lund (3656) | 2026-09-22T11:29:09.211886+02:00 | 2026-09-23T22:29:09.211886+02:00 | 2026-09-24T11:29:09.211886+02:00 | coop_35h_source_check_before_48h_stop |
| X:-Tra Skansvägen (3658) | 2026-09-22T11:34:53.008711+02:00 | 2026-09-23T22:34:53.008711+02:00 | 2026-09-24T11:34:53.008711+02:00 | coop_35h_source_check_before_48h_stop |

Coop/X:-tra har inte ICA:s särskilda undantag från generell prisålder. 35 h-kontroll används därför före 36/48 h-gränserna. Kampanjens tidigare start/slut går före denna tid. Skansvägens torsdagssida börjar 24 september 00:00, men källkontrollen föreslås redan 23 september cirka 22:34.
Vid misslyckad hämtning bevarar policyprovet senaste lyckade observation och föreslår första återförsöket efter 15 minuter, därefter begränsad backoff. Detta förlänger inte kampanjdatum eller 48 h-stopp. Den beständiga kopplingen från denna policy till publicerad Coop-källa saknas fortfarande i ordinarie drift.
Basens äldsta observation: 2026-09-21T03:17:55.407816+02:00. Föreslagen 35 h-kontroll: 2026-09-22T14:17:55.407816+02:00. Varning: 2026-09-22T15:17:55.407816+02:00. Stopp/rollbackgräns: 2026-09-23T03:17:55.407816+02:00.
Befintligt produktionscron lästes utan ändring: daglig refresh 03:17 Europe/Stockholm, nästa 23 september. Det är bara cirka 55 sekunder före den nuvarande basens stopp. Det är ingen säker insamlingsmarginal och inte ett installerat 35 h-schema. Den väntande ICA-/Windows-ändringen är orörd.

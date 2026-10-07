# Separat retentionförslag – ingen radering

Läsinventering 2026-10-07 09:22:52 UTC. Storlekarna är filernas logiska
byteantal, inte bevis på frigörbart diskutrymme. Inga referensberoenden
har ännu godkänts för borttagning. **Valda raderingsobjekt: 0 filer, 0 byte.**

| Område | Filer | Logiska byte |
| --- | ---: | ---: |
| `/srv/smako/backups` | 158 | 60 942 012 037 |
| `/srv/smako/data/raw_snapshots` | 68 076 | 3 660 548 489 |
| `/srv/smako/data/price_universes` | 83 | 5 056 507 422 |
| `/srv/smako/data/grocery` | 2 227 | 5 666 507 439 |
| `/srv/smako/data/plans` | 3 | 90 050 563 |
| `/var/tmp/smako-meal-library-20261006` | 9 181 | 875 846 588 |

## Föreslagen separat fortsättning

1. Inventera backupkedjornas innehåll och återställningsberoenden. Backuperna
   är det största uppmätta området ovan och bör granskas först. Behåll aktuell
   konsistent backup, aktiva återställningsankare och allt som krävs för
   senare användararbete. En eventuell arkivering till D: måste hashkontrolleras
   och återläsas innan serverkopior kan föreslås för borttagning.
2. Bygg en referenslista från aktiva prismanifest, produktfaktadokument,
   biblioteksversioner, sparade revisioner och återställningspaket. Ålder
   eller ett leveranskvitto räcker inte för att klassa råmaterial som överflödigt.
3. Leverera därefter en ny explicit dry-run med exakta filer, hash, referensstatus,
   allokerade byte och bevarat återställningsankare. Separat godkännande krävs
   innan den listan verkställs. Inga wildcard-raderingar eller Docker-prune.

Denna inventering återställer inte kapaciteten. Serverns fria utrymme var
fortfarande 0 byte vid återkontrollen 12:00:50 UTC. Insamlings-/mottagarskyddet
och den befintliga kön ska behållas tills verklig kapacitet finns.

Maskinunderlag: `.local/willys-storage-search-20261007/retention-server.json`.

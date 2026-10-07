# Exakt arkivförslag – ingen radering godkänd

| Objekt | Filer | Logiska byte | Allokerade byte |
| --- | ---: | ---: | ---: |
| `/var/tmp/smako-repo-release-20260929/ops-verification/old-pair-data/grocery.sqlite` | 1 | 2771906560 | 2771906560 |
| `/var/tmp/smako-repo-release-20260929/ops-verification/old-pair-data-v2/grocery.sqlite` | 1 | 2771906560 | 2771906560 |
| `/var/tmp/smako-repo-release-20260929/ops-verification/rollback-data/grocery.sqlite` | 1 | 2545623040 | 2545623040 |
| `/var/tmp/smako-repo-release-20260929/ops-verification/rollback-data-v2/grocery.sqlite` | 1 | 2545623040 | 2545623040 |
| `/var/tmp/smako-repo-release-20260929/ops-verification/old-pair-data/raw` | 26527 | 1382334213 | 1443131392 |
| `/var/tmp/smako-repo-release-20260929/ops-verification/old-pair-data-v2/raw` | 55973 | 2982365623 | 3114520576 |
| `/var/tmp/smako-repo-release-20260929/ops-verification/old-pair-data-v2/price-universes` | 48 | 1924926968 | 1925058560 |
| `/var/tmp/smako-repo-release-20260929/ops-verification/rollback-data-v2/raw` | 6973 | 322444930 | 338657280 |
| `/var/tmp/smako-repo-release-20260929/ops-verification/rollback-data-v2/price-universes` | 25 | 1944346179 | 1944428544 |

Totalt 89550 filer; 19400855552 allokerade byte.

Arkivstatus och verifiering:

```json
{
  "archive": "D:\\Projects\\Smako\\.local\\drift-restoration-20261007\\inactive-test-data.tar.gz",
  "archive_sha256": "21946e544ae4b8605c0d5f52aa32fad3ae21869052716c7c00207441a5f5e3f4",
  "archive_bytes": 3613102573,
  "files": 89550,
  "logical_bytes": 19191477113,
  "allocated_source_bytes": 19400855552,
  "transfer_exit": 0,
  "all_files_hash_verified": true,
  "unix_owner_mode_verified": true,
  "acls_xattrs_preserved_by_GNU_tar": true,
  "source_removed": false,
  "seconds": 826.8755238056183,
  "all_files_restored_with_correct_size": true,
  "restored_files": 89550,
  "restored_bytes": 19191477113,
  "restore_path": "D:\\Projects\\Smako\\.local\\drift-restoration-20261007\\restore-check",
  "all_files_restored_and_hash_verified": false,
  "restored_hash_verified_files": 39532,
  "restored_hash_scope": "Four complete database checks plus the first 40000 members of the remaining manifest; per-target and per-10000 completion records preserved. All 89550 archive members were independently SHA256-verified against original files before full restoration.",
  "optional_extra_restore_hash_check": "Stopped by operator agent after completed archive checksum validation, full restoration/size check and 39532 restored-file checksum checks. No checksum failure observed; remaining restored-file checks not claimed.",
  "stopped_at": "2026-10-07T21:23:42.069224+00:00",
  "restore_scope": "Full contents restored on NTFS; Unix ownership/mode and ACL/xattrs preserved in GNU tar metadata, not applied as Windows identities.",
  "verification_restarts": [
    "restore-check-restart.json",
    "restore-check-checkpoint.json"
  ]
}
```

Ingen serverkopia får tas bort före uttryckligt godkännande av dessa nio objekt, färdig hash-/återställningskontroll samt förnyad kontroll av innehåll och aktiva referenser. Inga planfiler eller privata konfigurationer ingår.

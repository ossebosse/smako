# Verifierad slutkandidatimage, 2026-10-03

Serverpaketet för runtime `ca57fb22ba0e58cee41cc1e40673e1edbfbf4d78` byggdes med
paketets root-Dockerfile i ett nytt markerat isolerat byggsammanhang. Alla 651
manifestbundna källfiler matchade SHA-256 före byggstart; ZIP-filen innehåller
dessutom `RELEASE.json`, alltså 652 filer totalt.

| Underlag | Exakt värde |
|---|---|
| Paket | `smako-server-ca57fb22ba0e.zip`, 2 736 155 byte |
| Paket-SHA-256 | `61c57bf98e853f86b02a49dea487dd06d9ecc5971aa19c171479450fbe382da2` |
| Imagetagg | `smako-complete-recipes-candidate:ca57fb22ba0e` |
| Oföränderligt image-ID | `sha256:51a1bffce59a1b5fc68ebab2364fdd952e6e6f4148a7c53814af2549d8edf9f8` |
| Plattform / användare | Linux amd64 / `app` |
| Runtimefiler i image | **645 matchande, 0 avvikande** |
| `pip check` | PASS |
| Chromiumstart utan nätverk | PASS, som bildens standardanvändare `app` |
| Byggtid / verifieringstid | 115,166 s / 3,476 s |

Verifieraren kom från samma commits Gitblob:
`scripts/release_verification/verify_server_image.py`. Enda tillåtna saknade
filen var `deploy/.env.production.example`, uttryckligen undantagen från image
via `.dockerignore`. Verifieringscontainern hade avstängt nätverk, 2 CPU,
3 GiB, skrivskyddat rotfilsystem och inga monterade hemligheter. Den togs bort
efter kontrollen.

Detaljerade hashvärden och resultat finns i
[den sanerade verifieringsfilen](image-verification-ca57fb22ba0e.json).
Full bygglogg, verifieringslogg och ett färdigt `packaged-http-run-command.json`
ligger utanför Git i `.local/releases/complete-recipes-20261002/ca57fb22ba0e`.

HTTP-kommandot använder exakt detta image-ID och testlaunchern från
`candidate-packaged-ca57`. Det behåller teststate, port och label men monterar
**inte** `backend/app` eller `grocery_data/app`. Kommandot är förberett men har
inte körts. Paketets rena planbenchmark och slutliga HTTP-/browserprov är
separata kontroller och intygas inte av denna imageverifiering.

Inga körande containrar, produktionsinställningar, insamlingar eller scheman
ändrades. Ingen produktionsaktivering eller Git-push genomfördes. Fjärrresursen
lämnades tillbaka efter verifiering och hämtning av bevisen.

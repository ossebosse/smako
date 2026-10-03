# Verifierad kandidat efter energispärr, 2026-10-03

Serverpaketet för runtime `dd3f6add6a6b4cffe58f1a72c9408816f08a6f25` byggdes
med paketets root-Dockerfile i ett nytt markerat isolerat byggsammanhang.
Samtliga 651 manifestbundna källfiler matchade SHA-256 före byggstart;
ZIP-filen innehåller dessutom `RELEASE.json`, alltså 652 filer totalt.

| Underlag | Exakt värde |
| --- | --- |
| Paket | `smako-server-dd3f6add6a6b.zip`, 2 737 637 byte |
| Paket-SHA-256 | `58eebb0c056bc6b9cd10c6d6392ac3855b2bbf6e51cc16f9fa1d937767837773` |
| Imagetagg | `smako-complete-recipes-candidate:dd3f6add6a6b` |
| Oföränderligt image-ID | `sha256:7a9834d2d5b58a7b7c835b77d833ae5640f0a6c53dda350282dc1e034329bbcb` |
| Plattform / användare | Linux amd64 / `app` |
| Runtimefiler i image | **645 matchande, 0 avvikande** |
| `pip check` | PASS |
| Chromiumstart utan nätverk | PASS, som standardanvändaren `app` |
| Byggtid / verifieringstid | 117,267 s / 4,121 s |

Verifieraren kom från samma commits Gitblob:
`scripts/release_verification/verify_server_image.py`. Enda tillåtna saknade
filen var `deploy/.env.production.example`, uttryckligen undantagen från
imagen via `.dockerignore`. Verifieringscontainern hade avstängt nätverk,
2 CPU, 3 GiB, skrivskyddat rotfilsystem och inga monterade hemligheter. Den
togs bort efter kontrollen.

Hashvärden och resultat finns i
[den sanerade verifieringsfilen](image-verification-dd3f6add6a6b.json).
Fulla bygg- och verifieringsloggar samt `packaged-http-run-command.json`
ligger utanför Git i `.local/releases/complete-recipes-20261002/dd3f6add6a6b`.
HTTP-kommandot använder exakt image-ID och testlaunchern från
`candidate-packaged-dd3`, behåller isolerat teststate, port och label och
monterar **inte** `backend/app` eller `grocery_data/app`. Det är förberett
men har inte startats i denna verifiering.

Receptkvalificering, fria menyer, rena benchmark och HTTP-/browserprov är
separata kontroller och intygas inte av imageverifieringen. Denna image
innehåller energispärren som beskrivs i
[deklarationsgranskningen](ENERGY-DECLARATION-REVIEW.md). Äldre imagebevis
bevaras som historik. Inga körande containrar, produktionsinställningar,
insamlingar eller scheman ändrades. Ingen produktionsaktivering eller
Git-push genomfördes.

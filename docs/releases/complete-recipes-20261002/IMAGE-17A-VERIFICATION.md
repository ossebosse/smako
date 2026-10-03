# Verifierad kandidat med energispärr och källbunden brödform, 2026-10-03

Serverpaketet för runtime `17a9c1330dcc72ff9750a3fa680fa6982f7ed99b` byggdes
med paketets root-Dockerfile i ett nytt markerat isolerat byggsammanhang.
Samtliga 651 manifestbundna källfiler matchade SHA-256 före byggstart;
ZIP-filen innehåller dessutom `RELEASE.json`, alltså 652 filer totalt.

| Underlag | Exakt värde |
| --- | --- |
| Paket | `smako-server-17a9c1330dcc.zip`, 2 739 005 byte |
| Paket-SHA-256 | `d3327b9137d4310707118b5272bc826ed0403ebd6d0c0ab935bb1196efee060a` |
| Imagetagg | `smako-complete-recipes-candidate:17a9c1330dcc` |
| Oföränderligt image-ID | `sha256:99bf3bfcb4f395ec1a06df23649e0241903d52bb5bba40ca4336abbd2bbecc35` |
| Plattform / användare | Linux amd64 / `app` |
| Runtimefiler i image | **645 matchande, 0 avvikande** |
| `pip check` | PASS |
| Chromiumstart utan nätverk | PASS, som standardanvändaren `app` |
| Byggtid / verifieringstid | 115,964 s / 2,657 s |

Verifieraren kom från samma commits Gitblob:
`scripts/release_verification/verify_server_image.py`. Enda tillåtna saknade
filen var `deploy/.env.production.example`, uttryckligen undantagen från
imagen via `.dockerignore`. Verifieringscontainern hade avstängt nätverk,
2 CPU, 3 GiB, skrivskyddat rotfilsystem och inga monterade hemligheter. Den
togs bort efter kontrollen.

Hashvärden och resultat finns i
[den sanerade verifieringsfilen](image-verification-17a9c1330dcc.json).
Fulla bygg- och verifieringsloggar samt `packaged-http-run-command.json`
ligger utanför Git i `.local/releases/complete-recipes-20261002/17a9c1330dcc`.
HTTP-kommandot använder exakt image-ID och testlaunchern från
`candidate-packaged-17a`, behåller isolerat teststate, port och label och
monterar **inte** `backend/app` eller `grocery_data/app`. Det är förberett
men har inte startats i denna verifiering.

Receptkvalificering, fria menyer, rena benchmark och HTTP-/browserprov är
separata kontroller och intygas inte av imageverifieringen. Denna image
innehåller energispärren och den snäva källkvalificeringen för färdigbakat
spannmålsbröd. Energifelet beskrivs i
[deklarationsgranskningen](ENERGY-DECLARATION-REVIEW.md). Äldre imagebevis
bevaras som historik. Inga körande containrar, produktionsinställningar,
insamlingar eller scheman ändrades. Ingen produktionsaktivering eller
Git-push genomfördes.

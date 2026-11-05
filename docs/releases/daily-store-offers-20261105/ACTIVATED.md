# Dagliga butikserbjudanden för alla kedjor (scheduler)

Aktiverad 2026-11-05 16:00 UTC. Ägarbeslut samma dag: alla butikserbjudanden dagliga.

## Orsak

Endagserbjudanden missades om de inte föll på mån/tors-natten: Hemköps
klubbdag (ons 4/11) och ICA Nära Söderlivs "Prisfest" (tors 5/11, fångades
endast för att torsdag är insamlingsnatt).

## Ändring

Kod `e6d4ceaca5bc` (main), en fil:
`grocery_data/app/services/campaign_refresh_policy.py`.
Under `mon_thu` ger `scheduled_source_times` varje butikserbjudanderad
(ICA, Coop, Lidl, Willys reklamblad, City Gross, Hemköp) dagligt 05:17-fönster
med tre timmars omförsök. Butiksinventering och baskataloger behåller mån/tors.

## Driftsättning och prov

- Paket sha256 `b8f424aba3739c278dcfe74eb41970a22ed866a170534b8ab14517c2f258e4b9`,
  bygge utan nätverk `sha256:790ca46a263e08bf013a5f536ef1937563c9bf1a06a935e40641fcda74365df8`.
- 137 schematester gröna (uppdaterade till dagligt erbjudandeschema).
- Compose-config före/efter: endast image och BUILD_ID; inget jobb pågick; appen orörd.
- Plan efter byte (Lund): ICA 12, Coop 10, Hemköp 3, Lidl 2, Willys reklamblad 1
  butik(er) nästa gång 2026-11-06 04:17 UTC; inventering 2026-11-09.

## Återställning

Compose utan `/opt/smako/overrides/source-ops-e6d4ceaca5bc.json`
(bild `sha256:3fc9aaac…`, BUILD_ID `source-ops-b25b76b412ed`).

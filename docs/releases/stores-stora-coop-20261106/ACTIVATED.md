# Stora Coop i stället för nätbutiken och butiksadresser aktiverat

Aktiverad **2026-11-06T07:58:06.287444+00:00** på https://beta.smako.nu.
Main `191f173f1e19`, app **app-191f173f1e19-e452c67c** (bild `sha256:842d11663897…`,
bas `sha256:53020af2a5ce…`). Schedulern orörd. Ägaren godkände aktiveringen
2026-11-06 06:29. Main-CI grön för samtliga jobb (planner-jobbet hade fastnat i
webbläsarinstallationen och kördes om).

## Ändring

- Planens priskontexter anger butikens adress och, för en butik med baspriser
  från en nätbutik, den nätbutiken (`base_price_context_id`). Stora Coop Lund
  pekar på Coop Online Syd via samma käll-ID (730400) i det aktiva universumet.
- Mina val: med alla butiker i kommunen jämförs Stora Coop Lund i stället för
  Coop Online Syd. Nätbutiken går att välja under Välj själv.
- Plan och inköpslista visar adress när namnet saknar gatan, till exempel
  "Willys Lund, Magistratsvägen 22".

Sex filer: `models/plan.py`, `services/meal_plan_optimizer.py`,
`static/personal.html`, `static/personal.js`, `static/service-worker.js`,
`static/shopping-location.js`.

## Förfarande

Bygget kördes med verktyget; SSH-anropet bröts av klientens tidsgräns medan
bygget fortsatte, och `candidates.json` (skriven efter alla kontroller) togs som
`build.json`, som vid förra aktiveringen. Aktiveringen väntade tills morgonens
butiksinsamling (05:17, omförsök 05:47 och 06:5x UTC) hade släppt driftlåset och
kördes sedan fristående på servern med verktygets egen aktiveringskod.

## Verifiering

- Endast appen bytt, enda miljöändring BUILD_ID, prismanifest och mountar
  bevarade. Bevarat: 335 planversioner, 149 privata tillstånd, 2 konton,
  1 session. Backup `/srv/smako/backups/20261106T074611Z`. Retention complete.
- `/ready` 22350 och 21120: ready, `app-191f173f1e19-e452c67c`.
- `/api/shopping-location?postal_code=22350`: Stora Coop Lund, Traktorvägen 2,
  har `base_price_context_id` = Coop Online Syd.
- Publikt prov, ny gäst, alla 32 butiker i Lund utom nätbutiken, högst två:
  Stora Coop Lund (Traktorvägen 2) 47,34 kr och Willys Lund (Magistratsvägen 22)
  121,03 kr, totalt 168,37 kr, VERIFIED. Coop Online Syd fanns inte bland de
  jämförda kontexterna.

## Nästa bas

Nästa appflöde utgår från `191f173f1e19`.

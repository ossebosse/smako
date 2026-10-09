# Inköpslistan aktiverad på beta – 9 oktober 2026

Användarens appgodkännande genomfört **16:48:27 UTC / 18:48 svensk tid**.
Beta kör **shopping-list-6b10628f22d8**, image
`sha256:a5b678ca483135037c8a4d20cb61738861b544bfbcc21c58e8389b9f022bae32`.
Paket/runtime enligt RESULTS.md. Ingen ombyggnad eller replaydata på servern.

## Utfört

- Kontrollerade verklig app (meal-library-42fab888ffd7), image, paket, miljö,
  mounts, operationstillstånd och ledigt utrymme före ändring.
- Befintligt operationslås; inga plananrop på 15 minuter, två CPU-lugnprov
  0,03/0,04 CPU-sekunder per 10 s. Ingen direkt räknare över processminnesjobb.
- Konsistent PlanStore-backup: 108 113 920 byte, full integrity/FK PASS,
  SHA-256 `3e9157c2521dc787b450b84ae86c46054aa0855c1983f9c313326abd0867e83b`.
  Skyddat under `/opt/smako/evidence/shopping-activation-20261009/current-state-backup`.
  Grocerys användar-/session-/kvittotabeller verifierat tomma; grocery ändrades inte.
- Upplöst Compose-diff endast app.image och app.BUILD_ID. Receptflaggan true
  bevarad. Oförändrade mounts, miljö i övrigt och andra containeridentiteter.
  Relä, scheduler, källprocesser, proxy och insamlingsregler orörda.
- Endast app up --no-deps --no-build --pull never. Senaste Compose-wrapper
  avslutas med `/opt/smako/overrides/shopping-list-6b10628f22d8.yaml`.
- /ready 200. Manifestet före/efter är
  `price-universe:4a4ec281af9830115e1187a9f7594a74ab8870c0ff7720c9d6fad9631be63c9e`.
  Alla fem baskontexter laddade och användbara; Coop/Hemköp FRESH,
  Willys cirka 41 timmar, AGING men under 48-timmarsstoppet. Ingen föryngring.
- Faktiskt serverad HTML, JavaScript och CSS hashmatchar leveranspaketet.
- Serverutrymme: 10 128 060 416 byte före, 10 017 951 744 efter byte/backup.
  Ingen rensning. Image strömmad från D: till docker load; delade lager återanvända.

## Verkliga knappflöden

Chromium och WebKit mobil layout: generiskt kaffe först, konkreta produkter
utan butiksväljare/priser, ändring av generisk mängd/enhet, tillbaka från
produkt till generisk vara, sparade produktalternativ, omladdning, dubbelklick
med ett startanrop/ett jobb, riktig inköpskorg och audit PASS. Explicit omräkning,
revisions-GET 1/2 och fel ägares nekade GET PASS. Inga pageerrors, nätfel eller
server-5xx i dessa slutprov. Dagens faktiskt publicerade data och separata
gästsessionsidentiteter. OIDC saknas fortfarande; ingen verifiering av verklig
kontoinloggning eller fysisk iPhone påstås.

Publik Chromium: fem enkla middagar via vanlig knapp, dubbelstart/omladdning,
audit och sparad läsning PASS. 145,125 s till resultat med dagens underlag.
Detta är inte ett PASS mot 60-sekundersmålet eller en kontrollerad
prestandajämförelse. Receptbyte gjordes inte om i detta avgränsade aktiveringsprov.

Alla tidigare 234 revisioner och 68 privata tillstånd hashmatchar efter bytet
utan förlust. Gamla och nya revisioner materialiseras av den aktiva versionen.

## Återgång och bevarande

COMPLETE_RECIPES_ENABLED=false är bara receptfunktionens flagga, inte en
avstängning av inköpslistan. Ingen generell flagga-av-återgång för denna funktion
påstås. Äldre binärers läsning av nya one_of-revisioner är inte kvalificerad.
Vid fel: bevara senaste data och gör bedömd framåträttning/kvalificerad återgång.
Återställ aldrig äldre databas över senare arbete. Tidigare image och paket bevaras.

Råa klientrapporter, privata konfigurationskopior och testidentiteter finns
utanför Git; den kompakta evidensen innehåller inga autentiseringsuppgifter.

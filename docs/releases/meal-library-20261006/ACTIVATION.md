# Separat app-only-kandidat – inte aktiverad

Etapp A aktiverade dd12. Denna instruktion gäller endast ett framtida, separat
beslut för måltidskandidaten. Läs RESULTS.md och aktuellt driftläge före beslut.
Detta dokument är ingen installation eller ny insamlings-/proxyrelease.

| Identitet | Värde |
| --- | --- |
| Låst implementation P2 | `e2e5d248ee44657b45080f20f5a003b1ced46a13` |
| Slutlig innehålls-/runtimecommit P3 | `fd2cfda5490ac93295e6a2cef6b6b8408497f89e` |
| Paket | `smako-server-fd2cfda5490a.zip` |
| Paket SHA-256 | `342b74f913ce0625ee78bcdf283f02937273e9b36b730d26216ec55ffd5014e3` |
| Image | `sha256:b8541e165a2075c4c5657e1296c83e276f3aa8f59607292e32b653b60a7655fb` |
| Avsett BUILD_ID | `meal-library-fd2cfda5490a` |
| Kompletta recept | `true` efter lyckad kontroll |

Paketet finns i `.local/releases/meal-library-final-20261006/`. Imagen byggdes
från hashkontrollerade paketfiler ovanpå identifierad, verifierad föregångare.
Dess 663 faktiskt kopierade filer matchar slutpaketet, inklusive
complete-recipes.js SHA-256
`c5d7a4e27a8b23a52499fedc73d2d688169e2c89f4b782d86eafd98a4644cd37`.
Webbläsarens URL-version är `meal-library-1`. OS- och Pythonberoenden matchar
dd12. Ingen ny byggning ska göras under aktiveringen.

## Förkontroller och avgränsning

1. Kontrollera faktisk produktion och senare releaser; skriv aldrig över en
   nyare fungerande kandidat. Kontrollera även ledigt diskutrymme och att
   publicerat prisunderlag klarar oförändrade 36/48-timmarsgränser. Historiska
   testpriser är inte dagens köpbarhetsbevis. Ett faktiskt hinder stoppar bytet.
2. Verifiera ZIP, RELEASE.json, image-ID och samtliga filhashar. Verifiera att
   inga mounts skuggar runtimekod. Isolerade testklockor, testdatabaser,
   RAM-testlagring eller `/evaluation`-harnessen ska aldrig installeras.
3. Läs den faktiskt använda wrappern `/opt/smako/compose`, ordnade Compose-
   filer och privata miljöfiler. Lägg en administratörsägd kopia av
   `app-only.override.example.yaml` sist. Den fullständiga upplösta diffen
   får endast ändra appens image, BUILD_ID och COMPLETE_RECIPES_ENABLED.
   Bevara scheduler, collector, migrate, relä, proxy, kanaler, policys och mounts.
   Wrappern innehåller redan dd12:s override. Förbered och kontrollera först
   konfigurationen med `compose -f /opt/smako/overrides/meal-library-fd2cfda5490a.yaml config`.
   Vid ett godkänt byte ska den nya `-f`-referensen sparas sist i wrappern,
   före dess `"$@"`, med bevarad filmode och atomiskt filbyte. Kontrollera
   den upplösta diffen igen innan `up`. Ett engångsargument utan beständig
   wrapperreferens är inte en beständig aktivering.
4. Låt pågående jobb avslutas; processminnesjobb överlever inte ett appbyte.
   Använd befintligt operation lock och ta konsistent backup av aktuell
   plan-/användarlagring. Kontrollera fingerprint för revisioner, ägarbindning,
   skafferi och reservationer. Återställ aldrig en äldre databas över senare data.
5. Byt enbart appen med befintlig wrapper och validerad override:
   `up -d --no-deps --no-build --pull never app`. Ingen global imagevariabel
   eller ombyggnad ska användas. Kontrollera image-ID, BUILD_ID, flagga,
   `/ready` och faktiskt laddat JavaScript mot ovanstående hash.
6. Använd separat verifieringsidentitet och faktiskt publicerade priser för
   publika/personliga knappflöden: alla måltidstyper, dubbelstart, omladdning,
   återanslutning, receptbyte, uttrycklig omräkning och revisions-GET. Läs äldre
   planer oförändrat. Kontrollera den sessionsform som faktiskt är aktiv;
   gästprov är inte signerad kontosessionsverifiering.

## Funktionsåtergång

Sätt endast `COMPLETE_RECIPES_ENABLED=false` i samma nya image. Bevara senaste
data, skafferi och revisioner. Läs gamla och nya sparade planer med rätt ägare
samt prova äldre menyflöde. Flagga av begränsar nya innehållskontroller; den
reparerar inte varje möjligt kodfel. Äldre binäråtergång är inte kvalificerad
av detta prov och får inte förutsättas kompatibel med nya planfält.

Denna leverans ändrar inga produktionsscheman eller källor. Recept- och
faktaunderlag från isolerad berikad historisk replay hör till testbevisen.
Isolerade prov begränsades till två CPU och 3 GiB. Etapp A bevarade faktisk
produktionskonfiguration, som saknade dessa explicita caps. Kontrollera och
redovisa detta före ett framtida beslut; ändra inte resursfält under en
godkänd diff som bara omfattar image, BUILD_ID och receptflagga.

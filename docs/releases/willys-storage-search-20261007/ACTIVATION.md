# Veckosökning – framtida separat app-only-aktivering

**Isolerad slutkvalificering PASS. Detta är en förberedd driftväg för ett separat aktiveringsbeslut.**

Ingen del av B är aktiverad. A:s aktuella serverutrymmes- och readinesshinder
måste vara lösta före ett framtida appbyte. Se QUALIFICATION.json och RESULTS.md.

Tidigare etapp aktiverade dd12; denna etapps reläarbete är separat. Denna instruktion gäller endast ett framtida, separat
beslut för måltidskandidaten. Läs SEARCH.md och A-STATUS.md och aktuellt driftläge före beslut.
Detta dokument är ingen installation eller ny insamlings-/proxyrelease.

| Identitet | Värde |
| --- | --- |
| Runtimecommit | `54cb2e8159a126de26fa11cb1d393dc275238fd3` |
| Paket | `smako-server-54cb2e8159a1.zip` |
| Paket SHA-256 | `98446fac69395c8f7eded6c15f23f8194b5e26dffde1810e83cb5a9007338667` |
| Image | `sha256:8a537fc4d333d9fc17fd06916061ed481ba433951126688df51b6b4da19766f3` |
| Avsett BUILD_ID | `week-search-54cb2e8159a1` |
| Kompletta recept | `true` efter lyckad kontroll |
| Exporterad imagefil | `smako-week-search-54cb2e8159a1-image.tar` |
| Imagefil SHA-256 | `ec82580cc0a7c6d001bfda93dd0f2b8fc48938cda5d0ea5f57f7d93d9879ff19` |
| Imagefil storlek | 593 880 576 byte |

Paketet finns i `.local/willys-storage-search-20261007/package-54cb2e8159a1/`. Imagen byggdes
från hashkontrollerade paketfiler ovanpå identifierad, verifierad föregångare.
Dess 664 faktiskt kopierade filer matchar slutpaketet, inklusive
complete-recipes.js SHA-256
`c5d7a4e27a8b23a52499fedc73d2d688169e2c89f4b782d86eafd98a4644cd37`.
Webbläsarens URL-version är `meal-library-1`. Före- och efterimagen i denna lokala jämförelse har samma OS- och
Pythonberoenden. Den lokala OS-basen är inte identisk med den historiska
serverimagen; inspektera paketinventeringen inför beslut. Ingen ny byggning ska göras under aktiveringen.
Den exporterade imagen ligger bredvid ZIP-filen. Efter separat godkänt
beslut: överför den hashkontrollerade TAR-filen till den valda releaseplatsen,
läs in den med `docker image load --input <verifierad-tar>` och kontrollera
ovanstående image-ID. Exporten innehåller inga testvolymer eller containerlager
från felinjektionerna. Bygg inte om paketet vid installation.

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
   konfigurationen med `compose -f /opt/smako/overrides/week-search-54cb2e8159a1.yaml config`.
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
Isolerade prov begränsades till två CPU och 3 GiB. Tidigare appaktivering bevarade faktisk
produktionskonfiguration, som saknade dessa explicita caps. Kontrollera och
redovisa detta före ett framtida beslut; ändra inte resursfält under en
godkänd diff som bara omfattar image, BUILD_ID och receptflagga.

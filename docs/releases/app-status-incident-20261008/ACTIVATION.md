# Separat app-only-kandidat – inget byte utfört

| Identitet | Värde |
| --- | --- |
| Kandidatdelta | `293fc6c49400f6f508eebb6772774d4fdfd995c9` |
| Basruntime | `dd12cc80e98c79aa32c159223c8bc1ceeaaa7580` |
| Selektiv tidigare statusfix | `ab2718aa645da0fcc797a746cbe47267ad1946a0`, endast API personal/plan |
| Paket | `smako-app-incident-293fc6c49400.zip` |
| Paketbyte | 28 578 |
| SHA-256 | `c75a23cd91d66c30b3a4517d977c33222f0e3e1288a8e2cce9945b8e75e71e78` |
| Testad image | `sha256:c7295a8ea5dcb716f1580b46936da48bd63f24542bca7042e76a2903d9182c8d` |
| Lokal imagetag på servern | `smako-app-incident:293fc6c49400` |
| BUILD_ID | `app-incident-293fc6c49400` |

Lokalt paket/manifest: `.local/releases/app-incident-20261008/`. Isolerat
serverprov: `/var/tmp/smako-app-incident-20261008/`; inte installerad driftrelease.
Byggkommandot är `scripts/build_app_incident_patch.py --commit 293fc6c49400
--output <ny privat målkatalog>` genom projektets Python. Det installerar inget.
Basimagen måste matcha `c8362751…` före bygge; alla ändrade basfiler kontrolleras
inuti bygget. APP-PATCH.json binder exakt fyra runtimefiler. Inga beroenden,
recept, modeller, priser, fakta eller nya databasfält ändras.

## Efter ett separat godkännande

1. Läs RESULTS och osäkerheten om originalfelet. Kontrollera aktuell produktion
   så att senare fungerande kod inte ersätts. Verifiera paket och faktisk image.
2. Läs verklig `/opt/smako/compose`, alla ordnade Compose-filer och privata env-
   referenser. Bevara bland annat nuvarande source-ops-override. Ändra ingen
   global imagevariabel. Lägg en separat sista app-override enligt exemplet nedan.
3. Under befintligt operationslås: vänta ut appjobb, ta konsistent backup av
   senaste plan-/användarlagring och privata revisionsfingeravtryck. Bevara allt
   senare arbete. Upplöst diff får bara innehålla `app.image`,
   `app.environment.BUILD_ID`, `app.environment.COMPLETE_RECIPES_ENABLED`.
4. Starta endast app via den verifierade wrappern, `up -d --no-deps --no-build
   --pull never app`. Installera inga testfiler, replayklockor eller testdatabaser.
5. Kontrollera faktisk image/build, `/ready`, kompletta recept och oförändrat
   laddat prisunderlag. Kontrollera APP-PATCH-filhashar och faktiskt serverad
   `complete-recipes.js`: SHA-256
   `17311d27a3a50ec9e75415316ca8cc90d10c94ac85380b36a75a3541d1b7114e`.
   Verifiera riktiga menyknappar, dubbelstart/återanslutning, ägarbunden sparad GET
   och gamla revisioner. Ingen produktionsfelinjektion behövs.
6. `smako_ops.py status` läser befintlig metrik och det privata incidentindexet.
   Index skapas vid första 5xx, inte av statuskontrollen. App-UID 10001 behöver
   skriva i befintlig PlanStore-katalog, som redan är dess lagringsvolym.

```yaml
services:
  app:
    image: sha256:c7295a8ea5dcb716f1580b46936da48bd63f24542bca7042e76a2903d9182c8d
    environment:
      BUILD_ID: app-incident-293fc6c49400
      COMPLETE_RECIPES_ENABLED: "true"
```

## Återgångens gräns

Flagga av i samma image stänger komplett receptskapande enligt befintlig dd12-
funktion; den stänger **inte** incidentmiddleware och reparerar inte godtyckliga
kodfel. Detta prov har inte gjort en ny flagga-av- eller binär återgångskörning.
Tidigare dd12-bevis gäller oförändrad funktionskod, inte alla framtida driftsfel.

Om binär återgång blir nödvändig krävs kontrollerat beslut och kontroll av den
faktiskt föregående imagen mot senaste lagring. Ingen äldre databas ska läggas
tillbaka. Kandidaten ändrar inga planmodeller eller DB-schema, men det ersätter
inte driftens förkontroller. Låt färdiga revisioner, ägarbindning, skafferi och
det separata privata incidentunderlaget ligga kvar. Inga reläer, source-images,
scheman eller proxy-/säkerhetsinställningar ingår i detta appbyte.

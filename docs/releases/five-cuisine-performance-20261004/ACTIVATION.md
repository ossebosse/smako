# Kontrollerad aktivering av enbart appen

Detta är en förberedd driftanvisning, inte en genomförd produktionsaktivering.
Ingen Git-push, källinsamling, reläinstallation eller schemaändring ingår.
Slutprov och eventuella öppna begränsningar i `RESULTS.md` ska granskas innan ett
separat aktiveringsbeslut fattas. Tidigare replaybelopp är inte prisacceptans för
dagens publicerade underlag.

Tidigare godkännande för 17a9c1330dcc gäller inte denna prestandakandidat.
Ett nytt uttryckligt aktiveringsbeslut krävs. Produktionsappen och användarplanerna
är orörda i denna leverans. Läs även redovisningen av det ännu ej nådda
60-sekundersmålet i RESULTS.md.

## Låst kandidat

| Artefakt | Identitet |
| --- | --- |
| Runtime-commit | `b89fadb96c4edc4576cb4daae6c5d80e553ad8ca` |
| Serverpaket | `smako-server-b89fadb96c4e.zip` |
| Paketstorlek | `2741764` byte |
| Paketets SHA-256 | `eafba3aa7b4ab59d8fb92e258c995792caff9b9a3eb41838c3481b47142f982b` |
| Verifierad Docker image-ID | `sha256:80dd265779182eb750453e3b12a2249e71a9ed845f62c6e9c3c5f1a3a86ee4d1` |
| Verifieringens lokala imagetagg | `smako-five-cuisine-candidate:b89fadb96c4e` |
| Appens föreskrivna drift-BUILD_ID | `five-cuisine-b89fadb96c4e` |

Image-ID är den lokala innehållsadresserade imagen, inte en registrys
manifestdigest. Den ska finnas installerad via ordinarie kontrollerad
imageöverföring. Ett annat resultat från en egen ombyggnad kräver separat
imageverifiering; ersätt inte ID:t med en rörlig tagg.
Taggen ovan är ett läsbart namn; override-filen låser det verifierade image-ID:t.

Kontrollera paketet innan uppackning. Följande Bash/Python-kommandon är för en
senare operatör, inte kommandon som körts i denna leverans. Sätt
`SMAKO_PACKAGE` till den faktiskt överförda paketfilen och kör:

```sh
set -euo pipefail
python3 - "$SMAKO_PACKAGE" <<'PY'
import hashlib, json, sys, zipfile
from pathlib import Path
p = Path(sys.argv[1])
assert p.name == "smako-server-b89fadb96c4e.zip"
assert p.stat().st_size == 2741764
assert hashlib.sha256(p.read_bytes()).hexdigest() == "eafba3aa7b4ab59d8fb92e258c995792caff9b9a3eb41838c3481b47142f982b"
with zipfile.ZipFile(p) as z:
    m = json.loads(z.read("RELEASE.json"))
    assert m["commit"] == "b89fadb96c4edc4576cb4daae6c5d80e553ad8ca" and m["kind"] == "server"
    assert set(z.namelist()) == set(m["files"]) | {"RELEASE.json"}
    assert all(hashlib.sha256(z.read(n)).hexdigest() == h for n, h in m["files"].items())
print("Paket och samtliga manifestbundna filer: PASS")
PY
test "$(docker image inspect --format '{{.Id}}' sha256:80dd265779182eb750453e3b12a2249e71a9ed845f62c6e9c3c5f1a3a86ee4d1)" = \
  'sha256:80dd265779182eb750453e3b12a2249e71a9ed845f62c6e9c3c5f1a3a86ee4d1'
```

Kopiera aldrig testklocka, frysta prisfiler, testdatabaser, utvecklingens `.local`
eller `scripts/recipe_layer/serve.py` till produktionsstarten. Detta serverpaket
ger ingen anledning att installera paketet för Windows-relä.

## Bind till faktisk driftkonfiguration

Läs den nu använda driftwrappern och dess ordnade Compose-argument, projekt-ID,
arbetskatalog och miljöfiler. Historiska servervägar är inte bevis för dagens
konfiguration. Bevara hela den sammanhängande konfigurationen, inklusive
tidigare appfixar och källöverlagringar. Basfiler, miljöfiler, `current`-länkar
och globala `SMAKO_RELEASE_IMAGE`, `APP_VERSION` eller `BUILD_ID` ska inte bytas
ut med denna instruktion.

Kontrollera också att appens befintliga startkommando och eventuella mounts inte
ersätter paketets runtimekod med historiska källfiler. Om sådan överlagring finns
behövs en separat granskad anpassning; denna anvisning får bara ändra tre fält.
Alla kommandon körs i Bash med `set -euo pipefail` och stopp vid första fel.

**Använd inte `deploy/compose.release.yaml` som denna versions nya override.**
Den filen byter även image för `scheduler`, `migrate`, `refresh-once` och
`backup-once`. Om den redan ingår i driftens bas behålls dess befintliga värden.
Det historiska hotfixskriptets `stage`/`activate` är inte ett generiskt
driftsättningsverktyg för detta paket.

Den enda nya konfigurationen är [app-only.override.example.yaml](app-only.override.example.yaml).
Den anger endast `services.app.image`, `services.app.environment.BUILD_ID` och
`services.app.environment.COMPLETE_RECIPES_ENABLED`. Befintliga bygginställningar
behålls; `--no-build --pull never` gör att den verifierade imagen används.

Operatören anger följande absoluta, kontrollerade sökvägar i den privata
driftmiljön. De är avsiktligt inte gissade i denna anvisning:

- `SMAKO_COMPOSE_WRAPPER`: den faktiskt använda Compose-wrappern.
- `SMAKO_APP_OVERRIDE`: en beständig, administratörsägd fil för kopian av exemplet.
- `SMAKO_ACTIVATION_EVIDENCE`: en ny skyddad katalog för före/efter-bevis.

Konfigurationsutdata innehåller hemligheter. Använd `umask 077`; spara filerna
privat, utanför Git och publika rapporter. Spara wrapperns ursprungliga fil och
metadata där. Ta en konsistent backup av plan-/personlagringen enligt befintlig
driftordning, med oförändrade sessionshemligheter, ägarbindningar och
skafferihistorik. Dokumentera befintliga planrevisioners identiteter och
innehållshashar privat för jämförelse efter bytet.

För kommandona nedan måste wrappern vara verifierad att vidarebefordra ett extra
`-f` före Compose-kommandot utan att ersätta tidigare filer eller projektval.
Om den inte har detta kontrakt ska samma fullständiga argumentlista rekonstrueras
och granskas som en Bash-array; lägg det nya `-f` sist. Använd inte `eval` och
ersätt inte driftens argumentlista med bara repositoryts grundfil.

```sh
umask 077
: "${SMAKO_COMPOSE_WRAPPER:?ange verifierad befintlig wrapper}"
: "${SMAKO_APP_OVERRIDE:?ange beständig app-only-override}"
: "${SMAKO_ACTIVATION_EVIDENCE:?ange skyddad evidenskatalog}"
"$SMAKO_COMPOSE_WRAPPER" config --format json > "$SMAKO_ACTIVATION_EVIDENCE/config-before.json"
"$SMAKO_COMPOSE_WRAPPER" ps -a --format json > "$SMAKO_ACTIVATION_EVIDENCE/containers-before.json"
"$SMAKO_COMPOSE_WRAPPER" -f "$SMAKO_APP_OVERRIDE" config --format json > "$SMAKO_ACTIVATION_EVIDENCE/config-candidate.json"
```

Kopian av exemplet ska i denna fas ha **`COMPLETE_RECIPES_ENABLED: "false"`**.
Jämför de upplösta konfigurationerna med kontrollen nedan. Den visar inga
hemliga värden och tillåter endast de tre avsedda appfälten att ändras, inklusive
att ett tidigare saknat flaggfält läggs till. Alla andra tjänster och inställningar
måste vara identiska: volymer, portar, kommandon, miljö, scheman, kanaler,
femkällorspolicy, kommunomfattning samt 36/48-timmarsgränser.

```sh
python3 - "$SMAKO_ACTIVATION_EVIDENCE/config-before.json" \
  "$SMAKO_ACTIVATION_EVIDENCE/config-candidate.json" false <<'PY'
import copy, json, sys
from pathlib import Path
before, actual = [json.loads(Path(p).read_text()) for p in sys.argv[1:3]]
assert sys.argv[3] in {"false", "true"}
expected = copy.deepcopy(before)
app = expected["services"]["app"]
assert isinstance(app.get("environment"), dict)
app["image"] = "sha256:80dd265779182eb750453e3b12a2249e71a9ed845f62c6e9c3c5f1a3a86ee4d1"
app["environment"]["BUILD_ID"] = "five-cuisine-b89fadb96c4e"
app["environment"]["COMPLETE_RECIPES_ENABLED"] = sys.argv[3]
assert actual == expected, "STOPP: annan konfigurationsskillnad eller fel kandidat"
print("Endast avsedda appfält skiljer sig: PASS")
PY
```

Gör först därefter override-filen beständig i den ordinarie wrapperns ordnade
Compose-fillista, sist bland `-f`-argumenten och före den vidarebefordrade
användarkommandoraden. Bevara wrapperns låsning, ägare, behörigheter, arbetskatalog,
projekt-ID och övriga argument. Spara ändringen i driftens vanliga beständiga
konfiguration så att rutinmässig återskapning och senare omstart använder samma
appval; en tillfällig shellvariabel räcker inte. Läs tillbaka wrappern och kör
`config --format json` utan extra `-f`. Den upplösta JSON-strukturen ska vara
exakt lika med den granskade `config-candidate.json`. Stoppa vid annan skillnad.

## Starta först med flaggan av

Ta befintligt driftlås och använd driftens ordinarie underhållsfönster. Låt
pågående menyjobb slutföras innan appen återskapas. Oavslutade jobb finns i
processminnet och överlever inte appomstart; färdiga sparade revisioner gör det.
Ändra eller starta inga insamlings-/reläjobb som del av detta appbyte.

```sh
"$SMAKO_COMPOSE_WRAPPER" up -d --no-build --pull never --no-deps --force-recreate app
APP_CID=$("$SMAKO_COMPOSE_WRAPPER" ps -q app)
test "$(docker inspect --format '{{.Image}}' "$APP_CID")" = \
  'sha256:80dd265779182eb750453e3b12a2249e71a9ed845f62c6e9c3c5f1a3a86ee4d1'
"$SMAKO_COMPOSE_WRAPPER" exec -T app python - <<'PY'
import json, urllib.request
with urllib.request.urlopen("http://127.0.0.1:8000/ready", timeout=5) as r:
    state = json.load(r)
assert state["status"] == "ready"
assert state["build_id"] == "five-cuisine-b89fadb96c4e"
assert state["features"]["complete_recipes_enabled"] is False
print("Appens image, readiness, BUILD_ID och flagga av: PASS")
PY
```

Vänta på normal healthcheck/readiness enligt driftordningen före kontrollen.
Verifiera att alla övriga tjänsters container-ID:n, image-ID:n och upplösta
konfiguration är oförändrade. Kontrollera gammalt publikt menyflöde, personlig
15/20-planering, ägaråtkomst och återläsning av gamla planer. Jämför samtliga
befintliga planrevisioners hashvärden; nya provrevisioner får tillkomma, gamla
ska inte skrivas om. Utred readiness-/prisfel enligt deras faktiska kategori;
aktivera inte mockdata, replayklocka eller längre färskhetsgränser.

## Senare uttrycklig aktivering och återgång

Efter ett separat beslut att slå på det nya läget: ändra endast flaggan i den
beständiga app-override-filen till `"true"`. Spara upplöst konfiguration före
och efter. Kör samma JSON-jämförelse med den nya före-filen, efter-filen och
argumentet `true`; kontrollera dessutom att image och BUILD_ID är oförändrade
från fasen ovan. Återskapa endast `app` med samma `up`-kommando. Readiness ska
visa samma build och `features.complete_recipes_enabled: true`.

Kör vanliga publika och personliga knappflöden mot aktuellt publicerat underlag:
fem middagar, två portioner, matkök, 10–15 ingredienser, tids- och näringsval samt
högst två inköpsställen. Kontrollera kort start/status, återanslutning efter
omladdning, komplett recept, faktiska inköp, byte till annan grundrätt, uttrycklig
omräkning och separat ny revision. Ett konkret datastopp ska redovisas som det;
replayrapportens historiska pris är inget krav på en ny meny.

**Funktionsåtergång:** sätt flaggan till `"false"` i samma beständiga override,
jämför upplöst konfiguration och återskapa enbart appen i **samma nya image**.
Det stänger ny komplett generering utan att ta bort befintliga receptversioner,
planrevisioner eller skafferihändelser. Bekräfta flaggan, gammalt menyflöde och
återläsning av både gamla och nya revisioner med oförändrade hashvärden.
Planerade rester får fortfarande inte automatiskt bokföras som skafferi.

Ingen databasnedgradering, återställning över senare användararbete, migrerings-
engångskörning, `down -v`, bildstädning eller uppdatering av scheduler/proxy ingår.
Ett äldre binärbyte kräver separat isolerat läskompatibilitetsprov och backup;
det ersätter inte den testade flaggåtergången ovan. Bevara image, paket,
override-historik, privata verifieringsbevis och samtliga revisioner.

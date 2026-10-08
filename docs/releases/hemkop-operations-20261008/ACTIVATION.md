# Utfört källprocessbyte

Detta är ingen konsumentapprelease.

- Runtime: `ce326c1d7fcf5235e77ea4fcf2139d4fb25be849`.
- Paket: `smako-source-ops-ce326c1d7fcf.zip`, 112 750 byte.
- SHA-256: `aed0cde11e6b4cf47ae8a6b3d3078e27034c45ddeb910b11be498709e267bb44`.
- Image: `sha256:8fce7b9c72fbadc615aba9b46d2a2fec32a81dfb87231b33aae20ebca6547e3b`.
- BUILD_ID: `source-ops-ce326c1d7fcf`.
- Installerat: `/opt/smako/releases/source-ops-ce326c1d7fcf`.

Alla delta-/bashashar i SOURCE-PACKAGE.json. Reproducerbar paketering:

```powershell
.venv\Scripts\python.exe scripts\build_source_patch.py --base-commit 08c137475d9ca96a6ef7673245a639c8c5c9e922 --parent-commit 0d4c1d73605be0261bf7bf2ce4665cae8c01985d --commit ce326c1d7fcf5235e77ea4fcf2139d4fb25be849 --base-image sha256:d8a166fa7ee162cd0570f9d8089ff800e00d9c949ac3c674e387c5fff1538dd7 --base-tag smako-source-base:08c-d8a166fa7ee1 --output .local/next-reviewed-source-package
```

Kommandot paketerar, installerar inte. Verifiera basens image-ID före lokalt
nätverksfritt Dockerbygge. Hasharna inne i basimagen kontrolleras innan den
granskade deltan kopieras; ambig/ändrad bas vägras. Inga nya beroenden.

## Genomförd aktivering

Faktisk Compose-wrapper/full config lästes; väntad scheduler och dd12-app
verifierades. Under befintligt kernel-operationslås byttes endast scheduler
via `up -d --no-deps --no-build --pull never scheduler`. Upplöst diff exakt
`scheduler.image` och `scheduler.environment.BUILD_ID`. Återlästa env/mounts
och oförändrad appcontainer-ID kontrollerades innan låset släpptes.
Ingen global imagevariabel, receiver, relä, proxy, migrate eller schema ändrades.

Override `/opt/smako/overrides/source-ops-ce326c1d7fcf.yaml` ligger sist i
`/opt/smako/compose`. Föregående wrapper finns som releasens `compose-wrapper.before`.
Journal för mellanversionerna och misslyckade paketprov ligger skyddat på D:.
Slutlig återläst identitet finns i ACTIVATION.json. Installera inte om när rätt
image redan körs. Endast källprocessens två fält ändrades även i mellanbytena.

## Avgränsad återgång vid nytt diagnosfel

Vänta ut aktiva källjobb och ta befintligt lås. Den bevarade källruntime
`08f7613a50c9`, image
`sha256:0c3b048c29e4f8e27847f4bbdc5d0a40628f622c0f26f6f14c839dc54d717b6c`,
innehåller båda nödvändiga schema-/byggfixarna utan nya diagnoskrokar.
Den har faktiskt byggt och publicerat det aktuella underlaget. En återgång
måste granska full diff till samma två schedulerfält och använda samma låsta
driftväg. Ingen automatisk återgång utförd eller testad här.

Bevara senaste DB, råarkiv, manifest, kvitton och app. Återställ ingen äldre
DB. Incidentindex är härlett administrativt underlag, ingen användardatamigration.
Återgå inte till äldre schema-/byggfel. Konsumentappens flagga-av är inte
källfixens återgång och konsumentappen ingår inte i denna aktivering.

# Reproducerbart Coop-kandidatpaket – inte produktionsaktivering

- Slutimage: `smako-coop-candidate:nutrition-20260922`, ID `sha256:3459fc115dbf4cbac006f8d1b6e654c397f12661735de190420620fc86a036d5`.
- Befintlig verifierad browserbas: `sha256:4fdaeeda6c1db2c0125a15bfc964cc57a2134154a4546a6c02a6d5d03208fdd5` (`smako-ica-shadow:20260915`). Detta är återanvändning av den redan fungerande transportmiljön, inte aktivering av det väntande ICA-paketet.
- Export på servern: `/tmp/smako-coop-nutrition-20260922/coop-candidate-image.tar`, 546 672 640 byte, SHA256 `2d8b05f0e469dc7828d78f64cdda678cf9a5c63c2815b1470d1e365addde6720`. Arkivet är läsbart endast för ägaren. Det innehåller image-lagren och behöver ingen ny browsernedladdning. Inga runtimehemligheter exporteras.
- Python och fullständiga kodhashar: `package-result.json`. Playwright 1.58.0, Pydantic 2.13.4, SQLAlchemy 2.0.51, HTTPX 0.28.1. Chromium/browserbibliotek är bundna i basimagen; ingen ny installation har gjorts i produktion.
- Köranvändare 10001:10001. Browserns sökväg ligger i `package-result.json`. En tidig uppmätt resurskontroll under kandidatbygge visade 298 MiB, inte ett uppmätt maxvärde. Alla provcontainer har gräns 2 CPU/5 GiB, skrivskyddad rot och /tmp på högst 512 MiB.

## Bygg och avgränsad körning

Från denna arbetskopia i PowerShell, med befintlig SSH-konfiguration för `smako`:

```powershell
py -3.12 reports/coop-nutrition-20260922/remote.py stage
py -3.12 reports/coop-nutrition-20260922/remote.py build
py -3.12 reports/coop-nutrition-20260922/package_inventory.py
```

`stage` kopierar endast till den ägarmärkta privata `/tmp`-katalogen, aldrig till aktiv app. `build` använder den lokala, hashidentifierade browserbasen och `docker build --network none`. Byggfil: `deploy/coop-candidate.Dockerfile`. Slutimagen är fryst i arkivet ovan. Kopiering av den här arbetskopian till produktion är inte ett releasekommando.

Direkt kandidatkörning på avsedd Linuxserver (ny unik outputkatalog krävs; föräldern `/tmp/smako-coop-nutrition-20260922/data` är redan avgränsad till användare 10001):

```sh
docker run --rm --read-only --user 10001:10001 --cpus 2 --memory 5g   --tmpfs /tmp:rw,size=512m,mode=1777 --network bridge   --mount type=bind,source=/tmp/smako-coop-nutrition-20260922/evaluation/inventory.json,target=/input/inventory.json,readonly   --mount type=bind,source=/tmp/smako-coop-nutrition-20260922/data,target=/work   --mount type=bind,source=/srv/smako/data/grocery,target=/srv/app/var/grocery,readonly   --mount type=bind,source=/srv/smako/data/price_universes,target=/srv/app/var/price_universes,readonly   --mount type=bind,source=/srv/smako/data/price_universes/.refresh-locks,target=/srv/app/var/price_universes/.refresh-locks   sha256:3459fc115dbf4cbac006f8d1b6e654c397f12661735de190420620fc86a036d5   --enabled --inventory /input/inventory.json --output /work/coop-next-unique-run   --operation-database /srv/app/var/grocery/grocery_data.sqlite   --operation-universe-root /srv/app/var/price_universes
```

Inga hemligheter behövs för den publika Coop-transporten. Upprepa inte samma outputnamn: befintlig evidens får inte skrivas över. `--store-id 3659` begränsar ett prov; utan `--store-id` används alla godkända fysiska Coop-ID:n i kommuninventeringen. X:-tra och okända kommunbutiker nekas. Output innehåller sources/raw, isolerad OWN och coverage.json. Misslyckade butiker står kvar; exitkod 1 vid någon misslyckad butik, ingen automatisk aktivering. Operationslåset är samma som befintliga refreshjobb. Låskatalogen är den enda skrivbara produktionsrelaterade monteringen.

Den faktiskt genomförda serverkörningen använde samma entrypoint genom `job.py collect-package` / `collect-package-smoke`, med schedulerprocessens befintliga miljö över privat stdin. Produktionsmiljön eller uppgiften ändrades inte. Applikationskod lästes ur imagen, inte från monterad utvecklarkatalog. För reproduktion av just genomförda HTTP-prov används `remote.py build-baseline`, `build-coop`, `baseline-acceptance`, `coop-acceptance`, `recipe-proofs`, `publication`, `retrieve`. Förnya körkatalogen vid omprov: freeze/insamling/publication nekar återanvändning där den kan skriva över evidens. Båda armarnas underlag måste frysas tillsammans; kör inte gamla artefakter efter färskhetsstoppet.

Ingen daemon, port, scheduler, Windows-uppgift eller produktionspublicering ingår i denna image-entrypoint. Framtida integration ska läsa kandidatutdata och använda befintlig validering/publiceringslåsning. De två redan implementerade byggargumenten är `coop_offer_database` och `coop_municipality_inventory` på `build_city_price_universe`; fel i det frivilliga tillskottet får behålla giltig bas. Det slutliga aktiveringsjobbet ska dessutom kräva explicit kontroll av rapportens Coop-status så att basfallback inte redovisas som lyckad Coop-aktivering.

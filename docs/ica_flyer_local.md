# Lokal reklambladstolkning via Ollama

Det lokala alternativet ansluter till samma `smako-public-flyer-page-v1` som
Responses-adaptern. Ingen API-nyckel, betald fallback eller alternativ prisdatabas.
OpenAI-adaptern finns kvar. Produktionskonfigurationen är oförändrad.

## Beroenden och modell

Python 3.12 och befintliga httpx/Pydantic/pypdf/PyMuPDF används. Inget nytt
Pythonpaket behövs utöver `grocery_data/requirements-flyer-vision.txt`.
Separat modellserver: Ollama **0.34.2**, MIT; lokala vikter
**qwen3-vl:4b-instruct**, Q4_K_M, cirka 3,3 GB, Apache-2.0. 8B är tillåtet
i adaptern men ska endast väljas efter en ny resursprövning. Inget automatiskt
modellbyte eller nedladdning sker i adaptern.

Officiella källor kontrollerade 20 september 2026:
[4B-vikter/licens](https://ollama.com/library/qwen3-vl:4b-instruct),
[Ollama-licens](https://github.com/ollama/ollama/blob/main/LICENSE),
[0.34.2](https://github.com/ollama/ollama/releases/tag/v0.34.2),
[CPU i Docker](https://docs.ollama.com/docker),
[GPU-krav](https://docs.ollama.com/gpu),
[bilder](https://docs.ollama.com/capabilities/vision),
[JSON-schema](https://docs.ollama.com/capabilities/structured-outputs),
[chat-API](https://docs.ollama.com/api/chat),
[lokalt/cloud-avstängning](https://docs.ollama.com/faq).

## Konfiguration och körning

| Variabel | Värde/roll |
|---|---|
| `ICA_FLYER_VISUAL_COMMAND_JSON` | `["python","-m","grocery_data.scripts.ica_flyer_ollama"]` |
| `ICA_FLYER_SOURCE_ROOT` | Tillåten rot för offentliga original-PDF:er |
| `ICA_FLYER_LOCAL_CACHE` | Isolerad innehållscache och råa modellsvar |
| `ICA_FLYER_OLLAMA_URL` | `http://127.0.0.1:11434`; endast bokstavlig loopback-IP accepteras |
| `ICA_FLYER_LOCAL_MODEL` | `qwen3-vl:4b-instruct` som standard |
| `ICA_FLYER_LOCAL_THREADS` | 2 som standard, högst 4; komplettera alltid med OS-resursgränser |
| `ICA_FLYER_LOCAL_CONTEXT` | 8192 token som standard |
| `ICA_FLYER_LOCAL_OUTPUT_TOKENS` | 4096 som standard |
| `ICA_FLYER_LOCAL_TIMEOUT_SECONDS` | 900 per modellpass; tillåtet 30–1800 |
| `ICA_FLYER_VISUAL_TIMEOUT_SECONDS` | Yttre processgräns, standard 240; exempel 1900 för två lokala 900-sekunderspass |
| `ICA_FLYER_LOCAL_VERIFY` | `true` normalt; `false` är ett extraktionsprov som uttryckligen spärrar köpimport |

Worker: `python -m grocery_data.scripts.ica_flyer_ollama < request.json`.
Processen läser verklig PDF och kontrollerar hash/sida/observation. Exempel på
request finns i sidresultaten i [det faktiska provet](../reports/ica-flyer-local-20260920/README.md).

Modellservern måste redan innehålla vikterna. Adaptern kontrollerar exakt
modellnamn, digest och bildkapabilitet före generering. Cloud-metadata stoppas.
HTTP-proxy från miljövariabler och omdirigeringar används inte.

Seriell batch använder nu samma kommandoinställning, alternativt en argv-fil
med `--visual-command-json`. Välj en **ny outputkatalog** och explicit
`--worker-revision` vid ändrad modell, vikter, prompt eller rendering:

```sh
python -m grocery_data.scripts.ica_flyer_vision_batch \
  --coverage /sources/coverage.json --source-root /sources \
  --output /results/new-batch --visual-command-json /config/local-command.json \
  --worker-revision ollama-qwen3vl-4b-v1 \
  --operation-database /isolated/own.sqlite --price-universe-root /isolated/universes
```

Detta är extraktion, inte aktivering. Samma cache kan sedan användas av den
befintliga collectorn och dess review → SourceOffer → OWN → PriceUniverse-kedja.
För det lokala pilotutfallet ska ingen sådan import antas vara godkänd.

## Bevis, cache och kvalitetsgräns

Gemensam rendering ger helsida, fyra överlappande utsnitt och första/sista
sidans villkorskontext. Lokalt förstapass använder endast målsidans helbild med
1280 pixlars längsta kant. Kontrollpasset behåller kontextsidor och utsnitt, 1024 pixlar
per bild. Dokumenttext används där den finns. Källans butik, hash och verkliga
observation skickas inte till modellen som fält att hitta på; programmet binder
dem efteråt. Dokumentinstruktioner är data.

Cachen omfattar faktiska bildbytes, dokumenttext, villkorskontext, schema,
prompt, version, vikt-digest och modellinställningar. Oförändrat underlag kan
återanvändas utan nya modellanrop. Ändrad butikskoppling återbinds endast till
den koppling som inventory redan belagt. Ny tolkning föryngrar aldrig en
prisobservation. Batchen skiljer även olika villkorskontexter för samma PDF.

Modellens JSON valideras i samma schema och prisvalidering som tidigare.
Kilopris/flerköp och okända GTIN/pant/mängder får bevaras som extraherade uppgifter,
utan att bli godkända köp. Ingen sänkt kvalitetsgräns eller ändrad nämnare.
En separat bildkontroll ersätter inte en oberoende pilotjämförelse mot original.
`VERIFY=false` lägger alltid in en gemensam blockerare; tom modellista med
osäkerheter kan inte ta bort den. Råa avslutade modellsvar och token/tidsmått
sparas även om schema eller slutstatus underkänns. Felaktiga modellsträngar
`"null"` bevaras i råsvaret men behandlas som saknade uppgifter med synlig
radspärr. De får inte skapa GTIN eller klassificera prisannonser som irrelevanta.

Ett request kan innehålla `focus_bbox: [vänster, topp, höger, botten]` i 0..1
för ett avgränsat diagnostiskt utsnitt. Programmet renderar original-PDF:en
vid 240 dpi och för tillbaka modellens koordinater till originalsidan. Ett
sådant svar markeras alltid `partial_page_focus_only`; det är aldrig bevis för
en fullständigt extraherad sida. Villkor utanför utsnittet förblir oklara tills
de faktiskt kontrollerats. Modellens egna felaktiga rektanglar korrigeras inte
genom gissning. Original, hash, butik och observation är oförändrade.

## Resursisolering

Septemberprovet kör på befintlig server med CPU, 2 kärnor, 6 GiB modellminne,
ingen swap, låg CPU-vikt/nice 19. Klienten har 1 CPU/1 GiB. Modellen kör med
`--network none`, loopback, inga publicerade portar, skrivskyddade modellvikter,
`OLLAMA_NO_CLOUD=1`, parallellitet 1, ingen restart-policy. Klienten delar bara
modellens isolerade nätverksnamespace. Produktionsdata är skrivskyddad input.

API-anropen använder `keep_alive=0`, enligt Ollamas dokumenterade beteende,
för att frigöra modellens arbetsminne efter varje pass. Det tillkom efter
provet med kvarhållet minne mellan sidor, som nådde testcontainerns 6 GiB-gräns.
Modellvikter och innehållscache på disk behöver inte hämtas eller
tolkas om. Timeout eller lokal HTTP-felkod rapporteras utan extern fallback.

En tillfällig övervakare samplar cgroup-minne/CPU och ledigt värdminne varannan
sekund. Den pausar endast testmodellen vid beta/scheduler över 0,30 CPU-kärna
och återupptar efter 20 lugna sekunder. Vid mindre än 4 GiB tillgängligt RAM
stoppas testmodellen för att frigöra minnet; en paus skulle behålla RAM.
Detta är ett tillfälligt testskydd, ingen ny driftsättning eller schemaläggning.
Resursmätning är inte bevis för flerdagarsstabilitet eller oförändrad svarstid.

# Kommun-Coop: kontrollerad 15/20, 22 september 2026

Läs RELEASE-COOP.md för beslut, PROFILE.md för kostnad/valda produkter och
COVERAGE.md för butiksvis bortfall. Allt nytillkommet är isolerat testarbete.

## Databas och källa

Den kompletta serverdatabasen och den validerade aktiva Primat-cachen frystes
08:32:48 Europe/Stockholm under befintligt gemensamt driftlås. Det är de
ordinarie senaste lyckade nätinsamlingarnas källdata, inte betans begränsade
sökprojektion. Vi gjorde inte en extra full bashämtning under denna etapp:
underlaget var redan färskt, högst cirka 30 timmar, under varningsgränsen 36 h.
Coop Online är från 21 september; Willys, Hemköp och Primat från 22 september.
Frysning, källsnapshot-ID:n och verkliga observationer finns i
server-results/base-final/frozen-base-manifest.json. Fullbasen innehåller
36 867 råprodukter; B innehåller 37 360. Inga observationer har föryngrats.

Coop hämtades faktiskt på nytt från varje officiell butik på servern
08:39:02–08:39:38, i den redan installerade browsermiljön. Käll-ID, hash,
observationsklocka, kvalitet och karantän finns i
server-results/browser/coop-live/coverage.json. Originalråsvar/OWN finns i
serverns privata testkatalog, inte i produktionen. En separat lokal
Windows-kontroll lyckades också; den används inte som serverarmens källa.

## Kod och reproduktion

Gren areas/municipality-audit-20260920, HEAD 02ad73b8491f4b30679b3151b52686e27bedb8e6
med tidigare ocommittat arbete bevarat. incremental.patch visar endast nya
applikationstillägg mot sparad smutsig bas; review-files.tar.gz är granskningsmaterial,
inte ett produktionspaket. Ingen commit/checkout/reset/deploy utförd.

Kör med Python 3.12, från projektroten, PYTHONPATH=backend;. och SSH-alias smako.
Relevanta genomförda kommandon:

```powershell
py -3.12 reports/coop-1520-20260922/remote.py stage
py -3.12 reports/coop-1520-20260922/remote.py freeze
py -3.12 reports/coop-1520-20260922/remote.py collect-browser
py -3.12 reports/coop-1520-20260922/remote.py baseline-acceptance
py -3.12 reports/coop-1520-20260922/remote.py coop-acceptance
py -3.12 reports/coop-1520-20260922/remote.py publication
py -3.12 reports/coop-1520-20260922/remote.py retrieve
py -3.12 reports/coop-1520-20260922/build_report.py
```

Detta är ordningsberoende engångssteg: freeze/collect-browser/publication vägrar
skriva över redan frysta provmappar. För en ny färsk körning, kopiera rapportens
körskript till en ny rapportmapp och välj ett nytt RUN/STAGE i remote.py först;
återanvänd inte gammalt material som nyinsamlat. Befintliga sparade JSON-resultat
kan rapporteras igen med build_report.py utan nätanrop. Alla prisbyggen utgår
från fulla källor. B läser A:s sparade receptpool som jämförelseindata; inget
pris- eller näringsresultat återspelas.

Containers: read-only, UID 10001, nät av vid bygg/planering, högst 2 CPU/5 GiB,
privat /work. Produktionens källor är read-only; endast det vanliga låsets
katalog delas skrivbart. Ordinarie app observerades omkring 0,2 % CPU under
provet. Ingen installation, bildmodell, OCR eller betalt API.

141 fokuserade regressioner passerade på 14,578 s, tests.xml. Ruff och compileall
passerade för de ändrade applikationsfilerna och nya testerna. A/B:s backendkod-
hashar är identiska; testinstrumenteringen för B fryser recept och loggar audit.

Första fulla provet visade att erbjudanden påverkar generatorns ekonomiska
signaler. Det sparas som pilot; slutlig acceptans använder samma 106 recept i
båda armarna. Ingen användarprofil eller tidigare sparad plan ändras.

En första fryst B-körning genomförde planeringen men rapportens extra
prisjämförelse försökte läsa ett ej berättigat enstyckskontrakt utanför sin
felhantering. Endast diagnostikskriptet rättades; hela B-bygg/HTTP-körningen
kördes om. Den slutliga jämförelsen använder enbart färdiga PASS-resultat.

## Exakta basobservationer (UTC)

| Källa | Första–sista prisobservation | Användning |
|---|---|---|
| Coop Online 730400 | 21/9 01:17:55–01:45:15 | Samma kompletta bas i A/B |
| Willys | 21/9 23:31:28–23:59:40 | Samma kompletta bas i A/B; 22/9 svensk tid |
| Hemköp 4224 | 22/9 01:55:34–02:06:35 | Samma kompletta bas i A/B |
| Primat | Cache infångad 22/9 02:07:24 | Två källkontexter; 1 876 produkter |
| Hemköp 4123 | 8/9 | För gammal, exkluderad |

Detaljer och oförändrade snapshot-ID:n: source-observations.json. Created_at,
promotionstid och prisobservation är separata fält; ny promotion betyder inte
ny prisobservation. Den befintliga exakta ICA-kopplingen i basens identity bridge
är identisk i båda armarna; ingen del av det väntande nya ICA-paketet aktiveras.

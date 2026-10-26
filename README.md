# Smako

Svensk måltidsplanering med recept, näringsval, skafferi och gemensam
inköpsoptimering utifrån verifierade matvarupriser.

Produktmålet är kompletta recept och billigast möjliga giltiga inköpslista
inom **30–60 sekunder**, även för nya kombinationer av användarval och med
tusentals recept. Detta är målbilden, inte en redan verifierad tidsutfästelse.
Läs [produktmål och hela valkatalogen](docs/PRODUCT-GOAL.md) samt
[planeringsarkitekturen](docs/PLANNING-ARCHITECTURE.md).

**`main` är huvudgren och utgångspunkt för utveckling och nya betareleaser.**
En vanlig kloning från GitHub hämtar den. Push till `main` startar ingen
automatisk deployment; betan aktiveras med det dokumenterade releaseflödet.

## Kom igång

Kräver Git och Python **3.12**. PowerShell på Windows:

```powershell
git clone https://github.com/ossebosse/smako.git
Set-Location smako
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv/Scripts/python.exe scripts/dev.py --reload
```

Öppna **http://127.0.0.1:8000/personal**. Hjälparen migrerar en separat lokal
databas under `.local/dev` och startar UI/API med mockpriser. Fullständig
planering med riktiga butiker kräver ett separat prisunderlag; se utvecklingsguiden.
På Linux/macOS används `python3.12` och `.venv/bin/python`.

- **[Utveckling: start, tester, riktiga prisunderlag och bidrag](docs/DEVELOPMENT.md)**
- **[Aktivera en granskad commit från main på betan](docs/BETA.md)**
- [Medlemskap, gästgränser och kontoskafferi](docs/MEMBERSHIP.md)
- [Aktiv betaversion och kommande arbete](docs/HANDOFF.md)
- [Nästa Sol-uppdrag: kvarstående receptfel, veckosökning och cache](docs/CODEX-SOL-NEXT-20261026-WEEK-SEARCH.md)
- [Driftstatus och felsökning](docs/OPERATIONS.md)
- [Projektregler](AGENTS.md)

Backend och levererade webbassets ligger i `backend/app`, källinsamling och
datamodeller i `grocery_data`, streckkodsläsarens byggkällor i
`frontend/barcode-scanner`. `scripts` innehåller utvecklings-/releaseverktyg
och `deploy` server-/reläkonfiguration.

Hemligheter, driftdatabaser, användarprofiler och stora privata testunderlag
ingår inte i Git. SSH-behörighet och skyddade data tillhandahålls separat.
Historiska grenar och [konsolideringsunderlag](docs/CONSOLIDATION.md) är bevarade.

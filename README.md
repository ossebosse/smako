# Smako

Permanent utvecklingsrot: **`D:\Projects\Smako`**. Huvudgren: **`master`**.
Detta repository samlar den verifierade lokala v5-implementationen och återfunnet
äldre arbete. Det är ingen produktionsrelease.

- [Aktuell handoff](docs/HANDOFF.md)
- [Start, beroenden, tester och dataåterställning](docs/DEVELOPMENT.md)
- [Konsolidering, ursprung och säkerhetskopia](docs/CONSOLIDATION.md)
- [Verifieringsresultat och kända basfel](docs/consolidation/VERIFICATION.md)
- [Projektregler](AGENTS.md)

Backend ligger i `backend`, källinsamling och datamodeller i `grocery_data`,
streckkodsläsarens byggkällor i `frontend/barcode-scanner`, driftverktyg i `deploy`
och lokala hjälpskript i `scripts`. Bevara denna struktur.

Hemligheter, driftdatabaser och användarprofiler ingår inte i nya commits.
Historiskt testunderlag återställs från separat backup med hashkontroll.
Gamla datum-mappar ska vara kvar tills separat städning uttryckligen godkänts.

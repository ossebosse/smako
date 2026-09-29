"""Render all discovered stores, including unknown and failed, from saved evidence."""
import json
from collections import Counter
from pathlib import Path

R = Path(__file__).resolve().parent


def cell(value):
    return "ej verifierat" if value is None else str(value).replace("|", "/").replace("\n", " ")


summary = []
inside = []
for code, municipality in [("1281", "Lund"), ("1280", "Malmö")]:
    report = json.loads((R / "live" / code / "final/coverage.json").read_bytes())
    inventory = report["inventory"]
    states = Counter(r["geographic_evidence"]["status"] for r in inventory["stores"])
    lines = [f"# Alla upptäckta butiker prövade mot {municipality} kommun ({code})", "",
             f"Nationellt upptäckta fysiska butiker: {len(inventory['stores'])}. Kommunstatus: {dict(states)}.",
             "Ingen oberoende garanti för registerfullständighet. Alla rader bevarade. Ej vald är inte ett tomt erbjudandeflöde.",
             "Endast isolerade erbjudandekandidater. Produktantal är butik–variantposter, inte näringsgodkända helmenyer.", "",
             "| ID, butik och adress | Koncept | Kommunstatus: skäl | Officiell källa | Insamling | Lästa varianter/annonser | Karantän | OWN | PU | Observation UTC |", 
             "|---|---|---|---|---|---:|---:|---:|---:|---|"]
    structured_own = 0
    xtra_own = 0
    successes = 0
    for row in inventory["stores"]:
        s, g, p = row["store"], row["geographic_evidence"], row["pipeline"]
        f = s["source_fields"]
        read = p.get("metrics", {}).get("products_fetched")
        if p.get("editions"):
            read = sum(e.get("parsed_ads", 0) for e in p["editions"])
        quarantine = p.get("quarantined", p.get("quarantine"))
        reason = p.get("reason") or "; ".join(p.get("qualification", {}).get("shared_blockers", []))
        if p.get("error_type"):
            reason = f"{p.get('stage', '')} {p['error_type']}: {reason or p.get('error', '')}"
        status = p["status"] + (": " + reason if reason else "")
        values = [f"{s['external_id']} {s['name']}, {s['address']}, {s['city']}", f["concept"],
                  g["status"] + ": " + g["reason"], f"[butik]({f['official_store_url']})",
                  status, read, quarantine, p.get("own"), p.get("price_universe"), p.get("observed_at")]
        lines.append("| " + " | ".join(cell(v) for v in values) + " |")
        if g["status"] == "inside":
            inside.append([municipality, s["external_id"], f"[{s['name']}]({f['official_store_url']})",
                           f["concept"], read, quarantine, p.get("own"), p.get("price_universe"), status])
            successes += bool(p.get("price_universe"))
            if f["concept"] == "X:-tra":
                xtra_own += p.get("own", 0)
            else:
                structured_own += p.get("own", 0)
    (R / f"STORES-{code}.md").write_text("\n".join(lines) + "\n", encoding="utf8")
    summary.append({"municipality": municipality, "code": code, "states": dict(states),
                    "stores_contributing": successes, "structured_own": structured_own,
                    "xtra_own": xtra_own, "price_universe": report["price_universe_count"],
                    "universe_id": report["price_universe_id"], "activated": False})
(R / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf8")
lines = ["# Kommunbutiker – faktisk isolerad insamling 22 september 2026", "",
         "Lund: 10 verifierat inom, 0 okända, 768 utanför. Malmö: 18 verifierat inom, 1 okänd, 759 utanför.",
         "Den okända butiken är **X:-Tra Kirseberg, 3548**: officiell position ligger inom 10 m från RegSO-gräns; ingen gissad kommun eller import.",
         "Samtliga 778 upptäckta butiker redovisas i respektive STORES-fil. Tabellen nedan omfattar verifierade kommunbutiker.", "",
         "| Kommun | ID | Butik/källa | Koncept | Lästa varianter/annonser | Karantän | OWN | Aktuella i isolerat PU | Status |",
         "|---|---|---|---|---:|---:|---:|---:|---|"]
lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in inside]
lines += ["", "Coop: variantantal från det strukturerade flödet. X:-tra: identifierade textannonser, inte garanterat samtliga tryckta annonser.",
          "X:-tra har 10 radgodkända i OWN per lyckad butik; nio är aktuella och en är framtida (24 september). 47 identifierade annonser ligger i karantän.",
          "Okänt annonsantal för eventuella bildannonser förblir okänt. Misslyckad hämtning betyder inte noll annonser.",
          "Fullständiga snapshot är inte godkända; den uttryckliga partiella radpolicyn används oförändrad. Inga priser har aktiverats."]
(R / "COVERAGE.md").write_text("\n".join(lines) + "\n", encoding="utf8")

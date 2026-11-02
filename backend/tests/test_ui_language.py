"""Stop internal planning vocabulary from returning to the consumer UI.

See docs/UI-LANGUAGE.md. The scan covers string literals in the scripts that
/personal loads and the visible text in personal.html. Server messages are
covered by their own tests. Add a word here only together with the guide.
"""

from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"
FILES = (
    "personal.html",
    "personal.js",
    "complete-recipes.js",
    "plan-progress.js",
    "product-search.js",
    "shopping-location.js",
    "choice-controls.js",
    "configurator.js",
)

# Word stem -> what to write instead (also listed in docs/UI-LANGUAGE.md).
BANNED = {
    r"underlag": "uppgifter, priser, varor",
    r"verifier": "kontrollerad, bekräftad, eller inget alls",
    r"priskontext|\bkontext": "butik, nätbutik",
    r"\bkorg(en|ar|arna)?\b": "inköpslista, inköp",
    r"tillfälle": "måltid",
    r"planeraren": "Smako",
    r"spårbar": "uppskattad",
    r"identitet": "produkt, vara",
    r"bokför": "registrera",
    r"hårda? (krav|val)": "något du har valt bort",
    r"\bogiltig|\bgiltig": "fungerar inte, stämmer inte",
    r"sökbudget|delsteg|delberäkning": "(beskriv vad användaren kan göra)",
    r"kvalificera": "kontrollera",
    r"disponib": "finns kvar",
    r"tillämp": "använd, gäller",
    r"revision": "version",
}

STRING = re.compile(r'"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'|`(?:[^`\\]|\\.)*`')
TAG = re.compile(r"<script.*?</script>|<style.*?</style>|<[^>]+>", re.S)
ATTR = re.compile(r'(?:placeholder|aria-label|title|alt)="([^"]*)"')


def visible_text(name: str) -> str:
    source = (STATIC / name).read_text(encoding="utf-8")
    if name.endswith(".html"):
        return "\n".join([TAG.sub("\n", source), *ATTR.findall(source)])
    literals = (m.group(0) for m in STRING.finditer(source))
    return "\n".join(re.sub(r"\$\{[^}]*\}", " ", s) for s in literals)


def test_consumer_copy_avoids_internal_vocabulary():
    found = []
    for name in FILES:
        text = visible_text(name)
        for line in text.splitlines():
            if not re.search(r"[A-Za-zÅÄÖåäö]{3} [A-Za-zÅÄÖåäö]", line):
                continue
            for pattern, instead in BANNED.items():
                hit = re.search(pattern, line, re.I)
                if hit:
                    found.append(f"{name}: '{hit.group(0)}' → skriv {instead}: {line.strip()[:120]}")
    assert not found, "Interna ord i användartext (se docs/UI-LANGUAGE.md):\n" + "\n".join(found)

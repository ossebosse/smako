"""Plain raw staples under common shelf spellings keep their identity (2026-11-07).

Only the label grammar widens. Composite, cooked, smoked, canned and other
foods stay rejected, and every quantity/price gate still runs afterwards.
"""
from types import SimpleNamespace

import pytest
from app.services.complete_recipes import _whole_food_identity


def item(name, category):
    return SimpleNamespace(name=name, brand=None, category=category, purchase_terms=None)


@pytest.mark.parametrize("canonical,name,category", [
    ("lax", "Laxfilè C-Trim", "Fisk & skaldjur > Fisk > Färsk fisk"),
    ("lax", "Laxfilé i Bit", "Fisk & skaldjur > Fisk > Färsk fisk"),
    ("lax", "Lax Back Loin 1/2", "Fisk & Skaldjur > Fisk > Kyld fisk"),
    ("lax", "Laxfilé Hel Sida", "Fisk & Skaldjur > Fisk > Kyld fisk"),
    ("lax", "Lax Grytbitar", "Fisk & Skaldjur > Fisk > Kyld fisk"),
    ("fisk", "Ryggfilè Kolja", "Fryst > Fisk & skaldjur > Fisk"),
    ("fisk", "Torskryggfilé", "Fisk & skaldjur"),
    ("kyckling", "Bröstfilé Majskyckling", "Kött, fågel & chark"),
    ("kyckling", "Finstrimlad Kycklingbröstfilé", "Kött & fågel > Kyckling & fågel, färsk"),
    ("kyckling", "Innerfilé av Svensk Kyckling Fryst", "Kött, chark & fågel > Fågel > Fryst fågel"),
    ("nötfärs", "Nötfärs 10-12% Sverige", "Kött, fågel & chark"),
    ("nötfärs", "Nötfärs 20% Irland", "Kött, chark & fågel > Kött > Köttfärs"),
    ("tomat", "Cocktailtomat Kvist Klass 1", "Frukt & Grönt > Grönsaker > Tomater"),
    ("tomat", "Babyplommon- tomater", "Frukt & grönt"),
    ("tomat", "Kvisttomat Import Klass 1", "Frukt & Grönt > Grönsaker > Tomater"),
    ("potatis", "Bakpotatis Klass 1", "Frukt & grönt > Potatis & rotsaker > Potatis"),
    ("potatis", "Potatis Mandel Klass 1", "Frukt & grönt > Potatis & rotsaker > Potatis"),
    ("potatis", "Potatis i lösvikt", "Frukt & Grönt"),
    ("gul lök", "Lök Gul i Säck Klass 1", "Frukt & grönt > Potatis & rotsaker > Lök"),
])
def test_plain_raw_staple_spellings_are_accepted(canonical, name, category):
    assert _whole_food_identity(canonical, "raw_edible", item(name, category), None)


@pytest.mark.parametrize("canonical,name,category", [
    ("lax", "Kallrökt Lax Skivad", "Fisk & skaldjur > Fisk > Rökt & gravat"),
    ("lax", "Lax Pokétärning", "Fisk & skaldjur > Fisk > Rökt & gravat"),
    ("lax", "Laxburgare med Fetaost", "Fisk & skaldjur"),
    ("fisk", "Fiskfilè Sprödbakad", "Fryst > Fisk & skaldjur > Panerad"),
    ("fisk", "Laxfilé", "Djupfryst"),
    ("kyckling", "Kycklingbröst Filé Citron Vitlök", "Kött & fågel > Kyckling & fågel, färsk"),
    ("kyckling", "Kalkon Bröstfilé", "Kött, chark & fågel > Fågel > Färsk fågel"),
    ("nötfärs", "Fläsk & Nötfärs 70/30", "Kött, chark & fågel > Kött > Köttfärs"),
    ("nötfärs", "Burek Nötfärs", "Färdigmat > Flerportionsrätter"),
    ("tomat", "Krossade Tomater Vitlök", "Skafferi > Konserver & burkar > Tomatkonserver"),
    ("tomat", "Körsbärstomat", "Skafferi > Konserver & burkar > Tomatkonserver"),
    ("tomat", "Feta & Soltorkad Tomat", "Mejeri > Matlagningsmejeri > Creme fraiche"),
    ("potatis", "Kroketter Potatis", "Fryst > Potatis > Klyftpotatis mm"),
    ("potatis", "Potatis Hel", "Skafferi > Konserver & burkar > Grönsakskonserver"),
    ("gul lök", "Lök Röd Klass 1", "Frukt & grönt > Potatis & rotsaker > Lök"),
    ("gul lök", "Lök Granulerad", "Skafferi > Kryddor & smaksättare > Kryddor"),
])
def test_composite_processed_or_other_foods_stay_rejected(canonical, name, category):
    assert not _whole_food_identity(canonical, "raw_edible", item(name, category), None)


def test_salted_or_marinated_composition_still_rejects_a_plain_label():
    fact = SimpleNamespace(ingredients=["laxfilé", "salt", "socker"])
    assert not _whole_food_identity("lax", "raw_edible", item("Laxfilé i Bit", "Fisk & skaldjur"), fact)

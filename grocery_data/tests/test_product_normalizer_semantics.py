from datetime import UTC, datetime
from decimal import Decimal

import pytest

from grocery_data.app.domain import Chain, Confidence, SourceProduct
from grocery_data.app.domain.recipe import RECIPE_RELEVANT_CANONICAL_FOODS
from grocery_data.app.normalization import ProductNormalizer
from grocery_data.app.normalization.products import _FOOD_IDENTITIES


def _source(
    name: str,
    *,
    brand: str | None = None,
    categories: tuple[str, ...] = (),
) -> SourceProduct:
    return SourceProduct(
        chain=Chain.WILLYS,
        store_external_id="2354",
        external_product_id=name,
        name=name,
        brand=brand,
        category_path=categories,
        sale_price=Decimal(10),
        sale_unit="st",
        package_quantity=Decimal(500),
        package_unit="g",
        basket_type="ST",
        raw_reference=f"raw:test#{name}",
        fetched_at=datetime(2026, 8, 21, tzinfo=UTC),
    )


@pytest.mark.parametrize(
    ("name", "brand", "categories"),
    [
        ("Adult Kyckling-potatis Torrfoder Hund", "Primadog", ()),
        ("Chicken Heart Kycklinghjärta Naturals Hundgodis", None, ()),
        ("Kycklingfilé med potatis", None, ("Djur", "Hund", "Foder")),
        ("Majssnack Morot Från 10 Månader", "Minstingen", ()),
        ("Potatissallad Vitlök", None, ()),
        ("Vitlöksbaguett Fryst/2-pack", None, ()),
        ("Linssoppa", None, ()),
        ("Catmilk Kattmjölk 3-pack", None, ()),
        ("Arrabbiata Pastasås", None, ()),
        ("Kycklingbröst Basilikasås", None, ()),
        ("Morötter Ärter Tärnade", None, ()),
        ("Cambozola Vitlök", None, ()),
        ("Vitlökspress", None, ()),
        ("Gröna Linser Cannellinibönor Indian Style Soppa", None, ()),
        ("Bouchée Elefant Mjölk", None, ()),
        ("Mellanrost Perfekt med Mjölk Bryggkaffe", None, ()),
        ("Pasta Bolognes Fryst", None, ()),
        ("Sour Pasta Basta Vegetarian", None, ()),
        ("Potatis&purjo Varma Koppen Pulver/3 Port", None, ()),
        ("Bbq Kulpotatis", None, ()),
        ("Dillkött Gourmetpotatis", None, ()),
        ("Gnocchi Classic Färsk Pasta", None, ()),
        ("Vitlök Rostad Burk", None, ()),
        # Brand text is provenance, not food identity.
        ("Pepparkakor Skåne", "Thulins", ()),
        ("Vanillinsocker", "Garant", ()),
        ("Nötfärs i Sås För Kastrerad Katt", None, ("Djur", "Katt", "Våtfoder")),
        ("Adult Lax & Ris", None, ("Djur", "Hund", "Torrfoder")),
        ("Paw Patrol Chokladägg", None, ("Godis",)),
        ("Kikärtor Chokladtäckta", None, ("Snacks",)),
        ("Fettuccine Tomat & Linser", None, ("Färdigrätter",)),
        ("Tortilla Chips Cheese", None, ("Snacks",)),
        ("Brödform 30 cm Nonstick", None, ("Köksredskap",)),
        ("Kokosmjölk Currysoppa", None, ("Soppor",)),
        ("Extrasaltat Smör & Rapsolja", None, ("Smör & margarin",)),
        ("Ost & Broccoli Soppa", None, ("Soppor",)),
        ("Hamburgergurka Längdskivad", None, ("Konserver", "Gurkinläggningar")),
        ("Bulgurgryta Kikärtor Och Nötkött", None, ("Färdigrätter",)),
        ("Fläskfilépasta", None, ("Färdigrätter",)),
        ("Gravad Lax", None, ("Fisk",)),
        ("Äggvita Flytande", None, ("Mejeri, ost & ägg", "Ägg")),
        ("Strawberry Milkshake", None, ("Mjölk & dryck",)),
        ("Majsvälling 6 Mån", None, ("Barn", "Barnmat")),
        ("Mozzarella Sticks", None, ("Fryst färdigmat",)),
        ("Cheddar Dressing", None, ("Kylda såser",)),
        ("Korvstroganoff Vildris", None, ("Färdiga rätter",)),
        ("Paprika Gourmet", None, ("Kryddor",)),
        ("Pumpa Vitlök Kyckling", None, ("Barn", "Barnmat")),
        ("Brödkryddor", None, ("Kryddor",)),
        ("Harissa Het Chilipasta", None, ("Kryddor & smaksättare",)),
        ("Majsolja", None, ("Kryddor & smaksättare",)),
        ("Ris Kyckling & Grönsaker", None, ("Barn", "Barnmat")),
    ],
)
def test_non_human_and_dominant_product_forms_are_not_high_confidence_foods(
    name: str,
    brand: str | None,
    categories: tuple[str, ...],
) -> None:
    product = ProductNormalizer().normalize(
        _source(name, brand=brand, categories=categories),
        parser_version="test",
    )

    assert product.canonical_food is None
    assert product.semantic_confidence == Confidence.UNKNOWN


@pytest.mark.parametrize(
    ("name", "canonical_food"),
    [
        ("Mellanmjölk 1,5%", "milk"),
        ("Vispgrädde 36%", "cream"),
        ("Crème Fraiche 34%", "creme_fraiche"),
        ("Normalsaltat Smör", "butter"),
        ("Hushållsost Mild", "cheese"),
        ("Ägg 12P Frigående Inomhus", "eggs"),
        ("Fast Potatis Sverige", "potato"),
        ("Basmatiris 1 kg", "ris"),
        ("Spaghetti", "pasta"),
        ("Glasnudlar", "nudlar"),
        ("Tortilla Original", "tortillas"),
        ("Knäckebröd Råg", "bröd"),
        ("Couscous Eko", "couscous"),
        ("Kycklingfilé 1 kg", "chicken_meat"),
        ("Nötfärs 12%", "minced_beef"),
        ("Blandfärs 50/50", "meat_mince"),
        ("Fläskfilé", "pork_meat"),
        ("Grillkorv Klassisk", "korv"),
        ("Falukorv Ring", "falukorv"),
        ("Laxfilé Portionsbitar", "salmon"),
        ("Torskfilé Utan Skinn", "fish_meat"),
        ("Tofu Fast Naturell", "tofu"),
        ("Gröna Linser Ekologiska", "lentil"),
        ("Röda Linser", "red_lentils"),
        ("Kidneybönor Röda", "kidney_bean"),
        ("Kikärtor Ekologiska", "chickpeas"),
        ("Gul Lök Sverige", "yellow_onion"),
        ("Vitlök Klass 1", "garlic"),
        ("Morot Klass 1", "carrot"),
        ("Röd Paprika", "pepper"),
        ("Vitkål Sverige", "white_cabbage"),
        ("Broccoli Eko", "broccoli"),
        ("Blomkål", "cauliflower"),
        ("Bifftomat", "tomato"),
        ("Gurka Sverige", "cucumber"),
        ("Zucchini", "zucchini"),
        ("Purjolök Eko", "leek"),
        ("Champinjoner Hela", "mushroom"),
        ("Krossade Tomater", "krossade_tomater"),
        ("Tomatpuré Tub", "tomato_puree"),
        ("Kokosmjölk 18%", "coconut_milk"),
        ("Grönsaksbuljong Tärningar", "broth"),
        ("Japansk Soja", "soy_sauce"),
        ("Majs Burk", "corn"),
        ("Gröna Ärtor Frysta", "peas"),
        ("Bladspenat Fryst", "spinach"),
        ("Bladselleri", "celery"),
        ("Rapsolja Kallpressad", "cooking_oil"),
    ],
)
def test_unprepared_base_foods_keep_strong_identity(name: str, canonical_food: str) -> None:
    product = ProductNormalizer().normalize(_source(name), parser_version="test")

    assert product.canonical_food == canonical_food
    assert product.semantic_confidence == Confidence.HIGH


def test_semantic_change_has_new_normalizer_provenance_version() -> None:
    product = ProductNormalizer().normalize(_source("Kycklingfilé"), parser_version="test")

    assert ProductNormalizer.normalizer_version == "product-normalizer-v3-recipe-taxonomy"
    assert product.normalizer_version == "product-normalizer-v3-recipe-taxonomy"


def test_normalizer_identity_rules_exactly_match_recipe_taxonomy() -> None:
    assert {canonical for canonical, _markers in _FOOD_IDENTITIES} == (
        RECIPE_RELEVANT_CANONICAL_FOODS
    )


def test_exact_terminal_category_can_supply_identity_but_broad_ancestor_cannot() -> None:
    exact = ProductNormalizer().normalize(
        _source("Frigående Inomhus 12P", categories=("Mejeri, ost & ägg", "Ägg")),
        parser_version="test",
    )
    broad = ProductNormalizer().normalize(
        _source("Original", categories=("Mejeri, ost & ägg",)),
        parser_version="test",
    )

    assert exact.canonical_food == "eggs"
    assert exact.semantic_confidence == Confidence.HIGH
    assert broad.canonical_food is None
    assert broad.semantic_confidence == Confidence.UNKNOWN

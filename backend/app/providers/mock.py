from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date

from ..models import CanonicalUnit, OfferKind, OfferMetadata, Product, Store
from ..models.product import QuantityConfidence
from .base import GroceryPriceProvider

_STORES: tuple[Store, ...] = (
    Store(
        store_id="willys-lund-norra-faladen",
        name="Willys Lund Norra Fäladen",
        chain="Willys",
        city="Lund",
        postal_code="22654",
        address="Magistratsvägen 22",
        latitude=55.7227,
        longitude=13.2017,
        distance_km=2.8,
    ),
    Store(
        store_id="ica-maxi-gunnesbo",
        name="ICA Maxi Gunnesbo",
        chain="ICA",
        city="Lund",
        postal_code="22651",
        address="Traktorvägen 1",
        latitude=55.7170,
        longitude=13.1547,
        distance_km=4.1,
    ),
    Store(
        store_id="coop-martenstorget",
        name="Coop Mårtenstorget",
        chain="Coop",
        city="Lund",
        postal_code="22351",
        address="Mårtenstorget 12",
        latitude=55.7022,
        longitude=13.1965,
        distance_km=0.9,
    ),
)


@dataclass(frozen=True, slots=True)
class _ItemSpec:
    key: str
    canonical_name: str
    category: str
    package_quantity: float
    package_unit: CanonicalUnit
    names: tuple[str, str, str]
    prices: tuple[float, float, float]
    brands: tuple[str, str, str]
    search_terms: tuple[str, ...] = ()
    usable_quantity: float | None = None
    usable_unit: CanonicalUnit | None = None
    quantity_confidence: QuantityConfidence = QuantityConfidence.EXACT
    variable_weight: bool = False


# The numbers below are intentionally mock data, not claims about current shelf
# prices. Every value is structured and deterministic so the complete PoC can be
# exercised without credentials. All package quantities are canonical g/ml/st.
_ITEMS: tuple[_ItemSpec, ...] = (
    # Protein
    _ItemSpec(
        "chicken-thigh-1000",
        "kycklinglårfilé",
        "protein/kyckling",
        1000,
        "g",
        ("Garant Kycklinglårfilé 1 kg", "ICA Kycklinglårfilé 1 kg", "Coop Kycklinglårfilé 1 kg"),
        (94.90, 99.90, 104.90),
        ("Garant", "ICA", "Coop"),
        ("kyckling", "lårfilé"),
    ),
    _ItemSpec(
        "chicken-thigh-700",
        "kycklinglårfilé",
        "protein/kyckling",
        700,
        "g",
        (
            "Eldorado Kycklinglårfilé 700 g",
            "I love eco Kycklinglårfilé 700 g",
            "Xtra Kycklinglårfilé 700 g",
        ),
        (72.90, 69.90, 76.90),
        ("Eldorado", "I love eco", "Xtra"),
        ("kyckling", "lårfilé"),
    ),
    _ItemSpec(
        "ground-beef-500",
        "nötfärs",
        "protein/nöt",
        500,
        "g",
        ("Garant Nötfärs 12% 500 g", "ICA Nötfärs 12% 500 g", "Coop Nötfärs 12% 500 g"),
        (64.90, 61.90, 66.90),
        ("Garant", "ICA", "Coop"),
        ("köttfärs", "färs", "nöt"),
    ),
    _ItemSpec(
        "mixed-mince-500",
        "blandfärs",
        "protein/köttfärs",
        500,
        "g",
        ("Garant Blandfärs 500 g", "ICA Blandfärs 500 g", "Coop Blandfärs 500 g"),
        (54.90, 56.90, 58.90),
        ("Garant", "ICA", "Coop"),
        ("köttfärs", "färs"),
    ),
    _ItemSpec(
        "pork-800",
        "fläskytterfilé",
        "protein/fläsk",
        800,
        "g",
        ("Garant Fläskytterfilé 800 g", "ICA Fläskytterfilé 800 g", "Coop Fläskytterfilé 800 g"),
        (79.90, 84.90, 82.90),
        ("Garant", "ICA", "Coop"),
        ("fläsk", "fläskkött"),
    ),
    _ItemSpec(
        "falukorv-800",
        "falukorv",
        "protein/korv",
        800,
        "g",
        ("Eldorado Falukorv 800 g", "ICA Falukorv 800 g", "Xtra Falukorv 800 g"),
        (34.90, 39.90, 36.90),
        ("Eldorado", "ICA", "Xtra"),
        ("korv",),
    ),
    _ItemSpec(
        "cod-400",
        "torskfilé",
        "protein/fisk",
        400,
        "g",
        ("Garant Fryst Torskfilé 400 g", "ICA Fryst Torskfilé 400 g", "Coop Fryst Torskfilé 400 g"),
        (64.90, 68.90, 62.90),
        ("Garant", "ICA", "Coop"),
        ("torsk", "fisk", "fryst"),
    ),
    _ItemSpec(
        "eggs-12",
        "ägg",
        "protein/ägg",
        12,
        "st",
        ("Garant Frigående Ägg 12-pack", "ICA Frigående Ägg 12-pack", "Coop Frigående Ägg 12-pack"),
        (34.90, 36.90, 37.90),
        ("Garant", "ICA", "Coop"),
        ("ägg", "agg"),
    ),
    _ItemSpec(
        "kidney-beans-380",
        "kidneybönor",
        "protein/baljväxter",
        380,
        "g",
        ("Garant Kidneybönor 380 g", "ICA Kidneybönor 380 g", "Coop Kidneybönor 380 g"),
        (12.90, 13.90, 12.50),
        ("Garant", "ICA", "Coop"),
        ("bönor", "kidney beans"),
        230,
        "g",
    ),
    _ItemSpec(
        "black-beans-380",
        "svarta bönor",
        "protein/baljväxter",
        380,
        "g",
        ("Garant Svarta Bönor 380 g", "ICA Svarta Bönor 380 g", "Coop Svarta Bönor 380 g"),
        (13.50, 14.50, 12.90),
        ("Garant", "ICA", "Coop"),
        ("bönor",),
        230,
        "g",
    ),
    _ItemSpec(
        "chickpeas-380",
        "kikärtor",
        "protein/baljväxter",
        380,
        "g",
        ("Garant Kikärtor 380 g", "ICA Kikärtor 380 g", "Coop Kikärtor 380 g"),
        (11.90, 13.50, 12.90),
        ("Garant", "ICA", "Coop"),
        ("ärtor", "baljväxter"),
        230,
        "g",
    ),
    _ItemSpec(
        "red-lentils-500",
        "röda linser",
        "protein/torra baljväxter",
        500,
        "g",
        ("Garant Röda Linser 500 g", "ICA Röda Linser 500 g", "Coop Röda Linser 500 g"),
        (20.90, 24.90, 22.90),
        ("Garant", "ICA", "Coop"),
        ("linser",),
    ),
    # Carbohydrates
    _ItemSpec(
        "pasta-1000",
        "pasta",
        "kolhydrat/pasta",
        1000,
        "g",
        ("Garant Spaghetti 1 kg", "ICA Basic Spaghetti 1 kg", "Xtra Spaghetti 1 kg"),
        (20.90, 22.90, 23.90),
        ("Garant", "ICA Basic", "Xtra"),
        ("spaghetti", "makaroner"),
    ),
    _ItemSpec(
        "pasta-500",
        "pasta",
        "kolhydrat/pasta",
        500,
        "g",
        ("Eldorado Penne 500 g", "ICA Penne 500 g", "Coop Fusilli 500 g"),
        (12.90, 11.90, 13.90),
        ("Eldorado", "ICA", "Coop"),
        ("penne", "fusilli", "makaroner"),
    ),
    _ItemSpec(
        "rice-1000",
        "ris",
        "kolhydrat/ris",
        1000,
        "g",
        ("Garant Långkornigt Ris 1 kg", "ICA Basic Ris 1 kg", "Xtra Ris 1 kg"),
        (25.90, 27.90, 28.90),
        ("Garant", "ICA Basic", "Xtra"),
        ("långkornigt",),
    ),
    _ItemSpec(
        "rice-2000",
        "ris",
        "kolhydrat/ris",
        2000,
        "g",
        ("Garant Jasminris 2 kg", "ICA Jasminris 2 kg", "Coop Jasminris 2 kg"),
        (48.90, 45.90, 51.90),
        ("Garant", "ICA", "Coop"),
        ("jasminris",),
    ),
    _ItemSpec(
        "potatoes-2000",
        "potatis",
        "kolhydrat/potatis",
        2000,
        "g",
        ("Svensk Potatis Fast 2 kg", "ICA Svensk Potatis 2 kg", "Coop Svensk Potatis 2 kg"),
        (29.90, 32.90, 31.90),
        ("Sverige", "ICA", "Coop"),
        ("fast potatis",),
    ),
    _ItemSpec(
        "couscous-500",
        "couscous",
        "kolhydrat/couscous",
        500,
        "g",
        ("Garant Couscous 500 g", "ICA Couscous 500 g", "Coop Couscous 500 g"),
        (19.90, 21.90, 20.90),
        ("Garant", "ICA", "Coop"),
    ),
    _ItemSpec(
        "noodles-250",
        "nudlar",
        "kolhydrat/nudlar",
        250,
        "g",
        ("Garant Äggnudlar 250 g", "ICA Äggnudlar 250 g", "Coop Äggnudlar 250 g"),
        (15.90, 16.90, 14.90),
        ("Garant", "ICA", "Coop"),
        ("äggnudlar",),
    ),
    # Vegetables
    _ItemSpec(
        "yellow-onion-1000",
        "gul lök",
        "grönsaker/lök",
        1000,
        "g",
        ("Gul Lök Sverige 1 kg", "ICA Gul Lök 1 kg", "Coop Gul Lök 1 kg"),
        (16.90, 18.90, 17.90),
        ("Sverige", "ICA", "Coop"),
        ("lök",),
    ),
    _ItemSpec(
        "carrots-1000",
        "morot",
        "grönsaker/rotfrukter",
        1000,
        "g",
        ("Morötter Sverige 1 kg", "ICA Morötter 1 kg", "Coop Morötter 1 kg"),
        (17.90, 19.90, 18.50),
        ("Sverige", "ICA", "Coop"),
        ("morötter",),
    ),
    _ItemSpec(
        "tomatoes-500",
        "tomat",
        "grönsaker/tomat",
        500,
        "g",
        ("Tomater 500 g", "ICA Tomater 500 g", "Coop Tomater 500 g"),
        (24.90, 22.90, 25.90),
        ("Sverige", "ICA", "Coop"),
        ("tomater", "färska tomater"),
    ),
    _ItemSpec(
        "bell-pepper-500",
        "paprika",
        "grönsaker/paprika",
        500,
        "g",
        ("Paprikamix 500 g", "ICA Paprikamix 500 g", "Coop Paprikamix 500 g"),
        (32.90, 29.90, 34.90),
        ("Garant", "ICA", "Coop"),
    ),
    _ItemSpec(
        "broccoli-500",
        "broccoli",
        "grönsaker/fryst",
        500,
        "g",
        ("Garant Fryst Broccoli 500 g", "ICA Fryst Broccoli 500 g", "Xtra Fryst Broccoli 500 g"),
        (19.90, 22.90, 18.90),
        ("Garant", "ICA", "Xtra"),
        ("fryst broccoli",),
    ),
    _ItemSpec(
        "white-cabbage-1000",
        "vitkål",
        "grönsaker/kål",
        1000,
        "g",
        ("Vitkål ca 1 kg", "ICA Vitkål ca 1 kg", "Coop Vitkål ca 1 kg"),
        (14.90, 16.90, 15.90),
        ("Sverige", "ICA", "Coop"),
        ("kål",),
    ),
    _ItemSpec(
        "frozen-vegetables-1000",
        "frysta grönsaker",
        "grönsaker/fryst",
        1000,
        "g",
        ("Garant Wokgrönsaker 1 kg", "ICA Basic Grönsaksmix 1 kg", "Xtra Wokmix 1 kg"),
        (28.90, 31.90, 29.90),
        ("Garant", "ICA Basic", "Xtra"),
        ("wokgrönsaker", "grönsaksmix", "wokmix"),
    ),
    _ItemSpec(
        "garlic-100",
        "vitlök",
        "grönsaker/lök",
        100,
        "g",
        ("Vitlök 100 g", "ICA Vitlök 100 g", "Coop Vitlök 100 g"),
        (9.90, 10.90, 9.50),
        ("Sverige", "ICA", "Coop"),
    ),
    # Dairy
    _ItemSpec(
        "milk-1000",
        "mjölk",
        "mejeri/mjölk",
        1000,
        "ml",
        ("Garant Mellanmjölk 1 l", "ICA Mellanmjölk 1 l", "Coop Mellanmjölk 1 l"),
        (15.90, 16.50, 16.90),
        ("Garant", "ICA", "Coop"),
    ),
    _ItemSpec(
        "cooking-cream-500",
        "matlagningsgrädde",
        "mejeri/grädde",
        500,
        "ml",
        (
            "Garant Matlagningsgrädde 5 dl",
            "ICA Matlagningsgrädde 5 dl",
            "Coop Matlagningsgrädde 5 dl",
        ),
        (22.90, 24.90, 23.90),
        ("Garant", "ICA", "Coop"),
        ("grädde",),
    ),
    _ItemSpec(
        "creme-fraiche-500",
        "crème fraiche",
        "mejeri/crème fraiche",
        500,
        "ml",
        ("Garant Crème Fraiche 500 ml", "ICA Crème Fraiche 500 ml", "Coop Crème Fraiche 500 ml"),
        (24.90, 26.90, 25.90),
        ("Garant", "ICA", "Coop"),
        ("creme fraiche",),
    ),
    _ItemSpec(
        "cheese-500",
        "ost",
        "mejeri/ost",
        500,
        "g",
        ("Garant Hushållsost 500 g", "ICA Hushållsost 500 g", "Coop Hushållsost 500 g"),
        (54.90, 57.90, 55.90),
        ("Garant", "ICA", "Coop"),
        ("hushållsost", "riven ost"),
    ),
    _ItemSpec(
        "butter-500",
        "smör",
        "mejeri/smör",
        500,
        "g",
        ("Garant Svenskt Smör 500 g", "ICA Svenskt Smör 500 g", "Coop Svenskt Smör 500 g"),
        (57.90, 59.90, 58.90),
        ("Garant", "ICA", "Coop"),
        ("svenskt smör",),
    ),
    # Pantry and other recipe staples
    _ItemSpec(
        "crushed-tomatoes-400",
        "krossade tomater",
        "övrigt/konserver",
        400,
        "g",
        (
            "Garant Krossade Tomater 400 g",
            "ICA Basic Krossade Tomater 400 g",
            "Xtra Krossade Tomater 400 g",
        ),
        (11.90, 12.50, 12.90),
        ("Garant", "ICA Basic", "Xtra"),
        ("tomatkross",),
    ),
    _ItemSpec(
        "coconut-milk-400",
        "kokosmjölk",
        "övrigt/konserver",
        400,
        "ml",
        ("Garant Kokosmjölk 400 ml", "ICA Kokosmjölk 400 ml", "Coop Kokosmjölk 400 ml"),
        (17.90, 18.90, 16.90),
        ("Garant", "ICA", "Coop"),
    ),
    _ItemSpec(
        "tortillas-8",
        "tortillabröd",
        "övrigt/tortilla",
        8,
        "st",
        (
            "Garant Tortilla Medium 8-pack",
            "ICA Tortilla Medium 8-pack",
            "Coop Tortilla Medium 8-pack",
        ),
        (20.90, 23.90, 22.90),
        ("Garant", "ICA", "Coop"),
        ("tortillas", "wraps"),
    ),
    _ItemSpec(
        "wheat-flour-2000",
        "vetemjöl",
        "övrigt/bakning",
        2000,
        "g",
        ("Garant Vetemjöl 2 kg", "ICA Basic Vetemjöl 2 kg", "Coop Vetemjöl 2 kg"),
        (22.90, 24.90, 23.90),
        ("Garant", "ICA Basic", "Coop"),
        ("mjöl",),
    ),
    _ItemSpec(
        "tomato-puree-200",
        "tomatpuré",
        "övrigt/konserver",
        200,
        "g",
        ("Garant Tomatpuré 200 g", "ICA Tomatpuré 200 g", "Coop Tomatpuré 200 g"),
        (15.90, 16.90, 14.90),
        ("Garant", "ICA", "Coop"),
    ),
    _ItemSpec(
        "oats-1500",
        "havregryn",
        "övrigt/gryn",
        1500,
        "g",
        ("Garant Havregryn 1,5 kg", "ICA Havregryn 1,5 kg", "Coop Havregryn 1,5 kg"),
        (22.90, 24.90, 23.90),
        ("Garant", "ICA", "Coop"),
    ),
)


_CAMPAIGN_START = date(2025, 1, 1)
_CAMPAIGN_END = date(2030, 12, 31)


def _offer(
    kind: OfferKind,
    description: str,
    price: float,
    required_packages: int = 1,
    member_program: str | None = None,
) -> OfferMetadata:
    return OfferMetadata(
        kind=kind,
        description=description,
        price=price,
        required_packages=required_packages,
        member_program=member_program,
        valid_from=_CAMPAIGN_START,
        valid_to=_CAMPAIGN_END,
    )


_OFFERS: dict[tuple[str, str], tuple[OfferMetadata, ...]] = {
    ("willys-lund-norra-faladen", "chicken-thigh-1000"): (
        _offer(OfferKind.CAMPAIGN, "Veckans pris", 69.90),
    ),
    ("willys-lund-norra-faladen", "pasta-1000"): (_offer(OfferKind.CAMPAIGN, "Kampanj", 17.90),),
    ("ica-maxi-gunnesbo", "ground-beef-500"): (
        _offer(OfferKind.MEMBER, "ICA Stammis-pris", 49.90, member_program="ICA Stammis"),
    ),
    ("ica-maxi-gunnesbo", "rice-2000"): (_offer(OfferKind.CAMPAIGN, "Veckans vara", 39.90),),
    ("ica-maxi-gunnesbo", "kidney-beans-380"): (
        _offer(OfferKind.MULTIPACK, "3 för 36 kr", 36.00, required_packages=3),
    ),
    ("coop-martenstorget", "eggs-12"): (
        _offer(OfferKind.MEMBER, "Coop medlemspris", 28.90, member_program="Coop Medlem"),
    ),
    ("coop-martenstorget", "crushed-tomatoes-400"): (
        _offer(OfferKind.MULTIPACK, "3 för 30 kr", 30.00, required_packages=3),
    ),
    ("coop-martenstorget", "cod-400"): (_offer(OfferKind.CAMPAIGN, "Fiskveckan", 54.90),),
}


_ALIASES: dict[str, tuple[str, ...]] = {
    "kyckling": ("kycklinglarfile",),
    "kycklingfile": ("kycklinglarfile",),
    "korv": ("falukorv",),
    "fisk": ("torskfile",),
    "bonor": ("kidneybonor", "svarta bonor"),
    "linser": ("roda linser",),
    "lok": ("gul lok",),
    "morotter": ("morot",),
    "krossad tomat": ("krossade tomater",),
    "tortillas": ("tortillabrod",),
    "gradde": ("matlagningsgradde",),
    "creme fraiche": ("creme fraiche",),
    "mjol": ("vetemjol",),
}


def _normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    ascii_like = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(
        "".join(character if character.isalnum() else " " for character in ascii_like).split()
    )


def _build_catalog() -> tuple[Product, ...]:
    products: list[Product] = []
    for store_index, store in enumerate(_STORES):
        for item in _ITEMS:
            offers = list(_OFFERS.get((store.store_id, item.key), ()))
            member_prices = [offer.price for offer in offers if offer.kind == OfferKind.MEMBER]
            products.append(
                Product(
                    product_id=f"mock-{store.store_id}-{item.key}",
                    name=item.names[store_index],
                    canonical_name=item.canonical_name,
                    category=item.category,
                    store_id=store.store_id,
                    store_name=store.name,
                    package_quantity=item.package_quantity,
                    package_unit=item.package_unit,
                    usable_quantity=item.usable_quantity or item.package_quantity,
                    usable_unit=item.usable_unit or item.package_unit,
                    quantity_confidence=item.quantity_confidence,
                    variable_weight=item.variable_weight,
                    price=item.prices[store_index],
                    member_price=min(member_prices) if member_prices else None,
                    offers=offers,
                    brand=item.brands[store_index],
                    search_terms=list(item.search_terms),
                )
            )
    return tuple(products)


class MockPriceProvider(GroceryPriceProvider):
    """Credential-free Lund provider with realistic but fictional prices."""

    source_name = "mock"
    location_name = "Lund"
    attribution_text = "Realistisk exempeldata från MockPriceProvider"
    attribution_url = None

    def __init__(self, use_member_prices: bool = False) -> None:
        super().__init__(use_member_prices=use_member_prices)
        self._products = _build_catalog()

    async def find_stores(self, postal_code: str) -> list[Store]:
        # A postal-code lookup is deliberately not simulated. Any valid or unknown
        # input gets the documented Lund fallback, ordered by mock distance.
        _ = "".join(character for character in postal_code if character.isdigit())
        return [
            store.model_copy(deep=True)
            for store in sorted(
                _STORES,
                key=lambda candidate: candidate.distance_km or float("inf"),
            )
        ]

    async def search_products(
        self,
        query: str,
        store_ids: list[str],
    ) -> list[Product]:
        normalized_query = _normalize_text(query)
        if not normalized_query:
            return []
        selected_stores = set(store_ids) if store_ids else {store.store_id for store in _STORES}
        query_variants = {normalized_query, *_ALIASES.get(normalized_query, ())}

        matches: list[Product] = []
        for product in self._products:
            if product.store_id not in selected_stores:
                continue
            haystack = _normalize_text(
                " ".join(
                    [
                        product.name,
                        product.canonical_name,
                        product.category,
                        product.brand or "",
                        *product.search_terms,
                    ]
                )
            )
            if any(
                variant in haystack or all(token in haystack for token in variant.split())
                for variant in query_variants
            ):
                matches.append(product)

        priced = self.apply_price_policy(matches)
        return sorted(
            priced,
            key=lambda product: (
                product.normalized_unit_price,
                float(product.effective_price),
                product.name,
            ),
        )

    async def get_store_products(self, store_id: str) -> list[Product]:
        products = [product for product in self._products if product.store_id == store_id]
        return self.apply_price_policy(products)

    async def get_offers(self, store_id: str) -> list[Product]:
        products = [
            product
            for product in self._products
            if product.store_id == store_id and product.active_offers()
        ]
        return self.apply_price_policy(products)

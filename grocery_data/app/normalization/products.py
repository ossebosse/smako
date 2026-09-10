from __future__ import annotations

import re
import unicodedata
from decimal import Decimal
from hashlib import sha256

from grocery_data.app.domain import (
    RECIPE_RELEVANT_CANONICAL_FOODS,
    CanonicalProduct,
    Confidence,
    SaleModel,
    SourceProduct,
)

_APPROXIMATE = re.compile(r"\bca\s*:?")
_WORD = re.compile(r"[^a-z0-9]+")

# This deliberately identifies only strong lexical evidence. Chain-specific
# parsers retain the source name/category, while richer semantic matching stays
# in the consumer layer. An unknown identity is safer than a guessed one.
_FOOD_IDENTITIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    # Specific identities precede overlapping generic words.  For example,
    # coconut milk must never become milk, red lentils must not become the
    # generic lentil identity, and falukorv must not be swallowed by korv.
    ("creme_fraiche", ("crème fraiche", "creme fraiche", "mini fraiche")),
    ("coconut_milk", ("kokosmjölk",)),
    (
        "krossade_tomater",
        ("krossade tomater", "tomater krossade", "finkrossade tomater", "tomater finkrossade"),
    ),
    ("tomato_puree", ("tomatpuré", "tomat puree")),
    ("red_lentils", ("röda linser", "röd lins", "linser röda", "lins röd")),
    ("kidney_bean", ("kidneyböna", "kidneybönor")),
    ("falukorv", ("falukorv",)),
    ("minced_beef", ("nötfärs", "nöt färs")),
    ("meat_mince", ("blandfärs", "bland färs")),
    (
        "chicken_meat",
        (
            "kycklingfilé",
            "kycklinginnerfilé",
            "kycklinglår",
            "kycklinglårfilé",
            "kycklingbröst",
            "kycklingklubba",
            "kycklingvinge",
            "hel kyckling",
        ),
    ),
    (
        "pork_meat",
        (
            "fläskkött",
            "fläskfilé",
            "fläskytterfilé",
            "fläskkotlett",
            "fläskkarré",
            "sidfläsk",
            "stekfläsk",
            "fläskfärs",
            "fläskgrytbitar",
        ),
    ),
    ("salmon", ("lax", "laxfilé", "laxsida")),
    (
        "fish_meat",
        (
            "torsk",
            "torskfilé",
            "torskrygg",
            "sejfilé",
            "koljafilé",
            "vit fisk",
        ),
    ),
    ("yellow_onion", ("gul lök", "gullök", "lök gul")),
    ("garlic", ("vitlök", "vitlöksklyfta")),
    ("cauliflower", ("blomkål",)),
    ("white_cabbage", ("vitkål",)),
    ("soy_sauce", ("sojasås", "japansk soja", "mörk soja", "ljus soja", "tamari")),
    ("cooking_oil", ("rapsolja", "matolja", "olivolja")),
    ("milk", ("mjölk",)),
    ("cream", ("vispgrädde", "matlagningsgrädde", "kaffegrädde", "grädde")),
    ("butter", ("mejerismör", "smör")),
    (
        "cheese",
        (
            "hushållsost",
            "prästost",
            "herrgårdsost",
            "grevé",
            "hårdost",
            "färskost",
            "mjukost",
            "grillost",
            "halloumi",
            "mozzarella",
            "parmesan",
            "pecorino",
            "cheddar",
            "gouda",
            "brie",
            "fetaost",
            "getost",
            "blåmögelost",
        ),
    ),
    ("eggs", ("hönsägg", "ägg")),
    ("potato", ("potatis",)),
    (
        "ris",
        (
            "basmatiris",
            "jasminris",
            "matris",
            "arborioris",
            "risottoris",
            "sushiris",
            "fullkornsris",
            "långkornigt ris",
            "parboiled ris",
            "ris",
        ),
    ),
    (
        "pasta",
        (
            "spaghetti",
            "fusilli",
            "makaron",
            "penne",
            "tagliatelle",
            "fettuccine",
            "linguine",
            "farfalle",
            "lasagneplatta",
            "pasta",
        ),
    ),
    ("nudlar", ("nudlar", "glasnudlar", "äggnudlar", "risnudlar")),
    ("tortillas", ("tortilla", "tortillabröd")),
    ("bröd", ("matbröd", "rostbröd", "knäckebröd", "tunnbröd", "bröd")),
    ("couscous", ("pärlcouscous", "couscous")),
    ("korv", ("grillkorv", "wienerkorv", "prinskorv", "chorizokorv", "korv")),
    ("tofu", ("tofu",)),
    ("lentil", ("gröna linser", "grön lins", "belugalinser", "beluga linser", "linser")),
    ("chickpeas", ("kikärta", "kikärtor", "kikärter")),
    ("carrot", ("morot", "morötter")),
    ("pepper", ("röd paprika", "paprika röd", "paprika")),
    ("broccoli", ("broccoli",)),
    ("tomato", ("tomat", "tomater")),
    ("cucumber", ("slanggurka", "gurka")),
    ("zucchini", ("zucchini", "squash")),
    ("leek", ("purjolök",)),
    ("mushroom", ("champinjon", "champinjoner", "portabello", "shiitake", "matsvamp")),
    ("broth", ("buljong", "grönsaksfond", "kycklingfond", "oxfond", "fiskfond")),
    ("corn", ("majskorn", "sockermajs", "majs")),
    ("peas", ("gröna ärtor", "grön ärta", "ärtor", "ärter")),
    ("spinach", ("babyspenat", "bladspenat", "spenat")),
    ("celery", ("blekselleri", "bladselleri", "rotselleri", "selleri")),
)

# Exact source category segments may provide identity when the retail title is
# only a variety or brand (for example "Präst Mellanlagrad").  Broad ancestors
# such as "Mejeri, ost & ägg" are deliberately absent.
_CATEGORY_IDENTITIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("eggs", ("ägg", "ägg/äggmix")),
    ("milk", ("standardmjölk", "mellanmjölk", "lättmjölk", "laktosfri mjölk")),
    ("cream", ("grädde",)),
    ("butter", ("smör",)),
    (
        "cheese",
        (
            "hårdost",
            "mozzarella",
            "fetaost",
            "grillost",
            "färskost naturell",
            "mjukost",
        ),
    ),
    ("minced_beef", ("nötfärs",)),
    ("meat_mince", ("blandfärs",)),
    ("red_lentils", ("röda linser",)),
    ("kidney_bean", ("kidneybönor",)),
    ("chickpeas", ("kikärtor", "kikärter")),
    ("yellow_onion", ("gul lök",)),
)

if {canonical for canonical, _markers in _FOOD_IDENTITIES} != (
    RECIPE_RELEVANT_CANONICAL_FOODS
):  # pragma: no cover - import-time invariant also has a focused regression test
    raise RuntimeError("ProductNormalizer identity rules must cover the recipe taxonomy exactly")

# These gates are deliberately conservative.  A source product remains
# available and replayable when one of them matches, but it is not promoted to
# a canonical recipe ingredient with HIGH confidence.  This is preferable to
# calling pet food, baby food or a prepared dish a raw grocery ingredient.
_NON_HUMAN_FOOD_MARKERS = (
    "torrfoder",
    "våtfoder",
    "hundmat",
    "kattmat",
    "hundfoder",
    "kattfoder",
    "djurfoder",
    "hundgodis",
    "kattgodis",
    "hundsnack",
    "kattsnack",
    "dog food",
    "cat food",
    "dog treat",
    "cat treat",
    "pet food",
    "catmilk",
    "kattmjölk",
)
_PET_AUDIENCE_MARKERS = ("hund", "katt", "dog", "cat", "valp", "puppy", "kitten")
_PET_PRODUCT_MARKERS = ("foder", "godis", "treat", "pet food")

_NON_FOOD_VISIBLE_MARKERS = (
    "färdigrätter",
    "färdigmat",
    "färdiga rätter",
    "färdiga såser",
    "kylda såser",
    "snabbnudlar torr färdigmat",
    "pesto pastasåser",
    "barn",
    "barnmat",
    "snacks",
    "hushållsartiklar",
    "köksredskap",
    "leksaker",
    "hudvård",
    "hårvård",
    "godis",
    "diskmedel",
    "rengöring",
    "schampo",
    "tvål",
    "handkräm",
    "ansiktskräm",
    "läppbalsam",
    "doftljus",
    "servetter",
    "kosttillskott",
)

_BABY_FOOD_MARKERS = (
    "barnmat",
    "baby food",
    "modersmjölk",
    "från 4 månader",
    "från 6 månader",
    "från 8 månader",
    "från 10 månader",
    "från 12 månader",
    "från 15 månader",
    "från 18 månader",
    "från 24 månader",
    "från 1 år",
    "från 1 3 år",
)

# Product-class words are evaluated only in the product name.  A generic
# category such as "Såser" must not invalidate an otherwise explicit product
# identity; conversely, "Basilikasås" in the name is dominant evidence that
# the sold item is not raw chicken breast.
_DOMINANT_NON_RAW_MARKERS: dict[str, tuple[str, ...]] = {
    "coconut_milk": (
        "soppa",
        "smoothie",
        "schampo",
        "balsam",
        "dusch",
        "mango kokosmjölk",
    ),
    "creme_fraiche": (
        "potatissallad",
        "paprika",
        "chili",
        "tomat",
        "basilika",
        "parmesan",
        "kantarell",
        "feta",
    ),
    "red_lentils": (
        "soppa",
        "bolognese",
        "linskaka",
        "linsbågar",
        "linspasta",
        "pasta",
        "snack",
        "gryta",
        "sötpotatis kyckling",
    ),
    "kidney_bean": ("soppa", "gryta", "burgare", "biff", "mix", "chili"),
    "chickpeas": (
        "choklad",
        "kanderad",
        "mjöl",
        "pasta",
        "snack",
        "gryta",
        "burgare",
        "mix",
        "tonfisk",
    ),
    "minced_beef": ("burgare", "biff", "köttbull", "lasagne", "sås", "gryta"),
    "meat_mince": ("burgare", "biff", "köttbull", "lasagne", "sås", "gryta"),
    "chicken_meat": (
        "sås",
        "soppa",
        "gryta",
        "färdigrätt",
        "nugget",
        "burgare",
        "korv",
        "kebab",
        "gyros",
        "grillad skivad",
        "grillkryddad skivad",
        "grillkryddad",
        "citron vitlök",
        "marinerad",
    ),
    "pork_meat": (
        "fläskfilégryta",
        "fläskfilépasta",
        "fläskkarré rostad klyftpotatis",
        "färdigrätt",
        "soppa",
        "örtagårdsgryta",
        "gryta med",
        "kebab",
    ),
    "salmon": (
        "sås",
        "soppa",
        "couscous",
        "sallad",
        "sushi",
        "gravad",
        "kallrökt",
        "varmrökt",
        "paj",
        "potatismos",
        "smörgås",
        "macka",
        "för ugnsbakad",
        "varmr",
    ),
    "fish_meat": (
        "sås",
        "soppa",
        "catsticks",
        "fiskbull",
        "gratäng",
        "panerad",
    ),
    "yellow_onion": ("chips", "picklad", "dressing", "soppa", "pulver"),
    "garlic": (
        "baguett",
        "bröd",
        "potatissallad",
        "dressing",
        "majonnäs",
        "majo",
        "marinad",
        "marinerad",
        "färskost",
        "cambozola",
        "crème bonjour",
        "labneh",
        "krossade tomater",
        "vitlökskräm",
        "sås",
        "dippmix",
        "chips",
        "crostini",
        "salami",
        "korv",
        "risotto",
        "gnocchi",
        "vitlökspulver",
        "vitlökssalt",
        "vitlökspeppar",
        "vitlökssmör",
        "vitlökspress",
        "kapsel",
        "granulerad",
        "rostad",
        "oliver",
        "örter",
        "sauce",
        "krutong",
        "bruschetta",
        "biff",
        "ost",
        "rapsolja",
        "räkor",
        "roulé",
        "ramslök",
        "gräslök",
    ),
    "cauliflower": ("soppa", "gratäng", "pizza", "wings", "paj"),
    "white_cabbage": ("coleslaw", "sallad", "kålmix", "surkål", "gryta"),
    "cooking_oil": (
        "smör",
        "margarin",
        "hud",
        "hår",
        "massage",
        "kapsel",
    ),
    "cream": (
        "kokosgrädde",
        "vaniljsås",
        "sås",
        "soppa",
        "glass",
        "godis",
        "kaka",
        "spray",
    ),
    "butter": (
        "jordnötssmör",
        "mandelsmör",
        "cashewsmör",
        "smörgås",
        "smördeg",
        "smörkola",
        "kryddsmör",
        "messmör",
        "persiljesmör",
        "vitlökssmör",
        "chili smör",
        "ramslök",
        "pepparsmör",
        "färsbiff",
        "raps",
    ),
    "cheese": (
        "ostbåg",
        "ostkrok",
        "ostkaka",
        "osthyvel",
        "ostkniv",
        "baguette",
        "sandwich",
        "sås",
        "soppa",
        "paj",
        "pizza",
        "chips",
        "snack",
        "spaghetti",
        "fettuccine",
        "gnocchi",
        "ravioli",
        "tortellini",
        "pasta",
        "mac cheese",
        "burgare",
    ),
    "eggs": (
        "chokladägg",
        "godis",
        "äggvita",
        "äggnudlar",
        "äggpasta",
        "majonnäs",
        "rom",
        "kaviar",
        "sallad",
        "pappardelle",
        "tagliatelle",
        "trio mix",
        "aprikos",
    ),
    "pasta": (
        "pastasås",
        "currypasta",
        "sesampasta",
        "dadelpasta",
        "pasta snack",
        "pasta bowl",
        "soppa",
        "gryta",
        "färdigrätt",
        "fryst 1 port",
        "fryst",
        "bolognese",
        "carbonara",
        "pastagratäng",
        "pastakrydda",
        "pastaslev",
        "fläskfilépasta",
        "pasta oxfilé",
        "pasta pesto",
        "pasta pomodoro",
        "dipping sauce",
        "sour pasta",
        "vodkapasta",
        "gnocchi",
        "alfredo",
        "fyra ostar",
        "chilipasta",
        "harissa",
    ),
    "ris": (
        "risifrutti",
        "riskaka",
        "risdryck",
        "risgrynsgröt",
        "risotto",
        "grönsaksris",
        "blomkålsris",
        "rischips",
        "krispig",
        "couscous",
        "soppa",
        "gryta",
        "färdigrätt",
        "stroganoff",
        "lasagne",
    ),
    "nudlar": (
        "chicken soup",
        "beef",
        "kyckling",
        "biff",
        "hot chili",
        "spicy",
        "chili",
        "teriyaki",
        "snabbnudlar",
        "kopp",
        "soppa",
        "wok färdig",
        "cup",
    ),
    "tortillas": ("chips", "strips", "snack", "bowl", "dippmix", "dip mix"),
    "bröd": (
        "ströbröd",
        "brödform",
        "brödkavel",
        "brödkniv",
        "brödkrydd",
        "tunnbrödschips",
        "bruschetta",
        "vitlöksbröd",
        "vitlöksbaguett",
    ),
    "couscous": ("kyckling", "lax", "biff", "sallad", "grönsaker", "färdigrätt"),
    "korv": (
        "gryta",
        "soppa",
        "pizza",
        "pasta",
        "sås",
        "färdigrätt",
        "stroganoff",
        "körvel",
    ),
    "tofu": ("pesto", "wok", "gryta", "soppa", "crispy", "färdigrätt"),
    "potato": (
        "sötpotatis",
        "potatissallad",
        "potatischips",
        "chips",
        "potatisgratäng",
        "potatismos",
        "potatisbullar",
        "potatiskrokett",
        "kroketter",
        "potatissoppa",
        "soppa",
        "potatisbröd",
        "potatismjöl",
        "potatisskalare",
        "potatissticka",
        "klyftpotatis",
        "kulpotatis",
        "potatisbakelse",
        "potatisstomp",
        "potatisklyftor",
        "potatis purjo",
        "varma koppen",
        "dillkött",
        "färdigrätt",
        "kalkon",
        "puré",
    ),
    "carrot": (
        "morotsjuice",
        "morotskaka",
        "morotsmuffin",
        "majssnack",
        "smoothie",
        "puré",
        "bröd",
        "burgare",
        "gryta",
        "surkål",
        "kålmix",
        "ärter",
        "juice",
        "soppa",
        "apelsin",
    ),
    "milk": (
        "mjölkchoklad",
        "choklad",
        "chokladmjölk",
        "filmjölk",
        "kokosmjölk",
        "kondenserad mjölk",
        "mjölkpulver",
        "mjölkfri",
        "välling",
        "gröt",
        "glass",
        "sås",
        "cookies",
        "kex",
        "kaka",
        "bouchée",
        "kaffe",
        "karamelliserad",
        "protein",
        "blåbär",
        "jordgubb",
        "vanilj",
        "persika",
        "filjmjölk",
        "milkshake",
        "strawberry",
    ),
    "lentil": (
        "linssoppa",
        "soppa",
        "linsbolognese",
        "linskaka",
        "linsbågar",
        "linspasta",
        "pasta",
        "snack",
        "gryta",
    ),
    "pepper": (
        "rostad",
        "sås",
        "pulver",
        "chips",
        "tonfiskfilé",
        "sandwich",
        "majonnäs",
        "mayo",
        "oliver",
        "gulasch",
        "kyckling",
        "ost",
        "paprikash",
        "tuc",
        "kex",
        "sallad",
        "snacks",
        "gourmet",
        "peperoni grigliati",
        "pesto",
        "räkor",
    ),
    "broccoli": ("paj", "soppa", "wings", "mix", "kyckling", "ost"),
    "tomato": (
        "ketchup",
        "sås",
        "soppa",
        "puré",
        "soltorkad",
        "fylld",
        "hummus",
        "pasta",
        "feta",
        "salsa",
        "soup",
        "sardin",
        "automat",
        "ostkuber",
        "juice",
        "sauce",
        "pesto",
        "vegoskivor",
    ),
    "cucumber": (
        "bostongurka",
        "hamburgergurka",
        "smörgåsgurka",
        "cornichon",
        "inlagd",
        "picklad",
        "tonic",
        "saltgurka",
        "gammaldags",
        "gammeldags",
        "finhackad",
        "leverpastej",
        "ättiksgurka",
        "vildgurka",
    ),
    "zucchini": ("pasta", "soppa", "gryta", "biff", "mix"),
    "leek": ("potatissallad", "soppa", "paj", "gryta"),
    "mushroom": ("soppa", "sås", "stuvning", "paj", "pizza", "mix"),
    "broth": ("fiskbull", "soppa", "nudlar", "färdigrätt"),
    "corn": (
        "majskak",
        "majssnack",
        "majspasta",
        "majspuff",
        "popcorn",
        "cornflakes",
        "tortilla",
        "bröd",
        "risotto",
        "gryta",
        "sallad",
        "majsstärkelse",
        "majsmjöl",
        "majsgryn",
        "polenta",
        "majskorv",
        "majskyckling",
        "majsolja",
    ),
    "peas": (
        "soppa",
        "snack",
        "pasta",
        "gryta",
        "mix",
        "puré",
        "gula ärter",
        "fläsk",
    ),
    "spinach": (
        "paj",
        "soppa",
        "pinnar",
        "gnocchi",
        "burek",
        "smoothie",
        "tortelloni",
        "äpple",
        "juice",
    ),
}


def _text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    unaccented = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(part for part in _WORD.sub(" ", unaccented).split() if part)


def _contains_marker(text: str, marker: str) -> bool:
    normalized = _text(marker)
    return bool(normalized) and f" {normalized} " in f" {text} "


def _contains_identity(text: str, marker: str) -> bool:
    """Require word/compound evidence instead of an arbitrary substring.

    Prefix/suffix support preserves Swedish retail compounds such as
    ``färskpotatis`` and ``vitlöksklyftor``.  It does not turn brand names
    such as ``Thulins`` or words such as ``vanillinsocker`` into lentils.
    """

    normalized = _text(marker)
    if not normalized:
        return False
    if " " in normalized:
        return _contains_marker(text, normalized)
    return any(
        token == normalized
        or len(normalized) >= 4
        and (token.startswith(normalized) or token.endswith(normalized))
        for token in text.split()
    )


def _is_non_human_food(visible: str) -> bool:
    if any(
        _contains_marker(visible, marker)
        for marker in (*_NON_HUMAN_FOOD_MARKERS, *_NON_FOOD_VISIBLE_MARKERS)
    ):
        return True
    return any(_contains_marker(visible, marker) for marker in _PET_AUDIENCE_MARKERS) and any(
        _contains_marker(visible, marker) for marker in _PET_PRODUCT_MARKERS
    )


def _has_dominant_marker(name: str, canonical: str) -> bool:
    markers = (*_BABY_FOOD_MARKERS, *_DOMINANT_NON_RAW_MARKERS.get(canonical, ()))
    # Dominant forms commonly occur as Swedish compounds (``linssoppa``,
    # ``ostbågar``), so a normalized substring is appropriate here. Identity
    # markers themselves use the stricter word/compound matcher above.
    return any(_text(marker) in name for marker in markers)


def _category_identity(source: SourceProduct) -> str | None:
    segments = tuple(_text(segment) for segment in source.category_path)
    for canonical, markers in _CATEGORY_IDENTITIES:
        normalized_markers = tuple(_text(marker) for marker in markers)
        if any(segment == marker for segment in segments for marker in normalized_markers):
            return canonical
    return None


def _canonical_food(source: SourceProduct) -> tuple[str | None, Confidence]:
    # Brand names are not food identity.  The live catalogue contained the
    # brand "Thulins", which previously matched the substring ``lins``.
    name = _text(source.name)
    visible = _text(" ".join((source.name, *source.category_path)))
    if _is_non_human_food(visible):
        return None, Confidence.UNKNOWN

    for canonical, markers in _FOOD_IDENTITIES:
        if any(_contains_identity(name, marker) for marker in markers):
            if _has_dominant_marker(name, canonical):
                return None, Confidence.UNKNOWN
            return canonical, Confidence.HIGH

    category_identity = _category_identity(source)
    if category_identity is not None and not _has_dominant_marker(name, category_identity):
        return category_identity, Confidence.HIGH
    return None, Confidence.UNKNOWN


def _price_unit(value: str | None) -> str | None:
    normalized = (value or "").casefold().strip().replace(" ", "")
    return {
        "kr/kg": "kg",
        "sek/kg": "kg",
        "kg": "kg",
        "kr/l": "l",
        "sek/l": "l",
        "l": "l",
        "kr/st": "st",
        "sek/st": "st",
        "st": "st",
    }.get(normalized)


class ProductNormalizer:
    """Convert source facts into conservative purchase semantics.

    Comparison price is copied as provenance only. It never creates package
    quantity, sale unit or a purchasable one-kilogram package.
    """

    normalizer_version = "product-normalizer-v3-recipe-taxonomy"

    def normalize(self, source: SourceProduct, *, parser_version: str) -> CanonicalProduct:
        basket_type = (source.basket_type or "").strip().upper()
        package_is_approximate = bool(
            source.package_text and _APPROXIMATE.search(source.package_text.casefold())
        )
        sale_model = SaleModel.UNKNOWN
        confidence = Confidence.UNKNOWN
        package_quantity = source.package_quantity
        package_unit = source.package_unit
        usable_quantity = package_quantity
        usable_unit = package_unit
        unit_price: Decimal | None = None
        sale_price = source.sale_price

        if source.sale_unit in {"kg", "l"} and basket_type == "VIKT":
            sale_model = SaleModel.SOLD_BY_WEIGHT
            confidence = Confidence.DERIVED
            unit_price = sale_price
            package_quantity = None
            package_unit = None
            usable_quantity = None
            usable_unit = None
        elif (
            source.sale_unit in {"kg", "l"}
            and basket_type == "ST"
            and source.average_weight_kg is not None
        ):
            sale_model = SaleModel.VARIABLE_WEIGHT_PACKAGE
            confidence = Confidence.ESTIMATED
            unit_price = sale_price
            package_quantity = source.average_weight_kg * Decimal(1000)
            package_unit = "g" if source.sale_unit == "kg" else "ml"
            usable_quantity = package_quantity
            usable_unit = package_unit
            sale_price = source.sale_price * source.average_weight_kg if source.sale_price else None
        elif source.sale_unit == "st" and package_quantity is not None:
            if package_unit == "st" and package_quantity == 1:
                sale_model = SaleModel.SOLD_BY_PIECE
            else:
                sale_model = SaleModel.FIXED_PACKAGE
            confidence = Confidence.ESTIMATED if package_is_approximate else Confidence.EXACT
        elif source.sale_unit == "st" and package_quantity is None:
            # ``kr/st`` means one priced sales unit, but it does not prove that
            # the unit is one edible piece rather than a fixed package whose
            # size metadata is missing. Keep the purchase model unknown.
            sale_model = SaleModel.UNKNOWN
            confidence = Confidence.UNKNOWN
            package_quantity = None
            package_unit = None
            usable_quantity = None
            usable_unit = None
        # A kg/l rate without basket-type or approximate-weight evidence stays
        # UNKNOWN; comparison metadata is intentionally absent from this gate.

        if source.drained_quantity is not None and sale_model == SaleModel.FIXED_PACKAGE:
            if package_quantity is None or source.drained_quantity > package_quantity:
                raise ValueError("drained quantity exceeds or lacks gross package quantity")
            usable_quantity = source.drained_quantity
            usable_unit = package_unit
            confidence = Confidence.DERIVED

        canonical_food, semantic_confidence = _canonical_food(source)
        key_material = (
            f"{source.chain.value}\0{source.store_external_id}\0"
            f"{source.external_product_id or source.name}"
        )
        source_key = sha256(key_material.encode()).hexdigest()
        return CanonicalProduct(
            source_product_key=source_key,
            chain=source.chain,
            store_external_id=source.store_external_id,
            external_product_id=source.external_product_id,
            gtin=source.gtin,
            name=source.name,
            brand=source.brand,
            category_path=source.category_path,
            canonical_food=canonical_food,
            semantic_confidence=semantic_confidence,
            sale_model=sale_model,
            quantity_confidence=confidence,
            package_quantity=package_quantity,
            package_unit=package_unit,
            usable_quantity=usable_quantity,
            usable_unit=usable_unit,
            sale_price=sale_price,
            sale_unit=source.sale_unit,
            unit_price=unit_price,
            comparison_price=source.comparison_price,
            comparison_unit=_price_unit(source.comparison_unit),
            availability=source.availability,
            offers=source.offers,
            raw_reference=source.raw_reference,
            parser_version=parser_version,
            normalizer_version=self.normalizer_version,
            observed_at=source.fetched_at,
        )

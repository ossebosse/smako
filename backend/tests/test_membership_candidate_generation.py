from __future__ import annotations

from datetime import date

from app.models.product import (
    OfferKind,
    OfferMetadata,
    ProductCandidate,
    QuantityConfidence,
    SaleModel,
    SemanticConfidence,
)
from app.models.recipe import Recipe, RecipeIngredient
from app.models.store import Store
from app.services.basket_optimizer import BasketOptimizer
from app.services.economic_ingredient_selector import (
    EconomicIngredientPool,
    EconomicIngredientSelector,
)
from app.services.ingredient_taxonomy import (
    IngredientCategory,
    IngredientTaxonomyEntry,
)
from app.services.menu_optimizer import MenuOptimizer
from app.services.user_pricing import (
    eligible_member_contract_fingerprints,
    eligible_member_contract_references,
    prepare_economic_pool_for_pricing,
    project_economic_pool,
)

from grocery_data.app.domain.promotion_pricing import (
    MembershipProgram,
    PromotionEligibility,
    PromotionMechanism,
    UserPricingContext,
)

TODAY = date(2026, 8, 31)
STORE = Store(
    store_id="own:coop:test",
    name="Coop Test",
    chain="coop",
    city="Lund",
    postal_code="22350",
)
ICA_STORE = Store(
    store_id="external:ica:test",
    name="ICA Test",
    chain="ica",
    city="Lund",
    postal_code="22350",
)


def _entry(
    canonical: str,
    *,
    typical_meal_quantity: float = 500,
) -> IngredientTaxonomyEntry:
    return IngredientTaxonomyEntry(
        canonical=canonical,
        display_name=canonical.title(),
        category=IngredientCategory.CARBOHYDRATE,
        search_query=canonical,
        expected_unit="g",
        typical_meal_quantity=typical_meal_quantity,
        identity_terms=(canonical,),
    )


def _candidate(
    canonical: str,
    product_id: str,
    regular_price: float,
    *,
    member_price: float | None = None,
    member_required_packages: int = 1,
    member_max_quantity: int | None = None,
    package_quantity: float = 500,
    membership_program: MembershipProgram = MembershipProgram.COOP_MEMBER,
    store: Store = STORE,
) -> ProductCandidate:
    offers = []
    if member_price is not None:
        offers.append(
            OfferMetadata(
                kind=(
                    OfferKind.MULTIPACK
                    if member_required_packages > 1
                    else OfferKind.MEMBER
                ),
                description=f"{membership_program.consumer_label} {member_price:g} kr",
                price=member_price,
                price_contract_id=f"contract:{product_id}:coop-member",
                eligibility=PromotionEligibility.MEMBER,
                mechanism=(
                    PromotionMechanism.MULTIBUY
                    if member_required_packages > 1
                    else PromotionMechanism.SALE_PRICE
                ),
                required_packages=member_required_packages,
                max_quantity=member_max_quantity,
                membership_program=membership_program,
                member_program=membership_program.consumer_label,
            )
        )
    return ProductCandidate(
        product_id=product_id,
        product_name=f"{canonical.title()} 500 g {product_id}",
        canonical_name=canonical,
        store_id=store.store_id,
        store_name=store.name,
        chain=store.chain,
        price=regular_price,
        effective_price=regular_price,
        member_price=(member_price if member_required_packages == 1 else None),
        match_score=1,
        offers=offers,
        sale_model=SaleModel.FIXED_PACKAGE,
        sale_price=regular_price,
        package_quantity=package_quantity,
        package_unit="g",
        usable_quantity=package_quantity,
        usable_unit="g",
        quantity_confidence=QuantityConfidence.EXACT,
        semantic_confidence=SemanticConfidence.HIGH,
    )


def _context(*memberships: MembershipProgram) -> UserPricingContext:
    return UserPricingContext(memberships=set(memberships))


def test_member_price_is_applied_before_per_store_product_shortlist() -> None:
    public_winner = _candidate("potatis", "public-winner", 10)
    member_winner = _candidate(
        "potatis",
        "member-winner",
        30,
        member_price=5,
    )
    pool = EconomicIngredientPool(
        candidates_by_name={"potatis": [public_winner]},
        semantic_candidates_by_name={"potatis": [public_winner]},
        matched_candidates_by_name={"potatis": [public_winner, member_winner]},
    )
    selector = EconomicIngredientSelector(
        taxonomy=(_entry("potatis"),),
        max_candidates_per_store=1,
    )

    public = project_economic_pool(
        pool,
        _context(),
        selector=selector,
        on_date=TODAY,
    )
    member = project_economic_pool(
        pool,
        _context(MembershipProgram.COOP_MEMBER),
        selector=selector,
        on_date=TODAY,
    )

    assert public.ingredients[0].example_products[0].product_id == "public-winner"
    assert member.ingredients[0].example_products[0].product_id == "member-winner"
    assert member.ingredients[0].best_local_unit_price == 10
    assert {row.product_id for row in member.candidates_by_name["potatis"]} == {
        "public-winner",
        "member-winner",
    }


def test_public_shortlist_support_matches_full_member_projection_exactly() -> None:
    rows = [
        _candidate("potatis", "public-a", 10, package_quantity=500),
        _candidate("potatis", "public-b", 18, package_quantity=1000),
        _candidate("potatis", "public-c", 24, package_quantity=1500),
        _candidate("potatis", "public-d", 31, package_quantity=2000),
        _candidate("potatis", "public-e", 39, package_quantity=2500),
        _candidate("potatis", "member-a", 45, member_price=6),
        _candidate(
            "potatis",
            "member-multibuy",
            20,
            member_price=24,
            member_required_packages=3,
        ),
    ]
    selector = EconomicIngredientSelector(
        taxonomy=(_entry("potatis"),),
        max_candidates_per_store=4,
    )
    base = prepare_economic_pool_for_pricing(
        EconomicIngredientPool(matched_candidates_by_name={"potatis": rows}),
        selector=selector,
    )
    context = _context(MembershipProgram.COOP_MEMBER)
    public = project_economic_pool(
        base,
        _context(),
        selector=selector,
        on_date=TODAY,
    )
    delta = project_economic_pool(
        base,
        context,
        selector=selector,
        on_date=TODAY,
        public_floor_pool=public,
    )
    authoritative_full = project_economic_pool(
        base,
        context,
        selector=selector,
        on_date=TODAY,
    )

    def dump_rows(mapping):
        return {
            canonical: [
                candidate.model_dump(mode="json", exclude_computed_fields=True)
                for candidate in candidates
            ]
            for canonical, candidates in mapping.items()
        }

    assert public.projection_shortlist_support_by_name["potatis"]
    assert [row.model_dump(mode="json") for row in delta.ingredients] == [
        row.model_dump(mode="json") for row in authoritative_full.ingredients
    ]
    assert dump_rows(delta.candidates_by_name) == dump_rows(
        authoritative_full.candidates_by_name
    )
    assert dump_rows(delta.semantic_candidates_by_name) == dump_rows(
        authoritative_full.semantic_candidates_by_name
    )
    public_by_id = {
        candidate.product_id: candidate
        for candidate in public.semantic_candidates_by_name["potatis"]
    }
    delta_by_id = {
        candidate.product_id: candidate
        for candidate in delta.semantic_candidates_by_name["potatis"]
    }
    # Immutable public rows are shared; only candidates whose eligible member
    # contracts can alter economics are copied and reranked.
    assert delta_by_id["public-a"] is public_by_id["public-a"]
    assert delta_by_id["member-a"] is not public_by_id["member-a"]


def test_member_price_is_applied_before_canonical_category_pruning() -> None:
    potato = _candidate("potatis", "potato-public", 10)
    pasta = _candidate("pasta", "pasta-member", 30, member_price=5)
    pool = EconomicIngredientPool(
        # This is the shortlist persisted by the shared PUBLIC build.
        candidates_by_name={"potatis": [potato]},
        semantic_candidates_by_name={"potatis": [potato]},
        # The matcher cache deliberately survives prebuild economic pruning.
        matched_candidates_by_name={"potatis": [potato], "pasta": [pasta]},
    )
    selector = EconomicIngredientSelector(
        taxonomy=(_entry("potatis"), _entry("pasta")),
        max_candidates_per_store=1,
        max_ingredients_per_category={IngredientCategory.CARBOHYDRATE: 1},
    )

    public = project_economic_pool(
        pool,
        _context(),
        selector=selector,
        on_date=TODAY,
    )
    member = project_economic_pool(
        pool,
        _context(MembershipProgram.COOP_MEMBER),
        selector=selector,
        on_date=TODAY,
    )

    assert [signal.canonical for signal in public.ingredients] == ["potatis"]
    assert [signal.canonical for signal in member.ingredients] == ["pasta"]
    assert member.ingredients[0].example_products[0].effective_price == 5
    # The generated economic signal may change, but a fixed public menu must
    # retain its exact purchasable canonical and product candidates.
    assert "potatis" in member.candidates_by_name


def test_member_multibuy_is_applied_before_canonical_category_pruning() -> None:
    potato = _candidate("potatis", "potato-public", 10)
    pasta = _candidate(
        "pasta",
        "pasta-member-multibuy",
        30,
        member_price=15,
        member_required_packages=3,
    )
    pool = EconomicIngredientPool(
        matched_candidates_by_name={"potatis": [potato], "pasta": [pasta]},
    )
    selector = EconomicIngredientSelector(
        taxonomy=(
            _entry("potatis", typical_meal_quantity=1500),
            _entry("pasta", typical_meal_quantity=1500),
        ),
        max_candidates_per_store=1,
        max_ingredients_per_category={IngredientCategory.CARBOHYDRATE: 1},
    )

    public = project_economic_pool(
        pool,
        _context(),
        selector=selector,
        on_date=TODAY,
    )
    member = project_economic_pool(
        pool,
        _context(MembershipProgram.COOP_MEMBER),
        selector=selector,
        on_date=TODAY,
    )

    assert [signal.canonical for signal in public.ingredients] == ["potatis"]
    assert [signal.canonical for signal in member.ingredients] == ["pasta"]
    member_offer = member.candidates_by_name["pasta"][0].offers[0]
    assert member_offer.mechanism is PromotionMechanism.MULTIBUY
    assert member_offer.required_packages == 3


def test_effective_contract_cache_identity_sees_pre_pruning_member_contracts() -> None:
    potato = _candidate("potatis", "potato-public", 10)
    pasta = _candidate("pasta", "pasta-member", 30, member_price=5)
    pool = EconomicIngredientPool(
        candidates_by_name={"potatis": [potato]},
        semantic_candidates_by_name={"potatis": [potato]},
        matched_candidates_by_name={"potatis": [potato], "pasta": [pasta]},
    )

    public_contracts = eligible_member_contract_references(
        pool,
        _context(),
        on_date=TODAY,
    )
    member_contracts = eligible_member_contract_references(
        pool,
        _context(MembershipProgram.COOP_MEMBER),
        on_date=TODAY,
    )

    assert public_contracts == frozenset()
    assert member_contracts == frozenset(
        {"contract:pasta-member:coop-member"}
    )


def test_fixed_menu_cost_is_monotone_when_membership_is_enabled() -> None:
    public_winner = _candidate("potatis", "public-winner", 10)
    member_winner = _candidate(
        "potatis",
        "member-winner",
        30,
        member_price=5,
    )
    pool = EconomicIngredientPool(
        candidates_by_name={"potatis": [public_winner]},
        semantic_candidates_by_name={"potatis": [public_winner]},
        matched_candidates_by_name={"potatis": [public_winner, member_winner]},
    )
    selector = EconomicIngredientSelector(
        taxonomy=(_entry("potatis"),),
        max_candidates_per_store=1,
    )
    public_context = _context()
    member_context = _context(MembershipProgram.COOP_MEMBER)
    public = project_economic_pool(
        pool,
        public_context,
        selector=selector,
        on_date=TODAY,
    )
    member = project_economic_pool(
        pool,
        member_context,
        selector=selector,
        on_date=TODAY,
    )
    fixed_menu = [
        Recipe(
            name="Fast potatismeny",
            servings=4,
            ingredients=[
                RecipeIngredient(
                    name="Potatis",
                    canonical_name="potatis",
                    quantity=500,
                    unit="g",
                )
            ],
            instructions=["Tillaga potatisen."],
        )
    ]
    optimizer = MenuOptimizer()

    before = optimizer.optimize(
        fixed_menu,
        public.candidates_by_name,
        [STORE],
        recipe_count=1,
        max_stores=1,
        user_pricing_context=public_context,
    )
    after = optimizer.optimize(
        fixed_menu,
        member.candidates_by_name,
        [STORE],
        recipe_count=1,
        max_stores=1,
        user_pricing_context=member_context,
    )

    assert before.basket.total == 10
    assert after.basket.total == 5
    assert after.basket.total <= before.basket.total
    selected = after.basket.stores[0].items[0]
    assert selected.membership_program is MembershipProgram.COOP_MEMBER
    assert selected.price_contract_id == "contract:member-winner:coop-member"


def test_fixed_menu_cost_is_monotone_for_membership_superset() -> None:
    potato = _candidate("potatis", "potato-public", 10)
    pasta = _candidate("pasta", "pasta-coop", 30, member_price=5)
    rice = _candidate(
        "ris",
        "rice-ica",
        30,
        member_price=4,
        membership_program=MembershipProgram.ICA_STAMMIS,
        store=ICA_STORE,
    )
    pool = EconomicIngredientPool(
        matched_candidates_by_name={
            "potatis": [potato],
            "pasta": [pasta],
            "ris": [rice],
        },
    )
    selector = EconomicIngredientSelector(
        taxonomy=(_entry("potatis"), _entry("pasta"), _entry("ris")),
        max_candidates_per_store=1,
        max_ingredients_per_category={IngredientCategory.CARBOHYDRATE: 1},
    )
    coop_context = _context(MembershipProgram.COOP_MEMBER)
    all_context = _context(
        MembershipProgram.COOP_MEMBER,
        MembershipProgram.ICA_STAMMIS,
    )
    public = project_economic_pool(
        pool,
        _context(),
        selector=selector,
        on_date=TODAY,
    )
    coop = project_economic_pool(
        pool,
        coop_context,
        selector=selector,
        on_date=TODAY,
        public_floor_pool=public,
    )
    all_memberships = project_economic_pool(
        pool,
        all_context,
        selector=selector,
        on_date=TODAY,
        public_floor_pool=public,
    )
    fixed_menu = [
        Recipe(
            name="Fast pastameny",
            servings=4,
            ingredients=[
                RecipeIngredient(
                    name="Pasta",
                    canonical_name="pasta",
                    quantity=500,
                    unit="g",
                )
            ],
            instructions=["Koka pastan."],
        )
    ]
    optimizer = MenuOptimizer()

    before = optimizer.optimize(
        fixed_menu,
        coop.candidates_by_name,
        [STORE, ICA_STORE],
        recipe_count=1,
        max_stores=2,
        user_pricing_context=coop_context,
    )
    after = optimizer.optimize(
        fixed_menu,
        all_memberships.candidates_by_name,
        [STORE, ICA_STORE],
        recipe_count=1,
        max_stores=2,
        user_pricing_context=all_context,
    )

    assert [signal.canonical for signal in coop.ingredients] == ["pasta"]
    assert [signal.canonical for signal in all_memberships.ingredients] == ["ris"]
    assert "pasta" in all_memberships.candidates_by_name
    assert before.basket.total == after.basket.total == 5


def test_fixed_menu_monotonicity_uses_reconstructed_public_floor() -> None:
    """Member metadata in the prebuild shortlist must not define its public floor."""

    entry = _entry("ris", typical_meal_quantity=320)
    rows = [
        _candidate("ris", "A", 10, package_quantity=320),
        _candidate("ris", "P", 35, package_quantity=1280),
        _candidate(
            "ris",
            "B",
            100,
            member_price=5,
            member_max_quantity=1,
            package_quantity=320,
        ),
        _candidate(
            "ris",
            "C",
            100,
            member_price=9,
            member_required_packages=2,
            member_max_quantity=1,
            package_quantity=320,
        ),
        _candidate(
            "ris",
            "D",
            100,
            member_price=20,
            member_required_packages=5,
            member_max_quantity=1,
            package_quantity=320,
        ),
        _candidate(
            "ris",
            "E",
            100,
            member_price=25,
            member_required_packages=7,
            member_max_quantity=1,
            package_quantity=320,
        ),
    ]
    selector = EconomicIngredientSelector(
        taxonomy=(entry,),
        max_candidates_per_store=4,
    )
    # This deliberately mirrors the shared prebuild before UserPricingContext:
    # BasketCalculator can see generic member offer metadata here, so this is
    # not a trustworthy public monotonicity floor.
    prebuild_shortlist = selector._select_store_candidates(entry, rows)
    assert "P" not in {candidate.product_id for candidate in prebuild_shortlist}
    pool = EconomicIngredientPool(
        candidates_by_name={"ris": prebuild_shortlist},
        semantic_candidates_by_name={"ris": prebuild_shortlist},
        matched_candidates_by_name={"ris": rows},
    )
    public_context = _context()
    member_context = _context(MembershipProgram.COOP_MEMBER)
    public = project_economic_pool(
        pool,
        public_context,
        selector=selector,
        on_date=TODAY,
    )
    member = project_economic_pool(
        pool,
        member_context,
        selector=selector,
        on_date=TODAY,
    )
    fixed_menu = [
        Recipe(
            name="Fyra portioner ris",
            servings=4,
            ingredients=[
                RecipeIngredient(
                    name="Ris",
                    canonical_name="ris",
                    quantity=1280,
                    unit="g",
                )
            ],
            instructions=["Koka riset."],
        )
    ]
    optimizer = MenuOptimizer()

    before = optimizer.optimize(
        fixed_menu,
        public.candidates_by_name,
        [STORE],
        recipe_count=1,
        max_stores=1,
        user_pricing_context=public_context,
    )
    after = optimizer.optimize(
        fixed_menu,
        member.candidates_by_name,
        [STORE],
        recipe_count=1,
        max_stores=1,
        user_pricing_context=member_context,
    )

    assert "P" in {candidate.product_id for candidate in member.candidates_by_name["ris"]}
    assert before.basket.total == 35
    assert after.basket.total == 35
    assert after.basket.total <= before.basket.total


def test_member_contract_cache_fingerprint_is_not_only_source_reference() -> None:
    first = _candidate("pasta", "first", 30, member_price=5)
    second = _candidate("pasta", "second", 30, member_price=4)
    first_offer = first.offers[0].model_copy(
        update={"price_contract_id": "source-local-collision"}
    )
    second_offer = second.offers[0].model_copy(
        update={"price_contract_id": "source-local-collision"}
    )
    first_pool = EconomicIngredientPool(
        matched_candidates_by_name={
            "pasta": [first.model_copy(update={"offers": [first_offer]})]
        }
    )
    second_pool = EconomicIngredientPool(
        matched_candidates_by_name={
            "pasta": [second.model_copy(update={"offers": [second_offer]})]
        }
    )
    context = _context(MembershipProgram.COOP_MEMBER)

    first_fingerprint = eligible_member_contract_fingerprints(
        first_pool,
        context,
        on_date=TODAY,
    )
    second_fingerprint = eligible_member_contract_fingerprints(
        second_pool,
        context,
        on_date=TODAY,
    )

    assert first_fingerprint != second_fingerprint
    assert len(first_fingerprint) == len(second_fingerprint) == 1


def test_economic_selector_cache_identity_includes_pruning_policy() -> None:
    entry = _entry("potatis")
    narrow = EconomicIngredientSelector(
        taxonomy=(entry,),
        max_candidates_per_store=1,
    )
    broad = EconomicIngredientSelector(
        taxonomy=(entry,),
        max_candidates_per_store=2,
    )

    assert narrow.cache_identity != broad.cache_identity


def test_quote_fingerprint_preserves_selected_contract_and_offer_provenance() -> None:
    candidate = _candidate("pasta", "member", 30, member_price=5)
    base = BasketOptimizer._build_candidate_fingerprint(candidate)
    selected_contract = candidate.model_copy(
        update={"selected_price_contract_id": "contract:selected"}
    )
    changed_offer = candidate.offers[0].model_copy(
        update={"source_confidence": "high"}
    )
    offer_provenance = candidate.model_copy(update={"offers": [changed_offer]})

    assert BasketOptimizer._build_candidate_fingerprint(selected_contract) != base
    assert BasketOptimizer._build_candidate_fingerprint(offer_provenance) != base

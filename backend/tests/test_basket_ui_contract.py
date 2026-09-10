from __future__ import annotations

from pathlib import Path

STATIC_DIR = Path(__file__).parents[1] / "app" / "static"


def _read(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


def test_basket_verification_status_has_accessible_ui_hooks_and_safe_copy() -> None:
    html = _read("index.html")
    javascript = _read("app.js")

    for hook in (
        'id="basket-verification"',
        'id="basket-verification-title"',
        'id="basket-verification-description"',
        'id="basket-verification-warnings"',
        'id="basket-total-label"',
    ):
        assert hook in html

    for status in (
        "VERIFIED",
        "VERIFIED_WITH_ESTIMATES",
        "UNVERIFIED",
        "INVALID",
    ):
        assert status in javascript

    assert "Matkasse verifierad" in javascript
    assert "Matkassen innehåller uppskattade lösvikter" in javascript
    assert "Matkassen är inte verifierad" in javascript
    assert "Matkassen är ogiltig" in javascript
    assert "inte ett säkert exakt totalpris" in javascript
    assert "Använd inte priset" in javascript
    assert "verification_warnings" in javascript
    assert "function basketVerificationRank(value)" in javascript
    assert "function worstBasketVerification(...values)" in javascript
    assert 'first(option, ["verification_status"], "UNVERIFIED")' in javascript
    assert "displayBasketMoney" in javascript


def test_comparisons_scenarios_and_tradeoff_preserve_verification_semantics() -> None:
    html = _read("index.html")
    javascript = _read("app.js")

    # The backend prices the selected menu in one grocery price context; that
    # context may be online and is not proof of a verified physical store.
    assert "samma meny i en enda giltig priskontext" in html
    assert "Samma meny i billigaste giltiga priskontext" in javascript
    assert "Samma meny i en giltig priskontext" in javascript
    assert "verifierad butik" not in html.casefold()
    assert "verifierad butik" not in javascript.casefold()
    assert "Bästa kvalitetsgodkända enbutiksmeny" not in javascript

    comparison = javascript[javascript.index("function explicitSingleStore(data)") :]
    comparison = comparison[: comparison.index("function optimizationStrategyLabel")]
    assert "basketVerificationRank" in comparison
    assert "displayBasketMoney" in comparison
    assert "worstBasketVerification" in comparison

    scenarios = javascript[javascript.index("function renderScenarios(data)") :]
    scenarios = scenarios[: scenarios.index("function optimizationStrategyLabel")]
    assert "verificationStatus" in scenarios
    assert "displayBasketMoney" in scenarios

    tradeoff = javascript[javascript.index("function renderStoreTradeoff(data)") :]
    tradeoff = tradeoff[: tradeoff.index("function warningText")]
    assert "one_store_verification_status" in tradeoff
    assert "selected_verification_status" in tradeoff
    assert "displayBasketMoney" in tradeoff

    optimization = javascript[javascript.index("function renderOptimizationSettings(data)") :]
    optimization = optimization[: optimization.index("function renderQuality")]
    assert "basket.verification_status" in optimization
    assert "optimized_basket.verification_status" in optimization
    assert "displayBasketMoney" in optimization
    assert "worstBasketVerification" in optimization


def test_diversity_premiums_use_the_worst_status_of_both_compared_plans() -> None:
    javascript = _read("app.js")

    premium_helper = javascript[javascript.index("function diversityPremiumVerification") :]
    premium_helper = premium_helper[: premium_helper.index("function planOptionCard")]
    assert 'plans.get("balanced")' in premium_helper
    assert '"optimized_basket.verification_status"' in premium_helper
    assert "worstBasketVerification(optionStatus, balancedStatus)" in premium_helper

    option_card = javascript[javascript.index("function planOptionCard") :]
    option_card = option_card[: option_card.index("function renderPlanOptions")]
    assert "diversityPremiumVerification(option, plans)" in option_card
    assert "appendVariationExplanation(button, option, mode, premiumVerification)" in option_card
    assert 'displayBasketMoney(first(option, ["premium_vs_balanced"], 0)' in javascript
    assert "premiumVerification" in option_card
    assert 'formatMoney(first(option, ["premium_vs_cheapest"]' not in option_card

    active_summary = javascript[javascript.index("function renderActivePlanSummary") :]
    active_summary = active_summary[: active_summary.index("function alternativePlanView")]
    assert "diversityPremiumVerification" in active_summary
    assert "appendVariationExplanation(dom.activePlanSummary" in active_summary
    assert "premiumVerification" in active_summary
    assert 'formatMoney(first(data, ["premium_vs_cheapest"]' not in active_summary


def test_shopping_rows_branch_on_every_sale_model_without_weight_package_fallback() -> None:
    javascript = _read("app.js")

    for sale_model in (
        "fixed_package",
        "sold_by_weight",
        "sold_by_piece",
        "variable_weight_package",
        "unknown",
    ):
        assert sale_model in javascript

    assert 'return { text: "Lösvikt"' in javascript
    assert 'return approximateText(purchased) || "Lösvikt saknas"' in javascript
    assert "saleRateText(item)" in javascript
    assert 'return { text: "Okänd"' in javascript
    assert 'if (packageText && saleModel === "fixed_package")' in javascript
    assert 'if (packageText && saleModel === "variable_weight_package")' in javascript
    assert 'saleModel === "sold_by_weight"' in javascript
    assert 'saleModel === "sold_by_piece"' in javascript


def test_weight_rate_prefers_applied_sale_rate_and_comparison_is_only_fallback() -> None:
    javascript = _read("app.js")
    sale_rate = javascript[javascript.index("function saleRateText(item)") :]
    sale_rate = sale_rate[: sale_rate.index("function purchaseBadge")]

    assert '"sale_price"' in sale_rate
    assert '"sale_unit"' in sale_rate
    assert '"comparison_price"' in sale_rate
    assert '"comparison_unit"' in sale_rate
    assert "if (appliedRate) return appliedRate;" in sale_rate
    assert "return ratePairText(comparisonPrice, comparisonUnit);" in sale_rate

    # Applied 29.90 kr/kg must win even if comparison metadata says 39.90 kr/kg.
    assert sale_rate.index('"sale_price"') < sale_rate.index('"comparison_price"')
    assert sale_rate.index("if (appliedRate) return appliedRate;") < sale_rate.index(
        '"comparison_price"'
    )

    # The early return also covers products with a sale rate but no comparison pair.
    assert sale_rate.index('"sale_unit"') < sale_rate.index("if (appliedRate) return appliedRate;")


def test_verification_and_purchase_state_have_visible_styles() -> None:
    css = _read("styles.css")

    for selector in (
        ".basket-verification",
        ".basket-verification.has-estimates",
        ".basket-verification.is-unverified",
        ".basket-verification.is-invalid",
        ".purchase-kind",
        ".purchase-kind-estimate",
        ".purchase-kind-unknown",
    ):
        assert selector in css


def test_result_transparency_explains_universe_freshness_and_price_context() -> None:
    javascript = _read("app.js")

    assert "förbyggt federerat prisuniversum" in javascript
    assert "online- eller butikskopplade" in javascript
    assert '"oldest_price_age_hours"' in javascript
    assert "Priser uppdaterade idag" in javascript
    assert "närmar sig stale-gränsen" in javascript
    assert "garanterade hyllpriser" in javascript

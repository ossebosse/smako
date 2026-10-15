from __future__ import annotations

from pathlib import Path

STATIC = Path(__file__).parents[1] / "app" / "static"


def test_consumer_planner_exposes_supported_primary_choices() -> None:
    page = (STATIC / "index.html").read_text(encoding="utf-8")

    assert 'id="recipes"' in page
    assert all(f'<option value="{count}"' in page for count in range(3, 8))
    assert 'id="servings"' in page and 'max="8"' in page
    assert 'id="max-stores"' in page
    assert '<option value="3">3 inköpsställen</option>' in page
    assert '<option value="4">4 inköpsställen</option>' not in page
    assert 'id="diet-preference"' in page
    assert 'value="vegetarian"' in page
    assert 'value="vegan"' in page
    assert 'name="membership"' in page
    assert 'value="ICA_STAMMIS"' in page
    assert 'value="COOP_MEMBER"' in page
    assert 'value="HEMKOP_MEMBER"' in page
    assert 'value="LIDL_PLUS"' in page
    assert 'name="availability_mode" value="strict"' in page
    assert "Verifierade medlemspriser används endast" in page
    assert "kräver ingen prisuppdatering" in page
    assert "Strikt (beta)" in page
    assert "styr ännu inte produktvalet" in page
    assert "Föredra varor med stark butiksspecifik evidens" not in page


def test_online_price_context_is_not_presented_as_verified_physical_store() -> None:
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    script = (STATIC / "app.js").read_text(encoding="utf-8")

    assert "Samma meny i billigaste giltiga priskontext" in script
    assert "Samma meny i en giltig priskontext" in script
    assert "verifierad butik" not in page.casefold()
    assert "verifierad butik" not in script.casefold()
    assert "inköpsställen" in page
    assert "Coop Online Syd · onlinepris" in script


def test_consumer_ui_has_report_and_reused_barcode_flows() -> None:
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    script = (STATIC / "app.js").read_text(encoding="utf-8")

    assert '/scanner-assets/physical-barcode-scanner.js' in page
    assert 'id="scan-entry-button"' in page
    assert 'id="report-dialog"' in page
    assert 'id="report-physical-store"' in page
    assert 'PRODUCT_NOT_FOUND' in page
    assert 'PRICE_DIFFERENCE' in page
    assert 'PROMOTION_MISSING_FROM_APP' in page
    assert 'window.GroceryBarcodeScanner.createBarcodeScanner' in script
    assert ': "/api/community-evidence";' in script
    assert "/products/${encodeURIComponent(reportContext.source_product_id)}/report" in script
    assert "const requestPayload = isSavedPlanProduct" in script
    assert "/api/community-evidence/store-options" in script
    assert 'fetch(`/api/products/${encodeURIComponent(gtin)}`' in script
    assert 'jobRequest({scope:"public",url:"/api/plans"' in script
    assert "/replace-recipe" in script
    assert "/replace-product" in script
    assert "grocery-anonymous-session-id" in script
    assert "price_snapshot_id" in script
    assert "source snapshot" not in page.casefold()


def test_saved_plan_product_reports_do_not_trust_client_provenance() -> None:
    script = (STATIC / "app.js").read_text(encoding="utf-8")

    bound_payload = script.split(
        "const requestPayload = isSavedPlanProduct", maxsplit=1
    )[1].split("} : payload;", maxsplit=1)[0]
    assert "source_product_id" not in bound_payload
    assert "price_snapshot_id" not in bound_payload
    assert "digital_price" not in bound_payload
    assert "grocery_context_id" not in bound_payload
    assert "physical_store_id" in bound_payload
    assert "shelf_price" in bound_payload
    assert '"PRODUCT_IDENTITY_CORRECTION"' in script


def test_consumer_ui_never_silently_applies_community_price() -> None:
    page = (STATIC / "index.html").read_text(encoding="utf-8")

    assert "ändrar aldrig prisdatakällan direkt" in page
    assert "inte att den säkert är slut" in (STATIC / "app.js").read_text(
        encoding="utf-8"
    )


def test_consumer_provenance_does_not_mislabel_price_context_as_physical_store() -> None:
    script = (STATIC / "app.js").read_text(encoding="utf-8")

    physical_mapping = script.split("physical_store_id:", maxsplit=1)[1].split(
        "grocery_context_id:", maxsplit=1
    )[0]
    grocery_mapping = script.split("grocery_context_id:", maxsplit=1)[1].split(
        "store_display_name:", maxsplit=1
    )[0]
    assert '"store_id"' not in physical_mapping
    assert '"store_id"' in grocery_mapping
    assert "source_provider_store_id" in script
    snapshot_mapping = script.split("price_snapshot_id:", maxsplit=1)[1].split(
        "physical_store_id:", maxsplit=1
    )[0]
    assert "source_provenance.source_snapshot_id" in snapshot_mapping
    assert "price_universe_id" not in snapshot_mapping


def test_community_promotion_uses_api_wire_values() -> None:
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    script = (STATIC / "app.js").read_text(encoding="utf-8")

    assert 'dom.promotionMember.checked ? "member" : "public"' in script
    assert 'multibuy ? "multibuy" : "sale_price"' in script
    assert 'multibuy ? "MULTIBUY" : "UNIT_SALE"' not in script
    assert 'id="promotion-quantity" type="number" min="2"' in page
    assert "(promotion.required_quantity || 0) < 2" in script


def test_membership_preferences_use_stable_program_ids_and_label_selected_prices() -> None:
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    script = (STATIC / "app.js").read_text(encoding="utf-8")

    assert 'id="membership-plan-summary"' in page
    assert 'membershipPreferenceKey = "grocery-membership-programs-v1"' in script
    assert "window.localStorage.setItem(membershipPreferenceKey" in script
    assert '"request.membership_programs"' in script
    assert "Kräver ${membershipLabel(program)}" in script
    assert "Medlemspris ${formatMoney(applied)}" in script
    assert "memberships.length > 0" in script
    assert "Ordinarie: ${regular}" in script
    assert "Publik kampanj: ${publicPrice}" in script
    assert "Gäller för dig" in script
    assert 'first(data, ["membership_coverage"], [])' in script
    assert 'first(data, ["membership_savings"])' in script
    assert "på exakt samma varor och mängder" in script


def test_consumer_v1_has_truthful_loading_and_mobile_result_landmarks() -> None:
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    script = (STATIC / "app.js").read_text(encoding="utf-8")
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")

    assert "Vad ska vi äta den här veckan?" in page
    assert "Skapa veckomeny" in page
    assert 'id="loading-state"' in page and 'role="status"' in page
    assert "Vi söker vidare tills en komplett, prisberäknad plan är klar" in page
    assert "window.setInterval" not in script
    assert "Skapar och validerar receptkandidater" not in script
    assert 'id="menu-section"' in page
    assert 'id="shopping-section"' in page
    assert 'class="result-jump-nav"' in page
    assert "shoppingColumns" in script
    assert "cell.dataset.label" in script
    assert "@media (max-width: 720px)" in styles
    assert ".shopping-table td::before" in styles
    assert "content: attr(data-label)" in styles
    assert 'first(data, ["recipe_costs"], [])' in script
    assert "Receptets extra råvarukostnad" in script
    assert "Kostnad per portion" in script
    assert "overflow-x: clip" in styles
    assert ".hero {" in styles and "overflow: clip" in styles
    assert styles.count("min-height: 44px") >= 5
    assert "canonical PoC" not in page
    assert "proof of concept" not in page.casefold()


def test_consumer_v1_surfaces_saved_plan_freshness_and_community_actions() -> None:
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    script = (STATIC / "app.js").read_text(encoding="utf-8")

    assert 'id="price-freshness"' in page
    assert 'id="plan-persistence-status"' in page
    assert 'id="copy-plan-link"' in page
    assert 'id="new-prices-banner"' in page
    assert 'id="recalculate-plan-button"' in page
    assert "function renderPriceFreshness" in script
    assert 'status === "degraded"' in script
    assert "Senast kända baspriser används, och utgångna kampanjpriser används inte." in script
    assert 'id="compared-sources"' in page
    assert 'id="unavailable-sources"' in page
    assert "Jämförda priskällor" in page
    assert "kunde inte jämföras eftersom prisunderlaget behöver uppdateras" in script
    assert "priceContextCoverageLabel" in script
    assert "context_id" in script
    assert "function updatePlanPersistence" in script
    assert "function copyCurrentPlanLink" in script
    assert "function applySavedRequestToForm" in script
    assert 'price_version_status: payload.price_version_status' in script
    assert "price_contexts_changed_since_creation" in script
    assert 'versionStatus === "coverage_changed"' in script
    assert "priset från när den skapades" in script
    assert "dom.form.requestSubmit()" in script
    assert 'fragment.set("plan", String(planId))' in script
    assert 'url.searchParams.set("plan", planId)' not in script
    assert 'lastPlanStorageKey = "grocery-last-plan-id-v1"' in script
    assert "window.localStorage.setItem(lastPlanStorageKey, plan.plan_id)" in script
    assert "urlPlanId || locallySavedPlanId" in script
    assert 'id="scan-result-button"' in page
    assert "Streckkoden identifierar varan" in page
    assert "sparas separat och ersätter aldrig prisdata automatiskt" in page
    assert "window.GroceryBarcodeScanner.createBarcodeScanner" in script


def test_planner_admission_full_has_retryable_consumer_copy_without_disabling_service() -> None:
    script = (STATIC / "app.js").read_text(encoding="utf-8")

    assert 'normalizedCode === "planner_admission_full"' in script
    assert "Det är många som skapar menyer just nu" in script
    assert "Math.max(1, Math.ceil(parsedRetry))" in script
    assert 'response.headers.get("Retry-After")' in script
    assert 'responseErrorCode.startsWith("price_universe_")' in script
    assert "setTimeout(submitPlan" not in script
    assert 'if (activePlanRequest) return;' in script


def test_consumer_v1_keeps_debug_explicit_and_accessible() -> None:
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    script = (STATIC / "app.js").read_text(encoding="utf-8")
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")

    assert 'id="results-title" tabindex="-1"' in page
    assert 'id="debug-notice"' in page and "data-debug-only" in page
    assert 'debug: debugMode' in script
    assert 'dom.debugNotice.hidden = !debugMode' in script
    assert "prefersReducedMotion" in script
    assert 'dom.reportDialog.addEventListener("cancel"' in script
    assert "input:focus-visible" in styles
    assert "@media (prefers-reduced-motion: reduce)" in styles


def test_membership_badge_prefers_program_identity_and_labels_price_scope() -> None:
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    script = (STATIC / "app.js").read_text(encoding="utf-8")

    assert 'value="WILLYS_PLUS"' in page
    assert 'WILLYS_PLUS: { label: "Willys Plus"' in script
    membership_function = script.split("function membershipProgramFor", maxsplit=1)[1].split(
        "function membershipLabel", maxsplit=1
    )[0]
    assert membership_function.index('"membership_program"') < membership_function.index(
        '"membership_required"'
    )
    assert 'typeof legacyRequired !== "string"' in membership_function
    assert "function priceContextLabel" in script
    assert "Coop Online Syd · onlinepris" in script
    assert "Priskontext ${contextId}" in script

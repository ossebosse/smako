from __future__ import annotations

from pathlib import Path

STATIC = Path(__file__).parents[1] / "app" / "static"
MOBILE_E2E = Path(__file__).parents[1] / "scripts" / "consumer_mobile_e2e.py"


def test_first_visit_onboarding_is_short_consumer_copy() -> None:
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    script = (STATIC / "app.js").read_text(encoding="utf-8")

    assert 'id="onboarding-dialog"' in page
    assert "Vi jämför matpriser." in page
    assert "Vi bygger recept utifrån vad som är billigt." in page
    assert "Du får en färdig inköpslista." in page
    assert "Skapa min veckomeny" in page
    assert 'onboardingSeenKey = "grocery-beta-onboarding-seen-v1"' in script
    assert "showFirstVisitOnboarding()" in script


def test_beta_geography_and_online_scope_are_explicit() -> None:
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    normalized = " ".join(page.split())

    assert "Publik beta i Lund" in page
    assert "Betan jämför just nu" in page and "kring Lund" in page
    assert 'class="online-price-explanation"' in page
    assert "inte ett bekräftat hyllpris" in normalized
    assert "garanti att varan finns" in normalized


def test_all_requested_preferences_persist_locally_and_can_be_cleared() -> None:
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    script = (STATIC / "app.js").read_text(encoding="utf-8")

    assert 'id="clear-preferences-button"' in page
    assert 'plannerPreferenceKey = "grocery-planner-preferences-v1"' in script
    assert "postal_code: dom.postalCode.value.trim()" in script
    assert "recipes: Number(dom.recipesInput.value)" in script
    assert "servings: Number(dom.servingsInput.value)" in script
    assert "max_stores: Number(dom.maxStoresInput.value)" in script
    assert "diet_preference: dom.dietPreference.value" in script
    assert "diversity_mode: selectedDiversityMode()" in script
    assert "memberships: selectedMemberships()" in script
    assert "window.localStorage.removeItem(plannerPreferenceKey)" in script
    assert "window.localStorage.removeItem(membershipPreferenceKey)" in script
    assert "window.crypto?.randomUUID" in script
    assert "window.crypto?.getRandomValues" in script
    session_generator = script.split("function createAnonymousSessionId", maxsplit=1)[1].split(
        "const anonymousSessionId",
        maxsplit=1,
    )[0]
    assert "Math.random" not in session_generator


def test_general_feedback_has_stable_safe_contract() -> None:
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    script = (STATIC / "app.js").read_text(encoding="utf-8")

    assert 'id="feedback-entry-button"' in page
    assert 'id="feedback-dialog"' in page
    assert 'value="something_broken"' in page
    assert 'value="wrong_price"' in page
    assert 'value="wrong_recipe"' in page
    assert 'value="missing_store"' in page
    assert 'value="suggestion"' in page
    assert 'value="other"' in page
    assert 'id="feedback-email"' in page and "valfritt" in page
    assert 'fetch("/api/feedback"' in script
    assert "anonymous_session_id: anonymousSessionId" in script
    assert "page_context: window.location.pathname" in script
    assert "cookies" not in script.split('fetch("/api/feedback"', maxsplit=1)[1].split(")", maxsplit=1)[0].casefold()


def test_first_party_events_and_frontend_errors_use_allowlisted_context() -> None:
    script = (STATIC / "app.js").read_text(encoding="utf-8")

    for event_name in (
        "planner_opened",
        "plan_requested",
        "plan_succeeded",
        "plan_failed",
        "diet_selected",
        "mode_selected",
        "max_stores_selected",
        "membership_enabled",
        "recipe_opened",
        "recipe_replaced",
        "shopping_list_opened",
        "product_report_created",
        "barcode_scan_success",
        "barcode_scan_unknown",
    ):
        assert f'"{event_name}"' in script
    assert 'fetch("/api/analytics/events"' in script
    assert 'fetch("/api/frontend-errors"' in script
    assert "safeEventProperties" in script
    assert "event.stack" not in script
    assert "document.cookie" not in script
    assert "route: window.location.pathname.slice(0, 300)" in script
    assert "window.location.pathname}${window.location.search}" not in script


def test_saved_plan_links_use_fragment_and_migrate_legacy_query() -> None:
    script = (STATIC / "app.js").read_text(encoding="utf-8")

    assert 'fragment.set("plan", String(planId))' in script
    assert 'url.searchParams.delete("plan")' in script
    assert "migrateLegacyPlanQuery()" in script
    assert 'url.searchParams.set("plan"' not in script
    assert 'window.localStorage.removeItem(lastPlanStorageKey)' in script
    assert 'window.localStorage.removeItem(anonymousSessionStorageKey)' in script


def test_saved_plan_id_survives_temporary_outage_and_only_404_or_410_clears_it() -> None:
    script = (STATIC / "app.js").read_text(encoding="utf-8")

    assert "const definitivelyGone = error?.httpStatus === 404 || error?.httpStatus === 410" in script
    assert "if (!urlPlanId && definitivelyGone)" in script
    assert "Plan-ID:t finns kvar på den här enheten" in script
    assert "Den sparade planen kunde inte hämtas just nu" in script


def test_planner_fails_closed_with_swedish_readiness_copy() -> None:
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    script = (STATIC / "app.js").read_text(encoding="utf-8")

    assert 'id="service-availability-banner"' in page
    assert 'id="service-retry-button"' in page
    assert 'id="submit-button" class="primary-button" type="submit" disabled' in page
    assert 'fetch("/ready"' in script
    assert "setPlannerReadiness(ready)" in script
    assert 'serviceRetryButton.addEventListener("click"' in script
    assert (
        'if (response.status === 503 && responseErrorCode.startsWith("price_universe_")'
        in script
    )
    assert 'normalizedCode === "planner_admission_full"' in script
    assert 'response.headers.get("Retry-After")' in script
    assert "Prisunderlaget är inte tillgängligt just nu" in script
    assert 'first(payload, ["status"], "not_ready") === "ready"' in script


def test_mobile_e2e_gates_browser_errors_and_marks_local_tls_bypass() -> None:
    runner = MOBILE_E2E.read_text(encoding="utf-8")

    assert '"#plan=" in saved_plan_url and "?plan=" not in saved_plan_url' in runner
    assert 'assert_check(checks, "no_console_errors", not console_errors' in runner
    assert 'assert_check(checks, "no_page_errors", not page_errors' in runner
    assert "ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)" in runner
    assert '"tls_verification_bypassed": ignore_https_errors' in runner


def test_privacy_and_beta_terms_are_factual_and_linked() -> None:
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    privacy = (STATIC / "privacy.html").read_text(encoding="utf-8")
    terms = (STATIC / "beta-terms.html").read_text(encoding="utf-8")

    assert 'href="/static/privacy.html"' in page
    assert 'href="/static/beta-terms.html"' in page
    assert "Ingen exakt plats" in privacy
    assert "Inga retailer-lösenord" in privacy
    assert "högst 180 dagar" in privacy
    assert "lagringstid 0 timmar" in privacy
    assert "IP-adresser eller frågesträngar" in privacy
    assert "Policy-TODO" in privacy
    assert 'id="privacy-erasure-form"' in privacy
    assert 'src="/static/privacy.js"' in privacy
    assert "Radera mina uppgifter" in privacy
    assert "högst 14 dagar" in privacy
    assert "automatisk återspelning" in privacy
    assert "före en bredare lansering" in privacy
    assert "Kontrollera alltid slutpriset" in terms
    assert "Online-sortiment är inte en garanti" in terms
    assert "Juridisk TODO" in terms


def test_privacy_erasure_is_confirmed_same_origin_and_clears_local_data_after_success() -> None:
    privacy = (STATIC / "privacy.html").read_text(encoding="utf-8")
    script = (STATIC / "privacy.js").read_text(encoding="utf-8")

    assert "<script>" not in privacy
    assert 'id="privacy-erasure-confirm"' in privacy
    assert "window.confirm" in script
    assert 'fetch("/api/privacy/erase"' in script
    assert 'credentials: "same-origin"' in script
    assert 'window.localStorage.getItem("grocery-anonymous-session-id")' not in script
    assert "window.localStorage.getItem(anonymousSessionStorageKey)" in script
    assert "if (!response.ok)" in script
    assert script.index("if (!response.ok)") < script.index("window.localStorage.clear()")

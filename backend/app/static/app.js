(() => {
  "use strict";

  const moneyFormatter = new Intl.NumberFormat("sv-SE", {
    style: "currency",
    currency: "SEK",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  const numberFormatter = new Intl.NumberFormat("sv-SE", {
    maximumFractionDigits: 2,
  });

  const percentFormatter = new Intl.NumberFormat("sv-SE", {
    style: "percent",
    minimumFractionDigits: 0,
    maximumFractionDigits: 1,
  });

  const prefersReducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches === true;

  const dom = {
    form: document.querySelector("#plan-form"),
    postalCode: document.querySelector("#postal-code"),
    postalError: document.querySelector("#postal-error"),
    recipesInput: document.querySelector("#recipes"),
    servingsInput: document.querySelector("#servings"),
    maxStoresInput: document.querySelector("#max-stores"),
    purchasePlanningMode: document.querySelector("#purchase-planning-mode"),
    dietPreference: document.querySelector("#diet-preference"),
    variedBudget: document.querySelector("#varied-budget"),
    membershipInputs: document.querySelectorAll('input[name="membership"]'),
    availabilityInputs: document.querySelectorAll('input[name="availability_mode"]'),
    excludedIngredients: document.querySelector("#excluded-ingredients"),
    clearPreferencesButton: document.querySelector("#clear-preferences-button"),
    preferencesStatus: document.querySelector("#preferences-status"),
    diversityInputs: document.querySelectorAll('input[name="diversity_mode"]'),
    submitButton: document.querySelector("#submit-button"),
    submitLabel: document.querySelector("#submit-button .button-label"),
    formChip: document.querySelector(".form-chip"),
    statusRegion: document.querySelector("#status-region"),
    loadingState: document.querySelector("#loading-state"),
    loadingMessage: document.querySelector("#loading-message"),
    errorState: document.querySelector("#error-state"),
    errorMessage: document.querySelector("#error-message"),
    results: document.querySelector("#results"),
    resultsTitle: document.querySelector("#results-title"),
    resultLocation: document.querySelector("#result-location"),
    priceFreshness: document.querySelector("#price-freshness"),
    planPersistenceStatus: document.querySelector("#plan-persistence-status"),
    copyPlanLink: document.querySelector("#copy-plan-link"),
    newPricesBanner: document.querySelector("#new-prices-banner"),
    newPricesTitle: document.querySelector("#new-prices-title"),
    newPricesMessage: document.querySelector("#new-prices-message"),
    recalculatePlanButton: document.querySelector("#recalculate-plan-button"),
    debugNotice: document.querySelector("#debug-notice"),
    summaryMeals: document.querySelector("#summary-meals"),
    summaryServings: document.querySelector("#summary-servings"),
    summaryStores: document.querySelector("#summary-stores"),
    summaryTotal: document.querySelector("#summary-total"),
    summaryPerServing: document.querySelector("#summary-per-serving"),
    membershipPlanSummary: document.querySelector("#membership-plan-summary"),
    planOptionsPanel: document.querySelector("#plan-options-panel"),
    planOptionsList: document.querySelector("#plan-options-list"),
    activePlanSummary: document.querySelector("#active-plan-summary"),
    primaryPlanNote: document.querySelector("#primary-plan-note"),
    recipesList: document.querySelector("#recipes-list"),
    ingredientsList: document.querySelector("#ingredients-list"),
    basketVerification: document.querySelector("#basket-verification"),
    basketVerificationIcon: document.querySelector("#basket-verification-icon"),
    basketVerificationTitle: document.querySelector("#basket-verification-title"),
    basketVerificationDescription: document.querySelector("#basket-verification-description"),
    basketVerificationWarnings: document.querySelector("#basket-verification-warnings"),
    storeGroups: document.querySelector("#store-groups"),
    basketTotalLabel: document.querySelector("#basket-total-label"),
    basketTotal: document.querySelector("#basket-total"),
    portionsMetric: document.querySelector("#portions-metric"),
    totalPortions: document.querySelector("#total-portions"),
    portionPriceMetric: document.querySelector("#portion-price-metric"),
    pricePerPortion: document.querySelector("#price-per-portion"),
    comparisonPanel: document.querySelector("#comparison-panel"),
    comparisonCards: document.querySelector("#comparison-cards"),
    scenariosPanel: document.querySelector("#scenarios-panel"),
    optimizationScenarios: document.querySelector("#optimization-scenarios"),
    optimizationSettingsPanel: document.querySelector("#optimization-settings-panel"),
    optimizationSettingsMetrics: document.querySelector("#optimization-settings-metrics"),
    qualityPanel: document.querySelector("#quality-panel"),
    qualityOverview: document.querySelector("#quality-overview"),
    nutritionQualitySection: document.querySelector("#nutrition-quality-section"),
    nutritionQualityList: document.querySelector("#nutrition-quality-list"),
    diversityQualitySection: document.querySelector("#diversity-quality-section"),
    diversityQualityMetrics: document.querySelector("#diversity-quality-metrics"),
    surplusPanel: document.querySelector("#surplus-panel"),
    surplusSummary: document.querySelector("#surplus-summary"),
    surplusItems: document.querySelector("#surplus-items"),
    storeTradeoffPanel: document.querySelector("#store-tradeoff-panel"),
    storeTradeoffCards: document.querySelector("#store-tradeoff-cards"),
    sourceDescription: document.querySelector("#source-description"),
    comparedSources: document.querySelector("#compared-sources"),
    comparedSourcesList: document.querySelector("#compared-sources-list"),
    unavailableSources: document.querySelector("#unavailable-sources"),
    unavailableSourcesList: document.querySelector("#unavailable-sources-list"),
    warningsList: document.querySelector("#warnings-list"),
    footerSource: document.querySelector("#footer-source"),
    newPlanButton: document.querySelector("#new-plan-button"),
    scanEntryButton: document.querySelector("#scan-entry-button"),
    scanResultButton: document.querySelector("#scan-result-button"),
    reportDialog: document.querySelector("#report-dialog"),
    reportForm: document.querySelector("#report-form"),
    reportType: document.querySelector("#report-type"),
    reportProductSummary: document.querySelector("#report-product-summary"),
    reportStoreRequirement: document.querySelector("#report-store-requirement"),
    reportPhysicalStore: document.querySelector("#report-physical-store"),
    reportPriceFields: document.querySelector("#report-price-fields"),
    reportPromotionFields: document.querySelector("#report-promotion-fields"),
    reportedPrice: document.querySelector("#reported-price"),
    reportedPriceUnit: document.querySelector("#reported-price-unit"),
    promotionMember: document.querySelector("#promotion-member"),
    promotionMultibuy: document.querySelector("#promotion-multibuy"),
    promotionRegularPrice: document.querySelector("#promotion-regular-price"),
    promotionQuantity: document.querySelector("#promotion-quantity"),
    promotionTotal: document.querySelector("#promotion-total"),
    reportStatus: document.querySelector("#report-status"),
    reportSubmit: document.querySelector("#report-submit"),
    scannerDialog: document.querySelector("#scanner-dialog"),
    scannerCamera: document.querySelector("#scanner-camera"),
    scannerVideo: document.querySelector("#scanner-video"),
    scannerStatus: document.querySelector("#scanner-status"),
    scannerStart: document.querySelector("#scanner-start"),
    scannerCancel: document.querySelector("#scanner-cancel"),
    manualGtin: document.querySelector("#manual-gtin"),
    manualGtinSubmit: document.querySelector("#manual-gtin-submit"),
    scannerResult: document.querySelector("#scanner-result"),
    alternativesDialog: document.querySelector("#product-alternatives-dialog"),
    alternativesSummary: document.querySelector("#product-alternatives-summary"),
    alternativesList: document.querySelector("#product-alternatives-list"),
    alternativesStatus: document.querySelector("#product-alternatives-status"),
    onboardingDialog: document.querySelector("#onboarding-dialog"),
    onboardingCta: document.querySelector("#onboarding-cta"),
    feedbackEntryButton: document.querySelector("#feedback-entry-button"),
    footerFeedbackButton: document.querySelector("#footer-feedback-button"),
    feedbackDialog: document.querySelector("#feedback-dialog"),
    feedbackForm: document.querySelector("#feedback-form"),
    feedbackCategory: document.querySelector("#feedback-category"),
    feedbackMessage: document.querySelector("#feedback-message"),
    feedbackEmail: document.querySelector("#feedback-email"),
    feedbackStatus: document.querySelector("#feedback-status"),
    feedbackSubmit: document.querySelector("#feedback-submit"),
    appVersion: document.querySelector("#app-version"),
    serviceAvailabilityBanner: document.querySelector("#service-availability-banner"),
    serviceAvailabilityTitle: document.querySelector("#service-availability-title"),
    serviceAvailabilityMessage: document.querySelector("#service-availability-message"),
    serviceRetryButton: document.querySelector("#service-retry-button"),
  };

  let currentResponse = null;
  let savedPlanRequest = null;
  let primaryPlanMode = "balanced";
  let activePlanMode = "balanced";
  let reportContext = null;
  let reportIdempotencyKey = null;
  let physicalStoreOptions = [];
  let physicalStoreOptionsPromise = null;
  let activeScanner = null;
  let plannerReady = false;
  // Transient request ownership is never persisted or inferred from restored DOM.
  const FRONTEND_VERSION = "complete-recipes-1";
  const recipeControls = window.SmakoRecipes.controls(document.getElementById("complete-recipe-controls"));
  // Same bounded wait as personal planning; the public proxy permits 540 s.
  const PLAN_WAIT_MS = 600000;
  let activePlanRequest = null;
  let savedPlanController = null;
  let planViewEpoch = 0;

  async function boundedRequest(controller, timeoutMs, work) {
    let timer;
    let onAbort;
    const interrupted = new Promise((_, reject) => {
      onAbort = () => reject(controller.signal.reason || new DOMException("Avbruten", "AbortError"));
      controller.signal.addEventListener("abort", onAbort, { once: true });
      timer = window.setTimeout(() => controller.abort(new DOMException("Väntetiden tog slut", "TimeoutError")), timeoutMs);
      if (controller.signal.aborted) onAbort();
    });
    try { return await Promise.race([work(controller.signal), interrupted]); }
    finally {
      window.clearTimeout(timer);
      controller.signal.removeEventListener("abort", onAbort);
    }
  }

  async function planningResponse(response) {
    const type = response.headers.get("Content-Type") || "";
    let data = null;
    if (/application\/(?:[a-z0-9.-]+\+)?json(?:;|$)/i.test(type)) {
      try { data = await response.json(); } catch (_error) { /* Checked below. */ }
    }
    response.smakoCheck?.();
    if (!response.ok) return { response, data };
    const plan = planFromEnvelope(data);
    if (!plan || !Array.isArray(plan.recipes) || !plan.recipes.length
        || !plan.optimized_basket || !Array.isArray(plan.optimized_basket.stores)) {
      throw new Error("Servern skickade ett ogiltigt planeringsresultat. Försök igen.");
    }
    return { response, data };
  }

  function reconcilePlanningState() {
    if (activePlanRequest && Date.now() >= activePlanRequest.deadline) {
      activePlanRequest.controller.abort(new DOMException("Väntetiden tog slut", "TimeoutError"));
    }
    setLoading(Boolean(activePlanRequest));
  }
  const debugMode = new URLSearchParams(window.location.search).get("debug") === "true";
  const membershipPreferenceKey = "grocery-membership-programs-v1";
  const lastPlanStorageKey = "grocery-last-plan-id-v1";
  const plannerPreferenceKey = "grocery-planner-preferences-v1";
  const onboardingSeenKey = "grocery-beta-onboarding-seen-v1";
  const anonymousSessionStorageKey = "grocery-anonymous-session-id";
  let frontendBuildId = "unknown";
  const membershipPrograms = Object.freeze({
    ICA_STAMMIS: { label: "ICA Stammis", legacyChain: "ica" },
    COOP_MEMBER: { label: "Coop medlem", legacyChain: "coop" },
    HEMKOP_MEMBER: { label: "Klubb Hemköp", legacyChain: "hemkop" },
    LIDL_PLUS: { label: "Lidl Plus", legacyChain: "lidl" },
    WILLYS_PLUS: { label: "Willys Plus", legacyChain: "willys" },
    CITY_GROSS_PRIO: { label: "City Gross Prio", legacyChain: "citygross" },
  });
  function createAnonymousSessionId() {
    if (window.crypto?.randomUUID) return window.crypto.randomUUID();
    if (window.crypto?.getRandomValues) {
      const bytes = window.crypto.getRandomValues(new Uint8Array(24));
      return `anon_${Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("")}`;
    }
    throw new Error("Säker sessionsgenerering kräver en säker webbläsarkontext.");
  }

  const anonymousSessionId = (() => {
    try {
      const existing = window.localStorage.getItem(anonymousSessionStorageKey);
      if (existing) return existing;
      const created = createAnonymousSessionId();
      window.localStorage.setItem(anonymousSessionStorageKey, created);
      return created;
    } catch (_error) {
      return createAnonymousSessionId();
    }
  })();

  function currentPlanId() {
    return first(currentResponse, ["plan_id", "id"], null);
  }

  function planIdFromHash() {
    const fragment = window.location.hash.startsWith("#")
      ? window.location.hash.slice(1)
      : window.location.hash;
    return new URLSearchParams(fragment).get("plan");
  }

  function legacyPlanIdFromQuery() {
    return new URLSearchParams(window.location.search).get("plan");
  }

  function planIdFromLocation() {
    return planIdFromHash() || legacyPlanIdFromQuery();
  }

  function planUrl(planId, { preserveNonPlanQuery = true } = {}) {
    const url = new URL(window.location.href);
    const fragment = new URLSearchParams(url.hash.startsWith("#") ? url.hash.slice(1) : url.hash);
    fragment.set("plan", String(planId));
    url.hash = fragment.toString();
    url.searchParams.delete("plan");
    if (!preserveNonPlanQuery) url.search = "";
    return url;
  }

  function migrateLegacyPlanQuery() {
    const legacyPlanId = legacyPlanIdFromQuery();
    if (!legacyPlanId) return planIdFromHash();
    const url = planUrl(planIdFromHash() || legacyPlanId);
    window.history.replaceState({ planId: planIdFromHash() || legacyPlanId }, "", url);
    return planIdFromHash() || legacyPlanId;
  }

  function safeEventProperties(properties = {}) {
    const allowed = new Set([
      "diet", "mode", "max_stores", "membership_program", "latency_ms",
      "total", "price_per_portion", "outcome", "error_code", "recipes",
      "servings", "actual_stores",
    ]);
    return Object.fromEntries(Object.entries(properties).filter(([key, value]) => (
      allowed.has(key) && value !== undefined && value !== null && value !== ""
    )));
  }

  function sendAnalyticsEvent(eventName, properties = {}) {
    const body = {
      event_name: eventName,
      anonymous_session_id: anonymousSessionId,
      page_context: window.location.pathname,
      plan_id: currentPlanId(),
      properties: safeEventProperties(properties),
    };
    void fetch("/api/analytics/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      keepalive: true,
    }).catch(() => undefined);
  }

  function sendFrontendError(errorCode, message) {
    const safeMessage = String(message || "Okänt frontendfel").slice(0, 500);
    void fetch("/api/frontend-errors", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        anonymous_session_id: anonymousSessionId,
        route: window.location.pathname.slice(0, 300),
        error_code: String(errorCode || "frontend_error").slice(0, 80),
        message: safeMessage,
        plan_id: currentPlanId(),
      }),
      keepalive: true,
    }).catch(() => undefined);
  }

  const diversityModes = {
    cheapest: {
      label: "Billigast",
      resultTitle: "Billigaste veckomenyn vi hittade",
      description: "Lägsta pris med planens grundläggande kvalitetskrav.",
    },
    balanced: {
      label: "Balanserad",
      resultTitle: "Balanserad veckomeny",
      description: "Rekommenderad balans mellan låg kostnad och omväxling.",
    },
    varied: {
      label: "Varierad",
      resultTitle: "Varierad veckomeny",
      description: "Mer omväxling i rättform, råvaror och tillagning.",
    },
  };

  function isPresent(value) {
    return value !== undefined && value !== null && value !== "";
  }

  function pathValue(source, path) {
    if (!source || typeof source !== "object") return undefined;
    return path.split(".").reduce((value, key) => {
      if (value && typeof value === "object" && key in value) return value[key];
      return undefined;
    }, source);
  }

  function first(source, paths, fallback = undefined) {
    for (const path of paths) {
      const value = pathValue(source, path);
      if (isPresent(value)) return value;
    }
    return fallback;
  }

  function list(value) {
    if (Array.isArray(value)) return value;
    return [];
  }

  function numeric(value) {
    if (!isPresent(value) || typeof value === "boolean") return null;
    const parsed = typeof value === "number" ? value : Number(String(value).replace(",", "."));
    return Number.isFinite(parsed) ? parsed : null;
  }

  function formatMoney(value) {
    const amount = numeric(value);
    return amount === null ? null : moneyFormatter.format(amount);
  }

  function formatNumber(value) {
    const amount = numeric(value);
    return amount === null ? null : numberFormatter.format(amount);
  }

  function formatPercent(value) {
    const amount = numeric(value);
    if (amount === null) return null;
    const ratio = amount > 1 && amount <= 100 ? amount / 100 : amount;
    return percentFormatter.format(ratio);
  }

  function formatDuration(value) {
    const seconds = numeric(value);
    return seconds === null ? null : `${numberFormatter.format(seconds)} s`;
  }

  function formatQuantity(quantity, unit) {
    const formatted = formatNumber(quantity);
    if (formatted === null) return null;
    return isPresent(unit) ? `${formatted} ${String(unit)}` : formatted;
  }

  function formatApproximate(value, suffix) {
    const formatted = formatNumber(value);
    return formatted === null ? null : `≈ ${formatted}${suffix ? ` ${suffix}` : ""}`;
  }

  function approximateText(value) {
    return isPresent(value) ? `ca ${value}` : null;
  }

  function normalizeSaleModel(value) {
    const model = String(value || "unknown").trim().toLowerCase();
    const supported = new Set([
      "fixed_package",
      "sold_by_weight",
      "sold_by_piece",
      "variable_weight_package",
      "unknown",
    ]);
    return supported.has(model) ? model : "unknown";
  }

  function normalizeBasketVerification(value) {
    const status = String(value || "UNVERIFIED").trim().toUpperCase();
    return new Set([
      "VERIFIED",
      "VERIFIED_WITH_ESTIMATES",
      "UNVERIFIED",
      "INVALID",
    ]).has(status) ? status : "UNVERIFIED";
  }

  function basketVerificationRank(value) {
    return {
      VERIFIED: 0,
      VERIFIED_WITH_ESTIMATES: 1,
      UNVERIFIED: 2,
      INVALID: 3,
    }[normalizeBasketVerification(value)];
  }

  function worstBasketVerification(...values) {
    return values
      .map(normalizeBasketVerification)
      .reduce((worst, status) => (
        basketVerificationRank(status) > basketVerificationRank(worst) ? status : worst
      ), "VERIFIED");
  }

  function basketVerificationMeta(status) {
    const normalized = normalizeBasketVerification(status);
    if (normalized === "VERIFIED") {
      return {
        status: normalized,
        className: "is-verified",
        icon: "✓",
        title: "Matkasse verifierad",
        description: "Alla valda produkter har säkra semantiska matchningar och härledda eller exakta inköpsmängder.",
        totalLabel: "Totalt",
      };
    }
    if (normalized === "VERIFIED_WITH_ESTIMATES") {
      return {
        status: normalized,
        className: "has-estimates",
        icon: "≈",
        title: "Matkassen innehåller uppskattade lösvikter",
        description: "Produktvalen är verifierade, men vissa vikter eller styckestorlekar är uppskattningar. Slutsumman är därför ungefärlig.",
        totalLabel: "Uppskattat totalpris",
      };
    }
    if (normalized === "INVALID") {
      return {
        status: normalized,
        className: "is-invalid",
        icon: "!",
        title: "Matkassen är ogiltig",
        description: "En produktmatchning eller mängdtäckning är underkänd. Planen ska inte användas som inköpsunderlag.",
        totalLabel: "Ogiltigt prisunderlag",
      };
    }
    return {
      status: "UNVERIFIED",
      className: "is-unverified",
      icon: "?",
      title: "Matkassen är inte verifierad",
      description: "Minst en produkt har otillräcklig mängdmetadata. Det visade beloppet är inte ett säkert exakt totalpris.",
      totalLabel: "Osäkert prisunderlag",
    };
  }

  function displayBasketMoney(value, status) {
    const money = formatMoney(value);
    if (!money) return null;
    const normalized = normalizeBasketVerification(status);
    if (normalized === "VERIFIED") return money;
    if (normalized === "VERIFIED_WITH_ESTIMATES") return `ca ${money}`;
    if (normalized === "INVALID") return "Använd inte priset";
    return `osäkert: ${money}`;
  }

  function statusMeta(value) {
    const key = String(value || "").trim().toUpperCase();
    if (key === "PASS") return { label: "Godkänd", className: "is-pass" };
    if (key === "FAIL") return { label: "Underkänd", className: "is-fail" };
    return { label: isPresent(value) ? String(value) : "Ej angiven", className: "is-unknown" };
  }

  function confidenceLabel(value) {
    const labels = {
      exact: "Exakt",
      derived: "Härledd",
      estimated: "Uppskattad",
      unknown: "Okänd",
      high: "Hög",
      medium: "Medel",
      low: "Låg",
    };
    const key = String(value || "unknown").trim().toLowerCase();
    return labels[key] || String(value || "Okänd");
  }

  function assortmentLabel(value) {
    const key = String(value || "").trim().toUpperCase();
    return {
      VERIFIED_RECENTLY_AVAILABLE: "Observerad nyligen",
      OBSERVED_AVAILABLE: "Observerad nyligen",
      PROBABLE_AVAILABLE: "Sannolikt i butik",
      SOURCE_SUPPORTED: "Online-sortiment",
      ONLINE_CATALOG: "Online-sortiment",
      USER_REPORTED_NOT_FOUND: "Nyligen ej hittad",
      SOURCE_REPORTED_UNAVAILABLE: "Källan anger otillgänglig",
      UNKNOWN: "Okänd fysisk tillgänglighet",
    }[key] || "Okänd fysisk tillgänglighet";
  }

  function normalizeDiversityMode(value, fallback = "balanced") {
    const mode = String(value || "").trim().toLowerCase();
    return Object.hasOwn(diversityModes, mode) ? mode : fallback;
  }

  function selectedDiversityMode() {
    const selected = Array.from(dom.diversityInputs).find((input) => input.checked);
    return normalizeDiversityMode(selected && selected.value);
  }

  function normalizeMembershipPrograms(value) {
    const rawValues = Array.isArray(value)
      ? value
      : value && typeof value === "object"
        ? Object.entries(value).filter(([, enabled]) => Boolean(enabled)).map(([key]) => key)
        : [];
    const aliases = Object.entries(membershipPrograms).reduce((rows, [program, details]) => {
      rows[program.toLowerCase()] = program;
      rows[details.legacyChain] = program;
      rows[details.label.toLowerCase()] = program;
      return rows;
    }, {});
    return Array.from(new Set(rawValues.map((raw) => aliases[String(raw).trim().toLowerCase()]).filter(Boolean))).sort();
  }

  function selectedMemberships() {
    return Array.from(dom.membershipInputs)
      .filter((input) => input.checked)
      .map((input) => input.value)
      .filter((program) => Object.hasOwn(membershipPrograms, program))
      .sort();
  }

  function setSelectedMemberships(value, { persist = false } = {}) {
    const selected = new Set(normalizeMembershipPrograms(value));
    dom.membershipInputs.forEach((input) => {
      input.checked = selected.has(input.value);
    });
    if (persist) {
      try {
        window.localStorage.setItem(membershipPreferenceKey, JSON.stringify(Array.from(selected).sort()));
      } catch (_error) {
        // Membership flags are optional device-local preferences. Planning still works.
      }
    }
  }

  function loadMembershipPreferences() {
    try {
      const saved = JSON.parse(window.localStorage.getItem(membershipPreferenceKey) || "[]");
      setSelectedMemberships(saved);
    } catch (_error) {
      setSelectedMemberships([]);
    }
  }

  function plannerPreferences() {
    return {
      postal_code: dom.postalCode.value.trim(),
      recipes: Number(dom.recipesInput.value),
      servings: Number(dom.servingsInput.value),
      max_stores: Number(dom.maxStoresInput.value),
      purchase_planning_mode: dom.purchasePlanningMode.value,
      diet_preference: dom.dietPreference.value,
      diversity_mode: selectedDiversityMode(),
      varied_budget_percent: Number(dom.variedBudget.value),
      memberships: selectedMemberships(),
      availability_mode: selectedAvailabilityMode(),
      avoid_ingredients: dom.excludedIngredients.value.split(",").map(value => value.trim()).filter(Boolean),
      ...recipeControls.values(),
    };
  }

  function persistPlannerPreferences() {
    try {
      window.localStorage.setItem(plannerPreferenceKey, JSON.stringify(plannerPreferences()));
      window.localStorage.setItem(membershipPreferenceKey, JSON.stringify(selectedMemberships()));
    } catch (_error) {
      // Preferences are a device-local convenience; planning remains available.
    }
  }

  function optionHasValue(select, value) {
    return Array.from(select.options).some((option) => option.value === String(value));
  }

  function loadPlannerPreferences() {
    loadMembershipPreferences();
    try {
      const saved = JSON.parse(window.localStorage.getItem(plannerPreferenceKey) || "null");
      if (!saved || typeof saved !== "object") return;
      if (/^\d{5}$/.test(String(saved.postal_code || ""))) dom.postalCode.value = String(saved.postal_code);
      if (optionHasValue(dom.recipesInput, saved.recipes)) dom.recipesInput.value = String(saved.recipes);
      if (Number(saved.servings) >= 1 && Number(saved.servings) <= 8) dom.servingsInput.value = String(saved.servings);
      if (optionHasValue(dom.maxStoresInput, saved.max_stores)) dom.maxStoresInput.value = String(saved.max_stores);
      if (optionHasValue(dom.purchasePlanningMode, saved.purchase_planning_mode)) dom.purchasePlanningMode.value = String(saved.purchase_planning_mode);
      if (optionHasValue(dom.dietPreference, saved.diet_preference)) dom.dietPreference.value = String(saved.diet_preference);
      checkDiversityInput(normalizeDiversityMode(saved.diversity_mode));
      if (Number.isFinite(saved.varied_budget_percent) && saved.varied_budget_percent >= 0 && saved.varied_budget_percent <= 100) dom.variedBudget.value = String(saved.varied_budget_percent);
      setSelectedMemberships(saved.memberships || []);
      dom.excludedIngredients.value = list(saved.avoid_ingredients).join(", ");
      if (saved.availability_mode) dom.availabilityInputs.forEach(input => { input.checked = input.value === saved.availability_mode; });
      if (saved.recipe_preferences || saved.personal) recipeControls.restore(saved);
    } catch (_error) {
      // Ignore malformed or unavailable local storage.
    }
  }

  function clearPlannerPreferences() {
    try {
      window.localStorage.removeItem(plannerPreferenceKey);
      window.localStorage.removeItem(membershipPreferenceKey);
      window.localStorage.removeItem(lastPlanStorageKey);
      window.localStorage.removeItem(anonymousSessionStorageKey);
    } catch (_error) {
      // The form can still be reset when storage is unavailable.
    }
    dom.postalCode.value = "22350";
    dom.recipesInput.value = "5";
    dom.servingsInput.value = "4";
    dom.maxStoresInput.value = "2";
    dom.purchasePlanningMode.value = "exact";
    dom.dietPreference.value = "mixed";
    dom.excludedIngredients.value = "";
    recipeControls.reset();
    checkDiversityInput("balanced");
    setSelectedMemberships([]);
    updatePortionChip();
    dom.preferencesStatus.textContent = "Sparade inställningar har rensats på den här enheten.";
  }

  function membershipProgramFor(item) {
    const direct = first(item, [
      "membership_program",
      "price_contract.membership_program",
      "promotion_contract.membership_program",
      "applied_offer.member_program",
    ]);
    const normalized = normalizeMembershipPrograms(direct ? [direct] : []);
    if (normalized[0]) return normalized[0];

    // Some older payloads used membership_required for a program id. A boolean
    // only proves member eligibility and must never shadow the actual program.
    const legacyRequired = first(item, ["membership_required"]);
    if (typeof legacyRequired !== "string") return null;
    return normalizeMembershipPrograms([legacyRequired])[0] || null;
  }

  function membershipLabel(program) {
    return membershipPrograms[program]?.label || String(program || "medlemskap");
  }

  function regularUnitPrice(item) {
    if (item.ordinary_price_known === false) return null;
    const explicit = numeric(first(item, [
      "regular_unit_price",
      "price_contract.regular_price",
      "promotion_contract.regular_price",
    ]));
    if (explicit !== null) return explicit;
    const total = numeric(first(item, ["regular_total_price"]));
    const packages = numeric(first(item, ["packages_needed", "package_count"]));
    return total !== null && packages !== null && packages > 0 ? total / packages : null;
  }

  function appendMembershipPriceMeta(item, productMeta) {
    const program = membershipProgramFor(item);
    const eligibility = String(first(item, [
      "eligibility",
      "price_eligibility",
      "price_contract.eligibility",
      "promotion_contract.eligibility",
    ], program ? "member" : "public")).toLowerCase();
    if (!program && eligibility !== "member") return;
    const ordinary = regularUnitPrice(item);
    const applied = numeric(first(item, ["unit_price", "effective_price"]));
    if (ordinary !== null) productMeta.push(`Ord. ${formatMoney(ordinary)}`);
    if (applied !== null) productMeta.push(`Medlemspris ${formatMoney(applied)}`);
    productMeta.push(`Kräver ${membershipLabel(program)}`);
  }

  function renderMembershipPlanSummary(groups, data) {
    const memberItems = groups.flatMap(storeItems).filter((item) => {
      const eligibility = String(first(item, [
        "eligibility",
        "price_eligibility",
        "price_contract.eligibility",
        "promotion_contract.eligibility",
      ], "")).toLowerCase();
      return Boolean(membershipProgramFor(item)) || eligibility === "member";
    });
    const coverageMessages = list(first(data, ["membership_coverage"], []))
      .map((row) => first(row, ["message"]))
      .filter(Boolean);
    const savings = first(data, ["membership_savings"]);
    const savingsAmount = numeric(first(savings, ["amount"]));
    const parts = [];
    if (memberItems.length) {
      const labels = Array.from(new Set(memberItems.map(membershipProgramFor).filter(Boolean).map(membershipLabel)));
      parts.push(`Din meny använder ${memberItems.length} medlemspris${memberItems.length === 1 ? "" : "er"}${labels.length ? `: ${labels.join(", ")}` : ""}.`);
    }
    if (savingsAmount !== null && savingsAmount > 0) {
      parts.push(`Dina medlemskap sparar ${formatMoney(savingsAmount)} på exakt samma varor och mängder jämfört med publika priser.`);
    }
    parts.push(...coverageMessages);
    dom.membershipPlanSummary.hidden = parts.length === 0;
    if (!parts.length) {
      dom.membershipPlanSummary.textContent = "";
      return;
    }
    dom.membershipPlanSummary.textContent = parts.join(" ");
  }

  function selectedAvailabilityMode() {
    const selected = Array.from(dom.availabilityInputs).find((input) => input.checked);
    return selected ? selected.value : "normal";
  }

  function decimalValue(value) {
    const text = String(value || "").trim().replace(/\s/g, "").replace(",", ".");
    if (!text) return null;
    const parsed = Number(text);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function newEvidenceIdempotencyKey() {
    const value = window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    return `consumer-${value}`;
  }

  function checkDiversityInput(mode) {
    dom.diversityInputs.forEach((input) => {
      input.checked = input.value === mode;
    });
  }

  function arrayOrValueCount(value) {
    if (Array.isArray(value)) return value.length;
    return numeric(value);
  }

  function createElement(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (isPresent(text)) node.textContent = String(text);
    return node;
  }

  function empty(node) {
    node.replaceChildren();
  }

  function emptyMessage(text) {
    return createElement("p", "empty-state", text);
  }

  function scrollToNode(node, block = "start") {
    node?.scrollIntoView({ behavior: prefersReducedMotion ? "auto" : "smooth", block });
  }

  function setLoading(active) {
    dom.submitButton.disabled = active || !plannerReady;
    dom.form.setAttribute("aria-busy", String(active));
    dom.submitLabel.textContent = active ? "Skapar veckomenyn…" : window.SmakoRecipes.pendingJob("public") ? "Återuppta statuskontrollen" : "Skapa veckomeny";

    if (!active) {
      dom.loadingState.hidden = true;
      return;
    }

    dom.statusRegion.hidden = false;
    dom.loadingState.hidden = false;
    dom.errorState.hidden = true;
    dom.errorState.querySelector(".recipe-planning-diagnostics")?.remove();
    dom.results.hidden = true;
    dom.loadingMessage.textContent = "Vi söker efter en komplett, prisberäknad plan. Det kan ta några minuter.";
  }

  function showError(message, diagnostics = null) {
    setLoading(false);
    dom.statusRegion.hidden = false;
    dom.errorState.hidden = false;
    dom.errorMessage.textContent = message || "Försök igen om en liten stund.";
    const pending=window.SmakoRecipes.pendingJob("public");
    dom.errorState.querySelector("h2").textContent=pending?"Statuskontrollen behöver återupptas":"Menyn kunde inte skapas";
    dom.errorState.querySelector(".plan-reconnect-actions")?.remove();
    if(pending){
      const actions=createElement("div","plan-reconnect-actions");
      const resume=createElement("button","secondary-button","Återuppta statuskontrollen");resume.type="button";
      resume.addEventListener("click",()=>void resumePublicJob());
      const fresh=createElement("button","secondary-button","Skapa en ny meny");fresh.type="button";
      fresh.addEventListener("click",()=>{window.SmakoRecipes.forgetJob("public");dom.errorState.hidden=true;setLoading(false);dom.submitButton.focus();});
      actions.append(resume,fresh);dom.errorMessage.after(actions);
    }
    dom.errorState.querySelector(".recipe-planning-diagnostics")?.remove();
    const explanation=window.SmakoRecipes.diagnostics(diagnostics);
    if(explanation)dom.errorMessage.after(explanation);
    dom.results.hidden = true;
    scrollToNode(dom.errorState, "center");
  }

  function clearStatus() {
    dom.statusRegion.hidden = true;
    dom.loadingState.hidden = true;
    dom.errorState.hidden = true;
  }

  function setPlannerReadiness(ready, message = null) {
    plannerReady = Boolean(ready);
    dom.serviceAvailabilityBanner.hidden = plannerReady;
    dom.submitButton.disabled = !plannerReady || Boolean(activePlanRequest);
    if (plannerReady) return;
    dom.serviceAvailabilityTitle.textContent = "Planeringen är tillfälligt pausad";
    dom.serviceAvailabilityMessage.textContent = message
      || "Planeringstjänsten är tillfälligt otillgänglig. Kontrollera status igen om en stund. Dina val är kvar.";
  }

  function validatePostalCode() {
    const digits = dom.postalCode.value.replace(/\s/g, "");
    const valid = /^\d{5}$/.test(digits);
    dom.postalCode.setAttribute("aria-invalid", String(!valid));
    dom.postalError.textContent = valid ? "" : "Ange ett giltigt svenskt postnummer med fem siffror.";
    return valid;
  }

  function updatePortionChip() {
    const recipes = numeric(dom.recipesInput.value);
    const servings = numeric(dom.servingsInput.value);
    if (recipes === null || servings === null) {
      dom.formChip.textContent = "Portioner beräknas från dina val";
      return;
    }
    const meals=recipeControls.values().personal?.meals;
    const portions=meals?meals.reduce((sum,m)=>sum+m.count*m.servings,0):recipes*servings;
    dom.formChip.textContent = meals?`${meals.reduce((sum,m)=>sum+m.count,0)} tillfällen · ${numberFormatter.format(portions)} portioner`:`${numberFormatter.format(portions)} portioner med valen`;
  }

  function errorFromResponse(payload, fallback, status = null, errorCode = null, retryAfter = null) {
    const reason = typeof payload?.detail === "string" ? payload.detail.trim() : "";
    const normalizedCode = String(errorCode || first(payload, ["error_code", "code"], ""))
      .trim()
      .toLowerCase();
    if (normalizedCode === "planner_admission_full" || status === 429 || (status === 503 && retryAfter && !normalizedCode.includes("price_universe"))) {
      const value = String(retryAfter || "").trim();
      const parsedRetry = /^\d+$/.test(value) ? Number(value) : (Date.parse(value) - Date.now()) / 1000;
      const seconds = Number.isFinite(parsedRetry) ? Math.max(1, Math.ceil(parsedRetry)) : null;
      return seconds === null
        ? "Det är många som skapar menyer just nu. Försök igen om några sekunder."
        : `Det är många som skapar menyer just nu. Försök igen om cirka ${seconds} sekunder.`;
    }
    if (normalizedCode === "data_blocked") {
      return `Nödvändigt underlag saknas. ${reason || "Pris-, mängd- eller näringsunderlaget kunde inte verifieras."} Dina val är kvar.`;
    }
    if (normalizedCode === "plan_infeasible") {
      return `${reason || "Ingen komplett meny hittades med dina krav och det tillgängliga underlaget."} Dina val är kvar.`;
    }
    if (status === 422 && Array.isArray(payload?.detail)) {
      return payload.detail.map((entry) => {
        const field = planErrorFields()[entry?.loc?.[1]];
        return field ? `${field.label}: ${entry.msg || "kontrollera värdet"}.` : "Ett värde i begäran är ogiltigt.";
      }).join(" ");
    }
    if (status === 422) return `${reason || "Planeringen kunde inte genomföras med det tillgängliga underlaget."} Dina val är kvar.`;
    if (status === 504) return "Planeringstjänsten svarade inte i tid. Försök igen om en stund.";
    if (status === 502) return "Servern kunde inte få svar från planeringstjänsten. Försök igen om en stund.";
    if (normalizedCode === "saved_plan_owner_session_unavailable") {
      return "Din session kunde inte upprättas för att spara menyn. Ladda om sidan och försök igen. Dina val är kvar.";
    }
    if (normalizedCode === "planner_job_expired") {
      return "Planeringsförsöket har gått ut eller tjänsten har startats om. Skapa menyn igen. Dina val är kvar.";
    }
    if (normalizedCode === "price_universe_unusable") {
      return "Prisunderlaget uppfyller inte färskhets- eller verifieringskraven just nu. Planeringen är därför pausad. Dina val är kvar.";
    }
    if (normalizedCode === "price_universe_unavailable") {
      return "Prisunderlaget är inte tillgängligt just nu. Försök igen om en stund. Dina val är kvar.";
    }
    if (status === 503) return "Planeringstjänsten är tillfälligt otillgänglig. Försök igen om en stund. Dina val är kvar.";
    if (status >= 500) return "Ett serverfel hindrade planeringen. Försök igen om en stund. Dina val är kvar.";
    if (status === 401 || status === 403) return "Din session saknar åtkomst. Ladda om sidan och försök igen. Dina val är kvar.";
    const detail = payload && payload.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (Array.isArray(detail)) {
      const messages = detail
        .map((entry) => (entry && (entry.msg || entry.message)) || (typeof entry === "string" ? entry : null))
        .filter(Boolean);
      if (messages.length) return messages.join(" ");
    }
    const message = first(payload, ["message", "error.message", "error"]);
    return isPresent(message) ? String(message) : fallback;
  }

  function planErrorFields() {
    return {
      postal_code: { node: dom.postalCode, label: "Postnummer" },
      recipes: { node: dom.recipesInput, label: "Middagar" },
      servings: { node: dom.servingsInput, label: "Portioner" },
      max_stores: { node: dom.maxStoresInput, label: "Max antal inköpsställen" },
      purchase_planning_mode: { node: dom.purchasePlanningMode, label: "Köpplanering" },
      diet_preference: { node: dom.dietPreference, label: "Kost" },
      varied_budget_percent: { node: dom.variedBudget, label: "Kostnadstak för Varierad" },
      avoid_ingredients: { node: dom.excludedIngredients, label: "Undvik ingredienser" },
      recipe_preferences: { node: document.getElementById("recipe-style"), label: "Receptval" },
      allowed_store_ids: { node: document.getElementById("recipe-price-contexts"), label: "Butiker och priskanaler" },
    };
  }

  function recipeIngredientAmount(ingredient) {
    const quantity = first(ingredient, ["quantity", "required_quantity", "amount"]);
    const unit = first(ingredient, ["unit", "normalized_unit"]);
    return formatQuantity(quantity, unit);
  }

  function renderRecipes(data) {
    empty(dom.recipesList);
    const recipes = list(first(data, ["recipes", "meal_plan.recipes", "plan.recipes"], []));
    const recipeCosts = list(first(data, ["recipe_costs"], []));
    const costsByRecipeName = new Map(recipeCosts.map((row) => [
      String(first(row, ["recipe_name", "recipe"], "")),
      row,
    ]));
    if (!recipes.length) {
      dom.recipesList.append(emptyMessage("Inga recept returnerades i svaret."));
      return recipes;
    }

    recipes.forEach((recipe, index) => {
      const recipeName = first(recipe, ["name", "title"], "Namnlöst recept");
      const recipeCost = costsByRecipeName.get(String(recipeName)) || recipeCosts[index] || {};
      const allocatedBasketCost = first(
        recipe,
        ["allocated_basket_cost", "basket_cost_allocation"],
        first(recipeCost, ["allocated_basket_cost"]),
      );
      const details = createElement("details", "recipe-card");
      details.addEventListener("toggle", () => {
        if (details.open) sendAnalyticsEvent("recipe_opened");
      });
      const summary = createElement("summary", "recipe-summary");
      summary.append(createElement("span", "recipe-index", String(index + 1).padStart(2, "0")));
      summary.append(createElement("span", "recipe-name", recipeName));

      const servings = first(recipe, ["servings", "portions"]);
      const summaryMeta = [
        isPresent(servings) ? `${servings} portioner` : null,
        formatMoney(allocatedBasketCost),
      ].filter(Boolean).join(" · ");
      if (summaryMeta) {
        summary.append(createElement("span", "servings-badge", summaryMeta));
      } else {
        summary.append(createElement("span"));
      }
      const chevron = createElement("span", "details-chevron", "+");
      chevron.setAttribute("aria-hidden", "true");
      summary.append(chevron);
      details.append(summary);

      const content = createElement("div", "recipe-content");
      const description = first(recipe, ["short_description", "description", "summary"]);
      if (isPresent(description)) {
        const descriptionRow = createElement("p", "recipe-description", String(description));
        content.append(descriptionRow);
      }
      const recipeMeta = createElement("dl", "recipe-meta");
      const timeMinutes = first(recipe, [
        "time_minutes",
        "total_time_minutes",
        "estimated_time_minutes",
        "cooking_time_minutes",
      ]);
      const incrementalCost = first(recipe, [
        "incremental_ingredient_cost",
        "estimated_recipe_cost",
        "recipe_cost",
        "cost",
      ], first(recipeCost, ["incremental_ingredient_cost"]));
      const costPerPortion = first(
        recipe,
        ["cost_per_portion", "price_per_portion"],
        first(recipeCost, ["cost_per_portion"]),
      );
      const allocatedCost = allocatedBasketCost;
      const recipeType = first(recipe, ["protein_source", "main_protein", "recipe_family", "family"]);
      const formattedTime = formatNumber(timeMinutes);
      [
        ["Tid", formattedTime ? `cirka ${formattedTime} min` : null],
        ["Receptets extra råvarukostnad", formatMoney(incrementalCost)],
        ["Kostnad per portion", formatMoney(costPerPortion)],
        ["Andel av matkassen", formatMoney(allocatedCost)],
        ["Typ", isPresent(recipeType) ? String(recipeType) : null],
      ].forEach(([label, value]) => {
        if (!value) return;
        const row = createElement("div");
        row.append(createElement("dt", null, label), createElement("dd", null, value));
        recipeMeta.append(row);
      });
      if (recipeMeta.childElementCount) content.append(recipeMeta);
      const ingredientsSection = createElement("div");
      ingredientsSection.append(createElement("h3", null, "Ingredienser"));
      const ingredientsList = createElement("ul", "recipe-ingredients");
      const ingredients = list(first(recipe, ["ingredients", "recipe_ingredients"], []));
      if (!ingredients.length) {
        ingredientsList.append(createElement("li", null, "Ingredienser saknas i svaret."));
      } else {
        ingredients.forEach((ingredient) => {
          const row = createElement("li");
          row.append(createElement("span", null, first(ingredient, ["name", "canonical_name", "ingredient"], "Ingrediens")));
          row.append(createElement("span", "ingredient-amount", recipeIngredientAmount(ingredient) || "—"));
          ingredientsList.append(row);
        });
      }
      ingredientsSection.append(ingredientsList);

      const instructionsSection = createElement("div");
      instructionsSection.append(createElement("h3", null, "Gör så här"));
      const instructionsList = createElement("ol", "instructions-list");
      const instructions = list(first(recipe, ["instructions", "steps", "method"], []));
      if (!instructions.length) {
        instructionsList.append(createElement("li", null, "Instruktioner saknas i svaret."));
      } else {
        instructions.forEach((instruction) => {
          const instructionText = typeof instruction === "string"
            ? instruction
            : first(instruction, ["text", "instruction", "description"], "");
          instructionsList.append(createElement("li", null, instructionText));
        });
      }
      instructionsSection.append(instructionsList);
      content.append(ingredientsSection, instructionsSection);
      if (recipe.design) {
        const slot = data.personal?.slots?.filter(row => row.recipe)[index];
        const nutrition = data.personal?.checks?.nutrition?.find(row => row.slot_id === slot?.id);
        const completeContent = window.SmakoRecipes.renderRecipe(recipe, {nutrition, personal:data.personal, slotId:slot?.id});
        content.replaceChildren(completeContent);
      }
      const recipeActions = createElement("div", "recipe-actions");
      const replaceButton = createElement("button", "secondary-button compact-button", recipe.design ? "Byt recept och räkna om inköpen" : "Byt recept");
      replaceButton.type = "button";
      replaceButton.hidden = !first(currentResponse, ["plan_id"]);
      replaceButton.addEventListener("click", () => void replaceRecipe(index, replaceButton));
      recipeActions.append(replaceButton);
      if (recipe.design && currentResponse?.plan_id) {
        const feedbackButton = createElement("button", "secondary-button compact-button", "Så blev rätten");
        feedbackButton.type = "button";
        feedbackButton.addEventListener("click", () => window.SmakoRecipes.recipeFeedback({recipe, recipeIndex:index, planId:currentResponse.plan_id, revision:currentResponse.plan_revision}));
        recipeActions.append(feedbackButton);
      }
      content.append(recipeActions);
      details.append(content);
      dom.recipesList.append(details);
    });

    return recipes;
  }

  function renderIngredients(data) {
    empty(dom.ingredientsList);
    const ingredients = list(first(data, [
      "ingredients",
      "normalized_ingredients",
      "aggregated_ingredients",
      "meal_plan.ingredients",
    ], []));

    if (!ingredients.length) {
      dom.ingredientsList.append(emptyMessage("Inga sammanställda ingredienser returnerades i svaret."));
      return;
    }

    ingredients.forEach((ingredient) => {
      const card = createElement("article", "ingredient-card");
      card.append(createElement("span", null, first(ingredient, ["canonical_name", "name", "ingredient"], "Ingrediens")));
      const quantity = first(ingredient, ["required_quantity", "total_quantity", "quantity", "amount"]);
      const unit = first(ingredient, ["unit", "normalized_unit"]);
      card.append(createElement("strong", null, formatQuantity(quantity, unit) || "Mängd saknas"));
      dom.ingredientsList.append(card);
    });
  }

  function optimizedBasket(data) {
    return first(data, ["optimized_basket", "multi_store_basket", "basket", "optimization.basket"], {}) || {};
  }

  function storeName(source) {
    return first(source, [
      "store_name",
      "name",
      "store.name",
      "store.store_name",
      "basket.store_name",
      "basket.store.name",
    ], "Priskontext ej angiven");
  }

  function priceContextLabel(source) {
    const contextType = String(first(source, [
      "price_context_type",
      "context_type",
      "store.price_context_type",
      "source_provenance.price_context_type",
    ], "")).toLowerCase();
    const scope = first(source, [
      "price_scope_label",
      "scope_label",
      "store.price_scope_label",
      "source_provenance.price_scope_label",
    ]);
    const contextId = first(source, ["grocery_context_id", "context_id", "store_id", "store.id"]);
    const name = storeName(source).toLowerCase();
    const parts = [];

    if (contextType.includes("online")) parts.push("Onlinepris");
    else if (contextType.includes("physical") || contextType.includes("store_offer")) parts.push("Fysiskt butikserbjudande");
    else if (contextType.includes("regional")) parts.push("Regionalt erbjudande");
    else if (contextType.includes("external")) parts.push("Pris från extern leverantör");
    else if (name.includes("coop") && String(contextId || "") === "730400") parts.push("Coop Online Syd · onlinepris");

    if (isPresent(scope) && !parts.some((part) => part.toLowerCase().includes(String(scope).toLowerCase()))) {
      parts.push(String(scope));
    }
    if (isPresent(contextId)) parts.push(`Priskontext ${contextId}`);
    return parts.join(" · ") || "Prisets räckvidd är inte specificerad";
  }

  function storeItems(source) {
    return list(first(source, ["items", "purchases", "lines", "basket_items", "basket.items"], []));
  }

  function basketGroups(basket) {
    const groups = list(first(basket, ["stores", "store_groups", "store_baskets", "baskets"], []));
    if (groups.length) return groups;

    const items = storeItems(basket);
    if (!items.length) return [];

    const grouped = new Map();
    items.forEach((item) => {
      const id = first(item, ["store_id", "product.store_id", "candidate.store_id"]);
      const name = first(item, ["store_name", "store.name", "product.store_name", "candidate.store_name"], "Priskontext ej angiven");
      const key = isPresent(id) ? String(id) : String(name);
      if (!grouped.has(key)) grouped.set(key, { store_name: name, items: [] });
      grouped.get(key).items.push(item);
    });
    return Array.from(grouped.values());
  }

  function itemProduct(item) {
    const candidate = first(item, ["product", "candidate", "product_candidate", "selected_product"], {});
    return candidate && typeof candidate === "object" ? candidate : {};
  }

  function appendCell(row, value, className = null) {
    const cell = createElement("td", className, isPresent(value) ? value : "—");
    row.append(cell);
    return cell;
  }

  function saleModelFor(item) {
    return normalizeSaleModel(first(item, [
      "sale_model",
      "purchase.sale_model",
      "product.sale_model",
      "candidate.sale_model",
    ], "unknown"));
  }

  function ratePairText(price, unit) {
    const money = formatMoney(price);
    return money && isPresent(unit) ? `${money}/${String(unit)}` : null;
  }

  function saleRateText(item) {
    const appliedPrice = first(item, [
      "sale_price",
      "purchase.sale_price",
      "product.sale_price",
      "candidate.sale_price",
    ]);
    const appliedUnit = first(item, [
      "sale_unit",
      "purchase.sale_unit",
      "product.sale_unit",
      "candidate.sale_unit",
    ]);
    const appliedRate = ratePairText(appliedPrice, appliedUnit);
    if (appliedRate) return appliedRate;

    const comparisonPrice = first(item, [
      "comparison_price",
      "purchase.comparison_price",
      "product.comparison_price",
      "candidate.comparison_price",
    ]);
    const comparisonUnit = first(item, [
      "comparison_unit",
      "purchase.comparison_unit",
      "product.comparison_unit",
      "candidate.comparison_unit",
    ]);
    return ratePairText(comparisonPrice, comparisonUnit);
  }

  function purchaseBadge(item, saleModel) {
    const packages = first(item, ["packages_needed", "package_count", "packages", "quantity"]);
    if (saleModel === "fixed_package") {
      return { text: formatNumber(packages), className: "package-count" };
    }
    if (saleModel === "sold_by_piece") {
      return { text: isPresent(packages) ? `${formatNumber(packages)} st` : "Styck", className: "purchase-kind" };
    }
    if (saleModel === "sold_by_weight") {
      return { text: "Lösvikt", className: "purchase-kind" };
    }
    if (saleModel === "variable_weight_package") {
      return { text: "Variabel", className: "purchase-kind purchase-kind-estimate" };
    }
    return { text: "Okänd", className: "purchase-kind purchase-kind-unknown" };
  }

  function purchaseQuantityText(item, saleModel, commonUnit) {
    const purchasedQuantity = first(item, [
      "purchased_quantity",
      "bought_quantity",
      "purchase_quantity",
      "total_quantity",
      "purchased_usable_quantity",
    ]);
    const purchasedUnit = first(item, [
      "purchased_unit",
      "bought_unit",
      "purchase.purchased_unit",
      "unit",
    ], commonUnit);
    const purchased = formatQuantity(purchasedQuantity, purchasedUnit);

    if (saleModel === "sold_by_weight") return approximateText(purchased) || "Lösvikt saknas";
    if (saleModel === "variable_weight_package") return approximateText(purchased) || "Variabel vikt";
    if (saleModel === "sold_by_piece") {
      const pieces = first(item, ["packages_needed", "piece_count", "pieces", "purchased_quantity"]);
      const pieceText = isPresent(pieces) ? `${formatNumber(pieces)} st` : "Antal saknas";
      const estimatedWeight = formatQuantity(first(item, [
        "purchased_usable_quantity",
        "estimated_purchased_weight",
      ]), first(item, ["usable_unit", "estimated_piece_weight_unit"], commonUnit));
      return estimatedWeight && commonUnit !== "st"
        ? `${pieceText} (${approximateText(estimatedWeight)})`
        : pieceText;
    }
    if (saleModel === "unknown") return "Okänd mängd";
    return purchased;
  }

  function purchasePriceText(item, saleModel) {
    const linePrice = first(item, [
      "unit_price",
      "effective_price",
      "package_price",
      "price",
      "product.effective_price",
      "product.price",
      "candidate.effective_price",
      "candidate.price",
    ]);
    if (saleModel === "sold_by_weight") {
      return saleRateText(item) || "Viktpris saknas";
    }
    if (saleModel === "sold_by_piece") {
      const piecePrice = formatMoney(first(item, [
        "piece_price",
        "purchase.piece_price",
        "product.piece_price",
        "candidate.piece_price",
      ], linePrice));
      return piecePrice ? `${piecePrice}/st` : "Styckpris saknas";
    }
    if (saleModel === "variable_weight_package") {
      return saleRateText(item) || approximateText(formatMoney(linePrice)) || "Prisuppskattning saknas";
    }
    if (saleModel === "unknown") return "Prisunderlag osäkert";
    return formatMoney(linePrice);
  }

  function purchaseLineTotalText(item, saleModel) {
    const lineTotal = formatMoney(first(item, ["total_price", "total", "total_cost", "line_total", "cost", "purchase_cost"]));
    if (saleModel === "unknown") return lineTotal ? `osäkert: ${lineTotal}` : "Ej verifierbart";
    if (["sold_by_weight", "sold_by_piece", "variable_weight_package"].includes(saleModel)) {
      return approximateText(lineTotal);
    }
    return lineTotal;
  }

  function renderStoreGroup(group, basketStatus, productDetails = []) {
    const items = storeItems(group);
    const article = createElement("article", "store-group");
    const heading = createElement("div", "store-heading");
    const headingText = createElement("div");
    headingText.append(createElement("h3", null, storeName(group)));
    headingText.append(createElement("p", null, `${items.length} produktrader`));
    headingText.append(createElement("p", "store-context-label", priceContextLabel(group)));
    heading.append(headingText);

    const groupTotal = displayBasketMoney(
      first(group, ["subtotal", "total", "total_cost", "basket_total", "basket.total", "basket.total_cost"]),
      basketStatus,
    );
    if (groupTotal) heading.append(createElement("strong", "store-total", groupTotal));
    article.append(heading);

    if (!items.length) {
      article.append(emptyMessage("Ingen inköpsrad returnerades för priskontexten."));
      return article;
    }

    const tableWrap = createElement("div", "shopping-table-wrap");
    const table = createElement("table", "shopping-table");
    const caption = createElement("caption", null, `Inköpslista för ${storeName(group)}`);
    caption.className = "visually-hidden";
    table.append(caption);
    const head = document.createElement("thead");
    const headRow = document.createElement("tr");
    const shoppingColumns = ["Köp", "Produkt", "Behövs", "Köps", "Över", "Prisgrund", "Summa", "Åtgärder"];
    shoppingColumns.forEach((label) => {
      headRow.append(createElement("th", null, label));
    });
    head.append(headRow);
    table.append(head);

    const body = document.createElement("tbody");
    items.forEach((item) => {
      const product = itemProduct(item);
      const row = document.createElement("tr");
      const saleModel = saleModelFor(item);
      const badge = purchaseBadge(item, saleModel);
      const packageCell = appendCell(row, null, "package-count-cell");
      packageCell.textContent = "";
      packageCell.append(createElement("span", badge.className, badge.text));

      const productCell = createElement("td", "product-cell");
      const productName = first(item, [
        "product_name",
        "name",
        "product.product_name",
        "product.name",
        "candidate.product_name",
        "selected_product.product_name",
      ], "Produktnamn saknas");
      productCell.append(createElement("strong", null, productName));

      const packageQuantity = first(item, ["package_quantity", "package_size", "product.package_quantity", "product.package_size", "candidate.package_quantity"]);
      const packageUnit = first(item, ["package_unit", "product.package_unit", "candidate.package_unit"]);
      const ingredientName = first(item, ["ingredient", "ingredient_name", "canonical_name", "ingredient.canonical_name", "ingredient.name"]);
      const productMeta = [];
      const packageText = formatQuantity(packageQuantity, packageUnit);
      if (packageText && saleModel === "fixed_package") productMeta.push(packageText);
      if (packageText && saleModel === "variable_weight_package") productMeta.push(`ca ${packageText} per förpackning`);
      if (ingredientName) productMeta.push(`för ${ingredientName}`);
      const semanticConfidence = first(item, ["semantic_confidence", "semantic.confidence", "product.semantic_confidence"]);
      const quantityConfidence = first(item, ["quantity_confidence", "purchase.quantity_confidence", "product.quantity_confidence"]);
      if (debugMode && semanticConfidence) productMeta.push(`semantik: ${confidenceLabel(semanticConfidence)}`);
      if (debugMode && quantityConfidence) productMeta.push(`mängd: ${confidenceLabel(quantityConfidence)}`);
      const offerDescription = first(item, ["offer_description", "applied_offer.description"]);
      if (offerDescription) productMeta.push(String(offerDescription));
      if (item.ordinary_price_known === false) productMeta.push("Ordinarie pris saknas");
      const offerFrom = first(item, ["applied_offer.valid_from"]);
      const offerTo = first(item, ["applied_offer.valid_to"]);
      if (offerFrom || offerTo) productMeta.push(`Gäller ${offerFrom || "?"}–${offerTo || "?"}`);
      const offerMax = numeric(first(item, ["applied_offer.max_quantity"]));
      const offerGroupSize = numeric(first(item, ["applied_offer.required_packages"], 1));
      if (offerMax !== null) productMeta.push(`Max ${offerMax * offerGroupSize} förpackningar i hela köpet`);
      if (item.purchase_date) productMeta.push(`Inköpsdag ${item.purchase_date}`);
      appendMembershipPriceMeta(item, productMeta);
      const availability = first(item, [
        "assortment_confidence",
        "availability_confidence",
        "product.assortment_confidence",
        "product.availability_confidence",
      ]);
      productMeta.push(assortmentLabel(availability));
      if (productMeta.length) productCell.append(createElement("span", null, productMeta.join(" · ")));
      const declaration=window.SmakoRecipes.productDetails(productDetails.find(detail=>detail.ingredient===ingredientName&&detail.product_name===productName));
      if(declaration)productCell.append(declaration);
      row.append(productCell);

      const commonUnit = first(item, ["unit", "required_unit", "ingredient.unit", "normalized_unit"]);
      const surplusUnit = first(item, ["surplus_unit", "waste_unit", "unit"], commonUnit);
      const required = formatQuantity(first(item, ["required_quantity", "required", "needed_quantity", "ingredient.required_quantity"]), commonUnit);
      const purchased = purchaseQuantityText(item, saleModel, commonUnit);
      const surplus = formatQuantity(first(item, ["surplus_quantity", "surplus", "waste_quantity", "leftover_quantity"]), surplusUnit);
      appendCell(row, required);
      appendCell(row, purchased);
      const displayedSurplus = ["sold_by_weight", "sold_by_piece", "variable_weight_package"].includes(saleModel)
        ? approximateText(surplus)
        : surplus;
      appendCell(row, displayedSurplus, surplus ? "waste-value" : null);
      appendCell(row, purchasePriceText(item, saleModel));
      appendCell(row, purchaseLineTotalText(item, saleModel), "row-total");
      const reportCell = appendCell(row, "", "report-cell");
      reportCell.textContent = "";
      const productId = first(item, ["source_product_id", "product_id", "product.product_id", "candidate.product_id"]);
      const replaceProductButton = createElement("button", "replace-product-button", "Byt vara");
      replaceProductButton.type = "button";
      replaceProductButton.hidden = !first(currentResponse, ["plan_id"]) || !productId;
      replaceProductButton.addEventListener("click", () => void openProductAlternatives({
        product_id: productId,
        product_name: productName,
      }));
      const reportButton = createElement("button", "report-button", "Rapportera");
      reportButton.type = "button";
      reportButton.setAttribute("aria-label", `Rapportera ${productName}`);
      reportButton.addEventListener("click", () => openReportDialog({
        evidence_source: "MANUAL",
        plan_id: first(currentResponse, ["plan_id", "id"]),
        price_snapshot_id: first(item, [
          "source_snapshot_id",
          "source_provenance.source_snapshot_id",
          "product.source_provenance.source_snapshot_id",
          "candidate.source_provenance.source_snapshot_id",
        ]),
        physical_store_id: first(group, ["physical_store_id", "store.physical_store_id"], first(item, ["physical_store_id", "product.physical_store_id"])),
        grocery_context_id: first(group, ["grocery_context_id", "context_id", "store_id", "store.id"], first(item, ["grocery_context_id", "context_id", "store_id", "product.context_id", "product.store_id"])),
        store_display_name: storeName(group),
        chain: first(item, ["chain", "product.chain", "candidate.chain"], first(group, ["chain", "store.chain"])),
        source_provider_store_id: first(item, [
          "source_provider_store_id",
          "source_provenance.provider_store_id",
          "product.source_provenance.provider_store_id",
          "candidate.source_provenance.provider_store_id",
        ]),
        source_product_id: productId,
        gtin: first(item, ["gtin", "product.gtin", "candidate.gtin"]),
        product_name: productName,
        brand: first(item, ["brand", "product.brand", "candidate.brand"]),
        package_description: packageText,
        digital_price: numeric(first(item, ["unit_price", "effective_price", "package_price", "price", "product.effective_price", "product.price"])),
      }));
      reportCell.append(replaceProductButton, reportButton);
      Array.from(row.cells).forEach((cell, cellIndex) => {
        cell.dataset.label = shoppingColumns[cellIndex] || "";
      });
      body.append(row);
    });
    table.append(body);
    tableWrap.append(table);
    article.append(tableWrap);
    return article;
  }

  function renderBasketVerification(basket) {
    const meta = basketVerificationMeta(first(basket, ["verification_status"], "UNVERIFIED"));
    dom.basketVerification.className = `basket-verification ${meta.className}`;
    dom.basketVerification.dataset.verificationStatus = meta.status;
    dom.basketVerificationIcon.textContent = meta.icon;
    dom.basketVerificationTitle.textContent = meta.title;
    dom.basketVerificationDescription.textContent = meta.description;
    dom.basketTotalLabel.textContent = meta.totalLabel;
    empty(dom.basketVerificationWarnings);
    list(first(basket, ["verification_warnings", "verification.warnings"], []))
      .map(warningText)
      .filter(Boolean)
      .forEach((warning) => {
        dom.basketVerificationWarnings.append(createElement("li", null, warning));
      });
    return meta;
  }

  function responseTotalPortions(data, recipes) {
    const supplied = first(data, ["portions", "total_portions", "summary.total_portions", "optimized_basket.total_portions"]);
    if (isPresent(supplied)) return supplied;
    if (!recipes.length) return null;
    const portions = recipes.map((recipe) => numeric(first(recipe, ["servings", "portions"])));
    return portions.every((value) => value !== null) ? portions.reduce((total, value) => total + value, 0) : null;
  }

  function renderShopping(data, recipes) {
    empty(dom.storeGroups);
    const financials=window.SmakoRecipes.financials(data);
    if(financials)dom.storeGroups.append(financials);
    const basket = optimizedBasket(data);
    const verification = renderBasketVerification(basket);
    const groups = basketGroups(basket);

    if (!groups.length) {
      dom.storeGroups.append(emptyMessage("Ingen optimerad inköpslista returnerades i svaret."));
    } else {
      groups.forEach((group) => dom.storeGroups.append(renderStoreGroup(group, verification.status, data.personal?.checks?.ingredient_product_details||[])));
    }
    renderMembershipPlanSummary(groups, data);

    const total = displayBasketMoney(
      first(basket, ["total", "total_cost", "grand_total", "basket_total"], first(data, ["total", "total_cost"])),
      verification.status,
    );
    dom.basketTotal.textContent = total || "Uppgift saknas";

    const totalPortions = responseTotalPortions(data, recipes);
    dom.portionsMetric.hidden = !isPresent(totalPortions);
    if (isPresent(totalPortions)) dom.totalPortions.textContent = String(totalPortions);

    const portionPrice = displayBasketMoney(
      first(basket, ["price_per_portion", "cost_per_portion"], first(data, ["price_per_portion", "cost_per_portion", "summary.price_per_portion"])),
      verification.status,
    );
    dom.portionPriceMetric.hidden = !portionPrice;
    if (portionPrice) dom.pricePerPortion.textContent = portionPrice;

    return { basket, groups, total };
  }

  function explicitSingleStore(data) {
    const direct = first(data, ["cheapest_single_store", "single_store_basket", "comparison.single_store"]);
    if (direct && typeof direct === "object") return direct;
    const options = list(first(data, ["single_store_options", "single_store_baskets"], []));
    const validOptions = options.filter((option) => {
      const valid = first(option, ["valid", "is_valid"], true);
      const complete = first(option, ["is_complete", "complete"], true);
      const missing = list(first(option, ["missing_ingredients", "missing_products"], []));
      return valid !== false && complete !== false && missing.length === 0;
    });
    return validOptions.reduce((cheapest, option) => {
      if (!cheapest) return option;
      const currentVerification = basketVerificationRank(first(option, ["verification_status"], "UNVERIFIED"));
      const cheapestVerification = basketVerificationRank(first(cheapest, ["verification_status"], "UNVERIFIED"));
      if (currentVerification !== cheapestVerification) {
        return currentVerification < cheapestVerification ? option : cheapest;
      }
      const currentTotal = numeric(first(option, ["total", "total_cost", "basket_total"]));
      const cheapestTotal = numeric(first(cheapest, ["total", "total_cost", "basket_total"]));
      if (currentTotal === null) return cheapest;
      return cheapestTotal === null || currentTotal < cheapestTotal ? option : cheapest;
    }, null);
  }

  function comparisonCard(label, value, note, highlight = false) {
    const card = createElement("article", `comparison-card${highlight ? " highlight" : ""}`);
    card.append(createElement("span", null, label));
    card.append(createElement("strong", null, value || "Uppgift saknas"));
    if (note) card.append(createElement("small", null, note));
    return card;
  }

  function renderComparison(data, shopping) {
    empty(dom.comparisonCards);
    const single = explicitSingleStore(data);
    const singleStatus = single && first(single, ["verification_status"], "UNVERIFIED");
    const singleTotal = single && displayBasketMoney(
      first(single, ["total", "total_cost", "basket_total"]),
      singleStatus,
    );
    const singleName = single && storeName(single);

    const selectedStoreNames = shopping.groups.map(storeName).filter(Boolean).join(" + ");
    const maxStores = first(data, ["max_stores", "request.max_stores", "parameters.max_stores"], dom.maxStoresInput.value);
    const optimizedLabel = isPresent(maxStores) ? `Optimerat med max ${maxStores} inköpsställen` : "Optimerad matkasse";

    dom.comparisonCards.append(comparisonCard(
      "Samma meny i billigaste giltiga priskontext",
      singleTotal,
      single ? singleName : "Ingen komplett korg för ett inköpsställe returnerades",
    ));
    dom.comparisonCards.append(comparisonCard(
      optimizedLabel,
      shopping.total,
      selectedStoreNames || "Butiksuppgift saknas",
    ));

    const savings = displayBasketMoney(first(shopping.basket, [
      "savings",
      "savings_vs_single_store",
      "saving",
    ], first(data, ["savings", "savings_vs_single_store", "comparison.savings"])),
    worstBasketVerification(singleStatus || "UNVERIFIED", shopping.basket.verification_status));
    if (savings) {
      dom.comparisonCards.append(comparisonCard(
        "Besparing mot ett inköpsställe",
        savings,
        "Beräknad av backend från de faktiska produktvalen",
        true,
      ));
    }
  }

  function scenarioLabel(scenario) {
    const supplied = first(scenario, ["label", "name"]);
    if (supplied) return supplied;
    const limit = numeric(first(scenario, ["max_stores", "store_limit"]));
    if (limit === null) return "Obegränsat antal inköpsställen";
    if (limit === 1) return "1 inköpsställe";
    return `Max ${formatNumber(limit)} inköpsställen`;
  }

  function renderScenarios(data) {
    empty(dom.optimizationScenarios);
    const scenarios = list(first(data, ["optimization_scenarios", "scenarios"], []));

    if (!scenarios.length) {
      dom.optimizationScenarios.append(emptyMessage("Inga separata inköpsscenarier returnerades i svaret."));
      return;
    }

    scenarios.forEach((scenario) => {
      const basket = first(scenario, ["basket", "optimized_basket"]);
      const error = first(scenario, ["error", "message"]);
      const hasBasket = basket && typeof basket === "object";
      const verificationStatus = hasBasket
        ? normalizeBasketVerification(first(basket, ["verification_status"], "UNVERIFIED"))
        : "INVALID";
      const card = createElement("article", `scenario-card${!hasBasket || error || verificationStatus === "INVALID" ? " is-error" : ""}`);
      card.setAttribute("role", "listitem");

      const heading = createElement("div");
      heading.append(createElement("h3", null, scenarioLabel(scenario)));
      heading.append(createElement(
        "p",
        "scenario-status",
        hasBasket && !error
          ? basketVerificationMeta(verificationStatus).title
          : "Ingen komplett korg",
      ));
      card.append(heading);

      if (!hasBasket || error) {
        card.append(createElement(
          "p",
          "scenario-error",
          error || "Backend returnerade ingen komplett korg för det här scenariot.",
        ));
        dom.optimizationScenarios.append(card);
        return;
      }

      const metrics = createElement("dl", "scenario-metrics");
      const totalRow = createElement("div");
      totalRow.append(createElement("dt", null, "Totalt"));
      totalRow.append(createElement(
        "dd",
        null,
        displayBasketMoney(first(basket, ["total", "total_cost"]), verificationStatus)
          || "Uppgift saknas",
      ));
      metrics.append(totalRow);

      const suppliedStoreCount = first(basket, ["store_count", "number_of_stores"]);
      const stores = list(first(basket, ["stores", "store_groups"], []));
      const storeCount = isPresent(suppliedStoreCount) ? suppliedStoreCount : stores.length;
      const storesRow = createElement("div");
      storesRow.append(createElement("dt", null, "Använda inköpsställen"));
      storesRow.append(createElement("dd", null, formatNumber(storeCount) || "Uppgift saknas"));
      metrics.append(storesRow);
      card.append(metrics);
      dom.optimizationScenarios.append(card);
    });
  }

  function optimizationStrategyLabel(value) {
    if (!isPresent(value)) return null;
    const strategy = String(value).toLowerCase();
    if (strategy === "optimized") return "Optimerad menysökning";
    if (strategy === "legacy") return "Legacy (recipe-first)";
    return String(value);
  }

  function optimizationCount(value) {
    if (Array.isArray(value)) return formatNumber(value.length);
    return formatNumber(value);
  }

  function renderOptimizationSettings(data) {
    empty(dom.optimizationSettingsMetrics);

    if (!debugMode) {
      dom.optimizationSettingsPanel.hidden = true;
      return;
    }

    const optimization = first(data, ["optimization"], null);
    const legacyComparison = first(data, ["legacy_comparison"], null);
    const optimizationObject = optimization && typeof optimization === "object" ? optimization : {};
    const legacyObject = legacyComparison && typeof legacyComparison === "object" ? legacyComparison : null;
    const legacyStatus = legacyObject
      ? first(legacyObject, ["basket.verification_status"], "UNVERIFIED")
      : "UNVERIFIED";
    const selectedStatus = first(data, ["optimized_basket.verification_status"], "UNVERIFIED");

    const hits = numeric(first(optimizationObject, ["basket_cache_hits", "cache_hits"], first(data, ["debug_info.search_stats.cache_hits"])));
    const misses = numeric(first(optimizationObject, ["basket_cache_misses", "cache_misses"], first(data, ["debug_info.search_stats.cache_misses"])));
    let hitRate = numeric(first(optimizationObject, ["basket_cache_hit_rate", "cache_hit_rate"], first(data, ["debug_info.search_stats.cache_hit_rate"])));
    if (hitRate === null && hits !== null && misses !== null && hits + misses > 0) {
      hitRate = hits / (hits + misses);
    }

    const metrics = [
      ["Strategi", optimizationStrategyLabel(first(optimizationObject, ["strategy"], first(data, ["strategy"])))],
      ["Max inköpsställen", optimizationCount(first(optimizationObject, ["max_stores"], first(data, ["max_stores", "request.max_stores", "parameters.max_stores"])))],
      ["Ekonomiska råvaror", optimizationCount(first(optimizationObject, ["economic_ingredients"], first(data, ["debug_info.economic_ingredients"])))],
      ["Kandidater skapade", optimizationCount(first(optimizationObject, ["candidate_recipes_generated"]))],
      ["Giltiga kandidater", optimizationCount(first(optimizationObject, ["candidate_recipes_valid"]))],
      ["Kandidater i sökpool", optimizationCount(first(optimizationObject, ["candidate_recipes_search_pool"]))],
      ["Legacy-kandidater tillagda", optimizationCount(first(optimizationObject, ["legacy_candidates_added"]))],
      ["Kandidater analyserade", optimizationCount(first(optimizationObject, ["candidate_recipes_analyzed"], first(data, ["debug_info.search_stats.candidate_count"])))],
      ["Beam width", optimizationCount(first(optimizationObject, ["beam_width"]))],
      ["Söktillstånd", optimizationCount(first(optimizationObject, ["states_evaluated"], first(data, ["debug_info.search_stats.states_evaluated"])))],
      ["Cacheträffar", hitRate === null ? null : formatPercent(hitRate)],
      ["Total körtid", formatDuration(first(optimizationObject, ["timings_seconds.total_runtime", "total_runtime", "runtime_seconds"], first(data, ["runtime_seconds", "timings.total_runtime"])))],
      ["Legacy-kostnad", legacyObject ? displayBasketMoney(first(legacyObject, ["total", "total_cost"]), legacyStatus) : null],
      ["Besparing mot legacy", legacyObject ? displayBasketMoney(
        first(legacyObject, ["savings"], first(optimizationObject, ["estimated_savings_vs_legacy"])),
        worstBasketVerification(legacyStatus, selectedStatus),
      ) : null],
    ];

    metrics.forEach(([label, value]) => {
      if (!isPresent(value)) return;
      const row = createElement("div", "optimization-metric");
      row.append(createElement("dt", null, label));
      row.append(createElement("dd", null, value));
      dom.optimizationSettingsMetrics.append(row);
    });

    dom.optimizationSettingsPanel.hidden = dom.optimizationSettingsMetrics.childElementCount === 0;
  }

  function appendQualityMetric(container, label, value, note = null) {
    if (!isPresent(value)) return;
    const card = createElement("article", "quality-metric");
    card.append(createElement("span", null, label));
    card.append(createElement("strong", null, value));
    if (note) card.append(createElement("small", null, note));
    container.append(card);
  }

  function appendStatusMetric(container, label, value) {
    if (!isPresent(value)) return;
    const status = statusMeta(value);
    const card = createElement("article", `quality-metric quality-status ${status.className}`);
    card.append(createElement("span", null, label));
    card.append(createElement("strong", null, status.label));
    container.append(card);
  }

  function repetitionText(value) {
    if (!value || typeof value !== "object") return null;
    const groups = [
      ["primary_proteins", "huvudråvara"], ["protein", "huvudråvara"],
      ["primary_carbs", "kolhydrat"], ["carb", "kolhydrat"],
    ];
    const seen = new Set();
    const parts = [];
    groups.forEach(([key, label]) => {
      const counts = value[key];
      if (!counts || typeof counts !== "object") return;
      Object.entries(counts).forEach(([name, countValue]) => {
        const count = numeric(countValue);
        const identity = `${label}:${name}`;
        if (count === null || count < 2 || seen.has(identity)) return;
        seen.add(identity);
        parts.push(`${label} ${name} × ${formatNumber(count)}`);
      });
    });
    return parts.length ? parts.join(" · ") : "Ingen markerad strukturell upprepning";
  }

  function renderQuality(data) {
    empty(dom.qualityOverview);
    empty(dom.nutritionQualityList);
    empty(dom.diversityQualityMetrics);
    dom.nutritionQualitySection.hidden = true;
    dom.diversityQualitySection.hidden = true;

    const quality = first(data, ["quality", "plan_quality"], null);
    if (!quality || typeof quality !== "object") {
      dom.qualityPanel.hidden = true;
      return;
    }

    const basketAudit = first(quality, ["basket_audit", "basketAudit"], {}) || {};
    const deficitsValue = first(basketAudit, ["deficits", "deficit_count"]);
    const deficitCount = arrayOrValueCount(deficitsValue);
    const ingredientsChecked = numeric(first(basketAudit, ["ingredients_checked", "checked_ingredients"]));
    const unknownQuantities = numeric(first(basketAudit, ["unknown_quantities", "unknown_quantity_count"]));

    appendStatusMetric(dom.qualityOverview, "Planens kvalitetsstatus", first(quality, ["status"]));
    appendQualityMetric(
      dom.qualityOverview,
      "Ingredienser kontrollerade",
      ingredientsChecked === null ? null : formatNumber(ingredientsChecked),
      "Gemensamt veckobehov mot köpt användbar mängd",
    );
    appendQualityMetric(
      dom.qualityOverview,
      "Mängdbrister",
      deficitCount === null ? null : formatNumber(deficitCount),
      deficitCount === 0 ? "Alla kontrollerade behov täcks" : "Minst ett behov saknar full täckning",
    );
    appendQualityMetric(
      dom.qualityOverview,
      "Okända produktmängder",
      unknownQuantities === null ? null : formatNumber(unknownQuantities),
      "Produktrader utan säker användbar mängd",
    );

    const nutrition = first(quality, ["nutrition"], null);
    const nutritionRecipes = nutrition && typeof nutrition === "object"
      ? list(first(nutrition, ["recipes", "recipe_results"], []))
      : [];
    if (nutritionRecipes.length) {
      nutritionRecipes.forEach((recipe) => {
        const card = createElement("article", "nutrition-quality-card");
        const heading = createElement("div", "nutrition-card-heading");
        heading.append(createElement("h4", null, first(recipe, ["recipe_name", "name"], "Recept")));
        const status = statusMeta(first(recipe, ["status"]));
        heading.append(createElement("span", `status-badge ${status.className}`, status.label));
        card.append(heading);

        const metrics = createElement("dl", "nutrition-card-metrics");
        [
          ["Energi", formatApproximate(first(recipe, ["kcal_per_serving", "kcal_per_portion"]), "kcal")],
          ["Protein", formatApproximate(first(recipe, ["protein_g_per_serving", "protein_g_per_portion"]), "g")],
          ["Grönsaker", formatApproximate(first(recipe, ["vegetable_g_per_serving", "vegetable_g_per_portion"]), "g")],
        ].forEach(([label, value]) => {
          if (!value) return;
          const row = createElement("div");
          row.append(createElement("dt", null, label));
          row.append(createElement("dd", null, value));
          metrics.append(row);
        });
        card.append(metrics);

        const confidence = first(recipe, ["confidence"]);
        const confidenceScore = formatPercent(first(recipe, ["confidence_score"]));
        if (isPresent(confidence) || confidenceScore) {
          card.append(createElement(
            "p",
            "quality-card-note",
            `Estimatets säkerhet: ${confidenceLabel(confidence)}${confidenceScore ? ` (${confidenceScore})` : ""}`,
          ));
        }
        const unestimated = list(first(recipe, ["unestimated_ingredients"], []));
        if (unestimated.length) {
          card.append(createElement(
            "p",
            "quality-card-warning",
            `Ej uppskattat: ${unestimated.join(", ")}`,
          ));
        }
        dom.nutritionQualityList.append(card);
      });
      dom.nutritionQualitySection.hidden = false;
    }

    const diversity = first(quality, ["diversity"], null);
    if (diversity && typeof diversity === "object") {
      appendStatusMetric(dom.diversityQualityMetrics, "Variationsstatus", first(diversity, ["status"]));
      appendQualityMetric(
        dom.diversityQualityMetrics,
        "Högsta receptlikhet",
        formatPercent(first(diversity, ["max_pairwise_similarity", "maximum_similarity"])),
      );
      appendQualityMetric(
        dom.diversityQualityMetrics,
        "Tillåten gräns",
        formatPercent(first(diversity, ["threshold", "near_duplicate_threshold"])),
      );
      appendQualityMetric(
        dom.diversityQualityMetrics,
        "Intern likhetspoäng",
        formatPercent(first(diversity, ["diversity_score"], first(data, ["diversity_score"]))),
        "Tekniskt mått, inte en validerad mänsklig kvalitetsprocent",
      );
      appendQualityMetric(
        dom.diversityQualityMetrics,
        "Återkommande struktur",
        repetitionText(first(diversity, ["repetition"], first(data, ["repetition"]))),
      );
      const pairs = list(first(diversity, ["pairs"], []));
      if (pairs.length) {
        const nearDuplicateCount = pairs.filter((pair) => first(pair, ["is_near_duplicate"], false) === true).length;
        appendQualityMetric(
          dom.diversityQualityMetrics,
          "Jämförda receptpar",
          formatNumber(pairs.length),
          nearDuplicateCount ? `${nearDuplicateCount} par över gränsen` : "Inga par över gränsen",
        );
      }
      dom.diversityQualitySection.hidden = dom.diversityQualityMetrics.childElementCount === 0;
    }

    dom.qualityPanel.hidden = dom.qualityOverview.childElementCount === 0
      && dom.nutritionQualitySection.hidden
      && dom.diversityQualitySection.hidden;
  }

  function renderSurplus(data) {
    empty(dom.surplusSummary);
    empty(dom.surplusItems);
    const surplus = first(data, ["surplus", "debug_info.surplus"], null);
    if (!surplus || typeof surplus !== "object") {
      dom.surplusPanel.hidden = true;
      return;
    }

    const estimatedValue = formatMoney(first(surplus, [
      "estimated_surplus_value",
      "estimated_surplus_value_total",
    ]));
    if (estimatedValue) {
      appendQualityMetric(
        dom.surplusSummary,
        "Uppskattat värde i överskott",
        estimatedValue,
        "Andel av inköpspriset för användbar mängd som blir kvar",
      );
    }

    const items = list(first(surplus, ["items", "audit_items"], []));
    if (!items.length) {
      dom.surplusItems.append(emptyMessage("Ingen användbar mängd blir över enligt basket-auditen."));
      dom.surplusPanel.hidden = false;
      return;
    }

    const table = createElement("table", "audit-table");
    const caption = createElement("caption", "visually-hidden", "Överskott per kontrollerad ingrediens");
    table.append(caption);
    const head = document.createElement("thead");
    const headRow = document.createElement("tr");
    ["Ingrediens", "Behövs", "Köps användbart", "Överskott", "Enhet", "Värde", "Mängdsäkerhet"].forEach((label) => {
      headRow.append(createElement("th", null, label));
    });
    head.append(headRow);
    table.append(head);

    const body = document.createElement("tbody");
    items.forEach((item) => {
      const row = document.createElement("tr");
      appendCell(row, first(item, ["canonical_name", "ingredient", "name"], "Ingrediens"), "audit-ingredient");
      appendCell(row, formatNumber(first(item, ["required_quantity", "required"])));
      appendCell(row, formatNumber(first(item, ["purchased_usable_quantity", "purchased_quantity", "purchased"])));
      appendCell(row, formatNumber(first(item, ["surplus_quantity", "surplus"])));
      appendCell(row, first(item, ["unit"], "—"));
      appendCell(row, formatMoney(first(item, ["estimated_surplus_value", "surplus_value"])));
      const confidenceCell = document.createElement("td");
      const confidence = first(item, ["quantity_confidence", "confidence"], "unknown");
      confidenceCell.append(createElement(
        "span",
        `confidence-badge confidence-${String(confidence).toLowerCase()}`,
        confidenceLabel(confidence),
      ));
      row.append(confidenceCell);
      body.append(row);
    });
    table.append(body);
    dom.surplusItems.append(table);
    dom.surplusPanel.hidden = false;
  }

  function storeNames(value) {
    if (Array.isArray(value)) return value.filter(isPresent).join(" + ");
    return isPresent(value) ? String(value) : "Butiksnamn saknas";
  }

  function appendTradeoffCard(container, label, value, stores, highlight = false) {
    const card = createElement("article", `tradeoff-card${highlight ? " highlight" : ""}`);
    card.append(createElement("span", null, label));
    card.append(createElement("strong", null, value || "Uppgift saknas"));
    if (stores) card.append(createElement("small", null, stores));
    container.append(card);
  }

  function renderStoreTradeoff(data) {
    empty(dom.storeTradeoffCards);
    const tradeoff = first(data, ["store_tradeoff", "debug_info.store_tradeoff"], null);
    if (!tradeoff || typeof tradeoff !== "object") {
      dom.storeTradeoffPanel.hidden = true;
      return;
    }

    const oneStoreStatus = first(
      tradeoff,
      ["one_store_verification_status"],
      "UNVERIFIED",
    );
    const selectedStatus = first(
      tradeoff,
      ["selected_verification_status"],
      first(data, ["optimized_basket.verification_status"], "UNVERIFIED"),
    );
    const oneStoreTotal = displayBasketMoney(first(tradeoff, ["one_store_total"]), oneStoreStatus);
    const selectedTotal = displayBasketMoney(first(tradeoff, ["selected_total"]), selectedStatus);
    const selectedStoreCount = numeric(first(tradeoff, ["selected_store_count"]));
    const extraStoreSavings = displayBasketMoney(
      first(tradeoff, ["extra_store_savings"]),
      worstBasketVerification(oneStoreStatus, selectedStatus),
    );
    const selectedLabel = selectedStoreCount === null
      ? "Vald plan"
      : `Vald plan · ${formatNumber(selectedStoreCount)} ${selectedStoreCount === 1 ? "inköpsställe" : "inköpsställen"}`;

    appendTradeoffCard(
      dom.storeTradeoffCards,
      "Samma meny i en giltig priskontext",
      oneStoreTotal || "Ingen komplett korg för ett inköpsställe",
      storeNames(first(tradeoff, ["one_store_names"])),
    );
    appendTradeoffCard(
      dom.storeTradeoffCards,
      selectedLabel,
      selectedTotal,
      storeNames(first(tradeoff, ["selected_store_names"])),
    );
    appendTradeoffCard(
      dom.storeTradeoffCards,
      "Besparing med extra inköpsställen",
      extraStoreSavings,
      "Deterministiskt beräknad skillnad mellan planerna",
      numeric(first(tradeoff, ["extra_store_savings"])) > 0,
    );
    dom.storeTradeoffPanel.hidden = dom.storeTradeoffCards.childElementCount === 0;
  }

  function warningText(warning) {
    if (typeof warning === "string") return warning;
    if (warning && typeof warning === "object") {
      return first(warning, ["message", "text", "detail", "warning"], null);
    }
    return null;
  }

  function localDateTime(value) {
    if (!value) return null;
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return null;
    return new Intl.DateTimeFormat("sv-SE", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(date);
  }

  function renderPriceFreshness(data) {
    const status = String(first(data, [
      "data.status",
      "price_data.status",
      "meta.data.status",
    ], "unknown")).toLowerCase();
    const observedAt = first(data, [
      "data.built_at",
      "price_data.built_at",
      "prices_updated_at",
      "snapshot_observed_at",
      "meta.data.built_at",
    ]);
    const timestamp = localDateTime(observedAt);
    const state = status === "fresh"
      ? "fresh"
      : status === "aging"
        ? "aging"
        : status === "degraded"
          ? "degraded"
        : new Set(["stale", "broken"]).has(status)
          ? "stale"
          : "unknown";
    const labels = {
      fresh: timestamp ? `Priser uppdaterade ${timestamp}` : "Prisunderlaget är färskt",
      aging: timestamp ? `Prisdata från ${timestamp}` : "Prisdata närmar sig stale-gränsen",
      degraded: timestamp ? `Aktuella priser från ${timestamp} med begränsad täckning` : "Aktuella priser med begränsad täckning",
      stale: timestamp ? `Äldre prisdata från ${timestamp}` : "Prisdata behöver uppdateras",
      unknown: timestamp ? `Prisdata byggda ${timestamp}` : "Prisdata: status saknas",
    };
    dom.priceFreshness.className = `freshness-pill is-${state === "degraded" ? "aging" : state}`;
    dom.priceFreshness.dataset.freshness = state;
    dom.priceFreshness.textContent = labels[state];
  }

  function priceContextCoverageLabel(context) {
    const name = String(first(context, ["display_name", "name"], "Priskälla"));
    const scope = String(first(context, ["price_scope_label", "scope_label"], "")).trim();
    if (!scope || name.toLowerCase().includes(scope.toLowerCase())) return name;
    return `${name} · ${scope}`;
  }

  function renderSourceCoverage(data) {
    empty(dom.comparedSourcesList);
    empty(dom.unavailableSourcesList);
    const priceData = first(data, ["data", "price_data", "meta.data"], {}) || {};
    const compared = list(first(priceData, ["compared_price_contexts"], []));
    const unavailable = list(first(priceData, ["excluded_price_contexts"], []));
    const seenCompared = new Set();
    compared.forEach((context) => {
      const key = String(first(context, ["context_id", "display_name"], ""));
      if (!key || seenCompared.has(key)) return;
      seenCompared.add(key);
      dom.comparedSourcesList.append(createElement("li", null, priceContextCoverageLabel(context)));
    });
    const seenUnavailable = new Set();
    unavailable.forEach((context) => {
      const key = String(first(context, ["context_id", "display_name"], ""));
      if (!key || seenUnavailable.has(key)) return;
      seenUnavailable.add(key);
      dom.unavailableSourcesList.append(createElement(
        "li",
        null,
        `${priceContextCoverageLabel(context)} kunde inte jämföras eftersom prisunderlaget behöver uppdateras.`,
      ));
    });
    dom.comparedSources.hidden = dom.comparedSourcesList.childElementCount === 0;
    dom.unavailableSources.hidden = dom.unavailableSourcesList.childElementCount === 0;
  }

  function renderSource(data, basket) {
    empty(dom.warningsList);
    empty(dom.sourceDescription);
    renderPriceFreshness(data);
    renderSourceCoverage(data);

    const providerValue = first(data, [
      "data_source",
      "provider",
      "provider_name",
      "price_provider",
      "meta.data_source",
      "meta.provider",
    ], "");
    const providerName = typeof providerValue === "object"
      ? first(providerValue, ["name", "provider", "type", "mode"], "")
      : String(providerValue || "");
    const mode = String(first(data, ["mode", "provider_mode", "meta.mode"], ""));
    const sourceKey = `${providerName} ${mode}`.toLowerCase();

    if (sourceKey.includes("federat") || sourceKey.includes("price-universe")) {
      const builtAt = first(data, ["data.built_at", "prices_updated_at"]);
      const updated = localDateTime(builtAt);
      dom.sourceDescription.textContent = `${updated ? `Priser uppdaterade ${updated}. ` : ""}Resultatet använder ett förbyggt federerat prisuniversum med tillgängliga online- eller butikskopplade prisdata. De ska inte tolkas som garanterade hyllpriser; fysisk tillgänglighet och hyllpris kan avvika.`;
      dom.footerSource.textContent = "Aktuella digitala prisdata. Pris och tillgänglighet kan förändras i butik.";
    } else if (sourceKey.includes("primat")) {
      dom.sourceDescription.append(document.createTextNode("Produkt-, pris- och priskontextdata i resultatet kommer via "));
      const link = createElement("a", null, "Primat");
      link.href = "https://primat.nu/";
      link.target = "_blank";
      link.rel = "noreferrer";
      dom.sourceDescription.append(link, document.createTextNode(". Recepten använder prisdatan som ekonomisk signal; alla visade priser och summor kommer från backend."));
      dom.footerSource.textContent = "Prisdata via Primat. Priser och tillgänglighet kan förändras i butik.";
    } else if (sourceKey.includes("mock") || sourceKey.includes("demo")) {
      dom.sourceDescription.textContent = "Resultatet använder demodata från MockPriceProvider. Den demonstrerar hela flödet, men priserna ska inte tolkas som aktuella butikspriser.";
      dom.footerSource.textContent = "Demoläge: prisdata från MockPriceProvider, inte aktuella butikspriser.";
    } else {
      dom.sourceDescription.textContent = "Backend-svaret angav ingen tydlig prisdatakälla. Kontrollera dataläget innan priserna används som inköpsunderlag.";
      dom.footerSource.textContent = "Produktpriser visas endast när de kommer från tjänstens prisdata.";
    }

    const priceData = first(data, ["data", "price_data", "meta.data"], null);
    if (priceData && typeof priceData === "object") {
      const freshness = String(first(priceData, ["status"], "")).toLowerCase();
      const ageHours = numeric(first(priceData, ["oldest_price_age_hours"], null));
      if (freshness === "fresh") {
        const freshnessText = ageHours !== null && ageHours < 24
          ? " Priser uppdaterade idag."
          : " Prisunderlaget är färskt enligt tjänstens freshness-policy.";
        dom.sourceDescription.append(document.createTextNode(freshnessText));
      } else if (freshness === "aging") {
        dom.warningsList.append(createElement("li", null, "Vissa priser närmar sig stale-gränsen och kan vara äldre än 24 timmar."));
      } else if (freshness === "degraded") {
        const excluded = numeric(first(priceData, ["excluded_stale_context_count"], null));
        const coverage = excluded === null ? "En eller flera äldre priskällor" : `${excluded} äldre priskontext${excluded === 1 ? "" : "er"}`;
        dom.warningsList.append(createElement("li", null, `${coverage} har uteslutits. Planen använder bara priskontexter som fortfarande klarar aktualitetskravet.`));
      } else if (freshness === "stale" || freshness === "broken") {
        dom.warningsList.append(createElement("li", null, "Prisunderlaget är inte färskt. Skapa inte ett inköpsunderlag innan datan har uppdaterats."));
      }
    }

    const warnings = [
      ...list(first(data, ["warnings", "meta.warnings"], [])),
      ...list(first(basket, ["warnings"], [])),
    ].map(warningText).filter(Boolean);

    warnings.forEach((warning) => dom.warningsList.append(createElement("li", null, warning)));
  }

  function plansByMode(data) {
    const rawPlans = first(data, ["plans"], null);
    const plans = new Map();
    if (Array.isArray(rawPlans)) {
      rawPlans.forEach((option) => {
        if (!option || typeof option !== "object") return;
        const mode = normalizeDiversityMode(first(option, ["mode"]), "");
        if (mode) plans.set(mode, option);
      });
      return plans;
    }
    if (!rawPlans || typeof rawPlans !== "object") return plans;
    Object.entries(rawPlans).forEach(([key, option]) => {
      if (!option || typeof option !== "object") return;
      const mode = normalizeDiversityMode(first(option, ["mode"], key), "");
      if (mode) plans.set(mode, option);
    });
    return plans;
  }

  function optionDiversityScore(option) {
    return first(option, [
      "diversity_score",
      "quality.diversity.diversity_score",
      "optimization.diversity_score",
    ]);
  }

  function optionMaximumSimilarity(option) {
    return first(option, [
      "max_pairwise_similarity",
      "quality.diversity.max_pairwise_similarity",
      "quality.diversity.maximum_similarity",
    ]);
  }

  function appendOptionMetric(container, label, value) {
    if (!isPresent(value)) return;
    const row = createElement("div");
    row.append(createElement("dt", null, label));
    row.append(createElement("dd", null, value));
    container.append(row);
  }

  function diversityPremiumVerification(option, plans) {
    const optionStatus = first(
      option,
      ["optimized_basket.verification_status"],
      "UNVERIFIED",
    );
    const balanced = plans.get("balanced");
    const balancedStatus = balanced
      ? first(balanced, ["optimized_basket.verification_status"], "UNVERIFIED")
      : "UNVERIFIED";
    return worstBasketVerification(optionStatus, balancedStatus);
  }

  function appendStructureMetrics(container, option) {
    if (option.variation_policy_version !== "structural-menu-v2") {
      appendOptionMetric(container, "Variationsbedömning", "Äldre meny – inte bedömd med aktuell policy");
      return;
    }
    const repetition = first(option, ["repetition", "quality.diversity.repetition"], {});
    const families = Object.keys(repetition.recipe_families || {}).length;
    const methods = Object.keys(repetition.cooking_methods || {}).length;
    appendOptionMetric(container, "Rättfamiljer", String(families));
    appendOptionMetric(container, "Tillagningssätt", String(methods));
  }

  function appendVariationExplanation(container, option, mode, verification) {
    if (option.variation_policy_version !== "structural-menu-v2") return;
    if (mode === "varied") {
      const distance = option.inter_plan_distance;
      if (distance) {
        container.append(createElement("p", "plan-option-footnote",
          `${distance.structurally_different_dinners} av ${distance.dinner_count} middagar skiljer sig från Balanserad`));
      }
      const delta = first(option, ["premium_vs_balanced"], 0);
      const premium = displayBasketMoney(Math.abs(delta), verification);
      const priceText = delta === 0 ? "Samma totalpris som Balanserad" : `${premium} ${delta > 0 ? "dyrare" : "billigare"} totalt`;
      container.append(createElement("p", "plan-option-footnote",
        `${priceText}. Kostnadstak: högst ${first(option, ["varied_budget_percent"], 25)} % över Balanserad.`));
    }
    list(first(option, ["variation_limitations"], [])).forEach((text) =>
      container.append(createElement("p", "plan-option-footnote", text)));
  }

  function planOptionCard(mode, option, plans) {
    const meta = diversityModes[mode];
    const premiumVerification = diversityPremiumVerification(option, plans);
    const button = createElement("button", "plan-option-card");
    button.type = "button";
    button.dataset.planMode = mode;
    button.setAttribute("role", "radio");
    button.setAttribute("aria-checked", String(mode === activePlanMode));

    const heading = createElement("div", "plan-option-heading");
    const title = createElement("div");
    title.append(createElement("strong", null, meta.label));
    title.append(createElement("small", null, meta.description));
    heading.append(title, createElement("span", "plan-option-check", "Vald"));
    button.append(heading);

    const metrics = createElement("dl", "plan-option-metrics");
    appendOptionMetric(
      metrics,
      "Matkasse",
      displayBasketMoney(
        first(option, ["optimized_basket.total", "optimized_basket.total_cost", "total"]),
        first(option, ["optimized_basket.verification_status"], "UNVERIFIED"),
      ),
    );
    appendStructureMetrics(metrics, option);
    button.append(metrics);
    appendVariationExplanation(button, option, mode, premiumVerification);
    return button;
  }

  function renderPlanOptions(data) {
    empty(dom.planOptionsList);
    empty(dom.activePlanSummary);
    const plans = plansByMode(data);
    if (!plans.size) {
      dom.planOptionsPanel.hidden = true;
      return plans;
    }

    if (!plans.has(primaryPlanMode)) plans.set(primaryPlanMode, data);
    ["cheapest", "balanced", "varied"].forEach((mode) => {
      const option = plans.get(mode);
      if (option) dom.planOptionsList.append(planOptionCard(mode, option, plans));
    });

    const errors = first(data, ["diversity_plan_errors"], {}) || {};
    Object.entries(errors).forEach(([rawMode, message]) => {
      const mode = normalizeDiversityMode(rawMode, "");
      if (!mode || plans.has(mode)) return;
      const card = createElement("article", "plan-option-card is-unavailable");
      card.append(createElement("strong", null, `${diversityModes[mode].label} · ej tillgänglig`));
      card.append(createElement("small", null, String(message)));
      dom.planOptionsList.append(card);
    });

    dom.planOptionsPanel.hidden = false;
    return plans;
  }

  function updatePlanOptionSelection() {
    dom.planOptionsList.querySelectorAll("[data-plan-mode]").forEach((button) => {
      const selected = button.dataset.planMode === activePlanMode;
      button.classList.toggle("is-selected", selected);
      button.setAttribute("aria-checked", String(selected));
    });
  }

  function renderActivePlanSummary(data, mode, isPrimary) {
    empty(dom.activePlanSummary);
    const meta = diversityModes[mode];
    const premiumVerification = diversityPremiumVerification(
      data,
      plansByMode(currentResponse || data),
    );
    const heading = createElement("div", "active-plan-heading");
    heading.append(createElement("span", null, "Visar nu"));
    heading.append(createElement("strong", null, meta.label));
    dom.activePlanSummary.append(heading);

    const metrics = createElement("dl", "active-plan-metrics");
    appendOptionMetric(
      metrics,
      "Total",
      displayBasketMoney(
        first(data, ["optimized_basket.total", "optimized_basket.total_cost", "total"]),
        first(data, ["optimized_basket.verification_status"], "UNVERIFIED"),
      ),
    );
    const selected = plansByMode(currentResponse || data).get(mode) || data;
    appendStructureMetrics(metrics, selected);
    dom.activePlanSummary.append(metrics);
    appendVariationExplanation(dom.activePlanSummary, selected, mode, premiumVerification);
    dom.primaryPlanNote.hidden = isPrimary;
  }

  function alternativePlanView(option, mode) {
    const view = { ...currentResponse, ...option };
    view.diversity_mode = mode;
    view.plans = currentResponse.plans;
    view.diversity_plan_errors = currentResponse.diversity_plan_errors;
    view.single_store_options = [];
    view.cheapest_single_store = null;
    view.single_store_basket = null;
    view.optimization_scenarios = [];
    view.scenarios = [];
    view.legacy_comparison = null;
    view.store_tradeoff = null;
    view.quality = first(option, ["quality"], null);
    view.surplus = first(option, ["surplus"], null);
    view.optimization = {
      ...(currentResponse.optimization || {}),
      diversity_mode: mode,
      diversity_score: optionDiversityScore(option),
      states_evaluated: first(option, ["states_evaluated"], first(currentResponse, ["optimization.states_evaluated"])),
      basket_calculations: first(option, ["basket_calculations"], first(currentResponse, ["optimization.basket_calculations"])),
    };
    return view;
  }

  function renderPlanContent(data, isPrimary) {
    const mode = normalizeDiversityMode(first(data, ["diversity_mode"], activePlanMode));
    dom.resultsTitle.textContent = diversityModes[mode].resultTitle;
    dom.results.querySelector(".recipe-search-status")?.remove();
    const searchNotice=window.SmakoRecipes.searchNotice(data,mode);
    if(searchNotice)dom.resultsTitle.after(searchNotice);
    const recipes = renderRecipes(data);
    renderIngredients(data);
    const shopping = renderShopping(data, recipes);
    dom.summaryMeals.textContent = String(recipes.length || "—");
    dom.summaryServings.textContent = String(first(recipes[0], ["servings", "portions"], dom.servingsInput.value));
    dom.summaryStores.textContent = String(shopping.groups.length || "—");
    dom.summaryTotal.textContent = shopping.total || "—";
    dom.summaryPerServing.textContent = displayBasketMoney(
      first(data, ["price_per_portion", "optimized_basket.price_per_portion"]),
      first(shopping.basket, ["verification_status"], "UNVERIFIED"),
    ) || "—";

    dom.comparisonPanel.hidden = !isPrimary;
    dom.scenariosPanel.hidden = !isPrimary;
    if (isPrimary) {
      renderComparison(data, shopping);
      renderScenarios(data);
      renderOptimizationSettings(data);
    } else {
      empty(dom.comparisonCards);
      empty(dom.optimizationScenarios);
      dom.optimizationSettingsPanel.hidden = true;
    }

    renderQuality(data);
    renderSurplus(data);
    renderStoreTradeoff(isPrimary ? data : { store_tradeoff: null });
    renderSource(data, shopping.basket);
  }

  function updatePlanPersistence(data) {
    const planId = first(data, ["plan_id", "id"]);
    const createdAt = localDateTime(first(data, ["plan_created_at", "created_at"]));
    const pricedAt = localDateTime(first(data, [
      "data.pricing_timestamp",
      "plan.data.pricing_timestamp",
    ]));
    if (!planId) {
      dom.planPersistenceStatus.textContent = "Planen är tillfällig och har ingen sparad planlänk.";
      dom.copyPlanLink.hidden = true;
      dom.newPricesBanner.hidden = true;
      return;
    }
    dom.planPersistenceStatus.textContent = createdAt
      ? `Sparad ${createdAt}${pricedAt ? ` · prisberäknad ${pricedAt}` : ""}. Beloppet ändras inte i efterhand.`
      : "Planen är sparad. Priserna ändras inte i efterhand.";
    if (data.personal) dom.planPersistenceStatus.textContent += ` Revision ${data.plan_revision}. Receptbyte och omräkning sparar en ny revision.`;
    dom.copyPlanLink.hidden = false;
    const versionStatus = String(first(data, ["price_version_status"], "current"));
    const savedUniverseId = first(data, ["price_universe_id", "data.price_universe_id"]);
    const showBanner = versionStatus === "newer_available"
      || versionStatus === "coverage_changed"
      || (versionStatus === "unavailable" && Boolean(savedUniverseId));
    dom.newPricesBanner.hidden = !showBanner && !data.personal;
    if (versionStatus === "coverage_changed") {
      dom.newPricesTitle.textContent = "En tidigare priskälla behöver uppdateras";
      dom.newPricesMessage.textContent = "Planen visas med priset från när den skapades. Räkna om för att använda bara priskällor som är aktuella nu.";
    } else if (versionStatus === "unavailable") {
      dom.newPricesTitle.textContent = "Aktuella priser kan inte kontrolleras just nu";
      dom.newPricesMessage.textContent = "Den sparade planen och dess ursprungliga pris visas oförändrade. Försök kontrollera aktuella priser senare.";
    } else {
      dom.newPricesTitle.textContent = showBanner ? "Nya priser finns" : "Samordnade inköp för hela veckan";
      dom.newPricesMessage.textContent = showBanner ? "Din sparade plan visas fortfarande med sitt ursprungliga prisunderlag." : "Räkna uttryckligen om med aktuellt prisunderlag och skafferi. Den tidigare revisionen bevaras.";
    }
    dom.recalculatePlanButton.hidden = !data.personal && !Boolean(first(data, ["recalculation_available"], false));
    dom.recalculatePlanButton.textContent = data.personal ? "Räkna om inköpslistan" : "Uppdatera planen";
  }

  function applySavedRequestToForm(request) {
    if (!request || typeof request !== "object") return;
    dom.postalCode.value = first(request, ["postal_code"], dom.postalCode.value);
    dom.recipesInput.value = String(first(request, ["recipes"], dom.recipesInput.value));
    dom.servingsInput.value = String(first(request, ["servings"], dom.servingsInput.value));
    dom.maxStoresInput.value = String(first(request, ["max_stores"], dom.maxStoresInput.value));
    dom.purchasePlanningMode.value = first(request, ["purchase_planning_mode"], "exact");
    recipeControls.restore(request);
    dom.dietPreference.value = first(request, ["diet_preference"], dom.dietPreference.value);
    checkDiversityInput(normalizeDiversityMode(first(request, ["diversity_mode"], "balanced")));
    dom.variedBudget.value = String(first(request, ["varied_budget_percent"], 25));
    setSelectedMemberships(first(request, ["membership_programs", "memberships"], []), { persist: true });
    const availability = first(request, ["availability_mode"], "normal");
    dom.availabilityInputs.forEach((input) => { input.checked = input.value === availability; });
    dom.excludedIngredients.value = list(first(request, ["avoid_ingredients"], [])).join(", ");
    updatePortionChip();
    persistPlannerPreferences();
  }

  function selectPlanMode(rawMode) {
    if (!currentResponse) return;
    const mode = normalizeDiversityMode(rawMode, "");
    if (!mode) return;
    const plans = plansByMode(currentResponse);
    const isPrimary = mode === primaryPlanMode;
    const option = plans.get(mode);
    if (!isPrimary && !option) return;

    activePlanMode = mode;
    checkDiversityInput(mode);
    const view = isPrimary ? currentResponse : alternativePlanView(option, mode);
    renderPlanContent(view, isPrimary);
    updatePlanOptionSelection();
    renderActivePlanSummary(option || view, mode, isPrimary);
  }

  function renderResults(data) {
    const location = first(data, ["location", "location_name", "area", "meta.location"]);
    dom.resultLocation.textContent = location ? `Prisområde: ${location}` : "Veckomeny från tillgänglig prisdata";
    currentResponse = data;
    primaryPlanMode = normalizeDiversityMode(first(data, ["diversity_mode"], selectedDiversityMode()));
    activePlanMode = primaryPlanMode;
    const plans = renderPlanOptions(data);
    const primaryOption = plans.get(primaryPlanMode);
    renderPlanContent(data, true);
    updatePlanOptionSelection();
    if (plans.size) renderActivePlanSummary(primaryOption || data, primaryPlanMode, true);
    checkDiversityInput(primaryPlanMode);
    updatePlanPersistence(data);

    clearStatus();
    dom.results.hidden = false;
    scrollToNode(dom.results, "start");
    window.requestAnimationFrame(() => dom.resultsTitle.focus({ preventScroll: true }));
    sendAnalyticsEvent("shopping_list_opened", {
      actual_stores: list(first(data, ["optimized_basket.stores"], [])).length,
    });
  }

  function planFromEnvelope(payload) {
    if (!payload || typeof payload !== "object") return null;
    if (!payload.plan || typeof payload.plan !== "object") return payload;
    const warnings = list(payload.plan.warnings).slice();
    if (payload.prices_changed_since_creation) {
      warnings.push("Prisunderlaget har uppdaterats sedan planen skapades. Den sparade planen visas fortfarande med sitt ursprungliga prisunderlag.");
    }
    if (payload.price_contexts_changed_since_creation) {
      warnings.push("En priskontext som planen använde är inte längre aktuell. Det sparade beloppet är priset från när planen skapades, inte ett nytt aktuellt pris.");
    }
    return {
      ...payload.plan,
      plan_id: payload.plan_id,
      plan_revision: payload.revision,
      plan_created_at: payload.created_at,
      reproducible: payload.reproducible,
      price_version_status: payload.price_version_status,
      price_universe_id: payload.price_universe_id,
      price_contexts_changed_since_creation: payload.price_contexts_changed_since_creation,
      unavailable_saved_context_ids: payload.unavailable_saved_context_ids,
      active_price_freshness: payload.active_price_freshness,
      recalculation_available: payload.recalculation_available,
      warnings,
    };
  }

  function applySavedPlan(payload, { updateUrl = true } = {}) {
    savedPlanRequest = payload && payload.request && typeof payload.request === "object"
      ? payload.request
      : null;
    if (savedPlanRequest) applySavedRequestToForm(savedPlanRequest);
    const savedMemberships = first(payload, [
      "request.membership_programs",
      "request.memberships",
    ]);
    if (savedMemberships !== undefined) setSelectedMemberships(savedMemberships, { persist: true });
    const plan = planFromEnvelope(payload);
    if (!plan) throw new Error("Servern returnerade ingen läsbar plan.");
    if (plan.plan_id) {
      try { window.localStorage.setItem(lastPlanStorageKey, plan.plan_id); } catch (_error) { /* Optional device-local convenience. */ }
    }
    renderResults(plan);
    window.SmakoRecipes.forgetJob("public");
    if (updateUrl && plan.plan_id) {
      const url = planUrl(plan.plan_id);
      if (!debugMode) url.searchParams.delete("debug");
      window.history.replaceState({ planId: plan.plan_id }, "", url);
    }
  }

  async function responseJson(response) {
    try { return await response.json(); } catch (_error) { return null; }
  }

  function planningError(payload, fallback, status = null, errorCode = null, retryAfter = null) {
    const error=new Error(errorFromResponse(payload,fallback,status,errorCode,retryAfter));
    error.planningDiagnostics=payload?.planning_diagnostics;return error;
  }

  async function changeCompletePlan(action, fields, button) {
    if (activePlanRequest || !currentResponse?.plan_id) return;
    const request = {controller:new AbortController(), deadline:Date.now()+PLAN_WAIT_MS, id:crypto.randomUUID()};
    activePlanRequest=request;setLoading(true);if(button)button.disabled=true;
    try {
      const result=await boundedRequest(request.controller,PLAN_WAIT_MS,async signal=>{
        const stateResponse=await fetch("/api/personal/state",{headers:{Accept:"application/json"},cache:"no-store",signal});
        const state=await responseJson(stateResponse);if(!stateResponse.ok)throw new Error(errorFromResponse(state,"Skafferiet kunde inte läsas."));
        const final=await window.SmakoRecipes.jobRequest({scope:"public",url:`/api/personal/plans/${encodeURIComponent(currentResponse.plan_id)}/change`,payload:{action,revision:currentResponse.plan_revision,pantry_revision:state.revision,...fields},requestId:request.id,signal,context:{kind:"change"},onProgress:message=>{dom.loadingMessage.textContent=message;}});
        const payload=await responseJson(final);final.smakoCheck?.();if(!final.ok)throw planningError(payload,"Planen kunde inte räknas om. Din tidigare revision finns kvar.",final.status);return payload;
      });
      applySavedPlan(result.saved);if(action==="replace")sendAnalyticsEvent("recipe_replaced");
    } catch(error){if(error.lifecycle)return;showError(`${error.message} Fel-ID: ${request.id}`,error.planningDiagnostics);}
    finally{if(activePlanRequest===request){activePlanRequest=null;setLoading(false);}if(button)button.disabled=false;}
  }

  async function resumePublicJob() {
    const pending=window.SmakoRecipes.pendingJob("public");if(!pending||activePlanRequest)return;
    const request={controller:new AbortController(),deadline:Date.now()+PLAN_WAIT_MS,id:crypto.randomUUID()};activePlanRequest=request;planViewEpoch+=1;savedPlanController?.abort();setLoading(true);
    dom.loadingMessage.textContent="Återansluter till din pågående menyberäkning…";
    try {
      const payload=await boundedRequest(request.controller,PLAN_WAIT_MS,async signal=>{
        const response=await window.SmakoRecipes.jobRequest({scope:"public",signal,onProgress:message=>{dom.loadingMessage.textContent=message;}});
        const data=await responseJson(response);response.smakoCheck?.();if(!response.ok)throw planningError(data,response.status===410?"Beräkningen avslutades vid serveromstart. Dina val finns kvar; skapa menyn igen.":"Beräkningen kunde inte återläsas.",response.status);return data;
      });
      applySavedPlan(payload.saved||payload);
    }catch(error){if(error.lifecycle)return;showError(`${error.message} Dina val och tidigare sparade planer finns kvar.`,error.planningDiagnostics);}
    finally{if(activePlanRequest===request){activePlanRequest=null;setLoading(false);}}
  }

  async function replaceRecipe(recipeIndex, button) {
    if (currentResponse?.personal) {
      const slots = currentResponse.personal.slots.filter(slot => slot.recipe);
      return changeCompletePlan("replace", {slot_id:slots[recipeIndex]?.id}, button);
    }
    const planId = first(currentResponse, ["plan_id"]);
    if (!planId) return;
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Byter…";
    try {
      const response = await fetch(`/api/plans/${encodeURIComponent(planId)}/replace-recipe`, {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        body: JSON.stringify({ recipe_index: recipeIndex }),
      });
      const payload = await responseJson(response);
      if (!response.ok) throw new Error(errorFromResponse(payload, "Receptet kunde inte bytas."));
      applySavedPlan(payload);
      sendAnalyticsEvent("recipe_replaced");
    } catch (error) {
      showError(error instanceof Error ? error.message : "Receptet kunde inte bytas.");
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }

  function closeAlternativesDialog() {
    if (dom.alternativesDialog.open) dom.alternativesDialog.close();
  }

  async function replaceProduct(productId, replacementProductId, button) {
    const planId = first(currentResponse, ["plan_id"]);
    if (!planId) return;
    button.disabled = true;
    dom.alternativesStatus.textContent = "Räknar om hela matkassen…";
    try {
      const response = await fetch(`/api/plans/${encodeURIComponent(planId)}/replace-product`, {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        body: JSON.stringify({ product_id: productId, replacement_product_id: replacementProductId }),
      });
      const payload = await responseJson(response);
      if (!response.ok) throw new Error(errorFromResponse(payload, "Varan kunde inte bytas."));
      closeAlternativesDialog();
      applySavedPlan(payload);
    } catch (error) {
      dom.alternativesStatus.textContent = error instanceof Error ? error.message : "Varan kunde inte bytas.";
    } finally {
      button.disabled = false;
    }
  }

  async function openProductAlternatives(context) {
    const planId = first(currentResponse, ["plan_id"]);
    if (!planId || !context.product_id) return;
    dom.alternativesSummary.textContent = `Alternativ till ${context.product_name}`;
    dom.alternativesStatus.textContent = "Hämtar kompatibla varor…";
    empty(dom.alternativesList);
    dom.alternativesDialog.showModal();
    try {
      const response = await fetch(
        `/api/plans/${encodeURIComponent(planId)}/products/${encodeURIComponent(context.product_id)}/alternatives`,
        { headers: { Accept: "application/json" } },
      );
      const payload = await responseJson(response);
      if (!response.ok) throw new Error(errorFromResponse(payload, "Alternativen kunde inte hämtas."));
      const alternatives = list(first(payload, ["alternatives", "products"], payload));
      dom.alternativesStatus.textContent = alternatives.length ? "" : "Inga kompatibla alternativ hittades.";
      alternatives.forEach((alternative) => {
        const alternativeId = first(alternative, ["product_id", "id"]);
        if (!alternativeId || alternativeId === context.product_id) return;
        const card = createElement("article", "product-alternative");
        const text = createElement("div");
        text.append(createElement("strong", null, first(alternative, ["product_name", "name"], "Namnlös vara")));
        text.append(createElement("span", null, [
          first(alternative, ["brand"]),
          first(alternative, ["package_description", "package_size"]),
          formatMoney(first(alternative, ["total_price", "effective_price", "price", "unit_price"])),
        ].filter(Boolean).join(" · ")));
        const choose = createElement("button", "secondary-button compact-button", "Välj");
        choose.type = "button";
        choose.addEventListener("click", () => void replaceProduct(context.product_id, alternativeId, choose));
        card.append(text, choose);
        dom.alternativesList.append(card);
      });
    } catch (error) {
      dom.alternativesStatus.textContent = error instanceof Error ? error.message : "Alternativen kunde inte hämtas.";
    }
  }

  function syncReportFields() {
    const type = dom.reportType.value;
    dom.reportPriceFields.hidden = !new Set([
      "PRICE_DIFFERENCE",
      "LOCAL_PROMOTION",
      "PROMOTION_MISSING_FROM_APP",
      "PRODUCT_IDENTITY_CORRECTION",
      "RECEIPT_PURCHASE",
    ]).has(type);
    dom.reportPromotionFields.hidden = !new Set([
      "LOCAL_PROMOTION",
      "PROMOTION_MISSING_FROM_APP",
    ]).has(type);
    if (type === "PRODUCT_NOT_FOUND") {
      dom.reportStatus.textContent = "Rapporten betyder att du inte kunde hitta exakt denna vara – inte att den säkert är slut.";
    } else {
      dom.reportStatus.textContent = "";
    }
    const requiresStore = new Set([
      "PRODUCT_FOUND",
      "PRODUCT_NOT_FOUND",
      "PRICE_DIFFERENCE",
      "LOCAL_PROMOTION",
      "PROMOTION_MISSING_FROM_APP",
      "RECEIPT_PURCHASE",
    ]).has(type);
    dom.reportPhysicalStore.required = requiresStore;
    dom.reportStoreRequirement.hidden = !requiresStore || Boolean(dom.reportPhysicalStore.value);
  }

  function renderPhysicalStoreOptions(options, context = {}) {
    const selectedBefore = context.physical_store_id || dom.reportPhysicalStore.value;
    while (dom.reportPhysicalStore.options.length > 1) dom.reportPhysicalStore.remove(1);
    options.forEach((store) => {
      const option = document.createElement("option");
      option.value = store.id;
      option.textContent = [store.name, store.address, store.city].filter(Boolean).join(" · ");
      option.dataset.chain = store.chain || "";
      option.dataset.externalStoreId = store.external_store_id || "";
      dom.reportPhysicalStore.append(option);
    });
    const inferred = options.find((store) => (
      context.source_provider_store_id
      && context.chain
      && String(store.external_store_id || "") === String(context.source_provider_store_id)
      && String(store.chain || "").toLowerCase() === String(context.chain).toLowerCase()
    ));
    const selected = selectedBefore || inferred?.id || "";
    if (Array.from(dom.reportPhysicalStore.options).some((option) => option.value === selected)) {
      dom.reportPhysicalStore.value = selected;
    }
    syncReportFields();
  }

  async function loadPhysicalStoreOptions(context = {}) {
    if (physicalStoreOptions.length) {
      renderPhysicalStoreOptions(physicalStoreOptions, context);
      return;
    }
    if (!physicalStoreOptionsPromise) {
      const location = first(currentResponse, ["plan.location", "location"], "");
      const params = new URLSearchParams();
      if (location && !/^\d{5}$/.test(String(location))) params.set("city", String(location));
      const queryString = params.toString();
      const url = `/api/community-evidence/store-options${queryString ? `?${queryString}` : ""}`;
      physicalStoreOptionsPromise = fetch(url, { headers: { Accept: "application/json" } })
        .then(async (response) => {
          const payload = await responseJson(response);
          if (!response.ok) throw new Error(errorFromResponse(payload, "Butikslistan kunde inte hämtas."));
          physicalStoreOptions = list(payload);
          return physicalStoreOptions;
        })
        .finally(() => { physicalStoreOptionsPromise = null; });
    }
    try {
      renderPhysicalStoreOptions(await physicalStoreOptionsPromise, context);
    } catch (error) {
      dom.reportStatus.textContent = error instanceof Error
        ? error.message
        : "Butikslistan kunde inte hämtas.";
    }
  }

  function ensureReportOption(value, label) {
    if (Array.from(dom.reportType.options).some((option) => option.value === value)) return;
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    dom.reportType.append(option);
  }

  function removeReportOption(value) {
    const option = Array.from(dom.reportType.options).find((row) => row.value === value);
    if (option) option.remove();
  }

  function openReportDialog(context = {}, preferredType = null) {
    reportContext = context;
    reportIdempotencyKey = newEvidenceIdempotencyKey();
    dom.reportForm.reset();
    if (context.plan_id && context.source_product_id) {
      // A product selected in a saved plan is necessarily known to the app.
      // Its report uses the server-bound endpoint below; missing-app reports
      // belong to the standalone unknown-barcode flow.
      removeReportOption("PRODUCT_MISSING_FROM_APP");
    } else {
      ensureReportOption("PRODUCT_MISSING_FROM_APP", "Varan saknas i appen");
    }
    ensureReportOption("LOCAL_PROMOTION", "Lokal kampanj saknas");
    dom.reportType.value = preferredType || context.evidence_type || "PRODUCT_NOT_FOUND";
    dom.reportProductSummary.textContent = [
      context.product_name || "Okänd vara",
      context.brand,
      context.package_description,
      context.store_display_name,
    ].filter(Boolean).join(" · ");
    dom.reportPhysicalStore.value = context.physical_store_id || "";
    dom.reportedPrice.value = "";
    dom.reportStatus.textContent = "";
    syncReportFields();
    dom.reportDialog.showModal();
    window.requestAnimationFrame(() => dom.reportType.focus());
    void loadPhysicalStoreOptions(context);
  }

  function closeReportDialog() {
    if (dom.reportDialog.open) dom.reportDialog.close();
    reportContext = null;
    reportIdempotencyKey = null;
  }

  async function submitCommunityReport(event) {
    event.preventDefault();
    if (!reportContext) return;
    const type = dom.reportType.value;
    const shelfPrice = decimalValue(dom.reportedPrice.value);
    const selectedStore = dom.reportPhysicalStore.value
      ? dom.reportPhysicalStore.selectedOptions[0]
      : null;
    if (dom.reportPhysicalStore.required && !dom.reportPhysicalStore.value) {
      dom.reportStatus.textContent = "Välj den exakta fysiska butik där du gjorde observationen.";
      dom.reportPhysicalStore.focus();
      return;
    }
    if (!dom.reportPriceFields.hidden && shelfPrice === null) {
      dom.reportStatus.textContent = "Ange ett giltigt pris, till exempel 29,95.";
      dom.reportedPrice.focus();
      return;
    }

    const multibuy = dom.promotionMultibuy.checked;
    const promotion = dom.reportPromotionFields.hidden ? null : {
      // These are the canonical PromotionEligibility/PromotionMechanism
      // wire values, not the Swedish labels shown to the user.
      eligibility: dom.promotionMember.checked ? "member" : "public",
      mechanism: multibuy ? "multibuy" : "sale_price",
      regular_price: decimalValue(dom.promotionRegularPrice.value),
      active_price: shelfPrice,
      required_quantity: multibuy ? Number(dom.promotionQuantity.value || 0) || null : null,
      total_price: multibuy ? decimalValue(dom.promotionTotal.value) : null,
    };
    if (multibuy && ((promotion.required_quantity || 0) < 2 || promotion.total_price === null)) {
      dom.reportStatus.textContent = "Ange minst 2 varor och totalpris för flerköpet.";
      return;
    }

    const idempotencyKey = reportIdempotencyKey || newEvidenceIdempotencyKey();
    const payload = {
      ...reportContext,
      physical_store_id: dom.reportPhysicalStore.value || reportContext.physical_store_id || null,
      chain: selectedStore?.dataset.chain || reportContext.chain || null,
      store_display_name: selectedStore?.textContent || reportContext.store_display_name || null,
      anonymous_session_id: anonymousSessionId,
      evidence_type: type,
      evidence_source: reportContext.evidence_source || "MANUAL",
      shelf_price: shelfPrice,
      price_unit: dom.reportPriceFields.hidden ? null : dom.reportedPriceUnit.value,
      promotion,
      idempotency_key: idempotencyKey,
    };
    const isSavedPlanProduct = Boolean(reportContext.plan_id && reportContext.source_product_id);
    const reportUrl = isSavedPlanProduct
      ? `/api/plans/${encodeURIComponent(reportContext.plan_id)}/products/${encodeURIComponent(reportContext.source_product_id)}/report`
      : "/api/community-evidence";
    const requestPayload = isSavedPlanProduct ? {
      anonymous_session_id: anonymousSessionId,
      evidence_type: type,
      evidence_source: reportContext.evidence_source || "MANUAL",
      physical_store_id: payload.physical_store_id,
      shelf_price: shelfPrice,
      price_unit: dom.reportPriceFields.hidden ? null : dom.reportedPriceUnit.value,
      promotion,
    } : payload;
    dom.reportSubmit.disabled = true;
    dom.reportStatus.textContent = "Sparar rapporten…";
    try {
      const response = await fetch(reportUrl, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "Idempotency-Key": idempotencyKey,
        },
        body: JSON.stringify(requestPayload),
      });
      let data = null;
      try { data = await response.json(); } catch (_error) { data = null; }
      if (!response.ok) {
        throw new Error(errorFromResponse(data, `Rapporten kunde inte sparas (HTTP ${response.status}).`));
      }
      dom.reportStatus.textContent = "Tack! Rapporten är sparad som separat evidens.";
      sendAnalyticsEvent("product_report_created");
      window.setTimeout(closeReportDialog, 900);
    } catch (error) {
      dom.reportStatus.textContent = error instanceof Error ? error.message : "Rapporten kunde inte sparas.";
    } finally {
      dom.reportSubmit.disabled = false;
    }
  }

  function stopScanner() {
    if (activeScanner) {
      try { activeScanner.stop(); } catch (_error) { /* Camera cleanup is best effort. */ }
      activeScanner = null;
    }
    const stream = dom.scannerVideo.srcObject;
    if (stream && typeof stream.getTracks === "function") {
      stream.getTracks().forEach((track) => track.stop());
    }
    dom.scannerVideo.srcObject = null;
    dom.scannerCamera.hidden = true;
    dom.scannerStart.disabled = false;
    dom.scannerCancel.hidden = true;
  }

  function closeScannerDialog() {
    stopScanner();
    if (dom.scannerDialog.open) dom.scannerDialog.close();
  }

  async function lookupScannedProduct(rawGtin, format = null, provider = "manual") {
    let normalized;
    try {
      if (!window.GroceryBarcodeScanner) throw new Error("Streckkodsbiblioteket kunde inte laddas.");
      normalized = window.GroceryBarcodeScanner.normalizeGtin(rawGtin, format);
    } catch (error) {
      dom.scannerStatus.textContent = error instanceof Error
        ? error.message
        : "GTIN har fel längd eller kontrollsiffra.";
      return;
    }
    const gtin = typeof normalized === "string" ? normalized : normalized.normalized_gtin;
    dom.manualGtin.value = gtin;
    dom.scannerStatus.textContent = "Söker efter varan…";
    stopScanner();
    try {
      const response = await fetch(`/api/products/${encodeURIComponent(gtin)}`, {
        headers: { Accept: "application/json" },
      });
      let product = null;
      try { product = await response.json(); } catch (_error) { product = null; }
      empty(dom.scannerResult);
      dom.scannerResult.hidden = false;
      const compare = createElement("button", "secondary-button", "Jämför priser och kampanjer");
      compare.type = "button";
      compare.addEventListener("click", () => {
        closeScannerDialog();
        window.dispatchEvent(new CustomEvent("smako:compare-gtin", { detail: { gtin } }));
      });
      dom.scannerResult.append(compare);
      if (response.status === 404 || !product || product.found === false) {
        dom.scannerStatus.textContent = "Den här varan finns inte i vår databas ännu.";
        sendAnalyticsEvent("barcode_scan_unknown");
        dom.scannerResult.append(createElement("strong", null, `GTIN ${gtin}`));
        const report = createElement("button", "primary-button", "Rapportera saknad vara");
        report.type = "button";
        report.addEventListener("click", () => {
          closeScannerDialog();
          openReportDialog({
            evidence_source: provider === "manual" ? "MANUAL" : "BARCODE_SCAN",
            gtin,
            product_name: `Okänd vara (${gtin})`,
          }, "PRODUCT_MISSING_FROM_APP");
        });
        dom.scannerResult.append(report);
        return;
      }
      if (!response.ok) throw new Error(errorFromResponse(product, `Varan kunde inte slås upp (HTTP ${response.status}).`));
      const identities = list(first(product, ["identities"], []));
      const directIdentity = first(product, ["product", "result"], null);
      if ((!directIdentity && identities.length > 1) || product.ambiguous_identity) {
        dom.scannerStatus.textContent = "Flera produkter delar denna GTIN. Välj inte automatiskt – rapportera en identitetskorrigering vid behov.";
        identities.forEach((identity) => {
          const card = createElement("div", "scanned-price-row");
          card.append(
            createElement("strong", null, first(identity, ["product_name", "name"], "Produktnamn saknas")),
            createElement("span", null, [first(identity, ["brand"]), first(identity, ["package_description"])].filter(Boolean).join(" · ")),
          );
          dom.scannerResult.append(card);
        });
        const correction = createElement("button", "secondary-button", "Rapportera fel produktkoppling");
        correction.type = "button";
        correction.addEventListener("click", () => {
          closeScannerDialog();
          openReportDialog({
            evidence_source: provider === "manual" ? "MANUAL" : "BARCODE_SCAN",
            gtin,
            product_name: `Tvetydig GTIN ${gtin}`,
          }, "PRODUCT_IDENTITY_CORRECTION");
        });
        dom.scannerResult.append(correction);
        return;
      }
      const resolved = directIdentity || identities[0] || product;
      const name = first(resolved, ["product_name", "name"], "Produktnamn saknas");
      const brand = first(resolved, ["brand"]);
      const packageDescription = first(resolved, ["package_description", "package_size"]);
      dom.scannerStatus.textContent = "Streckkoden lästes och varan hittades.";
      sendAnalyticsEvent("barcode_scan_success");
      dom.scannerResult.append(createElement("strong", null, name));
      dom.scannerResult.append(createElement("p", null, [brand, packageDescription, `GTIN ${gtin}`].filter(Boolean).join(" · ")));
      const prices = list(first(product, ["prices", "offers"], first(resolved, ["prices", "offers"], [])));
      if (prices.length) {
        const priceList = createElement("div", "scanned-price-list");
        prices.slice(0, 8).forEach((price) => {
          const row = createElement("div", "scanned-price-row");
          const label = createElement("span", null, first(price, ["store_display_name", "store_name", "name"], "Priskontext"));
          const values = createElement("div", "scanned-price-values");
          const regular = formatMoney(first(price, ["regular_price"]));
          const publicPrice = formatMoney(first(price, ["current_public_price", "effective_price", "price", "current_price"]));
          const memberPrice = formatMoney(first(price, ["member_price"]));
          const program = normalizeMembershipPrograms([first(price, ["membership_program"])])[0] || null;
          if (regular) values.append(createElement("span", null, `Ordinarie: ${regular}`));
          if (publicPrice && publicPrice !== regular) values.append(createElement("span", null, `Publik kampanj: ${publicPrice}`));
          if (memberPrice) {
            const qualifies = program && selectedMemberships().includes(program);
            const memberValue = createElement(
              "span",
              qualifies ? "qualified-member-price" : null,
              `Medlemspris: ${memberPrice}${program ? ` · ${membershipLabel(program)}` : ""}${qualifies ? " · Gäller för dig" : ""}`,
            );
            values.append(memberValue);
          }
          if (!values.children.length) values.append(createElement("strong", null, "Pris saknas"));
          row.append(label, values);
          priceList.append(row);
        });
        dom.scannerResult.append(priceList);
      }
      const actions = createElement("div", "dialog-actions");
      const found = createElement("button", "primary-button", "Rapportera hittad i butik");
      found.type = "button";
      found.addEventListener("click", () => {
        closeScannerDialog();
        openReportDialog({
          evidence_source: provider === "manual" ? "MANUAL" : "BARCODE_SCAN",
          gtin,
          source_product_id: first(resolved, ["source_product_id", "product_id"]),
          product_name: name,
          brand,
          package_description: packageDescription,
        }, "PRODUCT_FOUND");
      });
      const correction = createElement("button", "secondary-button", "Rapportera fel");
      correction.type = "button";
      correction.addEventListener("click", () => {
        closeScannerDialog();
        openReportDialog({
          evidence_source: provider === "manual" ? "MANUAL" : "BARCODE_SCAN",
          gtin,
          source_product_id: first(resolved, ["source_product_id", "product_id"]),
          product_name: name,
          brand,
          package_description: packageDescription,
        }, "PRODUCT_IDENTITY_CORRECTION");
      });
      actions.append(found, correction);
      dom.scannerResult.append(actions);
    } catch (error) {
      dom.scannerStatus.textContent = error instanceof Error ? error.message : "Varan kunde inte slås upp.";
    }
  }

  async function startScanner() {
    if (activeScanner) return;
    empty(dom.scannerResult);
    dom.scannerResult.hidden = true;
    if (!window.GroceryBarcodeScanner || !navigator.mediaDevices?.getUserMedia) {
      dom.scannerStatus.textContent = "Kameraskanning stöds inte här. Skriv GTIN manuellt.";
      dom.manualGtin.focus();
      return;
    }
    dom.scannerCamera.hidden = false;
    dom.scannerStart.disabled = true;
    dom.scannerCancel.hidden = false;
    dom.scannerStatus.textContent = "Startar bakre kameran…";
    try {
      const scanner = window.GroceryBarcodeScanner.createBarcodeScanner({
        mode: "product",
        videoElement: dom.scannerVideo,
        onResult: (result) => void lookupScannedProduct(
          result.normalized_gtin || result.raw_value,
          result.format,
          result.provider || scanner.provider || "zxing",
        ),
        onError: (error, detail = {}) => {
          if (detail.recoverable) {
            dom.scannerStatus.textContent = "Koden kunde inte valideras. Håll hela streckkoden inom ramen.";
            return;
          }
          stopScanner();
          dom.scannerStatus.textContent = error?.name === "NotAllowedError"
            ? "Kameraåtkomst nekades. Tillåt kameran i webbläsaren eller skriv GTIN manuellt."
            : "Kameran kunde inte startas. Skriv GTIN manuellt.";
        },
      });
      activeScanner = scanner;
      await scanner.start();
      if (activeScanner === scanner) dom.scannerStatus.textContent = "Håll streckkoden inom den breda ramen.";
    } catch (error) {
      stopScanner();
      dom.scannerStatus.textContent = error?.name === "NotAllowedError"
        ? "Kameraåtkomst nekades. Tillåt kameran eller skriv GTIN manuellt."
        : "Streckkodsläsaren kunde inte starta. Skriv GTIN manuellt.";
    }
  }

  function openScannerDialog() {
    stopScanner();
    empty(dom.scannerResult);
    dom.scannerResult.hidden = true;
    dom.scannerStatus.textContent = "Kameran startar först när du trycker på knappen.";
    dom.scannerDialog.showModal();
    window.requestAnimationFrame(() => dom.scannerStart.focus());
  }

  async function copyCurrentPlanLink() {
    const planId = first(currentResponse, ["plan_id", "id"]);
    if (!planId) return;
    const url = planUrl(planId, { preserveNonPlanQuery: false });
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(url.toString());
      } else {
        const input = document.createElement("textarea");
        input.value = url.toString();
        input.setAttribute("readonly", "");
        input.className = "visually-hidden";
        document.body.append(input);
        input.select();
        document.execCommand("copy");
        input.remove();
      }
      dom.planPersistenceStatus.textContent = "Planlänken är kopierad. Planens ursprungliga priser bevaras.";
    } catch (_error) {
      dom.planPersistenceStatus.textContent = "Länken kunde inte kopieras automatiskt. Kopiera adressen i webbläsaren.";
    }
  }

  function openFeedbackDialog() {
    dom.feedbackForm.reset();
    dom.feedbackStatus.textContent = "";
    dom.feedbackDialog.showModal();
    window.requestAnimationFrame(() => dom.feedbackCategory.focus());
  }

  function closeFeedbackDialog() {
    if (dom.feedbackDialog.open) dom.feedbackDialog.close();
  }

  async function submitFeedback(event) {
    event.preventDefault();
    const message = dom.feedbackMessage.value.trim();
    if (!message) {
      dom.feedbackStatus.textContent = "Skriv ett kort meddelande.";
      dom.feedbackMessage.focus();
      return;
    }
    dom.feedbackSubmit.disabled = true;
    dom.feedbackStatus.textContent = "Skickar feedback…";
    try {
      const response = await fetch("/api/feedback", {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        body: JSON.stringify({
          category: dom.feedbackCategory.value,
          message,
          anonymous_session_id: anonymousSessionId,
          page_context: window.location.pathname,
          plan_id: currentPlanId(),
          email: dom.feedbackEmail.value.trim() || null,
        }),
      });
      const payload = await responseJson(response);
      if (!response.ok) throw new Error(errorFromResponse(payload, "Feedbacken kunde inte sparas."));
      dom.feedbackStatus.textContent = "Tack! Din feedback är sparad.";
      window.setTimeout(closeFeedbackDialog, 900);
    } catch (error) {
      dom.feedbackStatus.textContent = error instanceof Error ? error.message : "Feedbacken kunde inte sparas.";
    } finally {
      dom.feedbackSubmit.disabled = false;
    }
  }

  function closeOnboarding({ remember = true } = {}) {
    if (remember) {
      try { window.localStorage.setItem(onboardingSeenKey, "true"); } catch (_error) { /* Optional. */ }
    }
    if (dom.onboardingDialog.open) dom.onboardingDialog.close();
    document.querySelector(".planner-card")?.scrollIntoView({
      behavior: prefersReducedMotion ? "auto" : "smooth",
      block: "start",
    });
    window.setTimeout(() => dom.postalCode.focus(), prefersReducedMotion ? 0 : 300);
  }

  function showFirstVisitOnboarding() {
    let seen = false;
    try { seen = window.localStorage.getItem(onboardingSeenKey) === "true"; } catch (_error) { seen = false; }
    if (!seen && !planIdFromLocation()) {
      dom.onboardingDialog.showModal();
    }
  }

  async function loadPublicRuntimeStatus() {
    dom.serviceRetryButton.disabled = true;
    try {
      const { response, payload } = await boundedRequest(new AbortController(), 15000, async (signal) => {
        const response = await fetch("/ready", { headers: { Accept: "application/json" }, signal });
        return { response, payload: await responseJson(response) };
      });
      if (!payload) throw new Error("readiness unavailable");
      frontendBuildId = String(first(payload, ["build_id", "app_version", "version"], "beta"));
      recipeControls.enabled(payload.features?.complete_recipes_enabled === true);
      dom.appVersion.textContent = `Beta · ${frontendBuildId} · UI ${FRONTEND_VERSION}`;
      // /ready owns the policy: AGING/WARNING remains usable, while missing,
      // STALE or BROKEN required data returns 503. Mock/local modes may be
      // ready without an active production universe.
      const ready = response.ok && first(payload, ["status"], "not_ready") === "ready";
      setPlannerReadiness(ready);
    } catch (_error) {
      dom.appVersion.textContent = "Publik beta";
      setPlannerReadiness(
        false,
        "Planeringstjänsten kan inte nås just nu. Kontrollera anslutningen och försök igen om en stund.",
      );
    } finally {
      dom.serviceRetryButton.disabled = false;
    }
  }

  async function submitPlan(event) {
    event.preventDefault();
    if (activePlanRequest) return;
    if (window.SmakoRecipes.pendingJob("public")) { await resumePublicJob(); return; }
    dom.errorState.hidden = true;
    Object.values(planErrorFields()).forEach(({ node }) => node.removeAttribute("aria-invalid"));

    if (!validatePostalCode()) {
      dom.postalCode.focus();
      return;
    }
    if (!dom.form.checkValidity()) {
      dom.form.reportValidity();
      return;
    }
    if (!recipeControls.validate()) { dom.form.reportValidity(); return; }

    const memberships = selectedMemberships();
    setSelectedMemberships(memberships, { persist: true });
    persistPlannerPreferences();
    const excludedIngredients = dom.excludedIngredients.value
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);
    const payload = {
      postal_code: dom.postalCode.value.trim(),
      recipes: Number(dom.recipesInput.value),
      servings: Number(dom.servingsInput.value),
      max_stores: Number(dom.maxStoresInput.value),
      purchase_planning_mode: dom.purchasePlanningMode.value,
      diet_preference: dom.dietPreference.value,
      availability_mode: selectedAvailabilityMode(),
      avoid_ingredients: excludedIngredients,
      diversity_mode: selectedDiversityMode(),
      varied_budget_percent: Number(dom.variedBudget.value),
      use_member_prices: memberships.length > 0,
      memberships,
      optimization_iterations: 1,
      strategy: "optimized",
      candidate_recipe_count: 80,
      beam_width: 30,
      debug: debugMode,
      ...recipeControls.values(),
    };

    const requestStartedAt = performance.now();
    sendAnalyticsEvent("plan_requested", {
      diet: payload.diet_preference,
      mode: payload.diversity_mode,
      max_stores: payload.max_stores,
      recipes: payload.recipes,
      servings: payload.servings,
    });

    planViewEpoch += 1;
    savedPlanController?.abort();
    const request = { controller: new AbortController(), deadline: Date.now() + PLAN_WAIT_MS, id: crypto.randomUUID() };
    activePlanRequest = request;
    setLoading(true);

    let planFailureCode = null;
    let renderingResult = false;
    try {
      scrollToNode(dom.statusRegion, "center");
      const { response, data } = await boundedRequest(request.controller, PLAN_WAIT_MS, async (signal) => {
        const response=await window.SmakoRecipes.jobRequest({scope:"public",url:"/api/plans",payload,requestId:request.id,signal,onProgress:message=>{dom.loadingMessage.textContent=message;}});
        return planningResponse(response);
      });
      if (activePlanRequest !== request) return;

      request.id = response.headers.get("X-Request-ID") || request.id;

      if (!response.ok) {
        const responseErrorCode = String(
          response.headers.get("X-Error-Code") || first(data, ["error_code", "code"], ""),
        ).trim().toLowerCase();
        planFailureCode = responseErrorCode || null;
        if (response.status === 422 && Array.isArray(data?.detail)) {
          data.detail.forEach((entry) => {
            const field = planErrorFields()[entry?.loc?.[1]];
            if (field) field.node.setAttribute("aria-invalid", "true");
          });
        }
        const message = errorFromResponse(
          data,
          "Planen kunde inte skapas. Försök igen om en stund.",
          response.status,
          responseErrorCode,
          response.headers.get("Retry-After"),
        );
        if (response.status === 503 && responseErrorCode.startsWith("price_universe_")) {
          // A failed plan does not establish global unavailability. Only /ready
          // may disable planning, with its existing status-retry control.
          await loadPublicRuntimeStatus();
        }
        const error=new Error(message);error.planningDiagnostics=data?.planning_diagnostics;throw error;
      }
      if (!data || typeof data !== "object") {
        throw new Error("Servern returnerade inget läsbart planeringsresultat.");
      }

      renderingResult = true;
      applySavedPlan(data);
      const plan = planFromEnvelope(data) || data;
      sendAnalyticsEvent("plan_succeeded", {
        latency_ms: Math.round(performance.now() - requestStartedAt),
        total: first(plan, ["optimized_basket.total", "total"]),
        price_per_portion: first(plan, ["price_per_portion"]),
        actual_stores: list(first(plan, ["optimized_basket.stores"], [])).length,
        outcome: "success",
      });
    } catch (error) {
      if (activePlanRequest !== request || error.lifecycle) return;
      const timedOut = error?.name === "TimeoutError";
      const aborted = error?.name === "AbortError";
      const networkError = error instanceof TypeError && !renderingResult;
      const message = timedOut
        ? "Det tog för lång tid att få svar. Servern kan fortfarande arbeta med menyn. Du kan försöka igen om en stund."
        : aborted ? "Begäran avbröts på den här enheten. Servern kan fortfarande arbeta. Du kan försöka igen."
        : networkError ? "Det gick inte att nå planeringstjänsten. Kontrollera anslutningen och försök igen."
        : renderingResult ? "Menyn kunde inte visas. Försök igen."
        : error instanceof Error ? error.message : "Menyn kunde inte visas. Försök igen.";
      sendAnalyticsEvent("plan_failed", {
        latency_ms: Math.round(performance.now() - requestStartedAt), outcome: "failed",
        error_code: timedOut ? "client_timeout" : aborted ? "client_aborted" : networkError ? "network_error" : planFailureCode || "planner_error",
      });
      showError(`${message} Fel-ID: ${request.id}`,error.planningDiagnostics);
      dom.form.querySelector('[aria-invalid="true"]')?.focus();
    } finally {
      if (activePlanRequest === request) {
        activePlanRequest = null;
        setLoading(false);
      }
    }
  }

  dom.form.addEventListener("submit", submitPlan);
  dom.membershipInputs.forEach((input) => {
    input.addEventListener("change", () => {
      setSelectedMemberships(selectedMemberships(), { persist: true });
      persistPlannerPreferences();
      if (input.checked) sendAnalyticsEvent("membership_enabled", { membership_program: input.value });
    });
  });
  dom.postalCode.addEventListener("input", () => {
    if (dom.postalCode.getAttribute("aria-invalid") === "true") validatePostalCode();
  });
  dom.recipesInput.addEventListener("input", () => { updatePortionChip(); persistPlannerPreferences(); });
  dom.servingsInput.addEventListener("input", () => { updatePortionChip(); persistPlannerPreferences(); });
  dom.postalCode.addEventListener("change", persistPlannerPreferences);
  dom.maxStoresInput.addEventListener("change", () => {
    persistPlannerPreferences();
    sendAnalyticsEvent("max_stores_selected", { max_stores: Number(dom.maxStoresInput.value) });
  });
  dom.purchasePlanningMode.addEventListener("change", persistPlannerPreferences);
  dom.excludedIngredients.addEventListener("change", persistPlannerPreferences);
  dom.availabilityInputs.forEach(input => input.addEventListener("change", persistPlannerPreferences));
  dom.dietPreference.addEventListener("change", () => {
    persistPlannerPreferences();
    sendAnalyticsEvent("diet_selected", { diet: dom.dietPreference.value });
  });
  dom.diversityInputs.forEach((input) => {
    input.addEventListener("change", () => {
      if (!input.checked) return;
      persistPlannerPreferences();
      sendAnalyticsEvent("mode_selected", { mode: input.value });
    });
  });
  dom.clearPreferencesButton.addEventListener("click", clearPlannerPreferences);
  dom.serviceRetryButton.addEventListener("click", () => void loadPublicRuntimeStatus());
  dom.planOptionsList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-plan-mode]");
    if (button) selectPlanMode(button.dataset.planMode);
  });
  dom.planOptionsList.addEventListener("keydown", (event) => {
    if (!new Set(["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"]).has(event.key)) return;
    const buttons = Array.from(dom.planOptionsList.querySelectorAll("[data-plan-mode]"));
    const currentIndex = buttons.findIndex((button) => button.dataset.planMode === activePlanMode);
    if (!buttons.length || currentIndex < 0) return;
    event.preventDefault();
    const direction = new Set(["ArrowRight", "ArrowDown"]).has(event.key) ? 1 : -1;
    const next = buttons[(currentIndex + direction + buttons.length) % buttons.length];
    selectPlanMode(next.dataset.planMode);
    next.focus();
  });
  dom.newPlanButton.addEventListener("click", () => {
    window.scrollTo({ top: 0, behavior: prefersReducedMotion ? "auto" : "smooth" });
    window.setTimeout(() => dom.postalCode.focus(), prefersReducedMotion ? 0 : 350);
  });
  dom.copyPlanLink.addEventListener("click", () => void copyCurrentPlanLink());
  dom.recalculatePlanButton.addEventListener("click", () => {
    if (currentResponse?.personal) { void changeCompletePlan("recalculate", {}, dom.recalculatePlanButton); return; }
    if (!savedPlanRequest) return;
    applySavedRequestToForm(savedPlanRequest);
    dom.form.requestSubmit();
  });

  dom.reportType.addEventListener("change", syncReportFields);
  dom.reportPhysicalStore.addEventListener("change", syncReportFields);
  dom.reportForm.addEventListener("submit", submitCommunityReport);
  document.querySelectorAll("[data-close-dialog]").forEach((button) => {
    button.addEventListener("click", closeReportDialog);
  });
  dom.reportDialog.addEventListener("click", (event) => {
    if (event.target === dom.reportDialog) closeReportDialog();
  });
  dom.reportDialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    closeReportDialog();
  });
  dom.feedbackEntryButton.addEventListener("click", openFeedbackDialog);
  dom.footerFeedbackButton.addEventListener("click", openFeedbackDialog);
  dom.feedbackForm.addEventListener("submit", submitFeedback);
  document.querySelectorAll("[data-close-feedback]").forEach((button) => {
    button.addEventListener("click", closeFeedbackDialog);
  });
  dom.feedbackDialog.addEventListener("click", (event) => {
    if (event.target === dom.feedbackDialog) closeFeedbackDialog();
  });
  dom.feedbackDialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    closeFeedbackDialog();
  });
  dom.onboardingCta.addEventListener("click", () => closeOnboarding());
  dom.onboardingDialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    closeOnboarding();
  });
  dom.scanEntryButton.addEventListener("click", openScannerDialog);
  dom.scanResultButton.addEventListener("click", openScannerDialog);
  dom.scannerStart.addEventListener("click", startScanner);
  dom.scannerCancel.addEventListener("click", () => {
    stopScanner();
    dom.scannerStatus.textContent = "Skanningen avbröts. Du kan skriva GTIN manuellt.";
  });
  dom.manualGtinSubmit.addEventListener("click", () => void lookupScannedProduct(dom.manualGtin.value));
  dom.manualGtin.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      void lookupScannedProduct(dom.manualGtin.value);
    }
  });
  document.querySelectorAll("[data-close-scanner]").forEach((button) => {
    button.addEventListener("click", closeScannerDialog);
  });
  dom.scannerDialog.addEventListener("click", (event) => {
    if (event.target === dom.scannerDialog) closeScannerDialog();
  });
  dom.scannerDialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    closeScannerDialog();
  });
  window.addEventListener("pagehide", stopScanner);
  window.addEventListener("beforeunload", stopScanner);
  document.querySelectorAll("[data-close-alternatives]").forEach((button) => {
    button.addEventListener("click", closeAlternativesDialog);
  });
  dom.alternativesDialog.addEventListener("click", (event) => {
    if (event.target === dom.alternativesDialog) closeAlternativesDialog();
  });
  dom.alternativesDialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    closeAlternativesDialog();
  });

  document.documentElement.classList.toggle("debug-mode", debugMode);
  dom.debugNotice.hidden = !debugMode;
  const urlPlanId = migrateLegacyPlanQuery();
  loadPlannerPreferences();
  updatePortionChip();
  showFirstVisitOnboarding();
  void loadPublicRuntimeStatus();
  sendAnalyticsEvent("planner_opened");

  window.addEventListener("error", (event) => {
    sendFrontendError("unhandled_error", event.message || "Unhandled frontend error");
  });
  window.addEventListener("unhandledrejection", (event) => {
    const message = event.reason instanceof Error ? event.reason.message : String(event.reason || "Unhandled promise rejection");
    sendFrontendError("unhandled_rejection", message);
  });

  let locallySavedPlanId = null;
  if (!urlPlanId) {
    try { locallySavedPlanId = window.localStorage.getItem(lastPlanStorageKey); } catch (_error) { locallySavedPlanId = null; }
  }
  const requestedPlanId = urlPlanId || locallySavedPlanId;
  if (requestedPlanId && !window.SmakoRecipes.pendingJob("public")) {
    const restoreEpoch = planViewEpoch;
    savedPlanController = new AbortController();
    void boundedRequest(savedPlanController, 20000, async (signal) => {
      const response = await fetch(`/api/plans/${encodeURIComponent(requestedPlanId)}`, {
        headers: { Accept: "application/json" }, signal,
      });
      const { data } = await planningResponse(response);
      if (!response.ok) {
        const error = new Error("Den sparade planen kunde inte öppnas.");
        error.httpStatus = response.status;
        throw error;
      }
      return data;
    }).then((payload) => {
      if (restoreEpoch === planViewEpoch) applySavedPlan(payload, { updateUrl: false });
    }).catch((error) => {
      if (restoreEpoch !== planViewEpoch) return;
      const definitivelyGone = error?.httpStatus === 404 || error?.httpStatus === 410;
      if (!urlPlanId && definitivelyGone) {
        try { window.localStorage.removeItem(lastPlanStorageKey); } catch (_storageError) { /* Optional. */ }
        return;
      }
      showError(definitivelyGone
        ? "Den sparade planen finns inte längre. Du kan skapa en ny veckomeny."
        : "Den sparade planen kunde inte hämtas just nu. Plan-ID:t finns kvar på den här enheten. Du kan ladda om sidan eller skapa en ny meny.");
    });
  }

  void resumePublicJob();
  window.addEventListener("online", () => { void loadPublicRuntimeStatus(); if(!activePlanRequest)void resumePublicJob(); });

  const resumeReader=()=>{reconcilePlanningState();if(!activePlanRequest)void resumePublicJob();};
  window.addEventListener("pageshow",()=>setTimeout(resumeReader,0));
  document.addEventListener("visibilitychange",()=>{if(!document.hidden)resumeReader();});
  reconcilePlanningState();
  document.documentElement.dataset.frontendInitialized = "true";
  document.documentElement.dataset.frontendVersion = FRONTEND_VERSION;

  if ("serviceWorker" in navigator && window.isSecureContext) {
    window.addEventListener(
      "load",
      () => {
        void navigator.serviceWorker.register("/service-worker.js", { scope: "/" }).catch(() => undefined);
      },
      { once: true },
    );
  }
})();

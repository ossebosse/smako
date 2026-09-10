"use strict";

const storeSelect = document.querySelector("#store");
const storeDetails = document.querySelector("#store-details");
const blindCapture = document.querySelector("#blind-capture");
const startButton = document.querySelector("#start-session");
const setup = document.querySelector("#session-setup");
const workspace = document.querySelector("#session-workspace");
const completedPanel = document.querySelector("#session-complete");
const activeStoreName = document.querySelector("#active-store-name");
const blindStatus = document.querySelector("#blind-status");
const progress = document.querySelector("#session-progress");
const progressText = document.querySelector("#progress-text");
const identifierPreparation = document.querySelector("#identifier-preparation");
const identifierPreparationTitle = document.querySelector("#identifier-preparation-title");
const identifierPreparationStatus = document.querySelector("#identifier-preparation-status");
const identifierPreparationCounts = document.querySelector("#identifier-preparation-counts");
const prepareIdentifiersButton = document.querySelector("#prepare-identifiers");
const suggestionsList = document.querySelector("#suggestions");
const suggestionSummary = document.querySelector("#suggestion-summary");
const currentTargetName = document.querySelector("#current-target-name");
const currentTargetMeta = document.querySelector("#current-target-meta");
const targetKindBadge = document.querySelector("#target-kind-badge");
const productBarcodeSection = document.querySelector("#product-barcode-section");
const weightIdentitySection = document.querySelector("#weight-identity-section");
const shelfCodePath = document.querySelector(".shelf-code-path");
const sessionItemId = document.querySelector("#session-item-id");
const gtinInput = document.querySelector("#gtin");
const productNameInput = document.querySelector("#product-name");
const shelfPrice = document.querySelector("#shelf-price");
const shelfPriceBlock = document.querySelector("#shelf-price-block");
const shelfPriceLabel = document.querySelector("#shelf-price-label");
const shelfPriceSuffix = document.querySelector("#shelf-price-suffix");
const noMatchInput = document.querySelector("#identity-no-match");
const form = document.querySelector("#physical-price-form");
const multibuyFields = document.querySelector("#multibuy-fields");
const weightFields = document.querySelector("#weight-fields");
const optionalComparisonFields = document.querySelector("#optional-comparison-fields");
const captureValidation = document.querySelector("#capture-validation");
const result = document.querySelector("#result");
const error = document.querySelector("#error");
const pageError = document.querySelector("#page-error");
const digitalPreview = document.querySelector("#digital-preview");
const digitalPreviewStatus = document.querySelector("#digital-preview-status");
const digitalPreviewItems = document.querySelector("#digital-preview-items");
const scanButton = document.querySelector("#scan-button");
const stopScanButton = document.querySelector("#stop-scan-button");
const scannerVideo = document.querySelector("#scanner-video");
const scannerOverlay = document.querySelector("#scanner-overlay");
const scannerProviderStatus = document.querySelector("#scanner-provider-status");
const scannerLiveStatus = document.querySelector("#scanner-live-status");
const scannerModalHeading = document.querySelector("#scanner-modal-heading");
const scanShelfCodeButton = document.querySelector("#scan-shelf-code");
const shelfCodeStatus = document.querySelector("#shelf-code-status");
const completeSummary = document.querySelector("#complete-summary");
const exportJson = document.querySelector("#export-json");
const exportCsv = document.querySelector("#export-csv");
const nextProductButton = document.querySelector("#next-product");
const saveButton = document.querySelector("#save-button");
const gtinHint = document.querySelector("#gtin-hint");
const identityStatus = document.querySelector("#identity-status");
const identifierActions = document.querySelector("#identifier-actions");
const enrichIdentifierButton = document.querySelector("#enrich-identifier");
const confirmManualIdentityButton = document.querySelector("#confirm-manual-identity");
const manualProductSearch = document.querySelector("#manual-product-search");
const manualProductResults = document.querySelector("#manual-product-results");
const weightRegularPrice = document.querySelector("#weight-regular-price");
const weightPriceType = document.querySelector("#weight-price-type");
const promotionSale = document.querySelector("#promotion-sale");
const promotionMember = document.querySelector("#promotion-member");
const promotionMultibuy = document.querySelector("#promotion-multibuy");
const promotionTextFields = document.querySelector("#promotion-text-fields");

let stores = [];
let activeSession = null;
let items = [];
let currentItem = null;
let fieldCsrfToken = null;
let savePending = false;
let activeBarcodeScanner = null;
let scannerStarting = false;
let scannerAttempt = null;
let activeScannerMode = "product";
let manualDiagnosticRecorded = false;
let identityLookupTimer = null;
let currentIdentityStatus = "manual_exact_match";
let currentIdentificationEvidence = "source_product_manual";
let enrichPending = false;
let preparationRunning = false;
const captureRequestIds = new Map();

const IDENTITY = Object.freeze({
  GTIN_MATCH: "gtin_match",
  GTIN_MISMATCH: "gtin_mismatch",
  GTIN_UNKNOWN: "gtin_not_known_by_source",
  WEIGHT: "weight_item_no_gtin_required",
  SHELF_MATCH: "shelf_code_match",
  SHELF_UNKNOWN: "shelf_code_unknown",
  MANUAL: "manual_exact_match",
  NO_MATCH: "no_match",
});

const EVIDENCE = Object.freeze({
  GTIN: "gtin_verified",
  MANUAL: "source_product_manual",
  WEIGHT: "weight_source_product",
  SHELF: "shelf_code_verified",
  UNVERIFIED: "unverified",
});

const REQUIRED_PHYSICAL_CHECK_CONTRACT = "product-identification-v2";

function decimalValue(value) {
  const normalized = String(value || "").trim().replaceAll(" ", "").replace(",", ".");
  return /^\d+(?:\.\d{1,2})?$/.test(normalized) ? normalized : null;
}

function moneyText(value) {
  if (value === null || value === undefined || value === "") return "–";
  return Number(value).toFixed(2).replace(".", ",");
}

function newClientRequestId() {
  if (window.crypto && typeof window.crypto.randomUUID === "function") {
    return window.crypto.randomUUID();
  }
  const bytes = new Uint8Array(16);
  window.crypto.getRandomValues(bytes);
  return Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
}

function isWeightItem(item) {
  if (!item) return false;
  return item.weight_item === true
    || item.identifier_status === "not_required_weight"
    || ["sold_by_weight", "variable_weight_package"].includes(String(item.target_sale_model || ""));
}

function setIdentityResult(status, evidence, message, visual = "") {
  currentIdentityStatus = status;
  currentIdentificationEvidence = evidence;
  showIdentityStatus(message, visual);
}

function renderIdentifierPreparation(preparation) {
  identifierPreparationCounts.replaceChildren();
  if (!preparation) {
    identifierPreparationTitle.textContent = "Produktidentiteter förberedda";
    identifierPreparationStatus.textContent = "Passet kan användas även när källan saknar GTIN.";
    return;
  }
  const targetProducts = preparation.target_products ?? activeSession?.target_count ?? items.length;
  const known = preparation.known_gtin_before ?? 0;
  const enriched = preparation.enriched_gtin ?? 0;
  const weight = preparation.weight_no_gtin_required ?? 0;
  const unavailable = preparation.gtin_unavailable ?? 0;
  const unresolved = preparation.true_unresolved ?? 0;
  identifierPreparationTitle.textContent = `${targetProducts} produktidentiteter förberedda`;
  identifierPreparationStatus.textContent = preparation.errors
    ? "Några detaljuppslag misslyckades. Passet fungerar ändå med manuell exakt bekräftelse."
    : "GTIN-berikningen är avgränsad till varorna i detta fältpass.";
  [
    `GTIN känd ${known}`,
    `GTIN berikad ${enriched}`,
    `Viktvara ${weight}`,
    `GTIN saknas ${unavailable}`,
    `Återstår ${unresolved}`,
  ].forEach((label) => {
    const chip = document.createElement("span");
    chip.textContent = label;
    identifierPreparationCounts.append(chip);
  });
  const finished = unresolved === 0;
  prepareIdentifiersButton.disabled = preparationRunning || finished;
  prepareIdentifiersButton.hidden = activeSession?.chain !== "hemkop";
  if (!preparationRunning) {
    prepareIdentifiersButton.textContent = finished
      ? "GTIN-förberedelse klar"
      : "Berika återstående GTIN";
  }
}

function selectedPriceBasis() {
  return document.querySelector('input[name="price_basis"]:checked').value;
}

function selectedPromotionMechanism() {
  if (promotionMultibuy.checked) return "multibuy";
  if (promotionSale.checked) return "sale";
  return "none";
}

function selectedSemantics() {
  if (selectedPriceBasis() === "weight") return "weight";
  const mechanism = selectedPromotionMechanism();
  if (mechanism === "multibuy") return "multibuy";
  if (mechanism === "sale") return "sale";
  if (promotionMember.checked) return "member";
  return "regular";
}

function showError(element, message) {
  element.textContent = message;
  element.hidden = !message;
}

async function jsonRequest(url, options = {}) {
  const method = String(options.method || "GET").toUpperCase();
  const headers = { ...(options.headers || {}) };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (!["GET", "HEAD", "OPTIONS"].includes(method) && fieldCsrfToken) {
    headers["X-Physical-Check-CSRF"] = fieldCsrfToken;
  }
  const response = await fetch(url, {
    ...options,
    method,
    credentials: "same-origin",
    cache: "no-store",
    headers,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const formatter = window.PhysicalCheckApiErrors?.formatApiErrorResponse;
    const message = typeof formatter === "function"
      ? formatter(body, response.status)
      : typeof body.detail === "string" && body.detail.trim()
        ? body.detail.trim()
        : `Begäran misslyckades (HTTP ${response.status}).`;
    throw new Error(message);
  }
  return body;
}

async function recordScannerDiagnostic(payload) {
  try {
    await jsonRequest("/physical-check/scanner-diagnostics", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  } catch {
    // Scanner telemetry is optional and must never block a field observation.
  }
}

function scannerFailureReason(problem) {
  const name = String(problem && problem.name ? problem.name : "");
  const code = String(problem && problem.code ? problem.code : "");
  if (code === "invalid_checksum") return "invalid_checksum";
  if (code === "no_barcode_detected") return "no_barcode_detected";
  if (name === "NotAllowedError" || name === "SecurityError") return "permission_denied";
  if (name === "NotFoundError" || name === "DevicesNotFoundError") return "no_camera";
  if (name === "NotReadableError" || name === "TrackStartError") return "camera_busy";
  if (!navigator.mediaDevices || typeof navigator.mediaDevices.getUserMedia !== "function") {
    return "unsupported_browser";
  }
  return "initialization_failed";
}

function swedishScannerError(problem) {
  const reason = scannerFailureReason(problem);
  if (reason === "permission_denied") {
    return "Kamerabehörigheten nekades. Tillåt kameran för sidan i Safari eller skriv GTIN manuellt.";
  }
  if (reason === "no_camera") return "Ingen kamera hittades. Skriv GTIN manuellt.";
  if (reason === "camera_busy") {
    return "Kameran används av en annan app. Stäng den andra kameraappen och försök igen.";
  }
  if (reason === "invalid_checksum") {
    return "Streckkoden lästes men kontrollsiffran är ogiltig. Håll kvar nästa kod inom ramen.";
  }
  if (reason === "no_barcode_detected") {
    return "Ingen kod hittades med den inbyggda läsaren. ZXing tar över automatiskt.";
  }
  if (reason === "unsupported_browser") {
    return "Webbläsaren saknar kamerastöd. Öppna HTTPS-länken i Safari eller skriv GTIN manuellt.";
  }
  return "Streckkodsläsaren kunde inte startas. Försök igen eller skriv GTIN manuellt.";
}

async function initializeFieldSession() {
  const response = await fetch("/physical-check/session", {
    credentials: "same-origin",
    cache: "no-store",
    headers: { Accept: "application/json" },
  });
  if (response.status === 404) return;
  if (response.status === 401) {
    window.location.assign("/physical-check/login");
    return;
  }
  if (!response.ok) throw new Error(`Fältinloggningen kunde inte verifieras (HTTP ${response.status}).`);
  const body = await response.json();
  if (body.physical_check_contract !== REQUIRED_PHYSICAL_CHECK_CONTRACT) {
    throw new Error(
      "Fältservern kör en äldre physical-check-version. Stoppa och starta om scripts/start_field_server.ps1 innan du fortsätter.",
    );
  }
  fieldCsrfToken = body.csrf_token;
}

async function loadStores() {
  try {
    const body = await jsonRequest("/physical-check/stores?city=Lund");
    stores = body.items;
    storeSelect.replaceChildren(new Option("Välj butik", ""));
    stores.forEach((store) => {
      storeSelect.add(new Option(`${store.chain.toUpperCase()} · ${store.name}`, store.id));
    });
    const karhogstorg = stores.find((store) => store.name.includes("Karhögstorg"));
    if (karhogstorg) storeSelect.value = karhogstorg.id;
    updateSelectedStore();
  } catch (requestError) {
    showError(pageError, `Butikerna kunde inte laddas: ${requestError.message}`);
  }
}

function updateSelectedStore() {
  const selected = stores.find((store) => store.id === storeSelect.value);
  startButton.disabled = !selected;
  storeDetails.textContent = selected
    ? [selected.address, selected.postal_code, selected.city].filter(Boolean).join(", ")
    : "";
}

function renderDigitalEvidence(item) {
  digitalPreviewItems.replaceChildren();
  const evidence = item.digital_evidence || [];
  if (!evidence.length) {
    digitalPreviewStatus.textContent = "Ingen säker digital match i det frysta underlaget.";
  } else {
    digitalPreviewStatus.textContent = `${evidence.length} fryst(a) digital(a) prisrad(er).`;
    evidence.forEach((candidate) => {
      const row = document.createElement("li");
      const heading = document.createElement("strong");
      heading.textContent = `${candidate.price_label}: ${candidate.digital_price} kr`;
      const details = document.createElement("span");
      details.textContent = `${candidate.source_provider.toUpperCase()} · ${candidate.context_id || candidate.grocery_context_id} · ${candidate.digital_observed_at}`;
      row.append(heading, details);
      digitalPreviewItems.append(row);
    });
  }
  digitalPreview.hidden = false;
}

async function loadOpenPreview() {
  if (!activeSession || activeSession.blind_capture || !gtinInput.value.trim()) return;
  const query = new URLSearchParams({
    store_id: activeSession.physical_store_id,
    gtin: gtinInput.value.trim(),
  });
  const preview = await jsonRequest(`/physical-check/digital-price-preview?${query}`);
  renderDigitalEvidence({
    digital_evidence: preview.items.map((item) => ({
      ...item,
      digital_price: item.current_price,
      digital_observed_at: item.observed_at,
    })),
  });
}

function showIdentityStatus(message, status = "") {
  identityStatus.textContent = message;
  identityStatus.classList.toggle("is-match", status === "match");
  identityStatus.classList.toggle("is-no-match", status === "no_match");
  identityStatus.classList.toggle("is-unknown", status === "unknown");
}

async function verifyCurrentIdentity(inputMethod = "manual_gtin") {
  if (!activeSession || !currentItem || !gtinInput.value.trim()) {
    setIdentityResult(
      IDENTITY.MANUAL,
      EVIDENCE.MANUAL,
      "MANUAL_EXACT_MATCH · exakt produkt vald manuellt i stickprovet.",
      "match",
    );
    return null;
  }
  const requestedItemId = currentItem.id;
  const requestedGtin = gtinInput.value.trim();
  const query = new URLSearchParams({ gtin: requestedGtin, contract: "v2" });
  try {
    const body = await jsonRequest(
      `/physical-check/sessions/${activeSession.id}/items/${requestedItemId}/identity?${query}`,
    );
    if (!currentItem || currentItem.id !== requestedItemId || gtinInput.value.trim() !== requestedGtin) {
      return { ...body, stale_ui_response: true };
    }
    const responseStatus = body.status === "match" ? IDENTITY.GTIN_MATCH : body.status;
    if (responseStatus === IDENTITY.GTIN_MATCH) {
      noMatchInput.checked = false;
      productNameInput.value = body.product_name || currentItem.target_product_name;
      identifierActions.hidden = true;
      const methodLabel = inputMethod === "scan" ? "skannad GTIN" : "manuellt inskriven GTIN";
      setIdentityResult(
        IDENTITY.GTIN_MATCH,
        EVIDENCE.GTIN,
        `GTIN_MATCH · ${methodLabel} · ${body.product_name || currentItem.target_product_name}`,
        "match",
      );
      await loadOpenPreview();
      return body;
    }
    if (body.status === "multiple_matches" || body.lookup_status === "ambiguous") {
      noMatchInput.checked = false;
      productNameInput.value = "";
      identifierActions.hidden = false;
      currentIdentityStatus = IDENTITY.GTIN_UNKNOWN;
      currentIdentificationEvidence = EVIDENCE.UNVERIFIED;
      showIdentityStatus(
        "AMBIGUOUS_GTIN · flera aktiva produkter använder denna kod. Välj rätt produkt uttryckligen.",
        "unknown",
      );
      manualProductResults.replaceChildren();
      (body.products || []).forEach((product) => {
        const button = document.createElement("button");
        button.type = "button";
        button.setAttribute("role", "option");
        button.textContent = [product.product_name, product.brand, product.package]
          .filter(Boolean)
          .join(" · ");
        button.addEventListener("click", async () => {
          productNameInput.value = product.product_name;
          noMatchInput.checked = false;
          manualProductResults.replaceChildren();
          setIdentityResult(
            IDENTITY.MANUAL,
            EVIDENCE.MANUAL,
            `MANUAL_EXACT_MATCH · manuellt bekräftad produkt · ${product.product_name}`,
            "match",
          );
          await loadOpenPreview();
        });
        manualProductResults.append(button);
      });
      return body;
    }
    noMatchInput.checked = false;
    identifierActions.hidden = false;
    if (
      responseStatus === IDENTITY.GTIN_UNKNOWN
      || body.lookup_status === "unknown_to_source"
      || (body.status === "no_match" && !currentItem.target_gtin)
    ) {
      setIdentityResult(
        IDENTITY.GTIN_UNKNOWN,
        EVIDENCE.UNVERIFIED,
        `GTIN_NOT_KNOWN_BY_SOURCE · skanningen lyckades (${body.gtin || gtinInput.value}), men källan har ännu ingen verifierad GTIN för den valda varan.`,
        "unknown",
      );
      return body;
    }
    setIdentityResult(
      IDENTITY.GTIN_MISMATCH,
      EVIDENCE.UNVERIFIED,
      "GTIN_MISMATCH · skanningen lyckades, men koden skiljer sig från den verifierade koden för vald vara.",
      "no_match",
    );
    return body;
  } catch (lookupError) {
    showIdentityStatus(`Identiteten kunde inte verifieras: ${lookupError.message}`, "unknown");
    return null;
  }
}

function renderManualProductResults() {
  manualProductResults.replaceChildren();
  const query = manualProductSearch.value.trim().toLocaleLowerCase("sv");
  if (!query) return;
  items
    .filter((item) => !item.captured)
    .filter((item) => item.target_product_name.toLocaleLowerCase("sv").includes(query))
    .slice(0, 10)
    .forEach((item) => {
      const button = document.createElement("button");
      button.type = "button";
      button.setAttribute("role", "option");
      button.textContent = [item.target_product_name, item.target_package]
        .filter(Boolean)
        .join(" · ");
      button.addEventListener("click", () => {
        setCurrentItem(item);
        manualProductSearch.value = item.target_product_name;
        manualProductResults.replaceChildren();
        setIdentityResult(
          IDENTITY.MANUAL,
          EVIDENCE.MANUAL,
          `MANUAL_EXACT_MATCH · exakt manuellt produktval · ${item.target_product_name}`,
          "match",
        );
      });
      manualProductResults.append(button);
    });
}

function scheduleManualGtinVerification() {
  window.clearTimeout(identityLookupTimer);
  const compactGtin = gtinInput.value.replaceAll(" ", "").replaceAll("-", "");
  if (!compactGtin) {
    identifierActions.hidden = false;
    setIdentityResult(
      IDENTITY.MANUAL,
      EVIDENCE.UNVERIFIED,
      "Vald källprodukt visas, men den fysiska varan är ännu inte bekräftad. Skanna eller bekräfta exakt manuellt.",
      "unknown",
    );
    return;
  }
  currentIdentityStatus = IDENTITY.GTIN_UNKNOWN;
  currentIdentificationEvidence = EVIDENCE.UNVERIFIED;
  if (compactGtin.length < 8) {
    showIdentityStatus("Skriv hela GTIN-numret eller rensa fältet för manuell exakt bekräftelse.", "unknown");
    return;
  }
  if (![8, 12, 13].includes(compactGtin.length)) {
    showIdentityStatus("INVALID_GTIN · GTIN måste innehålla 8, 12 eller 13 siffror.", "no_match");
    return;
  }
  identityLookupTimer = window.setTimeout(async () => {
    try {
      const normalized = window.GroceryBarcodeScanner.normalizeGtin(compactGtin);
      gtinInput.value = normalized.normalized_gtin;
      if (!manualDiagnosticRecorded) {
        manualDiagnosticRecorded = true;
        void recordScannerDiagnostic({
          scanner_provider: "manual",
          outcome: "manual_fallback",
        });
      }
      await verifyCurrentIdentity("manual_gtin");
    } catch {
      showIdentityStatus(
        "INVALID_GTIN · kontrollsiffran är ogiltig. Kontrollera siffrorna och försök igen.",
        "no_match",
      );
    }
  }, 400);
}

function setCurrentItem(item) {
  window.clearTimeout(identityLookupTimer);
  identityLookupTimer = null;
  currentItem = item;
  manualDiagnosticRecorded = false;
  const weightItem = isWeightItem(item);
  sessionItemId.value = item ? item.id : "";
  currentTargetName.textContent = item ? item.target_product_name : "Alla föreslagna varor är klara";
  currentTargetMeta.textContent = item
    ? [
        item.target_brand,
        weightItem ? "Viktvara / kr per kg" : item.target_package,
        !weightItem && item.target_gtin ? `GTIN ${item.target_gtin}` : null,
      ]
        .filter(Boolean)
        .join(" · ")
    : "";
  targetKindBadge.textContent = weightItem ? "VIKTVARA" : "FÖRPACKAD VARA";
  targetKindBadge.classList.toggle("is-weight", weightItem);
  shelfCodePath.hidden = activeSession?.chain !== "hemkop";
  productBarcodeSection.hidden = weightItem;
  weightIdentitySection.hidden = !weightItem;
  identifierActions.hidden = true;
  enrichIdentifierButton.hidden = !item?.identifier_enrichment_available;
  shelfCodeStatus.textContent = "";
  gtinHint.textContent = scanButton.hidden
    ? "Kameraskanning stöds inte i denna webbläsare. Skriv eller klistra in GTIN manuellt."
    : "Tryck Skanna produktkod för kameran, eller skriv GTIN manuellt.";
  gtinInput.value = "";
  productNameInput.value = item ? item.target_product_name : "";
  manualProductSearch.value = "";
  manualProductResults.replaceChildren();
  shelfPrice.value = "";
  document.querySelector("#multibuy-quantity").value = "";
  document.querySelector("#multibuy-total-price").value = "";
  document.querySelector("#optional-comparison-price").value = "";
  document.querySelector("#optional-comparison-unit").value = "";
  document.querySelector("#promotion-text").value = "";
  document.querySelector("#notes").value = "";
  weightRegularPrice.value = "";
  weightPriceType.value = "regular";
  promotionSale.checked = item?.stratum === "sale";
  promotionMember.checked = item?.stratum === "member";
  promotionMultibuy.checked = item?.stratum === "multibuy";
  noMatchInput.checked = false;
  digitalPreview.hidden = true;
  nextProductButton.hidden = true;
  result.textContent = "";
  setCaptureDisabled(!item);
  const basis = weightItem ? "weight" : "package";
  const radio = document.querySelector(`input[name="price_basis"][value="${basis}"]`);
  if (radio) radio.checked = true;
  updateSemanticFields();
  renderSuggestions();
  if (!item) {
    showIdentityStatus("Inga återstående produkter.");
  } else if (weightItem) {
    setIdentityResult(
      IDENTITY.WEIGHT,
      EVIDENCE.WEIGHT,
      "WEIGHT_ITEM_NO_GTIN_REQUIRED · exakt viktvara vald från källunderlaget.",
      "match",
    );
  } else {
    setIdentityResult(
      IDENTITY.MANUAL,
      EVIDENCE.UNVERIFIED,
      item.target_gtin
        ? "Källprodukten har en verifierad GTIN. Skanna förpackningen eller bekräfta vald vara manuellt."
        : "Källan saknar ännu verifierad GTIN. Försök berika eller bekräfta den fysiska varan exakt manuellt.",
      "unknown",
    );
    identifierActions.hidden = false;
  }
  if (item && !weightItem) gtinInput.focus();
  if (item && weightItem) shelfPrice.focus();
}

function setCaptureDisabled(disabled) {
  form.querySelectorAll("input, select, textarea, button").forEach((control) => {
    control.disabled = disabled;
  });
  saveButton.textContent = disabled && savePending ? "Sparar…" : "Spara hyllpris";
}

function renderSuggestions() {
  suggestionsList.replaceChildren();
  const counts = {};
  items.forEach((item) => {
    counts[item.stratum] = (counts[item.stratum] || 0) + 1;
    const row = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.itemId = item.id;
    button.setAttribute("aria-current", String(currentItem && currentItem.id === item.id));
    if (item.captured) button.classList.add("is-captured");
    const copy = document.createElement("span");
    copy.className = "suggestion-copy";
    const title = document.createElement("strong");
    title.textContent = item.target_product_name;
    const meta = document.createElement("small");
    meta.textContent = [
      item.target_brand,
      isWeightItem(item) ? "Viktvara / kr per kg" : item.target_package,
      item.target_category,
    ]
      .filter(Boolean)
      .join(" · ");
    const badge = document.createElement("span");
    badge.className = "stratum-badge";
    badge.textContent = isWeightItem(item) ? "VIKTVARA" : item.stratum.toUpperCase();
    copy.append(title, meta);
    button.append(copy, badge);
    button.addEventListener("click", () => setCurrentItem(item));
    row.append(button);
    suggestionsList.append(row);
  });
  suggestionSummary.replaceChildren();
  Object.entries(counts).forEach(([name, count]) => {
    const badge = document.createElement("span");
    badge.textContent = `${name.toUpperCase()} ${count}`;
    suggestionSummary.append(badge);
  });
}

function applySession(body, { selectNext = true } = {}) {
  activeSession = body.session;
  items = body.items;
  renderIdentifierPreparation(body.identifier_preparation);
  const captured = body.progress.captured;
  activeStoreName.textContent = activeSession.store_name;
  blindStatus.textContent = activeSession.blind_capture ? "BLIND INSAMLING" : "ÖPPEN JÄMFÖRELSE";
  blindStatus.classList.toggle("is-open", !activeSession.blind_capture);
  progress.max = activeSession.target_count;
  progress.value = captured;
  progressText.textContent = `${captured} av ${activeSession.target_count}`;
  if (selectNext) {
    const preferred = items.find((item) => !item.captured) || null;
    setCurrentItem(preferred);
  } else {
    renderSuggestions();
  }
}

async function startSession() {
  stopScanner();
  const selectedStore = stores.find((store) => store.id === storeSelect.value);
  if (!selectedStore) return;
  startButton.disabled = true;
  startButton.textContent = "Förbereder 25 varor…";
  showError(pageError, "");
  try {
    const body = await jsonRequest("/physical-check/sessions", {
      method: "POST",
      body: JSON.stringify({
        physical_store_id: selectedStore.id,
        target_sample_size: 25,
        sampling_strategy: "stratified",
        blind_capture: blindCapture.checked,
      }),
    });
    setup.hidden = true;
    completedPanel.hidden = true;
    workspace.hidden = false;
    applySession(body);
    if (activeSession.chain === "hemkop") void prepareSessionIdentifiers();
  } catch (requestError) {
    showError(pageError, `Fältpasset kunde inte startas: ${requestError.message}`);
    startButton.disabled = false;
    startButton.textContent = "Starta stickprov med 25 varor";
  }
}

function mergePreparedSession(body) {
  activeSession = body.session;
  const previousItemId = currentItem && currentItem.id;
  items = body.items;
  renderIdentifierPreparation(body.identifier_preparation);
  if (previousItemId) {
    const refreshedCurrent = items.find((item) => item.id === previousItemId);
    if (refreshedCurrent) {
      currentItem = refreshedCurrent;
      if (!isWeightItem(currentItem) && currentItem.target_gtin && !gtinInput.value.trim()) {
        currentTargetMeta.textContent = [
          currentItem.target_brand,
          currentItem.target_package,
          `GTIN ${currentItem.target_gtin}`,
        ].filter(Boolean).join(" · ");
      }
      if (
        !isWeightItem(currentItem)
        && currentItem.target_gtin
        && gtinInput.value.trim()
        && currentIdentityStatus === IDENTITY.GTIN_UNKNOWN
      ) {
        void verifyCurrentIdentity("scan");
      }
    }
  }
  renderSuggestions();
}

async function prepareSessionIdentifiers() {
  if (!activeSession || activeSession.chain !== "hemkop" || preparationRunning) return;
  preparationRunning = true;
  prepareIdentifiersButton.disabled = true;
  showError(error, "");
  try {
    for (let attempt = 0; attempt < activeSession.target_count + 2; attempt += 1) {
      prepareIdentifiersButton.textContent = "Berikar nästa vara…";
      identifierPreparationStatus.textContent = "Hämtar högst en godkänd produktdetalj åt gången. Du kan fortsätta använda passet.";
      const outcome = await jsonRequest(
        `/physical-check/sessions/${activeSession.id}/prepare-identifiers`,
        { method: "POST", body: JSON.stringify({ max_requests: 1 }) },
      );
      const refreshed = outcome.items && outcome.session
        ? outcome
        : await jsonRequest(`/physical-check/sessions/${activeSession.id}`);
      mergePreparedSession(refreshed);
      const pending = items.some((item) => item.identifier_status === "unknown_gtin");
      if (!pending || ["complete", "no_eligible_items", "budget_exhausted"].includes(outcome.status)) {
        break;
      }
    }
  } catch (requestError) {
    identifierPreparationStatus.textContent = "Automatisk GTIN-förberedelse pausades. Passet fungerar ändå; försök igen eller berika en enskild vara.";
    showError(error, `GTIN-förberedelsen pausades: ${requestError.message}`);
  } finally {
    preparationRunning = false;
    const pending = items.some((item) => item.identifier_status === "unknown_gtin");
    prepareIdentifiersButton.disabled = !pending;
    prepareIdentifiersButton.textContent = pending
      ? "Berika återstående GTIN"
      : "GTIN-förberedelse klar";
  }
}

async function enrichCurrentIdentifier() {
  if (
    !activeSession
    || !currentItem
    || enrichPending
    || preparationRunning
    || isWeightItem(currentItem)
  ) return;
  const requestedItemId = currentItem.id;
  enrichPending = true;
  enrichIdentifierButton.disabled = true;
  enrichIdentifierButton.textContent = "Hämtar produktdetaljer…";
  showError(error, "");
  try {
    const body = await jsonRequest(
      `/physical-check/sessions/${activeSession.id}/items/${requestedItemId}/enrich-identifier`,
      { method: "POST", body: JSON.stringify({}) },
    );
    if (!currentItem || currentItem.id !== requestedItemId) return;
    if (["enriched", "already_cached"].includes(body.status) && body.gtin) {
      currentItem.target_gtin = body.gtin;
      currentItem.identifier_status = "known_gtin";
      currentTargetMeta.textContent = [
        currentItem.target_brand,
        currentItem.target_package,
        `GTIN ${body.gtin}`,
      ].filter(Boolean).join(" · ");
      if (gtinInput.value.trim()) {
        await verifyCurrentIdentity("scan");
      } else {
        setIdentityResult(
          IDENTITY.MANUAL,
          EVIDENCE.UNVERIFIED,
          `GTIN berikad från produktdetaljen: ${body.gtin}. Skanna förpackningen eller bekräfta vald vara manuellt.`,
          "unknown",
        );
      }
      identifierActions.hidden = Boolean(gtinInput.value.trim());
    } else if (["unavailable", "budget_exhausted"].includes(body.status)) {
      setIdentityResult(
        IDENTITY.GTIN_UNKNOWN,
        gtinInput.value.trim() ? EVIDENCE.UNVERIFIED : EVIDENCE.MANUAL,
        body.status === "budget_exhausted"
          ? "GTIN_NOT_KNOWN_BY_SOURCE · detaljbudget för passet är slut. Bekräfta vald vara manuellt eller markera fel vara."
          : "GTIN_NOT_KNOWN_BY_SOURCE · produktdetaljen innehöll ingen verifierbar GTIN. Bekräfta vald vara manuellt eller markera fel vara.",
        "unknown",
      );
      identifierActions.hidden = false;
    } else {
      showIdentityStatus("Produktdetaljen kunde inte berikas just nu. Du kan bekräfta exakt vald vara manuellt.", "unknown");
    }
  } catch (requestError) {
    showError(error, `Produktdetaljen kunde inte hämtas: ${requestError.message}`);
  } finally {
    enrichPending = false;
    enrichIdentifierButton.disabled = false;
    enrichIdentifierButton.textContent = "Hämta produktdetaljer";
  }
}

function confirmCurrentItemManually() {
  if (!currentItem || isWeightItem(currentItem)) return;
  noMatchInput.checked = false;
  productNameInput.value = currentItem.target_product_name;
  if (currentIdentityStatus === IDENTITY.GTIN_UNKNOWN && gtinInput.value.trim()) {
    setIdentityResult(
      IDENTITY.GTIN_UNKNOWN,
      EVIDENCE.MANUAL,
      `GTIN_NOT_KNOWN_BY_SOURCE · vald vara bekräftad manuellt. Scannad kod: ${gtinInput.value.trim()}.`,
      "match",
    );
  } else {
    if (currentIdentityStatus === IDENTITY.GTIN_MISMATCH) gtinInput.value = "";
    setIdentityResult(
      IDENTITY.MANUAL,
      EVIDENCE.MANUAL,
      `MANUAL_EXACT_MATCH · vald vara bekräftad manuellt · ${currentItem.target_product_name}`,
      "match",
    );
  }
  identifierActions.hidden = true;
}

function updateSemanticFields() {
  let basis = selectedPriceBasis();
  if (currentItem && isWeightItem(currentItem) && basis !== "weight") {
    document.querySelector('input[name="price_basis"][value="weight"]').checked = true;
    basis = "weight";
  } else if (currentItem && !isWeightItem(currentItem) && basis === "weight") {
    document.querySelector('input[name="price_basis"][value="package"]').checked = true;
    basis = "package";
  }
  if (basis === "weight" && promotionMultibuy.checked) {
    promotionMultibuy.checked = false;
  }
  const effectiveMechanism = selectedPromotionMechanism();
  multibuyFields.hidden = effectiveMechanism !== "multibuy";
  weightFields.hidden = basis !== "weight";
  optionalComparisonFields.hidden = basis === "weight";
  shelfPriceBlock.hidden = effectiveMechanism === "multibuy";
  shelfPrice.required = effectiveMechanism !== "multibuy";
  promotionMultibuy.disabled = basis === "weight";
  promotionTextFields.hidden = !(
    promotionSale.checked || promotionMember.checked || promotionMultibuy.checked
  );
  shelfPriceLabel.textContent = basis === "weight" ? "Viktpris" : "Hyllpris, kr";
  shelfPriceSuffix.textContent = basis === "weight" ? "kr/kg" : "kr";
  weightPriceType.value = promotionSale.checked
    ? "sale"
    : promotionMember.checked
      ? "member"
      : "regular";
  const conditions = [
    promotionSale.checked ? "kampanj" : null,
    promotionMember.checked ? "medlemskap" : null,
    promotionMultibuy.checked ? "flerköp" : null,
  ].filter(Boolean);
  document.querySelector("#price-semantics-help").textContent = effectiveMechanism === "multibuy"
    ? `Ange erbjudandets antal och totalpris${promotionMember.checked ? " för medlem" : ""}. Du behöver inte räkna ut styckpris.`
    : basis === "weight"
      ? `Ange hyllans viktpris i kr/kg${conditions.length ? ` (${conditions.join(" + ")})` : ""}.`
      : conditions.length
        ? `Ange paket-/styckpriset som gäller för ${conditions.join(" + ")}.`
        : "Ange det ordinarie paket-/styckpriset på hyllkanten.";
}

async function saveCapture(event) {
  event.preventDefault();
  if (savePending) return;
  showError(captureValidation, "");
  showError(error, "");
  if (!activeSession || !currentItem) return;
  const requestedSessionId = activeSession.id;
  const requestedItemId = currentItem.id;
  const requestedItemName = currentItem.target_product_name;
  const priceBasis = selectedPriceBasis();
  const promotionMechanism = selectedPromotionMechanism();
  const semantics = selectedSemantics();
  const multibuyQuantity = semantics === "multibuy"
    ? Number(document.querySelector("#multibuy-quantity").value) || null
    : null;
  const multibuyTotal = semantics === "multibuy"
    ? decimalValue(document.querySelector("#multibuy-total-price").value)
    : null;
  const capturedPrice = semantics === "multibuy"
    ? multibuyTotal
    : decimalValue(shelfPrice.value);
  const comparisonPrice = semantics === "weight"
    ? null
    : decimalValue(document.querySelector("#optional-comparison-price").value);
  const comparisonUnit = semantics === "weight"
    ? document.querySelector("#comparison-unit").value
    : document.querySelector("#optional-comparison-unit").value.trim() || null;
  const regularShelfPrice = semantics === "weight"
    ? decimalValue(weightRegularPrice.value)
    : null;
  if (!capturedPrice) {
    showError(
      captureValidation,
      semantics === "multibuy"
        ? "Ange ett giltigt totalpris, till exempel 30 eller 30,00."
        : "Ange ett giltigt pris, till exempel 19,90.",
    );
    return;
  }
  if (semantics === "multibuy" && !multibuyQuantity) {
    showError(captureValidation, "Ange hur många varor erbjudandet gäller.");
    return;
  }
  if (
    !noMatchInput.checked
    && currentIdentificationEvidence === EVIDENCE.UNVERIFIED
    && currentIdentityStatus !== IDENTITY.GTIN_MISMATCH
  ) {
    showError(
      captureValidation,
      "Bekräfta den valda varan manuellt, försök berika produktdata eller markera Fel vara / NO_MATCH.",
    );
    return;
  }
  if (noMatchInput.checked) {
    currentIdentityStatus = IDENTITY.NO_MATCH;
    currentIdentificationEvidence = EVIDENCE.UNVERIFIED;
  }
  const requestId = captureRequestIds.get(requestedItemId) || newClientRequestId();
  captureRequestIds.set(requestedItemId, requestId);
  const payload = {
    gtin: gtinInput.value.trim() || null,
    product_name: productNameInput.value.trim() || currentItem.target_product_name,
    shelf_price: capturedPrice,
    price_semantics: semantics,
    price_basis: priceBasis,
    promotion_mechanism: promotionMechanism,
    member_only: promotionMember.checked,
    identity_status: currentIdentityStatus,
    identification_evidence: currentIdentificationEvidence,
    regular_shelf_price: regularShelfPrice,
    weight_price_type: semantics === "weight" ? weightPriceType.value : null,
    comparison_price: comparisonPrice,
    comparison_unit: semantics === "weight" || comparisonPrice ? comparisonUnit : null,
    multibuy_quantity: multibuyQuantity,
    multibuy_total_price: multibuyTotal,
    promotion_text: document.querySelector("#promotion-text").value.trim() || null,
    notes: document.querySelector("#notes").value.trim() || null,
    client_request_id: requestId,
  };
  savePending = true;
  setCaptureDisabled(true);
  let confirmed = false;
  try {
    const body = await jsonRequest(
      `/physical-check/sessions/${requestedSessionId}/items/${requestedItemId}/observation`,
      { method: "POST", body: JSON.stringify(payload) },
    );
    confirmed = true;
    captureRequestIds.delete(requestedItemId);
    if (
      !activeSession
      || activeSession.id !== requestedSessionId
      || !currentItem
      || currentItem.id !== requestedItemId
    ) {
      const visibleItemId = currentItem && currentItem.id;
      const refreshed = await jsonRequest(`/physical-check/sessions/${requestedSessionId}`);
      applySession(refreshed, { selectNext: false });
      currentItem = items.find((item) => item.id === visibleItemId) || currentItem;
      renderSuggestions();
      result.textContent = `Hyllpriset sparades för ${requestedItemName}. Den nu valda varan ändrades inte.`;
      setCaptureDisabled(!currentItem || currentItem.captured);
      return;
    }
    const comparison = body.comparisons && body.comparisons[0];
    const output = body.comparison_output || {};
    const physical = output.physical || {};
    const digital = output.digital;
    const outcome = output.result || {};
    const basisLabel = physical.basis === "weight" ? "kr/kg" : "paket/styck";
    const conditions = [
      physical.promotion_mechanism === "multibuy" ? "flerköp" : null,
      physical.promotion_mechanism === "sale" ? "kampanj" : null,
      physical.member_only ? "medlemskap" : null,
    ].filter(Boolean);
    const physicalText = physical.promotion_mechanism === "multibuy"
      ? `${physical.multibuy_quantity} för ${moneyText(physical.multibuy_total_price)} kr`
      : `${moneyText(physical.price ?? body.observation.shelf_price)} ${physical.basis === "weight" ? "kr/kg" : "kr"}`;
    const digitalText = digital && digital.price !== null
      ? `${moneyText(digital.price)} ${digital.basis === "weight" ? "kr/kg" : "kr"}`
      : "ingen säker match";
    const differenceText = comparison && comparison.signed_difference !== null
      ? ` · Skillnad ${moneyText(comparison.signed_difference)} ${physical.basis === "weight" ? "kr/kg" : "kr"}`
      : "";
    result.textContent = `Fysiskt: ${physicalText} · Bas: ${basisLabel} · Villkor: ${conditions.join(" + ") || "inga"} · Digitalt: ${digitalText}${differenceText} · Resultat: ${String(outcome.status || "no_digital_match").toUpperCase()}.`;
    renderDigitalEvidence(body.item);
    savePending = false;
    setCaptureDisabled(true);
    saveButton.textContent = body.idempotent_replay ? "Redan sparat" : "Sparat";
    nextProductButton.hidden = false;
    try {
      const savedItemId = requestedItemId;
      const refreshed = await jsonRequest(`/physical-check/sessions/${requestedSessionId}`);
      applySession(refreshed, { selectNext: false });
      currentItem = items.find((item) => item.id === savedItemId) || currentItem;
      renderSuggestions();
    } catch (refreshError) {
      showError(
        error,
        `Priset är sparat, men sessionen kunde inte uppdateras: ${refreshError.message}. Tryck Nästa för att försöka igen.`,
      );
    }
  } catch (requestError) {
    showError(
      error,
      `Priset är inte bekräftat sparat: ${requestError.message}. Din inmatning finns kvar; försök igen.`,
    );
  } finally {
    savePending = false;
    if (!confirmed) setCaptureDisabled(false);
  }
}

async function advanceToNextProduct() {
  if (!activeSession) return;
  showError(error, "");
  try {
    const refreshed = await jsonRequest(`/physical-check/sessions/${activeSession.id}`);
    applySession(refreshed);
    document.querySelector(".capture-card").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (requestError) {
    showError(error, `Nästa produkt kunde inte laddas: ${requestError.message}`);
  }
}

async function completeSession() {
  if (!activeSession) return;
  stopScanner();
  try {
    const body = await jsonRequest(`/physical-check/sessions/${activeSession.id}/complete`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    workspace.hidden = true;
    completedPanel.hidden = false;
    completeSummary.textContent = `${body.captured_observations} av ${activeSession.target_count} föreslagna varor sparades. Resultatet gäller endast stickprovet.`;
    exportJson.href = `/physical-check/sessions/${activeSession.id}/export?format=json`;
    exportCsv.href = `/physical-check/sessions/${activeSession.id}/export?format=csv`;
  } catch (requestError) {
    showError(error, `Fältpasset kunde inte avslutas: ${requestError.message}`);
  }
}

function scannerProviderLabel(provider) {
  if (provider === "zxing") return "ZXING";
  if (provider === "native_barcode_detector") return "NATIVE";
  if (provider === "manual") return "MANUELL";
  return "STARTAR";
}

function closeScannerOverlay() {
  scannerOverlay.hidden = true;
  document.body.classList.remove("scanner-open");
  scannerVideo.srcObject = null;
}

function stopScanner() {
  activeBarcodeScanner?.stop();
  activeBarcodeScanner = null;
  scannerStarting = false;
  closeScannerOverlay();
}

function finishScannerAttempt(outcome, details = {}, attempt = scannerAttempt) {
  if (!attempt || attempt.terminalSent) return;
  attempt.terminalSent = true;
  if (attempt.mode === "shelf") return;
  const provider = details.scanner_provider || attempt.provider;
  if (!provider || provider === "manual") return;
  const payload = {
    scanner_provider: provider,
    outcome,
  };
  if (details.barcode_format) payload.barcode_format = details.barcode_format;
  if (Number.isFinite(Number(details.duration_ms))) {
    payload.duration_ms = Math.max(0, Math.round(Number(details.duration_ms)));
  }
  if (details.failure_reason) payload.failure_reason = details.failure_reason;
  void recordScannerDiagnostic(payload);
}

function cancelScanner() {
  if (activeBarcodeScanner && scannerAttempt && !scannerAttempt.terminalSent) {
    finishScannerAttempt("failure", {
      scanner_provider: activeBarcodeScanner.provider || scannerAttempt.provider,
      duration_ms: performance.now() - scannerAttempt.startedAt,
      failure_reason: "cancelled",
    });
  }
  stopScanner();
  showError(error, "");
  gtinHint.textContent = "Skanningen avbröts. Du kan starta igen eller skriva GTIN manuellt.";
}

function handleScannerDiagnostic(diagnostic) {
  if (!diagnostic || typeof diagnostic !== "object") return;
  const provider = diagnostic.provider || diagnostic.scanner_provider;
  if (provider) {
    scannerProviderStatus.textContent = scannerProviderLabel(provider);
    if (scannerAttempt) scannerAttempt.provider = provider;
  }
  if (diagnostic.event === "provider_fallback") {
    scannerLiveStatus.textContent = provider === "zxing"
      ? "Den inbyggda läsaren fungerade inte. ZXing tar över automatiskt."
      : "Kameraläsaren fungerade inte. Manuell GTIN finns kvar.";
  }
  if (diagnostic.event === "camera_opened") {
    const size = diagnostic.width && diagnostic.height
      ? ` · ${diagnostic.width} × ${diagnostic.height}`
      : "";
    scannerLiveStatus.textContent = `Bakre kamera aktiv${size}. Håll streckkoden stilla inom ramen.`;
  }
}

async function handleScannerResult(scanResult) {
  const completedAttempt = scannerAttempt;
  if (scanResult.scanner_mode === "shelf" || activeScannerMode === "shelf") {
    const provider = scanResult.provider || (activeBarcodeScanner && activeBarcodeScanner.provider);
    const requestedSessionId = completedAttempt?.sessionId;
    const requestedStoreId = completedAttempt?.physicalStoreId;
    const requestedItemId = completedAttempt?.itemId;
    stopScanner();
    if (!requestedSessionId || !requestedStoreId || !requestedItemId) return;
    try {
      const evidence = await jsonRequest("/physical-check/shelf-identifiers", {
        method: "POST",
        body: JSON.stringify({
          physical_store_id: requestedStoreId,
          raw_value: scanResult.raw_value,
          barcode_format: scanResult.format,
          validation_session_id: requestedSessionId,
          validation_session_item_id: requestedItemId,
        }),
      });
      if (!currentItem || currentItem.id !== requestedItemId) return;
      shelfCodeStatus.textContent = `SHELF_CODE_UNKNOWN · ${scanResult.format} · ${String(scanResult.raw_value).length} tecken. Sparad som separat, overifierad diagnostik.`;
      if (evidence.status === IDENTITY.SHELF_MATCH) {
        shelfCodeStatus.textContent = `SHELF_CODE_MATCH · ${scanResult.format}. Den verifierade relationen sparades separat.`;
      }
    } catch (requestError) {
      if (!currentItem || currentItem.id !== requestedItemId) return;
      shelfCodeStatus.textContent = `Hyllkoden avkodades (${scanResult.format}) men diagnostiken kunde inte sparas: ${requestError.message}`;
    }
    if (!currentItem || currentItem.id !== requestedItemId) return;
    gtinHint.textContent = `Hyllkod skannad med ${scannerProviderLabel(provider)}. Den användes inte som GTIN.`;
    return;
  }
  if (completedAttempt?.itemId && currentItem?.id !== completedAttempt.itemId) {
    stopScanner();
    return;
  }
  gtinInput.value = scanResult.normalized_gtin;
  const provider = scanResult.provider || (activeBarcodeScanner && activeBarcodeScanner.provider);
  stopScanner();
  await verifyCurrentIdentity("scan");
  finishScannerAttempt("success", {
    scanner_provider: provider,
    barcode_format: scanResult.format,
    duration_ms: scanResult.scan_duration_ms,
  }, completedAttempt);
  gtinHint.textContent = `Scanner: SUCCESS · ${scannerProviderLabel(provider)} · ${scanResult.format}. Produktidentifieringen visas separat nedan.`;
}

function handleScannerError(problem, detail = {}) {
  if (detail.recoverable) {
    scannerLiveStatus.textContent = swedishScannerError(problem);
    return;
  }
  const provider = detail.provider || (activeBarcodeScanner && activeBarcodeScanner.provider);
  if (provider === "manual") {
    if (!manualDiagnosticRecorded) {
      manualDiagnosticRecorded = true;
      void recordScannerDiagnostic({
        scanner_provider: "manual",
        outcome: "manual_fallback",
      });
    }
  } else {
    finishScannerAttempt("failure", {
      scanner_provider: provider,
      duration_ms: scannerAttempt ? performance.now() - scannerAttempt.startedAt : undefined,
      failure_reason: scannerFailureReason(problem),
    });
  }
  showError(error, `${swedishScannerError(problem)} Manuell GTIN fungerar alltid.`);
  stopScanner();
  gtinInput.focus();
}

async function startScanner(mode = "product") {
  if (scannerStarting || activeBarcodeScanner) return;
  showError(error, "");
  if (
    !window.GroceryBarcodeScanner
    || !navigator.mediaDevices
    || typeof navigator.mediaDevices.getUserMedia !== "function"
  ) {
    if (!manualDiagnosticRecorded) {
      manualDiagnosticRecorded = true;
      void recordScannerDiagnostic({
        scanner_provider: "manual",
        outcome: "manual_fallback",
      });
    }
    showError(error, `${swedishScannerError({ name: "UnsupportedError" })} Manuell GTIN fungerar alltid.`);
    gtinInput.focus();
    return;
  }

  scannerStarting = true;
  activeScannerMode = mode === "shelf" ? "shelf" : "product";
  scannerAttempt = {
    startedAt: performance.now(),
    provider: null,
    terminalSent: false,
    mode: activeScannerMode,
    sessionId: activeSession?.id || null,
    physicalStoreId: activeSession?.physical_store_id || null,
    itemId: currentItem?.id || null,
  };
  scannerOverlay.hidden = false;
  document.body.classList.add("scanner-open");
  scannerProviderStatus.textContent = "STARTAR";
  scannerModalHeading.textContent = activeScannerMode === "shelf"
    ? "Skanna hyllans Självscanna-kod"
    : "Skanna produktstreckkod";
  scannerLiveStatus.textContent = activeScannerMode === "shelf"
    ? "Startar bred 1D-läsning för hyllkoden…"
    : "Startar bakre kameran…";
  stopScanButton.focus();
  try {
    const scanner = window.GroceryBarcodeScanner.createBarcodeScanner({
      mode: activeScannerMode,
      videoElement: scannerVideo,
      onResult: (scanResult) => void handleScannerResult(scanResult),
      onError: handleScannerError,
      onDiagnostic: handleScannerDiagnostic,
    });
    activeBarcodeScanner = scanner;
    await scanner.start();
    if (activeBarcodeScanner !== scanner) return;
    scannerAttempt.provider = scanner.provider;
    scannerProviderStatus.textContent = scannerProviderLabel(scanner.provider);
    if (scanner.provider === "manual") {
      handleScannerError(new Error("camera scanner unavailable"), {
        recoverable: false,
        provider: "manual",
      });
      return;
    }
    scannerLiveStatus.textContent = activeScannerMode === "shelf"
      ? "Håll hela hyllkoden stilla inom den breda ramen. Den tolkas inte som GTIN."
      : "Håll produktstreckkoden stilla inom den breda ramen.";
  } catch (scannerError) {
    handleScannerError(scannerError, {
      recoverable: false,
      provider: activeBarcodeScanner ? activeBarcodeScanner.provider : null,
    });
  } finally {
    scannerStarting = false;
  }
}

storeSelect.addEventListener("change", updateSelectedStore);
startButton.addEventListener("click", startSession);
form.addEventListener("submit", saveCapture);
document.querySelectorAll('input[name="price_basis"]').forEach((radio) => {
  radio.addEventListener("change", updateSemanticFields);
});
promotionMember.addEventListener("change", updateSemanticFields);
promotionSale.addEventListener("change", () => {
  if (promotionSale.checked) promotionMultibuy.checked = false;
  updateSemanticFields();
});
promotionMultibuy.addEventListener("change", () => {
  if (promotionMultibuy.checked) promotionSale.checked = false;
  updateSemanticFields();
});
document.querySelector("#load-suggestions").addEventListener("click", async () => {
  if (activeSession) applySession(await jsonRequest(`/physical-check/sessions/${activeSession.id}`));
});
document.querySelector("#complete-session").addEventListener("click", completeSession);
document.querySelector("#complete-session-top").addEventListener("click", completeSession);
document.querySelector("#new-session").addEventListener("click", () => window.location.reload());
nextProductButton.addEventListener("click", advanceToNextProduct);
scanButton.addEventListener("click", () => startScanner("product"));
scanShelfCodeButton.addEventListener("click", () => startScanner("shelf"));
stopScanButton.addEventListener("click", cancelScanner);
gtinInput.addEventListener("input", scheduleManualGtinVerification);
manualProductSearch.addEventListener("input", renderManualProductResults);
prepareIdentifiersButton.addEventListener("click", prepareSessionIdentifiers);
enrichIdentifierButton.addEventListener("click", enrichCurrentIdentifier);
confirmManualIdentityButton.addEventListener("click", confirmCurrentItemManually);
noMatchInput.addEventListener("change", () => {
  if (noMatchInput.checked) {
    setIdentityResult(
      IDENTITY.NO_MATCH,
      EVIDENCE.UNVERIFIED,
      "NO_MATCH · du har markerat att varan inte säkert kan kopplas till den valda källprodukten.",
      "no_match",
    );
    identifierActions.hidden = true;
    return;
  }
  if (isWeightItem(currentItem)) {
    setIdentityResult(
      IDENTITY.WEIGHT,
      EVIDENCE.WEIGHT,
      "WEIGHT_ITEM_NO_GTIN_REQUIRED · exakt viktvara vald från källunderlaget.",
      "match",
    );
    return;
  }
  confirmCurrentItemManually();
});

window.addEventListener("pagehide", stopScanner);
window.addEventListener("beforeunload", stopScanner);

if (
  window.GroceryBarcodeScanner
  && navigator.mediaDevices
  && typeof navigator.mediaDevices.getUserMedia === "function"
) {
  scanButton.hidden = false;
  gtinHint.textContent = "Tryck Skanna streckkod för kameran, eller skriv GTIN manuellt.";
} else {
  scanButton.hidden = true;
  gtinHint.textContent = "Kameraskanning stöds inte i denna webbläsare. Skriv eller klistra in GTIN manuellt.";
}
updateSemanticFields();
initializeFieldSession()
  .then(loadStores)
  .catch((sessionError) => {
    showError(pageError, sessionError.message);
  });

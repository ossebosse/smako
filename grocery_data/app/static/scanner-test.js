"use strict";

const video = document.querySelector("#scanner-test-video");
const cameraPanel = document.querySelector("#camera-panel");
const startButton = document.querySelector("#start-scanner");
const cancelButton = document.querySelector("#cancel-scanner");
const state = document.querySelector("#scanner-state");
const message = document.querySelector("#scanner-message");
const error = document.querySelector("#scanner-error");
const provider = document.querySelector("#scanner-provider");
const cameraSelected = document.querySelector("#camera-selected");
const resolution = document.querySelector("#camera-resolution");
const format = document.querySelector("#barcode-format");
const rawValue = document.querySelector("#barcode-raw");
const normalized = document.querySelector("#barcode-normalized");
const duration = document.querySelector("#scan-duration");
const browserEnvironment = document.querySelector("#browser-environment");
const manualGtin = document.querySelector("#manual-gtin");
const validateManual = document.querySelector("#validate-manual");
const manualResult = document.querySelector("#manual-result");
const modeInputs = [...document.querySelectorAll('input[name="scanner-mode"]')];
const modeDescription = document.querySelector("#scanner-mode-description");
const scannerHeading = document.querySelector("#scanner-heading");
const productResultCard = document.querySelector("#product-result-card");
const shelfResultCard = document.querySelector("#shelf-result-card");
const manualGtinCard = document.querySelector("#manual-gtin-card");
const shelfRawValue = document.querySelector("#shelf-barcode-raw");
const shelfFormat = document.querySelector("#shelf-barcode-format");
const shelfLength = document.querySelector("#shelf-barcode-length");

let activeScanner = null;
let scannerStarting = false;
let fieldCsrfToken = null;
let activeAttempt = null;
let manualFallbackRecorded = false;

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
  if (!response.ok) throw new Error("Fältinloggningen kunde inte verifieras.");
  fieldCsrfToken = (await response.json()).csrf_token;
}

async function recordDiagnostic(payload) {
  if (!fieldCsrfToken) return;
  try {
    await fetch("/physical-check/scanner-diagnostics", {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        "X-Physical-Check-CSRF": fieldCsrfToken,
      },
      body: JSON.stringify(payload),
    });
  } catch {
    // Diagnostics are optional and must never block another camera test.
  }
}

function finishAttempt(outcome, details = {}) {
  if (!activeAttempt || activeAttempt.terminalSent) return;
  activeAttempt.terminalSent = true;
  // Shelf-code diagnostics intentionally remain local and raw. They are not
  // mixed into retail-GTIN scanner metrics or sent to product endpoints.
  if (activeAttempt.mode === "shelf") return;
  const scannerProvider = details.scanner_provider || activeAttempt.provider;
  if (!scannerProvider || scannerProvider === "manual") return;
  const payload = { scanner_provider: scannerProvider, outcome };
  if (details.barcode_format) payload.barcode_format = details.barcode_format;
  if (Number.isFinite(Number(details.duration_ms))) {
    payload.duration_ms = Math.max(0, Math.round(Number(details.duration_ms)));
  }
  if (details.failure_reason) payload.failure_reason = details.failure_reason;
  void recordDiagnostic(payload);
}

function setError(text) {
  error.textContent = text || "";
  error.hidden = !text;
}

function safeText(value, fallback = "–") {
  if (value === null || value === undefined || value === "") return fallback;
  return String(value);
}

function selectedScannerMode() {
  return modeInputs.find((input) => input.checked)?.value === "shelf"
    ? "shelf"
    : "product";
}

function setModeControlsDisabled(disabled) {
  for (const input of modeInputs) input.disabled = disabled;
}

function updateModeUi() {
  const shelfMode = selectedScannerMode() === "shelf";
  productResultCard.hidden = shelfMode;
  shelfResultCard.hidden = !shelfMode;
  manualGtinCard.hidden = shelfMode;
  scannerHeading.textContent = shelfMode ? "Testa hyllkod" : "Testa produktstreckkod";
  modeDescription.textContent = shelfMode
    ? "Hyllkoden läses som rå diagnostik med bredare 1D-format. Den tolkas inte som GTIN."
    : "Produktläget läser EAN/UPC och validerar GTIN-kontrollsumman.";
  message.textContent = shelfMode
    ? "Tryck på ”Starta kameran” och rikta den mot Hemköps Självscanna-kod."
    : "Tryck på ”Starta kameran” och godkänn kamerabehörigheten.";
  setError("");
}

function browserLabel() {
  const ua = navigator.userAgent || "";
  const isIOS = /iPad|iPhone|iPod/.test(ua)
    || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const browser = /CriOS/.test(ua)
    ? "Chrome iOS"
    : /FxiOS/.test(ua)
      ? "Firefox iOS"
      : /Safari/.test(ua) && !/Chrome|Chromium/.test(ua)
        ? "Safari"
        : "Annan webbläsare";
  return `${isIOS ? "iOS" : "annan plattform"} · ${browser}`;
}

function swedishScannerError(problem) {
  const name = safeText(problem && problem.name, "");
  if (name === "NotAllowedError" || name === "SecurityError") {
    return "Kamerabehörigheten nekades. Tillåt kameran i Safari-inställningarna eller skriv GTIN manuellt.";
  }
  if (name === "NotFoundError" || name === "DevicesNotFoundError") {
    return "Ingen kamera hittades. Skriv GTIN manuellt.";
  }
  if (name === "NotReadableError" || name === "TrackStartError") {
    return "Kameran används av en annan app eller kunde inte startas. Stäng andra kameraappar och försök igen.";
  }
  if (!navigator.mediaDevices || typeof navigator.mediaDevices.getUserMedia !== "function") {
    return "Webbläsaren saknar kamerastöd. Öppna sidan via HTTPS i Safari eller skriv GTIN manuellt.";
  }
  return "Streckkodsläsaren kunde inte startas. Försök igen eller skriv GTIN manuellt.";
}

function scannerFailureReason(problem) {
  const name = safeText(problem && problem.name, "");
  const code = safeText(problem && problem.code, "");
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

function stopScanner(nextState = "REDO") {
  if (activeScanner) {
    activeScanner.stop();
    activeScanner = null;
  }
  scannerStarting = false;
  video.srcObject = null;
  cameraPanel.hidden = true;
  cancelButton.hidden = true;
  startButton.disabled = false;
  setModeControlsDisabled(false);
  state.textContent = nextState;
}

function updateResolution() {
  if (video.videoWidth > 0 && video.videoHeight > 0) {
    resolution.textContent = `${video.videoWidth} × ${video.videoHeight}`;
  }
}

function handleDiagnostic(diagnostic) {
  if (!diagnostic || typeof diagnostic !== "object") return;
  const providerValue = diagnostic.scanner_provider || diagnostic.provider;
  if (providerValue) {
    provider.textContent = safeText(providerValue);
    if (activeAttempt) activeAttempt.provider = providerValue;
  }
  const cameraValue = diagnostic.camera_label || diagnostic.camera_selected;
  if (cameraValue) cameraSelected.textContent = safeText(cameraValue);
  const width = Number(diagnostic.video_width || diagnostic.width || 0);
  const height = Number(diagnostic.video_height || diagnostic.height || 0);
  if (width > 0 && height > 0) resolution.textContent = `${width} × ${height}`;
  updateResolution();
}

function handleResult(scanResult) {
  if (scanResult.scanner_mode === "shelf" || selectedScannerMode() === "shelf") {
    if (activeAttempt) activeAttempt.terminalSent = true;
    const decodedRaw = safeText(scanResult.raw_value);
    shelfRawValue.textContent = decodedRaw;
    shelfFormat.textContent = safeText(scanResult.format);
    shelfLength.textContent = scanResult.raw_value === null || scanResult.raw_value === undefined
      ? "–"
      : String(Array.from(String(scanResult.raw_value)).length);
    updateResolution();
    stopScanner("KLAR");
    message.textContent = "Hyllkoden avkodades som rå diagnostik. Ingen GTIN-tolkning eller prisobservation gjordes.";
    return;
  }
  rawValue.textContent = safeText(scanResult.raw_value);
  normalized.textContent = safeText(scanResult.normalized_gtin);
  format.textContent = safeText(scanResult.format);
  provider.textContent = safeText(scanResult.provider || (activeScanner && activeScanner.provider));
  duration.textContent = Number.isFinite(Number(scanResult.scan_duration_ms))
    ? `${Math.round(Number(scanResult.scan_duration_ms))} ms`
    : "–";
  finishAttempt("success", {
    scanner_provider: scanResult.provider,
    barcode_format: scanResult.format,
    duration_ms: scanResult.scan_duration_ms,
  });
  updateResolution();
  stopScanner("KLAR");
  message.textContent = "Streckkoden lästes och validerades. Ingen observation sparades.";
}

async function startScanner() {
  if (scannerStarting || activeScanner) return;
  setError("");
  if (!navigator.mediaDevices || typeof navigator.mediaDevices.getUserMedia !== "function") {
    setError(swedishScannerError({ name: "UnsupportedError" }));
    state.textContent = "MANUELL";
    if (!manualFallbackRecorded) {
      manualFallbackRecorded = true;
      void recordDiagnostic({ scanner_provider: "manual", outcome: "manual_fallback" });
    }
    manualGtin.focus();
    return;
  }
  if (!window.GroceryBarcodeScanner) {
    setError("Streckkodsbiblioteket kunde inte laddas. Ladda om sidan eller skriv GTIN manuellt.");
    state.textContent = "MANUELL";
    if (!manualFallbackRecorded) {
      manualFallbackRecorded = true;
      void recordDiagnostic({ scanner_provider: "manual", outcome: "manual_fallback" });
    }
    return;
  }

  scannerStarting = true;
  const scannerMode = selectedScannerMode();
  activeAttempt = {
    startedAt: performance.now(),
    provider: null,
    terminalSent: false,
    mode: scannerMode,
  };
  startButton.disabled = true;
  setModeControlsDisabled(true);
  cancelButton.hidden = false;
  cameraPanel.hidden = false;
  state.textContent = "STARTAR";
  message.textContent = "Kameran startar…";
  let scanner = null;
  try {
    scanner = window.GroceryBarcodeScanner.createBarcodeScanner({
      mode: scannerMode,
      videoElement: video,
      onResult: handleResult,
      onError: (problem, detail = {}) => {
        if (detail.recoverable) {
          setError(scannerMode === "shelf"
            ? "Hyllkoden kunde inte avkodas. Håll den stilla inom ramen."
            : "Koden lästes men kontrollsiffran var ogiltig. Försök med nästa streckkod.");
          message.textContent = scannerMode === "shelf"
            ? "Skanningen fortsätter. Håll hela hyllkoden inom den breda ramen."
            : "Skanningen fortsätter. Håll en giltig EAN/UPC-kod inom ramen.";
          return;
        }
        if (detail.provider === "manual") {
          if (!manualFallbackRecorded) {
            manualFallbackRecorded = true;
            void recordDiagnostic({ scanner_provider: "manual", outcome: "manual_fallback" });
          }
        } else {
          finishAttempt("failure", {
            scanner_provider: detail.provider,
            duration_ms: activeAttempt ? performance.now() - activeAttempt.startedAt : undefined,
            failure_reason: scannerFailureReason(problem),
          });
        }
        setError(swedishScannerError(problem));
        message.textContent = "Kameraskanningen avbröts. Manuell GTIN fungerar alltid.";
        stopScanner("MANUELL");
      },
      onDiagnostic: handleDiagnostic,
    });
    activeScanner = scanner;
    await scanner.start();
    if (activeScanner !== scanner) return;
    provider.textContent = safeText(scanner.provider);
    updateResolution();
    state.textContent = "SKANNAR";
    message.textContent = scannerMode === "shelf"
      ? "Håll hyllkoden stilla inom den breda ramen."
      : "Håll produktstreckkoden stilla inom den breda ramen.";
  } catch (problem) {
    if (activeAttempt && !activeAttempt.terminalSent) {
      const selectedProvider = (scanner && scanner.provider) || activeAttempt.provider;
      if (selectedProvider === "manual") {
        if (!manualFallbackRecorded) {
          manualFallbackRecorded = true;
          void recordDiagnostic({ scanner_provider: "manual", outcome: "manual_fallback" });
        }
      } else if (selectedProvider) {
        finishAttempt("failure", {
          scanner_provider: selectedProvider,
          duration_ms: performance.now() - activeAttempt.startedAt,
          failure_reason: scannerFailureReason(problem),
        });
      }
    }
    setError(swedishScannerError(problem));
    message.textContent = "Kameran startade inte. Manuell GTIN fungerar alltid.";
    stopScanner("MANUELL");
  } finally {
    scannerStarting = false;
  }
}

function testManualGtin() {
  if (selectedScannerMode() !== "product") return;
  setError("");
  if (!window.GroceryBarcodeScanner) {
    manualResult.textContent = "Normaliseringsbiblioteket kunde inte laddas.";
    return;
  }
  try {
    const result = window.GroceryBarcodeScanner.normalizeGtin(manualGtin.value);
    const normalizedValue = typeof result === "string"
      ? result
      : result.normalized_gtin || result.gtin;
    const formatValue = typeof result === "string" ? "GTIN" : result.format;
    normalized.textContent = safeText(normalizedValue);
    rawValue.textContent = manualGtin.value.trim() || "–";
    format.textContent = safeText(formatValue, "GTIN");
    provider.textContent = "manual";
    duration.textContent = "–";
    state.textContent = "MANUELL";
    manualResult.textContent = `Giltig kod: ${safeText(normalizedValue)}`;
    if (!manualFallbackRecorded) {
      manualFallbackRecorded = true;
      void recordDiagnostic({ scanner_provider: "manual", outcome: "manual_fallback" });
    }
  } catch (_problem) {
    manualResult.textContent = "Koden har fel längd eller ogiltig kontrollsiffra.";
  }
}

browserEnvironment.textContent = browserLabel();
if (new URLSearchParams(window.location.search).get("mode") === "shelf") {
  const shelfModeInput = modeInputs.find((input) => input.value === "shelf");
  if (shelfModeInput) shelfModeInput.checked = true;
}
updateModeUi();
startButton.addEventListener("click", startScanner);
cancelButton.addEventListener("click", () => {
  if (activeScanner && activeAttempt && !activeAttempt.terminalSent) {
    finishAttempt("failure", {
      scanner_provider: activeScanner.provider || activeAttempt.provider,
      duration_ms: performance.now() - activeAttempt.startedAt,
      failure_reason: "cancelled",
    });
  }
  stopScanner();
  message.textContent = "Kameran är avstängd. Du kan starta igen eller skriva GTIN manuellt.";
});
validateManual.addEventListener("click", testManualGtin);
for (const input of modeInputs) {
  input.addEventListener("change", () => {
    stopScanner();
    updateModeUi();
  });
}
manualGtin.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    testManualGtin();
  }
});
video.addEventListener("loadedmetadata", updateResolution);
window.addEventListener("pagehide", () => stopScanner());
window.addEventListener("beforeunload", () => stopScanner());
initializeFieldSession().catch(() => {
  setError("Fältinloggningen kunde inte verifieras. Ladda om sidan och logga in igen.");
});

import {
  BrowserMultiFormatReader,
} from "@zxing/browser";
import {
  BarcodeFormat as ZxingBarcodeFormat,
  ChecksumException,
  DecodeHintType,
  FormatException,
  NotFoundException,
} from "@zxing/library";
import { GtinValidationError, normalizeFormat, normalizeGtin } from "./gtin.js";

export const SCANNER_PROVIDERS = Object.freeze({
  NATIVE: "native_barcode_detector",
  ZXING: "zxing",
  MANUAL: "manual",
});

export const SCANNER_MODES = Object.freeze({
  PRODUCT: "product",
  SHELF: "shelf",
});

export const PRODUCT_SCANNER_FORMATS = Object.freeze([
  "EAN_13",
  "EAN_8",
  "UPC_A",
  "UPC_E",
]);

export const SHELF_SCANNER_FORMATS = Object.freeze([
  "CODE_128",
  "CODE_39",
  "ITF",
  "EAN_13",
  "EAN_8",
  "UPC_A",
  "UPC_E",
  "RSS_14",
  "RSS_EXPANDED",
]);

// Backward-compatible name for callers that only support retail product GTINs.
export const SCANNER_FORMATS = PRODUCT_SCANNER_FORMATS;

class ScannerCancelledError extends Error {
  constructor() {
    super("Streckkodsläsaren avbröts.");
    this.name = "ScannerCancelledError";
    this.code = "scanner_cancelled";
  }
}

function isScannerCancelled(error) {
  return error instanceof ScannerCancelledError || error?.code === "scanner_cancelled";
}

function stopStream(stream) {
  for (const track of stream?.getTracks?.() || []) track.stop();
}

const NATIVE_FORMATS = Object.freeze({
  EAN_13: "ean_13",
  EAN_8: "ean_8",
  UPC_A: "upc_a",
  UPC_E: "upc_e",
});

const ZXING_PRODUCT_FORMATS = Object.freeze([
  ZxingBarcodeFormat.EAN_13,
  ZxingBarcodeFormat.EAN_8,
  ZxingBarcodeFormat.UPC_A,
  ZxingBarcodeFormat.UPC_E,
]);

const ZXING_SHELF_FORMATS = Object.freeze([
  ZxingBarcodeFormat.CODE_128,
  ZxingBarcodeFormat.CODE_39,
  ZxingBarcodeFormat.ITF,
  ZxingBarcodeFormat.EAN_13,
  ZxingBarcodeFormat.EAN_8,
  ZxingBarcodeFormat.UPC_A,
  ZxingBarcodeFormat.UPC_E,
  ZxingBarcodeFormat.RSS_14,
  ZxingBarcodeFormat.RSS_EXPANDED,
]);

const DEFAULT_CONSTRAINTS = Object.freeze({
  audio: false,
  video: {
    facingMode: { ideal: "environment" },
    width: { ideal: 1280 },
    height: { ideal: 720 },
    frameRate: { ideal: 30, max: 30 },
  },
});

function safeDiagnostic(callback, event) {
  if (typeof callback !== "function") return;
  const allowed = [
    "event",
    "provider",
    "scanner_mode",
    "camera_label",
    "width",
    "height",
    "format",
    "scan_duration_ms",
    "reason",
  ];
  const safe = {};
  for (const key of allowed) {
    if (event[key] !== undefined && event[key] !== null) safe[key] = event[key];
  }
  try {
    callback(Object.freeze(safe));
  } catch {
    // Diagnostics are optional and must never interrupt camera cleanup or scanning.
  }
}

function normalizeScannerMode(mode) {
  if (mode === undefined || mode === null || mode === "") return SCANNER_MODES.PRODUCT;
  if (Object.values(SCANNER_MODES).includes(mode)) return mode;
  throw new Error(`Okänt skanningsläge: ${String(mode)}`);
}

function scannerFormatsForMode(mode) {
  return mode === SCANNER_MODES.SHELF
    ? SHELF_SCANNER_FORMATS
    : PRODUCT_SCANNER_FORMATS;
}

function zxingFormatsForMode(mode) {
  return mode === SCANNER_MODES.SHELF
    ? ZXING_SHELF_FORMATS
    : ZXING_PRODUCT_FORMATS;
}

function barcodeFormatName(rawFormat) {
  if (typeof rawFormat === "number") {
    return Object.entries(ZxingBarcodeFormat).find(([, value]) => value === rawFormat)?.[0]
      || `UNKNOWN_${rawFormat}`;
  }
  const text = String(rawFormat ?? "").trim();
  return normalizeFormat(text) || text.toUpperCase() || "UNKNOWN";
}

export class BarcodeScanner {
  async start() {
    throw new Error("BarcodeScanner.start() måste implementeras.");
  }

  stop() {}

  supportedFormats() {
    return [];
  }
}

export class ScanDebouncer {
  constructor(cooldownMs = 1500, now = () => Date.now()) {
    this.cooldownMs = cooldownMs;
    this.now = now;
    this.lastValue = null;
    this.lastSeenAt = 0;
  }

  accept(value) {
    const timestamp = this.now();
    if (value === this.lastValue && timestamp - this.lastSeenAt < this.cooldownMs) return false;
    this.lastValue = value;
    this.lastSeenAt = timestamp;
    return true;
  }
}

class CameraScanner extends BarcodeScanner {
  constructor(options = {}) {
    super();
    this.mode = normalizeScannerMode(options.mode);
    this.videoElement = options.videoElement;
    this.mediaDevices = options.mediaDevices || globalThis.navigator?.mediaDevices;
    this.constraints = options.constraints || DEFAULT_CONSTRAINTS;
    this.onResult = options.onResult;
    this.onError = options.onError;
    this.onDiagnostic = options.onDiagnostic;
    this.debouncer = options.debouncer || new ScanDebouncer();
    this.stream = null;
    this.startedAt = 0;
    this.running = false;
    this.cancelled = false;
    this.pageHideTarget = options.pageHideTarget || globalThis.window;
    this.boundPageHide = () => this.stop();
  }

  ensureCameraSupport() {
    if (!this.videoElement) throw new Error("Kameravideon saknas.");
    if (!this.mediaDevices || typeof this.mediaDevices.getUserMedia !== "function") {
      throw new Error("Webbläsaren saknar kamerastöd.");
    }
  }

  async openCamera() {
    this.ensureCameraSupport();
    this.pageHideTarget?.addEventListener?.("pagehide", this.boundPageHide, { once: true });
    const stream = await this.mediaDevices.getUserMedia(this.constraints);
    if (this.cancelled) {
      stopStream(stream);
      throw new ScannerCancelledError();
    }
    this.stream = stream;
    const [track] = this.stream.getVideoTracks();
    if (!track) throw new Error("Ingen kamera hittades.");
    await this.applySafeCameraCapabilities(track);
    if (this.cancelled) {
      stopStream(stream);
      this.stream = null;
      throw new ScannerCancelledError();
    }
    this.videoElement.srcObject = this.stream;
    this.videoElement.setAttribute("playsinline", "");
    this.videoElement.muted = true;
    await this.videoElement.play();
    if (this.cancelled) {
      stopStream(stream);
      this.stream = null;
      this.videoElement.srcObject = null;
      throw new ScannerCancelledError();
    }
    const settings = typeof track.getSettings === "function" ? track.getSettings() : {};
    safeDiagnostic(this.onDiagnostic, {
      event: "camera_opened",
      provider: this.provider,
      camera_label: String(track.label || "bakre kamera"),
      width: settings.width,
      height: settings.height,
    });
    return this.stream;
  }

  async applySafeCameraCapabilities(track) {
    if (typeof track.getCapabilities !== "function" || typeof track.applyConstraints !== "function") {
      return;
    }
    const capabilities = track.getCapabilities();
    if (Array.isArray(capabilities.focusMode) && capabilities.focusMode.includes("continuous")) {
      try {
        await track.applyConstraints({ advanced: [{ focusMode: "continuous" }] });
      } catch {
        // Optional camera tuning must never make scanning unavailable.
      }
    }
  }

  emitResult(rawValue, formatHint) {
    if (this.mode === SCANNER_MODES.SHELF) {
      const shelfRawValue = String(rawValue ?? "");
      if (!shelfRawValue.trim()) return false;
      const shelfFormat = barcodeFormatName(formatHint);
      if (!this.debouncer.accept(`${shelfFormat}\0${shelfRawValue}`)) return false;
      const result = Object.freeze({
        raw_value: shelfRawValue,
        format: shelfFormat,
        provider: this.provider,
        scanner_mode: SCANNER_MODES.SHELF,
        scan_duration_ms: Math.max(0, Math.round(performance.now() - this.startedAt)),
      });
      safeDiagnostic(this.onDiagnostic, {
        event: "scan_succeeded",
        provider: this.provider,
        scanner_mode: this.mode,
        format: result.format,
        scan_duration_ms: result.scan_duration_ms,
      });
      this.stop();
      this.onResult?.(result);
      return true;
    }

    let normalized;
    try {
      normalized = normalizeGtin(rawValue, formatHint);
    } catch (error) {
      if (error instanceof GtinValidationError) {
        safeDiagnostic(this.onDiagnostic, {
          event: "invalid_barcode",
          provider: this.provider,
          reason: error.code,
        });
        return false;
      }
      throw error;
    }
    if (!this.debouncer.accept(normalized.normalized_gtin)) return false;
    const result = Object.freeze({
      ...normalized,
      provider: this.provider,
      scanner_mode: SCANNER_MODES.PRODUCT,
      scan_duration_ms: Math.max(0, Math.round(performance.now() - this.startedAt)),
    });
    safeDiagnostic(this.onDiagnostic, {
      event: "scan_succeeded",
      provider: this.provider,
      scanner_mode: this.mode,
      format: result.format,
      scan_duration_ms: result.scan_duration_ms,
    });
    this.stop();
    this.onResult?.(result);
    return true;
  }

  stop() {
    this.cancelled = true;
    this.running = false;
    stopStream(this.stream);
    this.stream = null;
    if (this.videoElement) {
      try {
        this.videoElement.pause?.();
      } catch {
        // Some synthetic test video elements do not implement pause.
      }
      this.videoElement.srcObject = null;
    }
    this.pageHideTarget?.removeEventListener?.("pagehide", this.boundPageHide);
  }
}

export class NativeBarcodeDetectorScanner extends CameraScanner {
  constructor(options = {}) {
    super(options);
    this.provider = SCANNER_PROVIDERS.NATIVE;
    this.BarcodeDetectorClass = options.BarcodeDetectorClass || globalThis.BarcodeDetector;
    this.requestFrame = options.requestFrame || ((callback) => requestAnimationFrame(callback));
    this.detector = null;
    this.nativeFormats = [];
    this.fallbackTimer = null;
    this.nativeFallbackAfterMs = options.nativeFallbackAfterMs ?? 4000;
  }

  supportedFormats() {
    return [...this.nativeFormats];
  }

  async querySupportedFormats() {
    if (!this.BarcodeDetectorClass) return [];
    const available = typeof this.BarcodeDetectorClass.getSupportedFormats === "function"
      ? await this.BarcodeDetectorClass.getSupportedFormats()
      : [];
    const availableSet = new Set(available);
    return PRODUCT_SCANNER_FORMATS.filter((format) => availableSet.has(NATIVE_FORMATS[format]));
  }

  async start() {
    this.cancelled = false;
    this.ensureCameraSupport();
    if (this.mode === SCANNER_MODES.SHELF) {
      throw new Error("Hyllkodsläget använder ZXing för utökat 1D-stöd.");
    }
    if (!this.BarcodeDetectorClass) throw new Error("Native BarcodeDetector saknas.");
    this.nativeFormats = await this.querySupportedFormats();
    if (!["EAN_13", "EAN_8", "UPC_A", "UPC_E"].every((format) => this.nativeFormats.includes(format))) {
      throw new Error("Native BarcodeDetector saknar nödvändiga handelsformat.");
    }
    this.detector = new this.BarcodeDetectorClass({
      formats: this.nativeFormats.map((format) => NATIVE_FORMATS[format]),
    });
    await this.openCamera();
    this.running = true;
    this.startedAt = performance.now();
    safeDiagnostic(this.onDiagnostic, { event: "scanner_started", provider: this.provider });
    this.fallbackTimer = setTimeout(() => {
      if (!this.running) return;
      const error = new Error("Den inbyggda streckkodsläsaren gav ingen träff.");
      error.code = "no_barcode_detected";
      this.stop();
      this.onError?.(error, { recoverable: false, provider: this.provider });
    }, this.nativeFallbackAfterMs);
    this.detectLoop();
    return this;
  }

  async detectLoop() {
    if (!this.running) return;
    try {
      const codes = await this.detector.detect(this.videoElement);
      const code = codes?.[0];
      if (code && this.emitResult(code.rawValue, code.format)) return;
    } catch (error) {
      if (!this.running) return;
      this.stop();
      this.onError?.(error, { recoverable: false, provider: this.provider });
      return;
    }
    if (this.running) this.requestFrame(() => this.detectLoop());
  }

  stop() {
    if (this.fallbackTimer !== null) clearTimeout(this.fallbackTimer);
    this.fallbackTimer = null;
    super.stop();
  }
}

export class ZXingBarcodeScanner extends CameraScanner {
  constructor(options = {}) {
    super(options);
    this.provider = SCANNER_PROVIDERS.ZXING;
    this.ReaderClass = options.ReaderClass || BrowserMultiFormatReader;
    this.reader = null;
    this.controls = null;
  }

  supportedFormats() {
    return [...scannerFormatsForMode(this.mode)];
  }

  async start() {
    this.cancelled = false;
    const hints = new Map();
    hints.set(DecodeHintType.POSSIBLE_FORMATS, zxingFormatsForMode(this.mode));
    hints.set(DecodeHintType.TRY_HARDER, true);
    this.reader = new this.ReaderClass(hints, {
      delayBetweenScanAttempts: 100,
      delayBetweenScanSuccess: 500,
    });
    const stream = await this.openCamera();
    this.running = true;
    this.startedAt = performance.now();
    safeDiagnostic(this.onDiagnostic, { event: "scanner_started", provider: this.provider });
    const controls = await this.reader.decodeFromStream(
      stream,
      this.videoElement,
      (decoded, decodeError) => {
        if (!this.running) return;
        if (decoded) {
          const rawValue = typeof decoded.getText === "function" ? decoded.getText() : decoded.text;
          const rawFormat = typeof decoded.getBarcodeFormat === "function"
            ? decoded.getBarcodeFormat()
            : decoded.format;
          this.emitResult(rawValue, barcodeFormatName(rawFormat));
        } else if (
          decodeError
          && !(decodeError instanceof NotFoundException)
          && !(decodeError instanceof ChecksumException)
          && !(decodeError instanceof FormatException)
        ) {
          this.stop();
          this.onError?.(decodeError, { recoverable: false, provider: this.provider });
        }
      },
    );
    this.controls = controls;
    if (!this.running) this.controls?.stop?.();
    return this;
  }

  stop() {
    try {
      this.controls?.stop?.();
      this.reader?.reset?.();
    } catch {
      // Media tracks are always stopped below, even if ZXing cleanup fails.
    }
    this.controls = null;
    super.stop();
  }
}

export class ManualBarcodeScanner extends BarcodeScanner {
  constructor(options = {}) {
    super();
    this.provider = SCANNER_PROVIDERS.MANUAL;
    this.onDiagnostic = options.onDiagnostic;
  }

  supportedFormats() {
    return [];
  }

  async start() {
    safeDiagnostic(this.onDiagnostic, {
      event: "manual_fallback",
      provider: this.provider,
      reason: "camera_scanner_unavailable",
    });
    return this;
  }
}

function isIOSLike(userAgent, platform, maxTouchPoints) {
  if (/iPad|iPhone|iPod/i.test(userAgent)) return true;
  return platform === "MacIntel" && Number(maxTouchPoints) > 1;
}

export class FallbackBarcodeScanner extends BarcodeScanner {
  constructor(options = {}) {
    super();
    this.options = options;
    this.userAgent = options.userAgent ?? globalThis.navigator?.userAgent ?? "";
    this.platform = options.platform ?? globalThis.navigator?.platform ?? "";
    this.maxTouchPoints = options.maxTouchPoints ?? globalThis.navigator?.maxTouchPoints ?? 0;
    this.NativeScannerClass = options.NativeScannerClass || NativeBarcodeDetectorScanner;
    this.ZXingScannerClass = options.ZXingScannerClass || ZXingBarcodeScanner;
    this.ManualScannerClass = options.ManualScannerClass || ManualBarcodeScanner;
    this.activeScanner = null;
    this.provider = SCANNER_PROVIDERS.MANUAL;
    this.stopped = false;
  }

  supportedFormats() {
    return this.activeScanner?.supportedFormats()
      || [...scannerFormatsForMode(normalizeScannerMode(this.options.mode))];
  }

  scannerOptions(provider) {
    const outerOnError = this.options.onError;
    return {
      ...this.options,
      onResult: this.options.onResult,
      onDiagnostic: this.options.onDiagnostic,
      onError: (error, detail = {}) => {
        if (provider === SCANNER_PROVIDERS.NATIVE && detail.recoverable === false && !this.stopped) {
          void this.fallbackAfterNativeFailure(error).catch((fallbackError) => {
            if (!this.stopped && !isScannerCancelled(fallbackError)) {
              outerOnError?.(fallbackError, {
                recoverable: false,
                provider: SCANNER_PROVIDERS.MANUAL,
              });
            }
          });
          return;
        }
        if (provider === SCANNER_PROVIDERS.ZXING && detail.recoverable === false && !this.stopped) {
          void this.fallbackAfterZxingFailure(error).catch((fallbackError) => {
            if (!this.stopped && !isScannerCancelled(fallbackError)) {
              outerOnError?.(fallbackError, {
                recoverable: false,
                provider: SCANNER_PROVIDERS.MANUAL,
              });
            }
          });
          return;
        }
        outerOnError?.(error, detail);
      },
    };
  }

  async startProvider(ScannerClass, provider) {
    const scanner = new ScannerClass(this.scannerOptions(provider));
    this.activeScanner = scanner;
    this.provider = provider;
    try {
      await scanner.start();
      if (this.stopped) {
        scanner.stop();
        throw new ScannerCancelledError();
      }
      return scanner;
    } catch (error) {
      scanner.stop();
      if (this.stopped) throw new ScannerCancelledError();
      throw error;
    }
  }

  async fallbackAfterNativeFailure(error) {
    this.activeScanner?.stop();
    safeDiagnostic(this.options.onDiagnostic, {
      event: "provider_fallback",
      provider: SCANNER_PROVIDERS.ZXING,
      reason: "native_runtime_failure",
    });
    try {
      await this.startProvider(this.ZXingScannerClass, SCANNER_PROVIDERS.ZXING);
    } catch (zxingError) {
      if (this.stopped || isScannerCancelled(zxingError)) return;
      await this.fallbackAfterZxingFailure(zxingError);
    }
  }

  async fallbackAfterZxingFailure(error) {
    this.activeScanner?.stop();
    if (this.stopped) return;
    safeDiagnostic(this.options.onDiagnostic, {
      event: "provider_fallback",
      provider: SCANNER_PROVIDERS.MANUAL,
      reason: "zxing_runtime_failure",
    });
    await this.startProvider(this.ManualScannerClass, SCANNER_PROVIDERS.MANUAL);
    if (!this.stopped) {
      this.options.onError?.(error, {
        recoverable: false,
        provider: SCANNER_PROVIDERS.ZXING,
        fallback_provider: SCANNER_PROVIDERS.MANUAL,
      });
    }
  }

  async start() {
    this.stopped = false;
    const ios = isIOSLike(this.userAgent, this.platform, this.maxTouchPoints);
    const shelfMode = normalizeScannerMode(this.options.mode) === SCANNER_MODES.SHELF;
    const order = ios || shelfMode
      ? [[this.ZXingScannerClass, SCANNER_PROVIDERS.ZXING]]
      : [
          [this.NativeScannerClass, SCANNER_PROVIDERS.NATIVE],
          [this.ZXingScannerClass, SCANNER_PROVIDERS.ZXING],
        ];
    let lastError = null;
    let lastProvider = SCANNER_PROVIDERS.MANUAL;
    for (const [ScannerClass, provider] of order) {
      try {
        await this.startProvider(ScannerClass, provider);
        return this;
      } catch (error) {
        if (this.stopped || isScannerCancelled(error)) return this;
        lastError = error;
        lastProvider = provider;
        safeDiagnostic(this.options.onDiagnostic, {
          event: "provider_fallback",
          provider: provider === SCANNER_PROVIDERS.NATIVE
            ? SCANNER_PROVIDERS.ZXING
            : SCANNER_PROVIDERS.MANUAL,
          reason: provider === SCANNER_PROVIDERS.NATIVE
            ? "native_initialization_failure"
            : "zxing_initialization_failure",
        });
      }
    }
    await this.startProvider(this.ManualScannerClass, SCANNER_PROVIDERS.MANUAL);
    if (lastError) this.options.onError?.(lastError, {
      recoverable: false,
      provider: lastProvider,
      fallback_provider: SCANNER_PROVIDERS.MANUAL,
    });
    return this;
  }

  stop() {
    this.stopped = true;
    this.activeScanner?.stop();
  }
}

export function createBarcodeScanner(options = {}) {
  return new FallbackBarcodeScanner(options);
}

export function createShelfBarcodeScanner(options = {}) {
  return new FallbackBarcodeScanner({ ...options, mode: SCANNER_MODES.SHELF });
}

export {
  DEFAULT_CONSTRAINTS,
  barcodeFormatName,
  isIOSLike,
  normalizeScannerMode,
  scannerFormatsForMode,
};

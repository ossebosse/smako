import assert from "node:assert/strict";
import test from "node:test";

import {
  ChecksumException,
  DecodeHintType,
  FormatException,
  NotFoundException,
} from "@zxing/library";

import {
  FallbackBarcodeScanner,
  NativeBarcodeDetectorScanner,
  PRODUCT_SCANNER_FORMATS,
  SCANNER_MODES,
  SCANNER_PROVIDERS,
  SHELF_SCANNER_FORMATS,
  ScanDebouncer,
  ZXingBarcodeScanner,
  createShelfBarcodeScanner,
  isIOSLike,
} from "../src/scanner.js";

class SuccessfulScanner {
  constructor(options) {
    this.options = options;
    this.stopped = false;
  }

  async start() {
    return this;
  }

  stop() {
    this.stopped = true;
  }

  supportedFormats() {
    return ["EAN_13"];
  }
}

class FailingScanner extends SuccessfulScanner {
  async start() {
    throw new Error("initialization failed");
  }
}

test("duplicate debounce rejects the same value during cooldown", () => {
  let timestamp = 1000;
  const debouncer = new ScanDebouncer(1500, () => timestamp);
  assert.equal(debouncer.accept("4006381333931"), true);
  timestamp += 200;
  assert.equal(debouncer.accept("4006381333931"), false);
  assert.equal(debouncer.accept("96385074"), true);
  timestamp += 1600;
  assert.equal(debouncer.accept("4006381333931"), true);
});

test("recognizes modern iPhone and iPad desktop user agents", () => {
  assert.equal(isIOSLike("Mozilla/5.0 (iPhone)", "iPhone", 5), true);
  assert.equal(isIOSLike("Mozilla/5.0", "MacIntel", 5), true);
  assert.equal(isIOSLike("Mozilla/5.0", "Win32", 0), false);
});

test("iOS prefers ZXing without starting native BarcodeDetector", async () => {
  let nativeStarts = 0;
  class NativeScanner extends SuccessfulScanner {
    async start() {
      nativeStarts += 1;
      return this;
    }
  }
  const scanner = new FallbackBarcodeScanner({
    userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)",
    NativeScannerClass: NativeScanner,
    ZXingScannerClass: SuccessfulScanner,
  });
  await scanner.start();
  assert.equal(scanner.provider, SCANNER_PROVIDERS.ZXING);
  assert.equal(nativeStarts, 0);
});

test("shelf mode always uses ZXing and advertises only supported 1D formats", async () => {
  let nativeStarts = 0;
  class NativeScanner extends SuccessfulScanner {
    async start() {
      nativeStarts += 1;
      return this;
    }
  }
  const scanner = new FallbackBarcodeScanner({
    mode: SCANNER_MODES.SHELF,
    userAgent: "Mozilla/5.0 (Linux; Android 15)",
    NativeScannerClass: NativeScanner,
    ZXingScannerClass: SuccessfulScanner,
  });
  await scanner.start();
  assert.equal(scanner.provider, SCANNER_PROVIDERS.ZXING);
  assert.equal(nativeStarts, 0);

  const configured = new ZXingBarcodeScanner({ mode: SCANNER_MODES.SHELF });
  assert.deepEqual(configured.supportedFormats(), [...SHELF_SCANNER_FORMATS]);
  assert.deepEqual(
    [...SHELF_SCANNER_FORMATS],
    [
      "CODE_128",
      "CODE_39",
      "ITF",
      "EAN_13",
      "EAN_8",
      "UPC_A",
      "UPC_E",
      "RSS_14",
      "RSS_EXPANDED",
    ],
  );
  assert.deepEqual(
    new ZXingBarcodeScanner().supportedFormats(),
    [...PRODUCT_SCANNER_FORMATS],
  );
});

test("shelf scanner helper cannot be overridden back to product mode", () => {
  const scanner = createShelfBarcodeScanner({ mode: SCANNER_MODES.PRODUCT });
  assert.equal(scanner.options.mode, SCANNER_MODES.SHELF);
});

test("native initialization failure automatically falls back to ZXing", async () => {
  const diagnostics = [];
  const scanner = new FallbackBarcodeScanner({
    userAgent: "Mozilla/5.0 (Linux; Android 15)",
    NativeScannerClass: FailingScanner,
    ZXingScannerClass: SuccessfulScanner,
    onDiagnostic: (entry) => diagnostics.push(entry),
  });
  await scanner.start();
  assert.equal(scanner.provider, SCANNER_PROVIDERS.ZXING);
  assert.ok(diagnostics.some((entry) => entry.reason === "native_initialization_failure"));
});

test("ZXing initialization failure leaves manual input available", async () => {
  const scanner = new FallbackBarcodeScanner({
    userAgent: "Mozilla/5.0 (iPhone)",
    ZXingScannerClass: FailingScanner,
  });
  await scanner.start();
  assert.equal(scanner.provider, SCANNER_PROVIDERS.MANUAL);
});

function fakeCamera() {
  const track = {
    label: "Rear Camera",
    stopped: false,
    stop() { this.stopped = true; },
    getCapabilities() { return {}; },
    getSettings() { return { width: 1280, height: 720 }; },
    async applyConstraints() {},
  };
  const stream = {
    getTracks: () => [track],
    getVideoTracks: () => [track],
  };
  return { track, stream };
}

function fakeVideo() {
  return {
    srcObject: null,
    muted: false,
    setAttribute() {},
    async play() {},
    pause() {},
  };
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

test("native scanner stops every camera track after a successful scan", async () => {
  const { track, stream } = fakeCamera();
  let result;
  class Detector {
    static async getSupportedFormats() {
      return ["ean_13", "ean_8", "upc_a", "upc_e"];
    }

    async detect() {
      return [{ rawValue: "4006381333931", format: "ean_13" }];
    }
  }
  const scanner = new NativeBarcodeDetectorScanner({
    videoElement: fakeVideo(),
    mediaDevices: { async getUserMedia() { return stream; } },
    BarcodeDetectorClass: Detector,
    requestFrame() {},
    pageHideTarget: null,
    onResult(value) { result = value; },
  });
  await scanner.start();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(result.normalized_gtin, "4006381333931");
  assert.equal(result.provider, SCANNER_PROVIDERS.NATIVE);
  assert.equal(track.stopped, true);
});

test("cancelling native scanner stops every camera track", async () => {
  const { track, stream } = fakeCamera();
  class Detector {
    static async getSupportedFormats() {
      return ["ean_13", "ean_8", "upc_a", "upc_e"];
    }

    async detect() {
      return [];
    }
  }
  const scanner = new NativeBarcodeDetectorScanner({
    videoElement: fakeVideo(),
    mediaDevices: { async getUserMedia() { return stream; } },
    BarcodeDetectorClass: Detector,
    requestFrame() {},
    pageHideTarget: null,
  });
  await scanner.start();
  scanner.stop();
  assert.equal(track.stopped, true);
});

test("cancelling while getUserMedia is pending stops the late camera stream", async () => {
  const { track, stream } = fakeCamera();
  const streamRequest = deferred();
  const cameraRequested = deferred();
  class Detector {
    static async getSupportedFormats() {
      return ["ean_13", "ean_8", "upc_a", "upc_e"];
    }
  }
  const scanner = new NativeBarcodeDetectorScanner({
    videoElement: fakeVideo(),
    mediaDevices: {
      getUserMedia() {
        cameraRequested.resolve();
        return streamRequest.promise;
      },
    },
    BarcodeDetectorClass: Detector,
    pageHideTarget: null,
  });
  const starting = scanner.start();
  await cameraRequested.promise;
  scanner.stop();
  streamRequest.resolve(stream);
  await assert.rejects(starting, (error) => error.code === "scanner_cancelled");
  assert.equal(track.stopped, true);
  assert.equal(scanner.running, false);
  assert.equal(scanner.stream, null);
});

test("pagehide while getUserMedia is pending stops the late camera stream", async () => {
  const { track, stream } = fakeCamera();
  const streamRequest = deferred();
  const cameraRequested = deferred();
  let pageHideHandler = null;
  const pageHideTarget = {
    addEventListener(_name, callback) { pageHideHandler = callback; },
    removeEventListener(_name, callback) {
      if (pageHideHandler === callback) pageHideHandler = null;
    },
  };
  class Detector {
    static async getSupportedFormats() {
      return ["ean_13", "ean_8", "upc_a", "upc_e"];
    }
  }
  const scanner = new NativeBarcodeDetectorScanner({
    videoElement: fakeVideo(),
    mediaDevices: {
      getUserMedia() {
        cameraRequested.resolve();
        return streamRequest.promise;
      },
    },
    BarcodeDetectorClass: Detector,
    pageHideTarget,
  });
  const starting = scanner.start();
  await cameraRequested.promise;
  pageHideHandler();
  streamRequest.resolve(stream);
  await assert.rejects(starting, (error) => error.code === "scanner_cancelled");
  assert.equal(track.stopped, true);
  assert.equal(scanner.stream, null);
});

test("ZXing scanner returns a normalized result and stops camera tracks", async () => {
  const { track, stream } = fakeCamera();
  let result;
  class Reader {
    constructor(hints, options) {
      assert.ok(hints instanceof Map);
      assert.equal(options.delayBetweenScanAttempts, 100);
    }

    async decodeFromStream(_stream, _video, callback) {
      callback({
        getText: () => "96385074",
        getBarcodeFormat: () => 6,
      });
      return { stop() {} };
    }

    reset() {}
  }
  const scanner = new ZXingBarcodeScanner({
    videoElement: fakeVideo(),
    mediaDevices: { async getUserMedia() { return stream; } },
    ReaderClass: Reader,
    pageHideTarget: null,
    onResult(value) { result = value; },
  });
  await scanner.start();
  assert.equal(result.normalized_gtin, "96385074");
  assert.equal(result.format, "EAN_8");
  assert.equal(result.provider, SCANNER_PROVIDERS.ZXING);
  assert.equal(track.stopped, true);
});

test("ZXing shelf scan preserves a raw internal code without GTIN interpretation", async () => {
  const { track, stream } = fakeCamera();
  let result;
  class Reader {
    constructor(hints) {
      const formats = hints.get(DecodeHintType.POSSIBLE_FORMATS);
      assert.deepEqual(formats, [4, 2, 8, 7, 6, 14, 15, 12, 13]);
    }

    async decodeFromStream(_stream, _video, callback) {
      callback({
        getText: () => "00-HEMKOP-SELFSCAN-4711",
        getBarcodeFormat: () => 4,
      });
      return { stop() {} };
    }

    reset() {}
  }
  const scanner = new ZXingBarcodeScanner({
    mode: SCANNER_MODES.SHELF,
    videoElement: fakeVideo(),
    mediaDevices: { async getUserMedia() { return stream; } },
    ReaderClass: Reader,
    pageHideTarget: null,
    onResult(value) { result = value; },
  });
  await scanner.start();
  assert.deepEqual(
    {
      raw_value: result.raw_value,
      format: result.format,
      scanner_mode: result.scanner_mode,
      hasNormalizedGtin: Object.hasOwn(result, "normalized_gtin"),
    },
    {
      raw_value: "00-HEMKOP-SELFSCAN-4711",
      format: "CODE_128",
      scanner_mode: SCANNER_MODES.SHELF,
      hasNormalizedGtin: false,
    },
  );
  assert.equal(track.stopped, true);
});

test("an invalid decoded checksum keeps scanning and only emits a diagnostic", async () => {
  const { stream } = fakeCamera();
  const diagnostics = [];
  let errors = 0;
  class Reader {
    async decodeFromStream(_stream, _video, callback) {
      callback({
        getText: () => "4006381333932",
        getBarcodeFormat: () => 7,
      });
      return { stop() {} };
    }
  }
  const scanner = new ZXingBarcodeScanner({
    videoElement: fakeVideo(),
    mediaDevices: { async getUserMedia() { return stream; } },
    ReaderClass: Reader,
    pageHideTarget: null,
    onError() { errors += 1; },
    onDiagnostic(entry) { diagnostics.push(entry); },
  });
  await scanner.start();
  assert.equal(scanner.running, true);
  assert.equal(errors, 0);
  assert.ok(diagnostics.some((entry) => entry.reason === "invalid_checksum"));
  scanner.stop();
});

test("ZXing no-result exceptions remain recoverable after production minification", async () => {
  for (const expectedProblem of [
    new NotFoundException(),
    new ChecksumException(),
    new FormatException(),
  ]) {
    const { track, stream } = fakeCamera();
    let errors = 0;
    class Reader {
      async decodeFromStream(_stream, _video, callback) {
        callback(null, expectedProblem);
        return { stop() {} };
      }
    }
    const scanner = new ZXingBarcodeScanner({
      videoElement: fakeVideo(),
      mediaDevices: { async getUserMedia() { return stream; } },
      ReaderClass: Reader,
      pageHideTarget: null,
      onError() { errors += 1; },
    });
    await scanner.start();
    assert.equal(scanner.running, true);
    assert.equal(errors, 0);
    assert.equal(track.stopped, false);
    scanner.stop();
    assert.equal(track.stopped, true);
  }
});

test("an unexpected ZXing decoder failure stops media and reaches the fallback callback", async () => {
  const { track, stream } = fakeCamera();
  const errors = [];
  class Reader {
    async decodeFromStream(_stream, _video, callback) {
      const problem = new Error("decoder stopped");
      problem.name = "UnexpectedDecoderError";
      callback(null, problem);
      return { stop() {} };
    }

    reset() {}
  }
  const scanner = new ZXingBarcodeScanner({
    videoElement: fakeVideo(),
    mediaDevices: { async getUserMedia() { return stream; } },
    ReaderClass: Reader,
    pageHideTarget: null,
    onError(problem, detail) { errors.push({ problem, detail }); },
  });
  await scanner.start();
  assert.equal(scanner.running, false);
  assert.equal(track.stopped, true);
  assert.equal(errors.length, 1);
  assert.equal(errors[0].detail.provider, SCANNER_PROVIDERS.ZXING);
});

test("a silent native detector automatically falls back to ZXing", async () => {
  const { track, stream } = fakeCamera();
  class Detector {
    static async getSupportedFormats() {
      return ["ean_13", "ean_8", "upc_a", "upc_e"];
    }

    async detect() {
      return [];
    }
  }
  const scanner = new FallbackBarcodeScanner({
    userAgent: "Mozilla/5.0 (Linux; Android 15)",
    videoElement: fakeVideo(),
    mediaDevices: { async getUserMedia() { return stream; } },
    BarcodeDetectorClass: Detector,
    requestFrame() {},
    pageHideTarget: null,
    nativeFallbackAfterMs: 5,
    ZXingScannerClass: SuccessfulScanner,
  });
  await scanner.start();
  assert.equal(scanner.provider, SCANNER_PROVIDERS.NATIVE);
  await new Promise((resolve) => setTimeout(resolve, 15));
  assert.equal(scanner.provider, SCANNER_PROVIDERS.ZXING);
  assert.equal(track.stopped, true);
  scanner.stop();
});

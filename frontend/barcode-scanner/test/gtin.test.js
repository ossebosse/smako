import assert from "node:assert/strict";
import test from "node:test";

import {
  GtinValidationError,
  expandUpceToUpca,
  hasValidGtinChecksum,
  normalizeGtin,
} from "../src/gtin.js";

test("normalizes a checksum-valid EAN-13", () => {
  assert.deepEqual(normalizeGtin("4006 3813-33931"), {
    raw_value: "4006 3813-33931",
    normalized_gtin: "4006381333931",
    format: "EAN_13",
  });
});

test("rejects an EAN-13 with an invalid checksum", () => {
  assert.throws(
    () => normalizeGtin("4006381333932"),
    (error) => error instanceof GtinValidationError && error.code === "invalid_checksum",
  );
});

test("normalizes a checksum-valid EAN-8 without changing its identity", () => {
  assert.deepEqual(normalizeGtin("96385074"), {
    raw_value: "96385074",
    normalized_gtin: "96385074",
    format: "EAN_8",
  });
});

test("handles a checksum-valid UPC-A", () => {
  assert.deepEqual(normalizeGtin("036000291452", "upc_a"), {
    raw_value: "036000291452",
    normalized_gtin: "036000291452",
    format: "UPC_A",
  });
});

test("losslessly expands a UPC-E to UPC-A", () => {
  assert.equal(expandUpceToUpca("04210007"), "042000001007");
  assert.deepEqual(normalizeGtin("04210007", "UPC_E"), {
    raw_value: "04210007",
    normalized_gtin: "042000001007",
    format: "UPC_E",
  });
  assert.equal(hasValidGtinChecksum("042000001007"), true);
});

test("does not guess an unsupported identifier length", () => {
  assert.throws(
    () => normalizeGtin("1234567890"),
    (error) => error instanceof GtinValidationError && error.code === "unsupported_length",
  );
});

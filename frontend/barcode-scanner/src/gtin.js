const GTIN_FORMATS = Object.freeze({
  EAN_13: "EAN_13",
  EAN_8: "EAN_8",
  UPC_A: "UPC_A",
  UPC_E: "UPC_E",
});

const FORMAT_ALIASES = new Map([
  ["ean_13", GTIN_FORMATS.EAN_13],
  ["ean13", GTIN_FORMATS.EAN_13],
  ["ean-13", GTIN_FORMATS.EAN_13],
  ["ean_8", GTIN_FORMATS.EAN_8],
  ["ean8", GTIN_FORMATS.EAN_8],
  ["ean-8", GTIN_FORMATS.EAN_8],
  ["upc_a", GTIN_FORMATS.UPC_A],
  ["upca", GTIN_FORMATS.UPC_A],
  ["upc-a", GTIN_FORMATS.UPC_A],
  ["upc_e", GTIN_FORMATS.UPC_E],
  ["upce", GTIN_FORMATS.UPC_E],
  ["upc-e", GTIN_FORMATS.UPC_E],
]);

export class GtinValidationError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "GtinValidationError";
    this.code = code;
  }
}

export function normalizeFormat(formatHint) {
  if (!formatHint) return null;
  return FORMAT_ALIASES.get(String(formatHint).trim().toLowerCase()) || null;
}

export function hasValidGtinChecksum(digits) {
  if (typeof digits !== "string" || !/^\d+$/.test(digits) || digits.length < 2) {
    return false;
  }
  const body = digits.slice(0, -1);
  const expected = Number(digits.at(-1));
  let sum = 0;
  let weight = 3;
  for (let index = body.length - 1; index >= 0; index -= 1) {
    sum += Number(body[index]) * weight;
    weight = weight === 3 ? 1 : 3;
  }
  return (10 - (sum % 10)) % 10 === expected;
}

/**
 * Expand a checksum-bearing UPC-E value to its unambiguous UPC-A form.
 * Number systems other than 0 and 1 are not defined for ordinary UPC-E.
 */
export function expandUpceToUpca(upce) {
  if (!/^\d{8}$/.test(upce)) {
    throw new GtinValidationError("invalid_upc_e", "UPC-E måste bestå av åtta siffror.");
  }
  const [numberSystem, d1, d2, d3, d4, d5, d6, checkDigit] = upce;
  if (numberSystem !== "0" && numberSystem !== "1") {
    throw new GtinValidationError("invalid_upc_e", "UPC-E har ett ogiltigt nummersystem.");
  }

  let body;
  if (["0", "1", "2"].includes(d6)) {
    body = `${numberSystem}${d1}${d2}${d6}0000${d3}${d4}${d5}`;
  } else if (d6 === "3") {
    body = `${numberSystem}${d1}${d2}${d3}00000${d4}${d5}`;
  } else if (d6 === "4") {
    body = `${numberSystem}${d1}${d2}${d3}${d4}00000${d5}`;
  } else {
    body = `${numberSystem}${d1}${d2}${d3}${d4}${d5}0000${d6}`;
  }
  const upca = `${body}${checkDigit}`;
  if (!hasValidGtinChecksum(upca)) {
    throw new GtinValidationError("invalid_checksum", "Streckkodens kontrollsiffra är ogiltig.");
  }
  return upca;
}

/**
 * Normalize a scanned retail barcode without inventing a product identity.
 * UPC-E is the sole expanding conversion because that mapping is lossless.
 */
export function normalizeGtin(raw, formatHint = null) {
  const rawValue = raw === null || raw === undefined ? "" : String(raw).trim();
  if (!rawValue) {
    throw new GtinValidationError("empty", "Ingen streckkod kunde läsas.");
  }
  const digits = rawValue.replace(/[\s-]/g, "");
  if (!/^\d+$/.test(digits)) {
    throw new GtinValidationError("non_numeric", "Streckkoden innehåller andra tecken än siffror.");
  }

  const hintedFormat = normalizeFormat(formatHint);
  let format = hintedFormat;
  if (!format) {
    if (digits.length === 13) format = GTIN_FORMATS.EAN_13;
    else if (digits.length === 12) format = GTIN_FORMATS.UPC_A;
    else if (digits.length === 8) format = GTIN_FORMATS.EAN_8;
    else {
      throw new GtinValidationError(
        "unsupported_length",
        "Streckkoden måste vara EAN-13, EAN-8, UPC-A eller UPC-E.",
      );
    }
  }

  const expectedLength = {
    [GTIN_FORMATS.EAN_13]: 13,
    [GTIN_FORMATS.EAN_8]: 8,
    [GTIN_FORMATS.UPC_A]: 12,
    [GTIN_FORMATS.UPC_E]: 8,
  }[format];
  if (!expectedLength || digits.length !== expectedLength) {
    throw new GtinValidationError(
      "unsupported_length",
      `Streckkodens längd stämmer inte med formatet ${format || "okänt"}.`,
    );
  }
  if (format !== GTIN_FORMATS.UPC_E && !hasValidGtinChecksum(digits)) {
    throw new GtinValidationError("invalid_checksum", "Streckkodens kontrollsiffra är ogiltig.");
  }

  const normalizedGtin = format === GTIN_FORMATS.UPC_E
    ? expandUpceToUpca(digits)
    : digits;

  return Object.freeze({
    raw_value: rawValue,
    normalized_gtin: normalizedGtin,
    format,
  });
}

export { GTIN_FORMATS };

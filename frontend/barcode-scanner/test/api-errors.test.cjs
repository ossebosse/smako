"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const {
  formatApiErrorDetail,
  formatApiErrorResponse,
} = require("../../../grocery_data/app/static/physical-check-api-errors.js");

test("formats an ordinary string detail", () => {
  assert.equal(
    formatApiErrorResponse({ detail: "Ogiltigt hyllpris." }, 422),
    "Ogiltigt hyllpris.",
  );
});

test("turns an expired field session into an actionable re-login message", () => {
  const message = formatApiErrorResponse(
    { detail: "field authentication required" },
    401,
  );

  assert.equal(
    message,
    "Fältsessionen har gått ut. Öppna /physical-check/login i en ny flik, logga in igen och återvänd sedan hit.",
  );
  assert.doesNotMatch(message, /GTIN_MISMATCH|field authentication required/);
});

test("formats FastAPI validation arrays without object stringification", () => {
  const message = formatApiErrorResponse(
    {
      detail: [
        {
          type: "extra_forbidden",
          loc: ["body", "weight_price_type"],
          msg: "Extra inputs are not permitted",
          input: "sale",
        },
        {
          type: "value_error",
          loc: ["body"],
          msg: "Value error, weight price fields require weight semantics",
        },
      ],
    },
    422,
  );

  assert.match(message, /Typ av viktpris: Extra inputs are not permitted/);
  assert.match(message, /Viktprisfält kan bara användas för en viktvara/);
  assert.doesNotMatch(message, /\[object Object\]/);
});

test("deduplicates repeated API errors", () => {
  assert.equal(
    formatApiErrorDetail([
      { loc: ["body", "shelf_price"], msg: "Field required" },
      { loc: ["body", "shelf_price"], msg: "Field required" },
    ]),
    "Hyllpris: Field required",
  );
});

test("uses a safe fallback for an unknown object shape", () => {
  assert.equal(
    formatApiErrorResponse({ unexpected: { secret: "must-not-render" } }, 422),
    "Begäran misslyckades (HTTP 422).",
  );
});

test("redacts server internals behind an actionable Swedish 5xx message", () => {
  const message = formatApiErrorResponse(
    {
      detail: "OperationalError: no such column at C:\\private\\database.sqlite",
      token: "must-not-render",
    },
    500,
  );

  assert.equal(
    message,
    "Serverfel i fältservern. Försök igen efter att servern har åtgärdats eller startats om.",
  );
  assert.doesNotMatch(message, /OperationalError|database|token|private/i);
});

test("keeps detailed validation messages for 4xx responses", () => {
  assert.equal(
    formatApiErrorResponse(
      { detail: [{ loc: ["body", "shelf_price"], msg: "Field required" }] },
      422,
    ),
    "Hyllpris: Field required",
  );
});

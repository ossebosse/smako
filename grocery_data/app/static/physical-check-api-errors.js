"use strict";

(function attachPhysicalCheckApiErrors(root) {
  const fieldLabels = Object.freeze({
    comparison_price: "Jämförpris",
    comparison_unit: "Jämförprisenhet",
    gtin: "GTIN",
    identification_evidence: "Identifieringsbevis",
    identity_status: "Identifieringsstatus",
    multibuy_quantity: "Antal i flerköp",
    multibuy_total_price: "Flerköpspris",
    member_only: "Medlemsvillkor",
    price_basis: "Prisbas",
    promotion_mechanism: "Kampanjmekanism",
    price_semantics: "Pristyp",
    product_name: "Produkt",
    regular_shelf_price: "Ordinarie viktpris",
    shelf_price: "Hyllpris",
    weight_price_type: "Typ av viktpris",
  });

  const translatedMessages = Object.freeze({
    "identification evidence is inconsistent with identity status":
      "Identifieringsbeviset stämmer inte med vald identifieringsstatus.",
    "SEK/kg price semantics must match a verified weight product":
      "Pris i kr/kg kan bara sparas för en verifierad viktvara.",
    "weight price fields require weight semantics":
      "Viktprisfält kan bara användas för en viktvara.",
    "weight capture requires a shelf-price unit":
      "Viktpriset saknar enhet. Välj kr/kg.",
    "weight identity requires the exact selected weight product":
      "Viktvaran måste vara exakt samma vara som valdes i stickprovet.",
    "weight identity requires SEK/kg price semantics":
      "Viktvaran måste registreras i kr/kg.",
    "manual exact identity must match the immutable session target":
      "Den manuellt valda varan stämmer inte med stickprovets valda vara.",
    "GTIN match requires the exact verified target GTIN":
      "Den skannade GTIN-koden stämmer inte med varans verifierade GTIN.",
  });

  function cleanMessage(value) {
    if (typeof value !== "string") return "";
    const text = value.trim().replace(/^Value error,\s*/i, "");
    return translatedMessages[text] || text;
  }

  function locationLabel(location) {
    if (!Array.isArray(location)) return "";
    const meaningful = location.filter((part) => !["body", "query", "path"].includes(String(part)));
    if (!meaningful.length) return "";
    const last = String(meaningful.at(-1));
    return fieldLabels[last] || last.replaceAll("_", " ");
  }

  function collectMessages(detail, messages) {
    if (typeof detail === "string") {
      const message = cleanMessage(detail);
      if (message) messages.push(message);
      return;
    }
    if (Array.isArray(detail)) {
      detail.forEach((entry) => collectMessages(entry, messages));
      return;
    }
    if (!detail || typeof detail !== "object") return;

    if (typeof detail.msg === "string") {
      const message = cleanMessage(detail.msg);
      const location = locationLabel(detail.loc);
      if (message) messages.push(location ? `${location}: ${message}` : message);
      return;
    }
    for (const key of ["detail", "message", "error", "errors"]) {
      if (Object.hasOwn(detail, key)) collectMessages(detail[key], messages);
    }
  }

  function formatApiErrorDetail(detail) {
    const messages = [];
    collectMessages(detail, messages);
    return [...new Set(messages)].join(" ");
  }

  function formatApiErrorResponse(body, status) {
    const httpStatus = Number(status);
    if (httpStatus === 401) {
      return "Fältsessionen har gått ut. Öppna /physical-check/login i en ny flik, logga in igen och återvänd sedan hit.";
    }
    if (Number.isFinite(httpStatus) && httpStatus >= 500) {
      return "Serverfel i fältservern. Försök igen efter att servern har åtgärdats eller startats om.";
    }
    const message = formatApiErrorDetail(body && typeof body === "object" ? body : null);
    return message || `Begäran misslyckades (HTTP ${Number(status) || "okänd"}).`;
  }

  const api = Object.freeze({ formatApiErrorDetail, formatApiErrorResponse });
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.PhysicalCheckApiErrors = api;
})(typeof window === "undefined" ? globalThis : window);

"use strict";
// Recovery also works when app.js fails to load or parse. No storage is erased.
(() => {
  function recoverInitialization() {
    if (document.documentElement.dataset.frontendInitialized === "true") return;
    const button = document.querySelector("#submit-button");
    const form = document.querySelector("#plan-form");
    if (!button || !form) return;
    button.disabled = true;
    button.querySelector(".button-label").textContent = "Skapa veckomeny";
    form.setAttribute("aria-busy", "false");
    document.querySelector("#loading-state").hidden = true;
    document.querySelector("#service-availability-banner").hidden = false;
    document.querySelector("#service-availability-title").textContent = "Sidan kunde inte starta";
    document.querySelector("#service-availability-message").textContent = "Ladda om sidan för att försöka igen. Dina inställningar och sparade planer finns kvar.";
    const retry = document.querySelector("#service-retry-button");
    retry.textContent = "Ladda om sidan";
    retry.addEventListener("click", () => window.location.reload(), { once: true });
  }
  window.addEventListener("DOMContentLoaded", recoverInitialization, { once: true });
})();

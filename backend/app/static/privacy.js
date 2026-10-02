(() => {
  "use strict";

  const form = document.querySelector("#privacy-erasure-form");
  const confirmation = document.querySelector("#privacy-erasure-confirm");
  const submit = document.querySelector("#privacy-erasure-submit");
  const status = document.querySelector("#privacy-erasure-status");
  const anonymousSessionStorageKey = "grocery-anonymous-session-id";

  if (!form || !confirmation || !submit || !status) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!confirmation.checked) {
      status.textContent = "Bekräfta först att du förstår vad som raderas.";
      return;
    }
    if (!window.confirm("Radera dina betauppgifter och sparade planer?")) return;

    const anonymousSessionId = window.localStorage.getItem(anonymousSessionStorageKey);
    if (!anonymousSessionId) {
      status.textContent = "Ingen lokal anonym session hittades i den här webbläsaren.";
      return;
    }

    submit.disabled = true;
    status.textContent = "Raderar dina uppgifter…";
    try {
      const response = await fetch("/api/privacy/erase", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ anonymous_session_id: anonymousSessionId }),
      });
      if (!response.ok) {
        throw new Error("Raderingen kunde inte genomföras. Försök igen senare.");
      }
      window.localStorage.clear();
      for (const key of ["smako.planJob.public", "smako.planJob.personal", "smako.recipeChoices.public", "smako.recipeChoices.personal", "smako.personal.requestDraft"]) {
        window.sessionStorage.removeItem(key);
      }
      confirmation.checked = false;
      status.textContent = "Dina betauppgifter har raderats.";
    } catch (error) {
      status.textContent = error instanceof Error
        ? error.message
        : "Raderingen kunde inte genomföras. Försök igen senare.";
    } finally {
      submit.disabled = false;
    }
  });
})();

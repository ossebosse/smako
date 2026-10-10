/* Municipality selection uses existing prepared area keys. No location is saved. */
(() => {
  "use strict";
  const postal = document.getElementById("postal-code");
  if (!postal) return;
  const host = document.createElement("div"); host.className = "field field-wide";
  const label = document.createElement("label"); label.htmlFor = "municipality"; label.textContent = "Kommun";
  const select = document.createElement("select"); select.id = "municipality";
  const status = document.createElement("p"); status.className = "field-hint"; status.setAttribute("role", "status");
  host.append(label, select, status); postal.closest("label")?.before(host);
  if (!host.isConnected) postal.parentElement.before(host);
  let rows = [];
  function sync() {
    const row = rows.find(row => row.postal_code === postal.value.replace(/\s/g, ""));
    select.value = row?.municipality_code || "";
    status.textContent = row ? (row.available ? "Välj de butiker och priskanaler du vill jämföra nedan." : "Prisunderlaget för kommunen är ännu inte tillgängligt.") : "Välj en kommun med tillgängliga priser.";
  }
  select.addEventListener("change", () => {
    const row = rows.find(row => row.municipality_code === select.value);
    if (!row) return;
    postal.value = row.postal_code;
    postal.dispatchEvent(new Event("input", {bubbles:true}));
    postal.dispatchEvent(new Event("change", {bubbles:true}));
    sync();
  });
  window.addEventListener("smako-area-restored", sync);
  postal.addEventListener("change", sync);
  async function load() {
    select.disabled = true; status.textContent = "Hämtar tillgängliga kommuner…";
    try {
      const response = await fetch("/api/municipalities", {cache:"no-store", headers:{Accept:"application/json"}});
      if (!response.ok) throw new Error("Kommunerna kunde inte hämtas. Försök igen.");
      rows = (await response.json()).municipalities || [];
      select.replaceChildren(new Option("Välj kommun", ""));
      for (const row of rows) {
        const option = new Option(row.name + (row.available ? "" : " · priser förbereds/otillgängliga"), row.municipality_code);
        option.disabled = !row.available; select.append(option);
      }
      if (rows.length) {
        // Existing requests retain their exact area key; the selector replaces
        // a build postcode that was never the customer's precise location.
        postal.hidden = true;
        const outerLabel = postal.closest("label");
        if (outerLabel) outerLabel.hidden = true;
        else for (const node of postal.parentElement.children) if (node !== host) node.hidden = true;
      }
      select.disabled = false; sync();
    } catch (error) { status.textContent = error.message; }
  }
  const retry = document.createElement("button"); retry.type = "button"; retry.className = "secondary-button";
  retry.textContent = "Uppdatera kommuner"; retry.addEventListener("click", load); host.append(retry);
  void load();
})();

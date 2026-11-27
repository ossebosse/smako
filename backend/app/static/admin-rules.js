"use strict";
// Tab "Matplanering": the planning rules an admin can fine-tune (owner request 2026-11-22).
(() => {
  const $ = id => document.getElementById(id);
  const node = (tag, text, cls) => {const n = document.createElement(tag); if (text != null) n.textContent = text; if (cls) n.className = cls; return n;};
  const TABLES = [
    ["mixed_meat_min", "Allt: kötträtter", "Kött eller kyckling"],
    ["mixed_fish_min", "Allt: fiskrätter", "Fisk eller skaldjur"],
    ["mixed_vegetarian_min", "Allt: vegetariska rätter", ""],
    ["pescetarian_fish_min", "Fisk och vegetariskt: fiskrätter", "Fisk eller skaldjur"],
  ];
  const SHARES = [
    ["meat_kind_max_percent", "Samma köttslag högst", "% av kötträtterna", "Till exempel fläsk. Avrundas uppåt; 100 % stänger av regeln.", 1, 100],
    ["cuisine_max_percent", "Samma matkök högst", "% av middagarna", "Gäller också Billigast först, men inte när personen valt ett enda matkök. 100 % stänger av regeln.", 1, 100],
  ];
  const WEIGHTS = [
    ["extra_store_min_saving_kr", "En butik till måste spara minst", "kr", "Annars handlar planen i färre butiker.", 0, 200],
    ["like_weight_kr", "Gillar och ogillar väger", "kr per rätt", "En rätt med något personen gillar får kosta så här mycket mer, och en med något den ogillar så här mycket mindre.", 0, 200],
    ["like_missing_kr", "En gillad råvara som saknas kostar", "kr", "Gör att varje gillad råvara kommer med när det går. 0 stänger av regeln.", 0, 100000],
    ["scaled_step_kr", "Anpassad mängd kostar", "kr per steg", "När en måltid har näringsgränser kan Smako ta mer av huvudråvaran eller mindre tillbehör i recept med granskade intervall. Varje steg från receptets mängd kostar så här mycket, så den närmaste mängden vinner.", 0, 200],
  ];
  const VARIATION = [
    ["popularity_floor", "Lägsta popularitet", "av 5", "Rätter under detta betyg (1 = polariserande, 5 = folkfavorit) föreslås bara när för få andra passar. Standard för den som inte valt själv. 1 stänger av.", 1, 5],
    ["variation_percent", "Slumpvariation", "% av en middags kostnad", "Hur mycket dyrare en vecka får bli för att nya planer ska skilja sig åt. 0 stänger av.", 0, 50],
    ["member_avoid_recent_plans", "Undvik rätter från senaste", "planer", "Standard för inloggade som inte valt själva.", 0, 10],
  ];
  const POINTS = [
    ["receipt_points", "Ett godkänt kvitto ger", "poäng", "När minst så många varor som anges nedan går att läsa på kvittot.", 0, 1000],
    ["receipt_price_points", "Annat pris än Smakos ger", "poäng per vara", "För en vara som Smako har i butiken men till ett annat pris.", 0, 1000],
    ["receipt_missing_points", "Vara eller butik utan Smako-pris ger", "poäng per vara", "För en vara som Smako inte har i butiken, eller varje vara från en butik som Smako saknar priser för, till exempel en liten butik utan näthandel.", 0, 1000],
    ["receipt_min_list_items", "Minst varor på kvittot", "varor", "Färre lästa varor ger inga poäng. Varorna behöver inte finnas på handlingslistan.", 1, 50],
    ["receipt_max_points", "Högst poäng per kvitto", "poäng", "Taket för ett kvitto.", 0, 10000],
    ["receipt_max_per_week", "Högst kvitton per vecka", "kvitton", "Per medlem, de senaste sju dagarna.", 1, 50],
    ["receipt_item_temporary_days", "Ny vara visas i", "dagar", "En skannad vara som butikens lista saknade visas som tillfällig så länge efter att den senast köptes.", 1, 60],
    ["receipt_item_persist_days", "Fast vara kräver", "dagar emellan", "Två olika medlemmar ska ha köpt varan med minst så många dagar emellan.", 1, 120],
    ["receipt_item_persist_points", "Bekräftad fast vara ger", "poäng", "Till kvittot som gör varan fast.", 0, 1000],
    ["receipt_item_forget_days", "Glöm vara efter", "dagar", "En vara som ingen köpt på så länge tas bort.", 7, 730],
  ];
  let saved = null, defaults = null, loaded = false;

  function input(name, value, min, max, extra) {
    const n = document.createElement("input");
    Object.assign(n, {type: "number", inputMode: "numeric", step: "1", min: String(min), max: String(max), name, value: String(value), required: true});
    if (extra) n.dataset.index = String(extra);
    n.addEventListener("input", mark);
    return n;
  }
  function mark() {
    for (const n of $("rules-form").querySelectorAll("input")) {
      const before = n.dataset.index ? saved[n.name][n.dataset.index - 1] : saved[n.name];
      n.classList.toggle("changed", Number(n.value) !== before);
    }
  }
  function grid(target, items, rules) {
    $(target).replaceChildren(...items.map(([key, label, unit, help, min, max]) => {
      const box = node("label", label), row = node("span");
      row.append(input(key, rules[key], min, max), ` ${unit}`);
      box.append(row, node("small", `${help} Standard: ${defaults[key]}.`));
      return box;
    }));
  }
  function show(doc) {
    saved = doc.rules; defaults = doc.defaults;
    $("rules-tables").replaceChildren(...TABLES.map(([key, label, help]) => {
      const tr = node("tr"), th = node("th", label); th.scope = "row";
      if (help) th.append(node("small", help));
      tr.append(th);
      doc.rules[key].forEach((value, i) => {const td = node("td"); const n = input(key, value, 0, i + 1, i + 1); n.setAttribute("aria-label", `${label}, ${i + 1} middagar`); td.append(n); tr.append(td);});
      return tr;
    }));
    grid("rules-shares", SHARES, doc.rules);
    grid("rules-weights", WEIGHTS, doc.rules);
    grid("rules-variation", VARIATION, doc.rules);
    grid("rules-points", POINTS, doc.rules);
    $("rules-updated").textContent = doc.updated_at
      ? `Senast sparade ${new Intl.DateTimeFormat("sv-SE", {dateStyle: "short", timeStyle: "short", timeZone: "Europe/Stockholm"}).format(new Date(doc.updated_at))}`
      : "Standardreglerna gäller.";
    $("rules-form").hidden = false; $("rules-status").textContent = ""; mark();
  }
  function collect() {
    const rules = {};
    for (const [key] of TABLES) rules[key] = [];
    for (const n of $("rules-form").querySelectorAll("input")) {
      if (n.dataset.index) rules[n.name][n.dataset.index - 1] = Number(n.value);
      else rules[n.name] = Number(n.value);
    }
    return rules;
  }
  async function call(method, body) {
    $("rules-error").hidden = true;
    const options = {method, credentials: "same-origin", cache: "no-store", headers: {}};
    if (body) {options.headers["Content-Type"] = "application/json"; options.body = JSON.stringify(body);}
    const response = await fetch("/api/admin/planning-rules", options);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(response.status === 401 ? "Admininloggningen behöver förnyas. Ladda om sidan." : (payload.detail || "Reglerna kunde inte sparas."));
    return payload;
  }
  async function receipts() {
    try {
      const response = await fetch("/api/admin/receipts", {credentials: "same-origin", cache: "no-store"});
      const data = await response.json();
      const box = $("rules-receipts");
      if (!data.receipts?.length) {box.replaceChildren(node("p", "Inga kvitton än.", "sub")); return;}
      box.replaceChildren(...data.receipts.map(r => {
        const d = node("details", null, "store"), s = node("summary");
        s.append(node("strong", `${r.store_text}${r.store_known ? "" : " · saknas i Smako"}`), node("span", ` ${r.purchased_on || r.created_at.slice(0, 10)} · ${r.points} poäng · ${r.lines.length} rader`, "sub"));
        const list = node("ul");
        for (const l of r.lines) list.append(node("li", `${l.description}: ${l.price} kr${l.item ? ` → ${l.item}` : ""}${l.price_differs ? ` (Smako: ${l.planned_price} kr)` : ""}${l.missing_in_smako ? " · butik utan priser" : ""}${l.gtin ? ` · ${l.gtin}` : ""}`));
        d.append(s, list); return d;
      }));
    } catch (_) {$("rules-receipts").replaceChildren(node("p", "Kvittona kunde inte hämtas.", "sub"));}
  }
  const STATES = {temporary: "tillfällig", persistent: "fast", dormant: "dold, väntar på nytt kvitto", gone: "glömd"};
  async function storeItems() {
    const box = $("rules-store-items");
    try {
      const response = await fetch("/api/admin/store-items", {credentials: "same-origin", cache: "no-store"});
      const data = await response.json();
      if (!data.items?.length) {box.replaceChildren(node("p", "Inga varor från kvitton än.", "sub")); return;}
      const list = node("ul");
      for (const i of data.items) {
        const row = node("li", `${i.store}: ${i.name} · ${i.price} kr${i.kind === "price" ? ` (Smako ${i.smako_price} kr)` : " · ny vara"} · ${STATES[i.state] || i.state} · ${i.members} ${i.members === 1 ? "medlem" : "medlemmar"} · senast ${i.last_seen} · ${i.gtin} `);
        const remove = node("button", "Ta bort");
        remove.type = "button";
        remove.addEventListener("click", async () => {
          remove.disabled = true;
          const done = await fetch(`/api/admin/store-items/${encodeURIComponent(i.id)}`, {method: "DELETE", credentials: "same-origin"});
          if (done.ok) row.remove(); else {remove.disabled = false; remove.textContent = "Gick inte, försök igen";}
        });
        row.append(remove); list.append(row);
      }
      box.replaceChildren(list);
    } catch (_) {box.replaceChildren(node("p", "Varorna kunde inte hämtas.", "sub"));}
  }
  async function load() {
    void receipts();
    void storeItems();
    try {show(await call("GET")); loaded = true;}
    catch (error) {$("rules-status").textContent = ""; $("rules-error").textContent = error.message; $("rules-error").hidden = false;}
  }
  function busy(on) {for (const id of ["rules-save", "rules-undo", "rules-reset"]) $(id).disabled = on;}
  $("rules-form").addEventListener("submit", async event => {
    event.preventDefault(); busy(true);
    try {show(await call("PUT", {rules: collect()})); $("rules-status").textContent = "Reglerna är sparade och gäller nya matplaner.";}
    catch (error) {$("rules-error").textContent = error.message; $("rules-error").hidden = false;}
    finally {busy(false);}
  });
  $("rules-undo").addEventListener("click", load);
  $("rules-reset").addEventListener("click", async () => {
    if (!confirm("Återställa alla regler för matplaneringen till standard?")) return;
    busy(true);
    try {show(await call("PUT", {reset: true})); $("rules-status").textContent = "Standardreglerna är återställda.";}
    catch (error) {$("rules-error").textContent = error.message; $("rules-error").hidden = false;}
    finally {busy(false);}
  });

  function select(tab) {
    const rules = tab === "rules";
    $("tab-rules").setAttribute("aria-selected", String(rules)); $("tab-ops").setAttribute("aria-selected", String(!rules));
    $("page-rules").hidden = !rules; $("page-ops").hidden = rules;
    if (rules && !loaded) load();
  }
  $("tab-ops").addEventListener("click", () => {history.replaceState(null, "", "#drift"); select("ops");});
  $("tab-rules").addEventListener("click", () => {history.replaceState(null, "", "#matplanering"); select("rules");});
  select(location.hash === "#matplanering" ? "rules" : "ops");
})();

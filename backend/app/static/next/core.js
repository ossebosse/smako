/* Shared parts of the two trial interfaces (/ui/a and /ui/b): the calls to
   Smako's existing API, the saved choices, and the building blocks both
   layouts arrange in their own way (postcode, own items, meal choices,
   recipes, and the shopping list per store). No planning or pricing happens
   here; requests have the same shape as the ones /personal sends. */
(() => {
  "use strict";
  const el = (tag, text, cls, attrs) => {
    const n = document.createElement(tag);
    if (text != null) n.textContent = text;
    if (cls) n.className = cls;
    if (attrs) for (const [k, v] of Object.entries(attrs)) { if (v === true) n.setAttribute(k, ""); else if (v !== false && v != null) n.setAttribute(k, v); }
    return n;
  };
  const button = (text, onClick, cls = "btn", attrs) => { const b = el("button", text, cls, { type: "button", ...attrs }); b.addEventListener("click", onClick); return b; };
  const number = v => new Intl.NumberFormat("sv-SE", { maximumFractionDigits: 2 }).format(v);
  const money = v => `${new Intl.NumberFormat("sv-SE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v)} kr`;
  const amount = (q, u) => u === "g" && q >= 1000 ? `${number(q / 1000)} kg` : u === "ml" && q >= 1000 ? `${number(q / 1000)} l` : `${number(q)} ${u}`;
  const capital = s => s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
  const uuid = () => crypto.randomUUID ? crypto.randomUUID() : "10000000-1000-4000-8000-100000000000".replace(/[018]/g, c => (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16));

  const KEY = "smako.next.v1";
  const saved = (() => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (_) { return {}; } })();
  const persist = () => { try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch (_) { /* private mode: choices last for this visit */ } };
  const DEFAULTS = { dinners: 3, servings: 2, breakfasts: 0, snacks: 0, diet: "mixed", cooking: "free", avoid: [], allergies: [], likes: [], cuisines: [], variety: "low", maxStores: 2, organic: 0, usePantry: true, surplus: "minimize", radius: 3 };
  saved.settings = { ...DEFAULTS, ...(saved.settings || {}) };

  const S = { location: null, storeIds: saved.storeIds || [], state: null, items: [], plan: saved.plan || null, busy: null, error: "", notice: "" };
  const listeners = new Set();
  const emit = () => { for (const fn of [...listeners]) fn(S); };
  const on = fn => { listeners.add(fn); return () => listeners.delete(fn); };
  const fail = error => { S.error = error?.message || String(error); S.busy = null; emit(); };
  const clearError = () => { if (S.error || S.notice) { S.error = ""; S.notice = ""; } };

  // ---- API -----------------------------------------------------------------
  async function read(response) {
    const text = await response.text();
    try { return text ? JSON.parse(text) : {}; } catch (_) { return { detail: "Servern svarade oväntat. Försök igen." }; }
  }
  function message(data, status) {
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail) && data.detail[0]?.msg) return "Kontrollera det du har fyllt i och försök igen.";
    return status === 429 ? "Många räknar just nu. Försök igen om en stund." : "Det gick inte att nå Smako. Försök igen.";
  }
  async function api(url, body, method) {
    const response = await fetch(url, { method: method || (body === undefined ? "GET" : "POST"), cache: "no-store", credentials: "same-origin",
      headers: body === undefined ? { Accept: "application/json" } : { "Content-Type": "application/json", Accept: "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body) });
    const data = await read(response);
    if (!response.ok) { const error = new Error(message(data, response.status)); error.status = response.status; error.data = data; throw error; }
    return data;
  }
  const STAGES = { queued: "Väntar på en ledig plats.", product_facts: "Kontrollerar varor, priser och erbjudanden.", candidate_qualification: "Kontrollerar att varorna passar recepten.",
    week_search: "Sätter ihop måltiderna och jämför vad inköpen kostar.", final_audit: "Kontrollerar hela inköpslistan en sista gång.", saving: "Sparar.", library_preparation: "Förbereder recepten för dina val." };
  const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
  // Long calculations run as a job on the server; the page asks for the result every other second.
  async function job(url, body, title) {
    S.busy = { title, text: "Skickar till Smako.", started: Date.now() }; emit();
    let response = await fetch(url, { method: "POST", cache: "no-store", credentials: "same-origin",
      headers: { "Content-Type": "application/json", Accept: "application/json", Prefer: "respond-async" }, body: JSON.stringify(body) });
    let data = await read(response), failures = 0;
    while (response.status === 202) {
      const p = data.progress;
      S.busy.text = (STAGES[data.stage] || "Smako räknar.") + (p && p.total > 0 && p.unit === "recipes" ? ` ${p.completed} av ${p.total} recept prövade.` : "");
      emit();
      await delay(2000);
      try { response = await fetch(data.status_url, { cache: "no-store", credentials: "same-origin", headers: { Accept: "application/json" } }); data = { status_url: data.status_url, ...(await read(response)) }; failures = 0; }
      catch (error) { if (++failures > 8) throw new Error("Anslutningen bröts. Ladda om sidan för att se om beräkningen blev klar."); await delay(2000); }
    }
    S.busy = null;
    if (!response.ok) { const error = new Error(message(data, response.status)); error.status = response.status; error.data = data; throw error; }
    return data;
  }

  // ---- Place ---------------------------------------------------------------
  function chooseStores() {
    const contexts = S.location?.contexts || [];
    if (saved.storeMode === "specific" && saved.storeIds?.length) { const known = new Set(contexts.map(c => c.context_id)); S.storeIds = saved.storeIds.filter(id => known.has(id)); }
    else if (saved.storeMode === "municipality") S.storeIds = contexts.map(c => c.context_id);
    else S.storeIds = contexts.filter(c => c.distance_km != null && c.distance_km <= saved.settings.radius).map(c => c.context_id);
    if (!S.storeIds.length) S.storeIds = contexts.map(c => c.context_id);
    saved.storeIds = S.storeIds; persist();
  }
  async function lookup(postcode) {
    const postal = String(postcode || "").replace(/\s/g, "");
    if (!/^\d{5}$/.test(postal)) throw new Error("Ange ett postnummer med fem siffror.");
    const data = await api(`/api/shopping-location?postal_code=${encodeURIComponent(postal)}`);
    if (data.status !== "eligible" || !data.contexts?.length) throw new Error("Vi har inga butiker med priser nära det postnumret än. Just nu finns Smako i Lund och Malmö.");
    S.location = data; saved.postcode = postal; chooseStores(); clearError(); emit();
    return data;
  }
  const placeText = () => S.location ? `${S.location.municipality_name || S.location.area_name} · ${S.storeIds.length} butiker` : "Välj postnummer";

  // ---- Own items -----------------------------------------------------------
  const NONFOOD = /(servett|toalettpapper|hushållspapper|diskmedel|diskborste|bakplåtspapper|avfallspåsar|soppåsar|blöj|tvättmedel|sköljmedel|tandkräm|tandborste|schampo|tvål|folie|plastpåsar)/i;
  async function loadState() { S.state = await api("/api/personal/state"); S.items = structuredClone(S.state.shopping_items || []); emit(); return S.state; }
  async function saveItems() {
    try { S.state = await api("/api/personal/shopping-list", { revision: S.state.revision, items: S.items }, "PUT"); }
    catch (error) { if (error.status === 409) { const mine = S.items; await loadState(); S.items = mine; S.state = await api("/api/personal/shopping-list", { revision: S.state.revision, items: S.items }, "PUT"); } else throw error; }
    emit();
  }
  async function addGeneric(row) {
    clearError();
    S.items.push({ id: uuid(), kind: "generic", query: row.query.slice(0, 120), quantity: row.quantity, unit: row.unit, properties: row.properties || [], confirmed: true, use_pantry: false, food: row.food ?? !NONFOOD.test(row.query) });
    await saveItems();
  }
  async function addProduct(product, typed) {
    clearError();
    const keys = product.matches?.length > 1 ? product.matches.map(m => m.product_key) : [product.product_key];
    if (keys.length > 8) throw new Error("Varan finns i för många varianter. Skriv mer av namnet.");
    const link = await api("/api/personal/product-generic", { query: (typed || product.name || "vara").slice(0, 120), postal_code: saved.postcode || "22350", product_keys: keys });
    const packs = Boolean(product.purchase_units);
    S.items.push({ id: uuid(), kind: keys.length > 1 ? "one_of" : "exact", query: (product.display_name || product.name).slice(0, 120), quantity: packs ? 1 : product.package_quantity, unit: packs ? "st" : product.package_unit,
      ...(packs ? { purchase_units: true } : {}), product_key: keys.length > 1 ? null : keys[0],
      ...(keys.length > 1 ? { alternatives: keys, alternative_names: product.matches.map(m => (m.display_name || m.name).slice(0, 200)) } : {}),
      properties: [], confirmed: true, use_pantry: false, food: !NONFOOD.test(product.name), generic: link.generic });
    await saveItems();
  }
  // The same product under another identity in other chains. Offered, never added on its own.
  const sameCache = new Map();
  function sameElsewhere(row) {
    const keys = row.alternatives?.length ? row.alternatives : row.product_key ? [row.product_key] : [];
    if (!keys.length || keys.length >= 8) return Promise.resolve([]);
    const cacheKey = keys.join(",");
    if (!sameCache.has(cacheKey)) sameCache.set(cacheKey, api("/api/personal/same-product", { query: row.query.slice(0, 120), postal_code: saved.postcode || "22350", product_keys: keys, ...(row.generic ? { generic: row.generic } : {}) })
      .then(data => data.products.slice(0, 8 - keys.length)).catch(() => []));
    return sameCache.get(cacheKey);
  }
  async function includeSame(id, others) {
    const row = S.items.find(r => r.id === id); if (!row || !others.length) return;
    const keys = row.alternatives?.length ? row.alternatives : [row.product_key];
    const names = row.alternative_names?.length ? row.alternative_names : [row.query];
    const all = [...keys, ...others.map(o => o.product_key)];
    const link = await api("/api/personal/product-generic", { query: row.query.slice(0, 120), postal_code: saved.postcode || "22350", product_keys: all, ...(row.generic ? { generic: row.generic } : {}) });
    Object.assign(row, { kind: "one_of", product_key: null, alternatives: all, alternative_names: [...names, ...others.map(o => o.display_name)], properties: [], generic: link.generic });
    await saveItems();
  }
  async function removeItem(id) { S.items = S.items.filter(row => row.id !== id); await saveItems(); }
  const stepOf = row => row.purchase_units || row.unit === "st" ? 1 : row.quantity >= 2000 ? 1000 : row.quantity >= 1000 ? 500 : row.quantity > 250 ? 250 : 100;
  async function changeAmount(id, direction) {
    const row = S.items.find(r => r.id === id); if (!row) return;
    const next = Math.round((row.quantity + direction * stepOf(row)) * 1000) / 1000;
    if (next <= 0) return removeItem(id);
    row.quantity = next; await saveItems();
  }
  async function suggestions(text, signal) {
    const [interpreted, found] = await Promise.all([
      api("/api/personal/interpret-extra", { text }).catch(error => ({ error: error.message })),
      fetch(`/api/personal/shopping-suggestions?q=${encodeURIComponent(text)}&postal_code=${encodeURIComponent(saved.postcode || "22350")}`, { cache: "no-store", credentials: "same-origin", signal }).then(read),
    ]);
    const generics = found.generics || [], typedName = interpreted.error ? null : interpreted.query.toLowerCase();
    const options = [], seen = new Set();
    const push = row => { const key = `${row.query.toLowerCase()}|${row.quantity}|${row.unit}`; if (!seen.has(key)) { seen.add(key); options.push(row); } };
    if (typedName && interpreted.quantity != null) push({ query: interpreted.query, quantity: interpreted.quantity, unit: interpreted.unit, properties: interpreted.properties, food: interpreted.food });
    else if (typedName) {
      const same = generics.find(g => g.query.toLowerCase() === typedName || g.name.toLowerCase() === typedName);
      if (same) push(same);
      else if (found.usual) push({ query: interpreted.query, quantity: found.usual.quantity, unit: found.usual.unit, properties: interpreted.properties, food: interpreted.food });
    }
    generics.forEach(push);
    return { options, products: (found.products || []).filter(p => p.selectable), error: interpreted.error && !options.length ? interpreted.error : "", noArea: found.status === "no_area_data" };
  }

  // ---- Plans ---------------------------------------------------------------
  const guest = () => S.state?.account?.guest_limits || null;
  const limit = (key, fallback) => guest()?.[key] ?? fallback;
  function storeFields() {
    if (!S.location || !S.storeIds.length) throw new Error("Ange ditt postnummer först, så vet vi vilka butiker som gäller.");
    const all = saved.settings.maxStores === "all";
    return { postal_code: S.location.area_postal_code || saved.postcode, allowed_store_ids: S.storeIds.slice(),
      ...(all ? { max_stores: S.storeIds.length, store_cap: "all_selected" } : { max_stores: Math.min(Number(saved.settings.maxStores) || 2, S.storeIds.length) }) };
  }
  function baseRequest(meals) {
    const s = saved.settings;
    return { ...storeFields(), membership_price_policy: "all_advertised", purchase_planning_mode: "estimated", memberships: [], diversity_mode: "balanced", varied_budget_percent: 25, strategy: "optimized",
      recipes: meals.find(m => m.meal_type === "dinner")?.count || 0, servings: meals.find(m => m.meal_type === "dinner")?.servings || 1,
      personal: { profile: { likes: s.likes, dislikes: [], exclusions: s.avoid, allergies: s.allergies }, meals, extras: S.items, pantry_revision: S.state.revision, use_pantry: s.usePantry,
        allow_nutrition_estimates: true, organic_percent: Number(s.organic) || 0, organic_animals: false, surplus_mode: s.surplus } };
  }
  const COOKING = { quick: { max_active_minutes: 30, max_ingredients: 8 }, everyday: { max_active_minutes: 45, max_ingredients: 12 }, free: {} };
  // "Kött" applies to dinners; breakfasts and snacks keep every recipe to choose from.
  function mealRows() {
    const s = saved.settings, cap = limit("recipes", 21);
    const counts = { dinner: Math.min(s.dinners, cap), breakfast: s.breakfasts, snack: s.snacks };
    let left = cap;
    return ["dinner", "breakfast", "snack"].map(type => {
      const count = Math.max(0, Math.min(counts[type], left)); left -= count;
      const choices = count ? { min_ingredients: null, max_ingredients: null, max_active_minutes: null, max_total_minutes: null, max_waiting_minutes: null, ...(type === "dinner" ? COOKING[s.cooking] : {}) } : null;
      return { meal_type: type, count, servings: Math.min(s.servings, limit("servings", 8)), diet: s.diet === "meat" && type !== "dinner" ? "mixed" : s.diet, profile: {}, distribution: {}, limits: {}, organic_animals: false, recipe_choices: choices, max_same_base_meals: null };
    });
  }
  function keep(envelope) {
    // The saved copy leaves out the server's long calculation notes, so the page starts quickly next time.
    const plan = structuredClone(envelope);
    if (plan.plan?.personal?.checks) delete plan.plan.personal.checks.planning_diagnostics;
    for (const key of ["data", "source_diagnostics", "debug_info", "optimization_scenarios", "single_store_options", "cheap_ingredients", "ingredients", "plans"]) if (plan.plan && key in plan.plan) delete plan.plan[key];
    S.plan = plan; saved.plan = plan;
    try { persist(); } catch (_) { saved.plan = null; }
    S.items = structuredClone(plan.request.personal.extras || []);
  }
  async function refreshState() { try { const mine = S.items; S.state = await api("/api/personal/state"); S.items = mine; } catch (_) { /* the next save reads it again */ } }
  async function run(title, work) {
    clearError();
    try { await work(); await refreshState(); S.busy = null; emit(); return true; }
    catch (error) { fail(error); return false; }
  }
  const calculateList = () => run("Letar upp de billigaste butikerna", async () => {
    if (!S.items.length) throw new Error("Lägg till minst en vara först.");
    await saveItems();
    keep(await job("/api/plans", baseRequest([]), "Letar upp de billigaste butikerna"));
  });
  const createPlan = () => run("Skapar din matplan", async () => {
    const meals = mealRows(), s = saved.settings;
    if (!meals.some(m => m.count)) throw new Error("Välj minst en måltid, eller räkna bara ut din inköpslista.");
    await saveItems();
    const dinners = meals[0].count, varied = s.variety === "normal" && dinners >= 3;
    keep(await job("/api/plans", { ...baseRequest(meals),
      recipe_preferences: { mode: "complete", cuisines: s.cuisines, cuisine_distribution: varied ? "minimum" : "free", min_distinct_cuisines: varied ? 3 : null, max_same_main_protein_dinners: varied ? 2 : null,
        min_ingredients: 10, max_ingredients: 15, max_minutes: null, adaptation: "approved", min_protein_g: null, allow_fish: true },
      max_same_primary_ingredient_meals: 2, max_same_recipe_family: 2, max_same_carbohydrate_meals: 3, max_same_cooking_method_meals: null, max_same_dish_form_meals: null,
      max_pairwise_culinary_similarity: null, max_pairwise_recipe_similarity: 0.7 }, "Skapar din matplan"));
  });
  const change = (title, action, fields) => run(title, async () => {
    if (!S.plan) throw new Error("Skapa en plan först.");
    const extra = ["extras", "recalculate"].includes(action) ? { purchase_planning_mode: "estimated", allow_nutrition_estimates: true } : {};
    const result = await job(`/api/personal/plans/${encodeURIComponent(S.plan.plan_id)}/change`, { revision: S.plan.revision, pantry_revision: S.state.revision, action, ...extra, ...fields }, title);
    keep(result.saved); if (result.state) S.state = result.state;
  });
  const replaceRecipe = slotId => change("Byter recept och räknar om inköpen", "replace", { slot_id: slotId });
  const removeRecipe = slotId => change("Tar bort receptet och räknar om inköpen", "remove", { slot_id: slotId });
  const updateListInPlan = () => change("Räknar om inköpslistan", "extras", { extras: S.items });
  const forgetPlan = () => { S.plan = null; saved.plan = null; persist(); emit(); };
  const planHasRecipes = () => Boolean(S.plan?.plan?.personal?.slots?.some(slot => slot.recipe));
  const itemsChanged = () => S.plan ? JSON.stringify((S.plan.request.personal.extras || []).map(r => [r.id, r.quantity])) !== JSON.stringify(S.items.map(r => [r.id, r.quantity])) : false;

  // ---- Building blocks -----------------------------------------------------
  function postcodeBox({ onDone, compact } = {}) {
    const box = el("form", null, "place-box"), field = el("label", "Ditt postnummer", "field");
    const input = el("input", null, null, { inputmode: "numeric", autocomplete: "postal-code", maxlength: "6", placeholder: "223 50", value: saved.postcode || "" });
    const go = el("button", compact ? "Ändra" : "Hitta butiker", "btn primary", { type: "submit" }), status = el("p", null, "hint", { role: "status" });
    field.append(input); box.append(field, go, status);
    const show = () => { status.textContent = S.location ? `${S.location.municipality_name || S.location.area_name}: ${S.storeIds.length} butiker ${saved.storeMode === "municipality" ? "i kommunen" : saved.storeMode === "specific" ? "som du har valt" : `inom ${saved.settings.radius} km`}.` : "Vi jämför priserna i butikerna nära dig."; };
    show();
    box.addEventListener("submit", async event => { event.preventDefault(); go.disabled = true; status.textContent = "Letar butiker.";
      try { await lookup(input.value); show(); onDone?.(); } catch (error) { status.textContent = error.message; } finally { go.disabled = false; } });
    return box;
  }
  function storePicker() {
    const box = el("div", null, "store-picker");
    if (!S.location) { box.append(el("p", "Ange postnummer först.", "hint")); return box; }
    const modes = [["radius", `Nära mig (${saved.settings.radius} km)`], ["municipality", "Hela kommunen"], ["specific", "Välj själv"]];
    const row = el("div", null, "chips", { role: "radiogroup", "aria-label": "Vilka butiker ska jämföras" });
    for (const [value, label] of modes) row.append(button(label, () => { saved.storeMode = value; if (value === "specific") saved.storeIds = S.storeIds; chooseStores(); emit(); }, "chip", { role: "radio", "aria-checked": String((saved.storeMode || "radius") === value) }));
    box.append(row);
    if ((saved.storeMode || "radius") === "radius") {
      const radius = el("div", null, "chips", { role: "radiogroup", "aria-label": "Avstånd" });
      for (const km of [1, 2, 3, 5]) radius.append(button(`${km} km`, () => { saved.settings.radius = km; chooseStores(); emit(); }, "chip small", { role: "radio", "aria-checked": String(saved.settings.radius === km) }));
      box.append(radius);
    }
    const list = el("div", null, "store-list");
    for (const context of S.location.contexts) {
      const label = el("label", null, "check"), check = el("input", null, null, { type: "checkbox" });
      check.checked = S.storeIds.includes(context.context_id);
      check.addEventListener("change", () => { const ids = new Set(S.storeIds); if (check.checked) ids.add(context.context_id); else ids.delete(context.context_id);
        if (!ids.size) { check.checked = true; return; } saved.storeMode = "specific"; saved.storeIds = [...ids]; chooseStores(); emit(); });
      label.append(check, el("span", [context.display_name, context.address, context.distance_km == null ? null : `${number(Math.round(context.distance_km * 10) / 10)} km`].filter(Boolean).join(" · ")));
      list.append(label);
    }
    box.append(list);
    return box;
  }

  function itemsEditor({ placeholder = "Skriv en vara, till exempel mjölk eller kaffe 500 g", quick = true } = {}) {
    const box = el("section", null, "items"), search = el("div", null, "item-search");
    const input = el("input", null, null, { type: "search", maxlength: "120", autocomplete: "off", placeholder, "aria-label": "Lägg till vara", enterkeyhint: "done" });
    const results = el("div", null, "item-results", { hidden: true }), status = el("p", null, "hint", { role: "status" }), list = el("ul", null, "item-list");
    search.append(input, results); box.append(search, status);
    let timer, controller, generation = 0, first = null;
    const close = () => { results.hidden = true; results.replaceChildren(); first = null; };
    const added = text => { input.value = ""; close(); status.textContent = `${text} är tillagd.`; input.focus(); };
    const guard = work => async () => { try { await work(); } catch (error) { status.textContent = error.message; } };
    async function searchNow() {
      const text = input.value.trim(), mine = ++generation; controller?.abort();
      if (text.length < 2) { close(); return; }
      controller = new AbortController();
      try {
        const found = await suggestions(text, controller.signal); if (mine !== generation) return;
        results.replaceChildren(); results.hidden = false; first = null;
        found.options.forEach((row, index) => { const b = button(null, guard(async () => { await addGeneric(row); added(`${capital(row.query)} · ${amount(row.quantity, row.unit)}`); }), `result${index ? "" : " best"}`);
          b.append(el("span", `${capital(row.name || row.query)} · ${amount(row.quantity, row.unit)}`, "result-name"), el("span", index ? "Lägg till" : "Lägg till · Smako väljer den billigaste", "result-note")); results.append(b); if (!index) first = b; });
        if (!found.options.length) results.append(el("p", found.error || (found.noArea ? "Vi har inga varor för ditt postnummer än." : "Skriv också hur mycket du vill ha, till exempel 500 g, 1 l eller 6 st."), "hint"));
        if (found.products.length) {
          const more = el("details", null, "exact"), summary = el("summary", `Välj en bestämd vara (${found.products.length})`); more.append(summary);
          for (const product of found.products.slice(0, 12)) { const b = button(null, guard(async () => { await addProduct(product, text); added(product.display_name || product.name); }), "result");
            b.append(el("span", product.display_name || product.name, "result-name"), el("span", product.package, "result-note")); more.append(b); }
          results.append(more);
        }
      } catch (error) { if (mine === generation && error.name !== "AbortError") { close(); status.textContent = error.message; } }
    }
    input.addEventListener("input", () => { clearTimeout(timer); status.textContent = ""; timer = setTimeout(searchNow, 280); });
    input.addEventListener("keydown", event => { if (event.key === "Enter") { event.preventDefault(); if (first) first.click(); else { clearTimeout(timer); void searchNow(); } } if (event.key === "Escape") close(); });
    document.addEventListener("click", event => { if (!search.contains(event.target)) close(); });
    const common = el("div", null, "chips common");
    function render() {
      list.replaceChildren();
      for (const row of S.items) {
        const li = el("li", null, "item"), text = el("div", null, "item-text");
        text.append(el("span", capital(row.query), "item-name"), el("span", row.kind === "generic" ? "Smako väljer den billigaste" : row.kind === "one_of" ? "Samma vara, billigaste butiken" : row.kind === "campaign" ? "Vara på kampanj" : "Just den här varan", "item-kind"));
        const stepper = el("div", null, "stepper");
        stepper.append(button("−", guard(() => changeAmount(row.id, -1)), "step", { "aria-label": `Mindre ${row.query}` }), el("span", row.purchase_units ? `${number(row.quantity)} förp.` : amount(row.quantity, row.unit), "step-value"),
          button("+", guard(() => changeAmount(row.id, 1)), "step", { "aria-label": `Mer ${row.query}` }));
        li.append(text, stepper, button("×", guard(() => removeItem(row.id)), "remove", { "aria-label": `Ta bort ${row.query}` }));
        if (["exact", "one_of"].includes(row.kind)) {
          const offer = el("div", null, "item-offer"); li.append(offer);
          sameElsewhere(row).then(others => { if (!others.length || !li.isConnected) return;
            const chains = [...new Set(others.flatMap(o => o.chains))];
            offer.append(el("span", `Samma vara finns hos ${chains.join(" och ")} under ett annat namn.`), button("Ta med, välj billigaste", guard(() => includeSame(row.id, others)), "btn small")); });
        }
        list.append(li);
      }
      if (!S.items.length) list.append(el("li", "Listan är tom. Skriv en vara ovan.", "empty"));
      common.replaceChildren();
      if (quick) {
        const have = new Set(S.items.map(r => r.query.toLowerCase()));
        const usual = (S.state?.shopping_common || []).map(c => c.item).filter(i => i.kind === "generic");
        const starters = [["mjölk", 1000, "ml"], ["ägg", 12, "st"], ["bryggkaffe", 500, "g"], ["smör", 500, "g"], ["banan", 500, "g"], ["havregryn", 1000, "g"], ["toalettpapper", 6, "st"]].map(([query, quantity, unit]) => ({ query, quantity, unit, properties: [] }));
        const shown = [];
        for (const row of [...usual, ...starters]) { const key = row.query.toLowerCase(); if (have.has(key) || shown.some(s => s.query.toLowerCase() === key)) continue; shown.push(row); if (shown.length >= 6) break; }
        for (const row of shown) common.append(button(`+ ${capital(row.query)}`, guard(async () => { await addGeneric(row); status.textContent = `${capital(row.query)} · ${amount(row.quantity, row.unit)} är tillagd.`; }), "chip small"));
      }
    }
    box.append(common, list);
    const off = on(render); render();
    box.dispose = off;
    return box;
  }

  const DIETS = [["mixed", "Allt"], ["meat", "Kött", "Nöt, fläsk, kyckling med mera"], ["pescetarian", "Fisk och vegetariskt"], ["vegetarian", "Vegetariskt"], ["vegan", "Veganskt"]];
  const COOK = [["quick", "Snabbt", "Högst 30 min i köket"], ["everyday", "Vardag", "Högst 45 min"], ["free", "Spelar ingen roll", ""]];
  const ALLERGENS = ["jordnötter", "nötter", "mjölk", "ägg", "gluten", "fisk", "skaldjur", "soja", "sesam"];
  const CUISINES = [["italian", "Italienskt"], ["greek", "Grekiskt"], ["mexican", "Mexikanskt"], ["indian", "Indiskt"], ["thai", "Thailändskt"], ["swedish", "Svenskt"]];
  const set = (key, value) => { saved.settings[key] = value; persist(); emit(); };
  function choice(label, options, current, onPick, cls = "") {
    const group = el("fieldset", null, `choice ${cls}`); group.append(el("legend", label));
    const row = el("div", null, "chips", { role: "radiogroup" });
    for (const [value, text, note] of options) { const b = button(null, () => onPick(value), "chip", { role: "radio", "aria-checked": String(current === value) }); b.append(el("span", text)); if (note) b.append(el("small", note)); row.append(b); }
    group.append(row); return group;
  }
  function counter(label, key, min, max, unit) {
    const group = el("fieldset", null, "choice counter"); group.append(el("legend", label));
    const row = el("div", null, "stepper big"), value = Math.min(saved.settings[key], max);
    row.append(button("−", () => set(key, Math.max(min, value - 1)), "step", { "aria-label": `Färre ${unit}`, disabled: value <= min }), el("span", `${value}`, "step-value"), button("+", () => set(key, Math.min(max, value + 1)), "step", { "aria-label": `Fler ${unit}`, disabled: value >= max }));
    group.append(row); return group;
  }
  function tags(label, key, placeholder, suggestions = []) {
    const group = el("fieldset", null, "choice"); group.append(el("legend", label));
    const row = el("div", null, "chips");
    for (const word of saved.settings[key]) row.append(button(`${word} ×`, () => set(key, saved.settings[key].filter(w => w !== word)), "chip on", { "aria-label": `Ta bort ${word}` }));
    for (const word of suggestions.filter(w => !saved.settings[key].includes(w))) row.append(button(`+ ${word}`, () => set(key, [...saved.settings[key], word]), "chip small"));
    const form = el("form", null, "tag-form"), input = el("input", null, null, { placeholder, maxlength: "40", "aria-label": label });
    form.append(input, el("button", "Lägg till", "btn small", { type: "submit" }));
    form.addEventListener("submit", event => { event.preventDefault(); const word = input.value.trim().toLowerCase(); if (word && !saved.settings[key].includes(word)) set(key, [...saved.settings[key], word]); });
    group.append(row, form); return group;
  }
  // Part "basic" is what most people need; "advanced" is everything else Smako can take into account.
  function settings(part) {
    const s = saved.settings, box = el("div", null, `settings ${part}`), g = guest();
    if (part === "basic") {
      box.append(counter("Middagar", "dinners", 0, limit("recipes", 7), "middagar"), counter("Portioner per rätt", "servings", 1, limit("servings", 8), "portioner"),
        choice("Vad äter ni?", DIETS, s.diet, v => set("diet", v)), choice("Tid i köket", COOK, s.cooking, v => set("cooking", v)));
      if (g) box.append(el("p", `Som gäst får du ${g.recipes} recept och ${g.servings} portioner per rätt. Med ett konto får du fler.`, "hint"));
      return box;
    }
    box.append(tags("Allergier", "allergies", "Annan allergi", ALLERGENS), tags("Ät inte", "avoid", "Till exempel koriander", ["fläsk", "svamp", "oliver"]), tags("Gillar extra", "likes", "Till exempel kyckling"),
      choice("Butiker att handla i", [[1, "1"], [2, "Högst 2"], [3, "Högst 3"], ["all", "Så många som lönar sig"]], s.maxStores, v => set("maxStores", v)),
      choice("Omväxling", [["low", "Billigast först"], ["normal", "Blanda matkök", "Minst 3 middagar"]], s.variety, v => set("variety", v)));
    const kitchens = el("fieldset", null, "choice"); kitchens.append(el("legend", "Matkök (inget valt betyder alla)"));
    const row = el("div", null, "chips");
    for (const [value, label] of CUISINES) row.append(button(label, () => set("cuisines", s.cuisines.includes(value) ? s.cuisines.filter(c => c !== value) : [...s.cuisines, value]), "chip", { "aria-pressed": String(s.cuisines.includes(value)) }));
    kitchens.append(row); box.append(kitchens,
      counter("Frukostar", "breakfasts", 0, Math.max(0, limit("recipes", 7) - s.dinners), "frukostar"), counter("Mellanmål", "snacks", 0, Math.max(0, limit("recipes", 7) - s.dinners - s.breakfasts), "mellanmål"),
      choice("Ekologiskt, minst andel av kostnaden", [[0, "Inget krav"], [25, "25 %"], [50, "50 %"]], Number(s.organic), v => set("organic", v)),
      choice("Det som blir över", [["minimize", "Så lite som möjligt"], ["allow_larger", "Större köp går bra"]], s.surplus, v => set("surplus", v)),
      choice("Skafferiet", [[true, "Använd det jag har hemma"], [false, "Räkna utan"]], s.usePantry, v => set("usePantry", v)));
    return box;
  }
  function settingsSummary() {
    const s = saved.settings, parts = [`${Math.min(s.dinners, limit("recipes", 7))} middagar`, `${Math.min(s.servings, limit("servings", 8))} portioner`, DIETS.find(d => d[0] === s.diet)[1].toLowerCase()];
    if (s.cooking !== "free") parts.push(COOK.find(c => c[0] === s.cooking)[1].toLowerCase());
    const avoid = [...s.allergies, ...s.avoid]; if (avoid.length) parts.push(`utan ${avoid.join(", ")}`);
    return parts.join(" · ");
  }

  const MEALS = { dinner: "Middag", breakfast: "Frukost", snack: "Mellanmål" };
  const FORMS = [[/\bas_sold\b/g, "som såld"], [/\braw_edible\b/g, "rå, rensad"], [/\bcooked_drained\b/g, "kokt och avrunnen"], [/\bdry\b/g, "torr"]];
  function recipeCard(slot, { actions = true } = {}) {
    const card = el("article", null, "recipe"), recipe = slot.recipe;
    card.append(el("p", `Dag ${slot.day} · ${MEALS[slot.meal_type] || "Måltid"}`, "eyebrow"), el("h3", recipe?.name || "Tom måltid"));
    if (!recipe) { if (actions) card.append(button("Föreslå ett recept", () => replaceRecipe(slot.id), "btn")); return card; }
    const minutes = recipe.design?.active_minutes ?? recipe.design?.time?.active_minutes;
    card.append(el("p", [`${recipe.servings} portioner`, `${recipe.ingredients.length} ingredienser`, minutes ? `${minutes} min` : null].filter(Boolean).join(" · "), "meta"));
    const more = el("details", null, "recipe-more"); more.append(el("summary", "Visa receptet"));
    const ingredients = el("ul", null, "ingredients"); for (const i of recipe.ingredients) ingredients.append(el("li", `${number(i.quantity)} ${i.unit} ${i.name}`));
    const steps = el("ol", null, "steps"); for (const step of recipe.instructions || []) steps.append(el("li", FORMS.reduce((text, [from, to]) => text.replace(from, to), step)));
    more.append(el("h4", "Ingredienser"), ingredients, el("h4", "Gör så här"), steps); card.append(more);
    if (actions) { const row = el("div", null, "recipe-actions"); row.append(button("Byt recept", () => replaceRecipe(slot.id), "btn"), button("Ta bort", () => removeRecipe(slot.id), "btn quiet")); card.append(row); }
    return card;
  }
  function recipesView(options) {
    const box = el("div", null, "recipes"), slots = [...(S.plan?.plan?.personal?.slots || [])].sort((a, b) => a.day - b.day || Object.keys(MEALS).indexOf(a.meal_type) - Object.keys(MEALS).indexOf(b.meal_type));
    for (const slot of slots) box.append(recipeCard(slot, options));
    if (!slots.length) box.append(el("p", "Planen har inga recept. Den innehåller bara dina egna varor.", "hint"));
    return box;
  }

  const AISLES = [["produce", "Frukt och grönt"], ["bread", "Bröd"], ["protein", "Kött, fågel och fisk"], ["dairy", "Mejeri och ägg"], ["pantry", "Skafferi"], ["frozen", "Fryst"], ["other", "Övrigt"]];
  function aisle(row) {
    const family = row.food_family, text = `${row.ingredient} ${row.product_name}`.toLowerCase();
    if (/fryst|frozen/.test(`${row.product_form || ""} ${text}`)) return "frozen";
    if (row.product_role === "bread" || /bröd|tortilla|pita|baguette|bagel|bulle|limpa/.test(text)) return "bread";
    if (["vegetable", "fruit", "allium", "fungus", "herb"].includes(family)) return "produce";
    if (["meat", "poultry", "fish", "seafood"].includes(family)) return "protein";
    if (["dairy", "egg"].includes(family)) return "dairy";
    if (["grain", "legume", "condiment", "broth", "fat", "spice", "nut", "seed", "sugar"].includes(family)) return "pantry";
    if (/kyckling|fläsk|nötkött|färs|\blax|torsk|fisk|räk|bacon|korv|skinka|kött/.test(text)) return "protein";
    if (/mjölk|grädde|yoghurt|\bost|smör|ägg|\bfil\b|crème|kvarg|keso/.test(text)) return "dairy";
    if (/banan|äpple|päron|apelsin|citron|lime|tomat|gurka|sallad|lök|potatis|morot|morötter|paprika|vitkål|broccoli|svamp|champinjon|avokado|zucchini|purjo|spenat|persilja|dill|basilika|koriander|ingefära|chili/.test(text) && !/kross|passera|pulver|juice|puré|torkad|buljong|ketchup|konserv/.test(text)) return "produce";
    if (/pasta|spaghetti|ris\b|mjöl|gryn|bönor|linser|ärtor|olja|vinäger|socker|salt|peppar|krydd|buljong|kaffe|\bte\b|tomat|soja|senap|ketchup|honung|nötter|müsli|flingor|läsk|juice|cola/.test(text)) return "pantry";
    return "other";
  }
  const pickedKey = () => `smako.next.picked.${S.plan?.plan_id}.${S.plan?.revision}`;
  const picked = () => { try { return new Set(JSON.parse(localStorage.getItem(pickedKey())) || []); } catch (_) { return new Set(); } };
  function basket() { const b = S.plan?.plan?.optimized_basket; return b ? { ...b, estimated: b.verification_status === "VERIFIED_WITH_ESTIMATES" } : null; }
  const totalText = () => { const b = basket(); return b ? `${b.estimated ? "ca " : ""}${money(b.total)}` : ""; };
  function storesView({ open = true } = {}) {
    const box = el("div", null, "stores"), b = basket(), done = picked();
    if (!b) return box;
    const names = new Map((S.location?.contexts || []).map(c => [c.context_id, c]));
    const count = b.stores.reduce((n, s) => n + s.items.length, 0), progress = el("p", null, "picked", { role: "status" });
    const update = () => { progress.textContent = `${done.size} av ${count} varor plockade`; try { localStorage.setItem(pickedKey(), JSON.stringify([...done])); } catch (_) { /* kept for this visit */ } };
    box.append(progress);
    for (const store of b.stores) {
      const section = el("details", null, "store"), context = names.get(store.store_id), head = el("summary");
      section.open = open;
      const title = el("span", null, "store-title"); title.append(el("span", store.store_name, "store-name"), el("span", [context?.address, `${store.items.length} varor`].filter(Boolean).join(" · "), "store-note"));
      head.append(title, el("span", money(store.subtotal), "store-sum")); section.append(head);
      const groups = new Map(AISLES.map(([key]) => [key, []]));
      for (const row of store.items) groups.get(aisle(row)).push(row);
      for (const [key, label] of AISLES) {
        const rows = groups.get(key).sort((x, y) => x.product_name.localeCompare(y.product_name, "sv")); if (!rows.length) continue;
        section.append(el("p", label, "aisle"));
        for (const row of rows) {
          const id = `${store.store_id}|${row.product_id}`, line = el("label", null, "line"), check = el("input", null, null, { type: "checkbox" });
          check.checked = done.has(id); line.classList.toggle("is-picked", check.checked);
          check.addEventListener("change", () => { if (check.checked) done.add(id); else done.delete(id); line.classList.toggle("is-picked", check.checked); update(); });
          const text = el("span", null, "line-text"), wanted = String(row.ingredient || "").replace(/ \[\d+\]$/, "");
          const weighed = row.variable_weight || ["sold_by_weight", "variable_weight_package"].includes(row.sale_model);
          text.append(el("span", row.product_name, "line-name"), el("span", [weighed ? `ca ${amount(row.purchased_quantity ?? row.packages_needed * row.package_quantity, row.purchased_unit || row.package_unit)}` : `${row.packages_needed} st × ${amount(row.package_quantity, row.package_unit)}`,
            wanted && wanted.toLowerCase() !== row.product_name.toLowerCase() ? `till ${wanted}` : null, row.offer_description || (row.membership_required ? "medlemspris" : null)].filter(Boolean).join(" · "), "line-note"));
          line.append(check, text, el("span", money(row.total_price), "line-price")); section.append(line);
        }
      }
      box.append(section);
    }
    if (b.estimated) box.append(el("p", "Varor som säljs per vikt har ett uppskattat pris. Det du betalar beror på vad de väger.", "hint"));
    box.append(el("p", "Priserna är de vi senast hämtade från butikerna. Hyllpriset kan ha ändrats.", "hint"));
    update();
    return box;
  }
  function busyView() {
    const box = el("div", null, "busy", { role: "status", "aria-live": "polite" });
    if (!S.busy) { box.hidden = true; return box; }
    const seconds = Math.round((Date.now() - S.busy.started) / 1000);
    box.append(el("div", null, "spinner"), el("h2", S.busy.title), el("p", S.busy.text), el("p", seconds > 8 ? `${seconds} sekunder. Det brukar ta upp till en minut.` : "Det brukar ta upp till en minut.", "hint"));
    return box;
  }
  function errorView() { const box = el("div", null, "error", { role: "alert" }); if (!S.error) { box.hidden = true; return box; } box.append(el("p", S.error), button("Stäng", () => { S.error = ""; emit(); }, "btn small")); return box; }

  async function start() {
    try { await loadState(); } catch (error) { fail(error); }
    if (S.plan?.request?.personal?.extras && !S.items.length && !S.state?.shopping_initialized) S.items = structuredClone(S.plan.request.personal.extras);
    if (saved.postcode) { try { await lookup(saved.postcode); } catch (_) { /* asked for again where it is needed */ } }
    emit();
  }
  setInterval(() => { if (S.busy) emit(); }, 1000);

  window.SmakoNext = { el, button, money, number, amount, S, saved, persist, on, emit, start, lookup, placeText, postcodeBox, storePicker, itemsEditor, settings, settingsSummary, recipesView, storesView, busyView, errorView,
    calculateList, createPlan, updateListInPlan, forgetPlan, planHasRecipes, itemsChanged, basket, totalText, guest, set,
    // Used by mine.js (account, pantry, registering what was bought).
    api, change, keep, loadState, refreshState, suggestions, uuid, capital, stepOf, isNonfood: text => NONFOOD.test(text) };
})();

/* Account, pantry and "I have shopped" for the two trial interfaces. Loaded
   after core.js and adds its views to window.SmakoNext. Everything goes
   through the API that /personal uses: /api/account/*, /api/personal/pantry
   and the plan actions "purchase" and "consume". */
(() => {
  "use strict";
  const N = window.SmakoNext, { el, button, S, api, amount, number, capital, emit } = N;

  // ---- Account -------------------------------------------------------------
  const account = () => S.state?.account || null;
  const signedIn = () => account()?.status === "SIGNED_IN";
  const accountLabel = () => (signedIn() ? "Konto" : "Logga in");
  // What the account screen is showing. Kept here so it survives a redraw of the page.
  const auth = { mode: "login", code: null, offer: null, note: "" };

  // After sign-in the browser is another owner on the server: the plan made as
  // a guest cannot be changed from the account unless it is moved there.
  async function entered() {
    const plan = S.plan;
    N.forgetPlan();
    await N.loadState();
    let preview = null;
    try { preview = await api("/api/account/guest-migration-preview"); } catch (_) { /* nothing to offer */ }
    if (preview?.can_move) auth.offer = { preview, plan };
    else auth.note = preview?.guest_items ? "Kontot har redan ett sparat skafferi. Det du gjorde som gäst finns kvar när du loggar ut." : "";
  }
  async function moveGuest() {
    const { preview, plan } = auth.offer;
    await api("/api/account/migrate-guest", { guest_revision: preview.guest_revision, account_revision: preview.account_revision, confirm_move_to_verified_account: true });
    auth.offer = null; auth.note = "Det du gjorde som gäst finns nu på ditt konto.";
    if (plan) N.keep(plan);
    await N.loadState();
  }
  async function signOut() {
    await api("/api/account/logout", {});
    auth.mode = "login"; auth.note = ""; auth.offer = null;
    N.forgetPlan();
    await N.loadState();
  }

  function accountView({ onPantry } = {}) {
    const box = el("section", null, "account");
    const act = (status, work) => async () => { status.textContent = "Arbetar."; try { await work(); draw(); emit(); } catch (error) { status.textContent = error.message; } };
    function draw() {
      box.replaceChildren();
      const status = el("p", null, "hint", { role: "status" });
      if (auth.code) {
        const code = el("input", null, null, { readonly: true, autocomplete: "off", "aria-label": "Din återställningskod", value: auth.code.value });
        box.append(el("h2", auth.code.reset ? "Lösenordet är bytt" : "Välkommen som medlem"),
          el("p", "Spara återställningskoden, till exempel i din lösenordshanterare. Den visas bara nu och behövs om du glömmer lösenordet."), code,
          button(auth.code.reset ? "Jag har sparat koden, logga in" : "Jag har sparat koden", () => { auth.code = null; draw(); }, "btn primary cta"));
        return;
      }
      if (auth.offer) {
        const n = auth.offer.preview.guest_items;
        box.append(el("h2", "Ta med det du gjorde som gäst?"),
          el("p", `Som gäst har du ${n === 1 ? "1 vara" : `${n} varor`} i skafferiet, en inköpslista och kanske en plan. Vill du flytta det till kontot?`),
          button("Ja, flytta till kontot", act(status, moveGuest), "btn primary cta"),
          button("Nej, börja med ett tomt konto", () => { auth.offer = null; draw(); }, "btn"), status);
        return;
      }
      if (!account()) { box.append(el("p", "Hämtar kontot.", "hint")); return; }
      if (signedIn()) {
        const pantry = (S.state.items || []).length;
        box.append(el("h2", "Du är inloggad"), el("p", "Skafferiet, inköpslistan och dina val sparas på kontot. Du får fler recept och portioner än som gäst."));
        if (auth.note) box.append(el("p", auth.note, "hint"));
        if (onPantry) box.append(button(pantry ? `Öppna skafferiet (${pantry} ${pantry === 1 ? "vara" : "varor"})` : "Öppna skafferiet", onPantry, "btn primary cta"));
        box.append(button("Logga ut", act(status, signOut), "btn"), status);
        return;
      }
      const register = auth.mode === "register", recover = auth.mode === "recover", limits = account().guest_limits;
      const form = el("form", null, "auth");
      const email = el("input", null, null, { type: "email", name: "email", required: true, maxlength: "254", autocomplete: "username" });
      const password = el("input", null, null, { type: "password", name: "password", required: true, minlength: "12", maxlength: "128", autocomplete: register || recover ? "new-password" : "current-password" });
      const emailField = el("label", "E-postadress", "field"), passwordField = el("label", recover ? "Nytt lösenord (minst 12 tecken)" : "Lösenord (minst 12 tecken)", "field");
      emailField.append(email); passwordField.append(password);
      form.append(el("h2", register ? "Skapa konto" : recover ? "Byt lösenord" : "Logga in"));
      if (!recover && limits) form.append(el("p", `Som gäst får du ${limits.recipes} recept och ${limits.servings} portioner per rätt. Med ett konto får du fler, och skafferiet sparas mellan dina enheter.`, "hint"));
      form.append(emailField, passwordField);
      let code = null;
      if (recover) { code = el("input", null, null, { name: "recovery", required: true, maxlength: "128", autocomplete: "off" }); const field = el("label", "Återställningskod", "field"); field.append(code); form.append(field); }
      if (register) form.append(el("p", "E-postadressen används bara för att logga in. Vi skickar ingen e-post. Du får en återställningskod att spara.", "hint"));
      const submit = el("button", register ? "Skapa konto" : recover ? "Byt lösenord" : "Logga in", "btn primary cta", { type: "submit" });
      form.append(submit, status);
      form.addEventListener("submit", async event => {
        event.preventDefault(); submit.disabled = true; status.textContent = "Arbetar.";
        try {
          const result = await api(`/api/account/${register ? "register" : recover ? "recover" : "login"}`, { email: email.value, password: password.value, ...(recover ? { recovery_code: code.value } : {}) });
          password.value = "";
          if (recover) { auth.mode = "login"; auth.code = { value: result.recovery_code, reset: true }; }
          else { if (result.recovery_code) auth.code = { value: result.recovery_code }; await entered(); }
          draw(); emit();
        } catch (error) { status.textContent = error.message; submit.disabled = false; }
      });
      const others = el("div", null, "links");
      const mode = (text, value) => button(text, () => { auth.mode = value; draw(); }, "text-link");
      if (!register) others.append(mode("Skapa ett konto", "register"));
      if (register || recover) others.append(mode("Jag har redan ett konto", "login"));
      if (!recover) others.append(mode("Glömt lösenordet?", "recover"));
      box.append(form, others);
      if (account().oidc_available) box.append(el("a", "Logga in via extern kontoleverantör", "text-link", { href: "/api/account/login" }));
    }
    draw();
    return box;
  }

  // ---- Pantry --------------------------------------------------------------
  // Goods in the pantry count as uncooked; the server decides which recipes they fit.
  const UNITS = { g: "gram", ml: "milliliter", st: "styck" };
  const clean = ({ available, reserved, ...rest }) => rest;
  const pantry = () => S.state?.items || [];
  async function savePantry(items) {
    try { S.state = await api("/api/personal/pantry", { revision: S.state.revision, items }, "PUT"); }
    catch (error) { if (error.status === 409) { await N.refreshState(); throw new Error("Skafferiet ändrades på ett annat ställe. Försök igen."); } throw error; }
    emit();
  }
  async function addToPantry(row) {
    const items = pantry().map(clean);
    const same = items.find(i => !row.product_key ? !i.product_key && !i.prepared_origin && i.unit === row.unit && (i.form || null) === (row.form || null) && i.name.toLowerCase() === row.name.toLowerCase() : i.product_key === row.product_key && i.unit === row.unit);
    if (same) same.quantity = Math.round((same.quantity + row.quantity) * 1000) / 1000;
    else items.push({ id: N.uuid(), unusable: false, product_key: null, ...row });
    await savePantry(items);
  }
  async function changePantryAmount(id, direction) {
    const items = pantry().map(clean), item = items.find(i => i.id === id); if (!item) return;
    const next = Math.round((item.quantity + direction * N.stepOf(item)) * 1000) / 1000;
    await savePantry(next <= 0 ? items.filter(i => i.id !== id) : (item.quantity = next, items));
  }
  const removeFromPantry = id => savePantry(pantry().map(clean).filter(i => i.id !== id));

  function pantryView() {
    const box = el("section", null, "items pantry"), search = el("div", null, "item-search");
    const input = el("input", null, null, { type: "search", maxlength: "120", autocomplete: "off", placeholder: "Skriv vad du har hemma, till exempel ris 1 kg", "aria-label": "Lägg till i skafferiet", enterkeyhint: "done" });
    const results = el("div", null, "item-results", { hidden: true }), status = el("p", null, "hint", { role: "status" }), confirm = el("div", null, "pantry-confirm", { hidden: true }), note = el("p", null, "hint"), list = el("ul", null, "item-list");
    search.append(input, results); box.append(search, status, confirm, note, list);
    let timer, controller, generation = 0, first = null;
    const close = () => { results.hidden = true; results.replaceChildren(); first = null; };
    const guard = work => async () => { try { status.textContent = ""; await work(); } catch (error) { status.textContent = error.message; } };
    const done = text => { input.value = ""; close(); confirm.hidden = true; confirm.replaceChildren(); status.textContent = `${text} ligger i skafferiet.`; };
    // A typed item is saved at once, unless recipes would not be able to use it as written.
    async function ask(row, products = []) {
      close();
      const use = await api(`/api/personal/pantry-use?name=${encodeURIComponent(row.query)}`).catch(() => ({ unit: null, used_in_recipes: false, usable: [0, 0], food: !N.isNonfood(row.query) }));
      const save = () => addToPantry({ name: row.query.slice(0, 120), quantity: row.quantity, unit: row.unit, food: use.food }).then(() => done(`${capital(row.query)} · ${amount(row.quantity, row.unit)}`));
      // Many recipes ask for a particular kind (which rice, which cut). Only a chosen product can show that.
      const [fits, uses] = use.usable || [0, 0], narrow = use.food && uses > 0 && fits < uses / 2, wrongUnit = use.food && use.unit && use.unit !== row.unit;
      if (!narrow && !wrongUnit) { await save(); return; }
      const draw = () => {
        confirm.replaceChildren(el("h3", `${capital(row.query)} · ${amount(row.quantity, row.unit)}`));
        {
          if (use.unit && use.unit !== row.unit) confirm.append(el("p", `Recepten räknar ${row.query} i ${UNITS[use.unit]}. Skriv mängden så om recepten ska kunna använda varan.`, "hint"));
          else if (narrow) confirm.append(el("p", fits ? `Bara några recept kan använda ${row.query} när varan är skriven så här. De flesta behöver veta precis vilken sort det är.` : `Recepten behöver veta precis vilken sorts ${row.query} det är.`, "hint"));
          if (narrow && products.length) {
            const exact = el("div", null, "pantry-exact"); exact.append(el("p", "Välj den vara du har hemma, så kan recepten använda den:"));
            for (const product of products.slice(0, 6)) { const b = button(null, guard(() => addProduct(product)), "result"); b.append(el("span", product.display_name || product.name, "result-name"), el("span", product.package, "result-note")); exact.append(b); }
            confirm.append(exact);
          } else if (narrow) confirm.append(el("p", "Sök på varans namn och märke och välj en bestämd vara, så kan recepten använda den.", "hint"));
        }
        const actions = el("div", null, "links");
        actions.append(button(narrow ? "Lägg in den ändå" : "Lägg i skafferiet", guard(save), "btn primary"),
          button("Avbryt", () => { confirm.hidden = true; confirm.replaceChildren(); }, "btn quiet"));
        confirm.append(actions);
      };
      draw(); confirm.hidden = false;
    }
    async function addProduct(product) {
      if (product.purchase_units || product.campaign_choice) throw new Error("Vi vet inte hur mycket förpackningen innehåller. Skriv varan med mängd i stället, till exempel 500 g.");
      const name = (product.display_name || product.name).slice(0, 120);
      await addToPantry({ name, quantity: product.package_quantity, unit: product.package_unit, product_key: product.product_key, food: !N.isNonfood(product.name) });
      done(name);
    }
    async function searchNow() {
      const text = input.value.trim(), mine = ++generation; controller?.abort();
      if (text.length < 2) { close(); return; }
      controller = new AbortController();
      try {
        const found = await N.suggestions(text, controller.signal); if (mine !== generation) return;
        results.replaceChildren(); results.hidden = false; first = null;
        const products = found.products.filter(p => !p.purchase_units && !p.campaign_choice);
        found.options.forEach((row, index) => { const b = button(null, guard(() => ask(row, products)), `result${index ? "" : " best"}`);
          b.append(el("span", `${capital(row.name || row.query)} · ${amount(row.quantity, row.unit)}`, "result-name"), el("span", "Lägg i skafferiet", "result-note")); results.append(b); if (!index) first = b; });
        if (!found.options.length) results.append(el("p", found.error || "Skriv också hur mycket du har, till exempel 500 g, 1 l eller 6 st.", "hint"));
        if (products.length) {
          const more = el("details", null, "exact"); more.append(el("summary", `Välj en bestämd vara (${products.length})`));
          for (const product of products.slice(0, 12)) { const b = button(null, guard(() => addProduct(product)), "result");
            b.append(el("span", product.display_name || product.name, "result-name"), el("span", product.package, "result-note")); more.append(b); }
          results.append(more);
        }
      } catch (error) { if (error.name !== "AbortError") { results.replaceChildren(el("p", "Sökningen gick inte att göra. Försök igen.", "hint")); results.hidden = false; } }
    }
    input.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => void searchNow(), 250); });
    input.addEventListener("keydown", event => { if (event.key === "Enter") { event.preventDefault(); if (first) first.click(); else { clearTimeout(timer); void searchNow(); } } if (event.key === "Escape") close(); });
    const outside = event => { if (!search.contains(event.target)) close(); };
    document.addEventListener("click", outside);
    function render() {
      list.replaceChildren();
      const s = N.saved.settings, strict = [...s.allergies, ...s.avoid];
      note.textContent = !s.usePantry ? "Du har valt att räkna utan skafferiet. Ändra det under Fler val i matplanen."
        : strict.length && pantry().some(i => !i.product_key) ? `Du har valt bort ${strict.join(", ")}. Då använder recepten bara skafferivaror som är en bestämd vara, eftersom vi inte vet vad de andra innehåller.` : "";
      note.hidden = !note.textContent;
      for (const item of pantry()) {
        const li = el("li", null, "item"), text = el("div", null, "item-text");
        const kind = item.unusable ? "Går inte att använda" : item.product_key ? "Bestämd vara" : item.food ? "Otillagad" : "Inte mat";
        text.append(el("span", capital(item.name), "item-name"), el("span", [kind, item.reserved > 0 ? `${amount(item.reserved, item.unit)} till planerade måltider` : null].filter(Boolean).join(" · "), "item-kind"));
        const stepper = el("div", null, "stepper");
        stepper.append(button("−", guard(() => changePantryAmount(item.id, -1)), "step", { "aria-label": `Mindre ${item.name}` }), el("span", amount(item.quantity, item.unit), "step-value"), button("+", guard(() => changePantryAmount(item.id, 1)), "step", { "aria-label": `Mer ${item.name}` }));
        li.append(text, stepper, button("×", guard(() => removeFromPantry(item.id)), "remove", { "aria-label": `Ta bort ${item.name}` }));
        const below = el("div", null, "item-offer"); li.append(below);
        for (const check of S.state.pantry_checks || []) if (check.item_id === item.id) below.append(el("span", check.message));
        list.append(li);
      }
      if (!pantry().length) list.append(el("li", "Skafferiet är tomt. Skriv en vara ovan, eller tryck Jag har handlat när du har köpt en inköpslista.", "empty"));
    }
    const off = N.on(render); render();
    box.dispose = () => { off(); document.removeEventListener("click", outside); };
    return box;
  }
  const pantrySummary = () => { const n = pantry().length; return n ? `${n} ${n === 1 ? "vara" : "varor"} hemma` : "Tomt"; };
  // What the current plan takes from the pantry instead of buying.
  function pantryUsed() {
    const rows = S.plan?.plan?.personal?.allocations || [], sums = new Map();
    for (const row of rows) { const key = `${row.name.toLowerCase()}|${row.unit}`, sum = sums.get(key) || { name: row.name, unit: row.unit, quantity: 0 }; sum.quantity += row.quantity; sums.set(key, sum); }
    return [...sums.values()].map(r => `${r.name} ${amount(Math.round(r.quantity * 100) / 100, r.unit)}`);
  }

  // ---- After shopping ------------------------------------------------------
  const ledger = () => (S.state?.ledger || []).filter(e => e.plan_id === S.plan?.plan_id);
  const purchased = () => ledger().some(e => e.action === "purchase" && e.revision === S.plan.revision);
  const consumed = () => ledger().some(e => e.action === "consume" && e.operation_id === `consume:${S.plan.revision}`);
  // Goods sold by weight, or with an estimated amount, are entered as they turned out.
  function toMeasure() {
    const plan = S.plan.plan;
    return plan.optimized_basket.stores.flatMap(g => g.items).filter(i => i.quantity_confidence === "estimated" || i.unit !== i.purchased_unit || plan.personal.needs?.find(n => n.key === i.ingredient)?.preparation);
  }
  const register = quantities => N.change("Lägger varorna i skafferiet", "purchase", quantities ? { measured_purchase_quantities: quantities } : {});
  function measureDialog(rows) {
    const dialog = el("dialog", null, "measure", { "aria-labelledby": "measure-title" }), form = el("form", null, "auth"), inputs = [], status = el("p", null, "hint", { role: "status" });
    form.append(el("h2", "Hur mycket blev det?", null, { id: "measure-title" }), el("p", "De här varorna säljs efter vikt eller har en uppskattad mängd. Ändra siffran om du fick mer eller mindre.", "hint"));
    for (const row of rows) {
      const start = Math.max(row.required_quantity, row.purchased_usable_quantity || 0);
      const input = el("input", null, null, { type: "number", inputmode: "decimal", step: "any", min: String(row.required_quantity), required: true, value: String(Math.round(start * 1000) / 1000) });
      const field = el("label", `${row.product_name} (${UNITS[row.unit] || row.unit})`, "field"); field.append(input, el("span", `Planen behöver minst ${amount(Math.round(row.required_quantity * 100) / 100, row.unit)}.`, "hint"));
      inputs.push([row, input]); form.append(field);
    }
    const actions = el("div", null, "links"); actions.append(el("button", "Spara i skafferiet", "btn primary", { type: "submit" }), button("Avbryt", () => dialog.close(), "btn quiet"));
    form.append(actions, status); dialog.append(form);
    form.addEventListener("submit", async event => {
      event.preventDefault();
      const quantities = {};
      for (const [row, input] of inputs) {
        const q = Number(input.value);
        if (!Number.isFinite(q) || q < row.required_quantity) { status.textContent = `${row.product_name}: mängden behöver räcka till planen. Räkna om planen om du köpte mindre.`; return; }
        quantities[`${row.store_id}|${row.product_id}|${row.ingredient}`] = q;
      }
      dialog.close(); await register(quantities);
    });
    dialog.addEventListener("close", () => dialog.remove());
    document.body.append(dialog); dialog.showModal();
  }
  function afterShopping({ onPantry } = {}) {
    const box = el("section", null, "after");
    if (!S.plan || !S.state) { box.hidden = true; return box; }
    const used = pantryUsed();
    if (used.length) box.append(el("p", `Från skafferiet, behöver inte köpas: ${used.join(", ")}.`, "meta"));
    box.append(el("h2", "När du har handlat"));
    if (!purchased()) {
      box.append(el("p", "Tryck här när varorna är hemma. De läggs i skafferiet, så räknar Smako med dem nästa gång.", "hint"),
        button("Jag har handlat", () => { const rows = toMeasure(); if (rows.length) measureDialog(rows); else void register(); }, "btn primary"));
      return box;
    }
    box.append(el("p", "Inköpet ligger i skafferiet."));
    if (N.planHasRecipes()) {
      if (consumed()) box.append(el("p", "Det som gick åt till maten är borttaget ur skafferiet.", "hint"));
      else box.append(el("p", "När maten är lagad tar Smako bort det som gick åt ur skafferiet.", "hint"), button("Maten är lagad", () => void N.change("Uppdaterar skafferiet", "consume", {}), "btn"));
    }
    if (onPantry) box.append(button("Öppna skafferiet", onPantry, "text-link"));
    return box;
  }

  Object.assign(N, { signedIn, accountLabel, accountView, pantryView, pantrySummary, pantryUsed, afterShopping });
})();

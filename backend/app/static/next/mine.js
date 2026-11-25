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

  // Owner decision 2026-11-21: how much new plans vary, a member setting.
  function settingsView() {
    const now = S.state?.variation || { avoid_recent_plans: 2, random_variation: true };
    const box = el("section", null, "settings");
    const status = el("p", null, "hint", { role: "status" });
    const plans = el("select", null, null, { name: "avoid_recent_plans" });
    for (const [value, text] of [[0, "Nej, rätterna får komma igen"], [1, "Från min senaste plan"], [2, "Från mina 2 senaste planer"],
      [3, "Från mina 3 senaste planer"], [5, "Från mina 5 senaste planer"], [10, "Från mina 10 senaste planer"]]) {
      plans.append(el("option", text, null, { value: String(value), ...(now.avoid_recent_plans === value ? { selected: true } : {}) }));
    }
    const random = el("input", null, null, { type: "checkbox", name: "random_variation", ...(now.random_variation ? { checked: true } : {}) });
    const plansField = el("label", "Undvik rätter jag redan fått", "field"), randomField = el("label", null, "check");
    plansField.append(plans);
    randomField.append(random, document.createTextNode(" Variera lite: välj ibland en annan vecka som kostar högst cirka 10 % mer"));
    async function save() {
      status.textContent = "Sparar.";
      const variation = { avoid_recent_plans: Number(plans.value), random_variation: random.checked };
      try { S.state = await api("/api/personal/variation", { revision: S.state.revision, variation }, "PUT"); status.textContent = "Sparat. Gäller nästa plan du skapar."; }
      catch (error) {
        if (error.status === 409) { await N.refreshState(); try { S.state = await api("/api/personal/variation", { revision: S.state.revision, variation }, "PUT"); status.textContent = "Sparat. Gäller nästa plan du skapar."; return; } catch (again) { status.textContent = again.message; return; } }
        status.textContent = error.message;
      }
    }
    plans.addEventListener("change", save); random.addEventListener("change", save);
    box.append(el("h2", "Inställningar"),
      el("p", "Nya planer och ”Byt rätt” undviker middagar från dina senaste planer. Finns det ingen vecka som passar dina val tillåts de äldsta rätterna igen först.", "hint"),
      plansField, randomField, status);
    return box;
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
        box.append(pointsView());
        box.append(settingsView());
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

  // ---- Points for receipts (owner request 2026-11-22) -----------------------
  // A receipt is read here: a photo with text recognition in the browser (the
  // picture never leaves the phone) or a PDF whose text the server extracts.
  // The member checks the lines; Smako matches them to the shopping list.
  const points = { data: null, loading: false };
  async function loadPoints() {
    if (points.loading || !signedIn()) return; points.loading = true;
    try { points.data = await api("/api/member/points"); } catch (_) { points.data = null; } finally { points.loading = false; emit(); }
  }
  const when = value => new Intl.DateTimeFormat("sv-SE", { dateStyle: "short", timeZone: "Europe/Stockholm" }).format(new Date(value));
  function pointsView() {
    const box = el("section", null, "panel points");
    function fill() {
      box.replaceChildren(el("h2", "Dina poäng"));
      if (!points.data) { box.append(el("p", points.loading ? "Hämtar poängen." : "Poängen kunde inte hämtas just nu.", "hint")); return; }
      box.append(el("strong", number(points.data.balance), "balance"),
        el("p", "Du får poäng när du skannar kvittot, och extra poäng för varje vara som har ett annat pris än i Smako. Saknas en vara i Smako skannar du streckkoden, så får du poäng och Smako lär sig varan.", "hint"));
      if (S.plan) box.append(button("Skanna kvitto", () => receiptDialog(fill), "btn primary"));
      if (points.data.history.length) { const list = el("ul"); for (const h of points.data.history) list.append(el("li", `${when(h.created_at)}: ${h.points > 0 ? "+" : ""}${h.points} · ${h.reason}`)); box.append(el("h4", "Senaste"), list); }
    }
    fill();
    if (!points.loading) void loadPoints().then(fill);
    return box;
  }
  const loadScript = src => new Promise((resolve, reject) => { if ([...document.scripts].some(x => x.src.endsWith(src))) return resolve(); const tag = document.createElement("script"); tag.src = src; tag.onload = resolve; tag.onerror = () => reject(new Error("Det gick inte att ladda läsaren. Kontrollera nätet och försök igen.")); document.head.append(tag); });
  const OCR = "/static/vendor/tesseract/";
  async function photoText(file, status) {
    await loadScript(`${OCR}tesseract.min.js`);
    const bitmap = await createImageBitmap(file), scale = Math.min(1, 2200 / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas"); canvas.width = Math.round(bitmap.width * scale); canvas.height = Math.round(bitmap.height * scale);
    const ctx = canvas.getContext("2d"); ctx.filter = "grayscale(1) contrast(1.4)"; ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    const worker = await window.Tesseract.createWorker("swe", 1, { workerPath: `${OCR}worker.min.js`, corePath: OCR, langPath: OCR, gzip: true,
      logger: m => { if (m.status === "recognizing text") status.textContent = `Läser kvittot … ${Math.round(m.progress * 100)} %`; } });
    try { await worker.setParameters({ preserve_interword_spaces: "1" }); return (await worker.recognize(canvas)).data.text; } finally { await worker.terminate(); }
  }
  async function pdfText(file) {
    const response = await fetch("/api/member/receipts/pdf-text", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/pdf", Accept: "application/json" }, body: file });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "PDF:en gick inte att läsa.");
    return data.text;
  }
  // createBarcodeScanner returns the scanner itself, not a promise (fix 2026-11-25:
  // the old `.then` on it threw, so no scan ever started). A camera that cannot
  // start or read now ends the wait with an error, and the row offers typing the
  // digits instead.
  let scanner = null, cancelScan = null;
  const cameraMessage = error => error?.name === "NotAllowedError"
    ? "Kameran är inte tillåten för sidan. Tillåt kameran i webbläsarens inställningar, eller skriv streckkoden."
    : "Kameran kunde inte läsa streckkoden. Skriv siffrorna under streckkoden i stället.";
  async function scanBarcode(video, status) {
    await loadScript("/scanner-assets/physical-barcode-scanner.js");
    if (!window.GroceryBarcodeScanner || !navigator.mediaDevices?.getUserMedia) throw new Error("Kameran går inte att använda här. Skriv siffrorna under streckkoden.");
    return new Promise((resolve, reject) => {
      let done = false;
      const finish = (settle, value) => { if (done) return; done = true; cancelScan = null; scanner?.stop?.(); scanner = null; settle(value); };
      cancelScan = () => finish(reject, Object.assign(new Error("Skanningen avbröts."), { cancelled: true }));
      const current = window.GroceryBarcodeScanner.createBarcodeScanner({ mode: "product", videoElement: video,
        onResult: result => finish(resolve, result.normalized_gtin || result.raw_value),
        onError: (error, detail = {}) => {
          if (detail.recoverable) { status.textContent = "Håll hela streckkoden i bild."; return; }
          finish(reject, new Error(cameraMessage(error)));
        } });
      scanner = current;
      current.start().then(() => { if (!done) status.textContent = "Håll varans streckkod framför kameran."; })
        .catch(error => finish(reject, new Error(cameraMessage(error))));
    });
  }
  function typeBarcode(row, status, onGtin) {
    if (row.querySelector(".gtin-entry")) return;
    const box = el("div", null, "gtin-entry"), input = el("input", null, null, { inputmode: "numeric", autocomplete: "off", maxlength: "14", placeholder: "Siffrorna under streckkoden", "aria-label": "Streckkod" });
    const use = () => {
      try { const gtin = window.GroceryBarcodeScanner.normalizeGtin(input.value).normalized_gtin; box.remove(); onGtin(gtin); }
      catch (error) { status.textContent = error?.message || "Det är inte en giltig streckkod. Kontrollera siffrorna."; }
    };
    input.addEventListener("keydown", event => { if (event.key === "Enter") use(); });
    box.append(input, button("Använd", use, "btn small")); row.append(box); input.focus();
  }
  // A small mouse comes out of Smako's hole, sniffs the accepted item and pulls
  // it down into Smako (owner request 2026-11-24). Reduced motion: a short note.
  const MOUSE = '<svg viewBox="0 0 64 36" aria-hidden="true"><path class="tail" d="M12 25c-6 1-9-3-11-7" fill="none" stroke="#c9a3a0" stroke-width="2" stroke-linecap="round"/><ellipse cx="28" cy="24" rx="17" ry="10" fill="#a39a92"/><circle cx="45" cy="19" r="9" fill="#b3aaa2"/><circle cx="42" cy="10" r="5.5" fill="#b3aaa2"/><circle cx="42" cy="10" r="3.2" fill="#efc2c0"/><circle cx="48" cy="17" r="1.5" fill="#2b2522"/><g class="nose"><circle cx="54" cy="21" r="2.2" fill="#e58f97"/><path d="M53 22l9-2M53 23l9 2M52 24l8 4" stroke="#6f6660" stroke-width=".8" stroke-linecap="round"/></g><path d="M20 33v2M34 33v2" stroke="#8d847d" stroke-width="2" stroke-linecap="round"/></svg>';
  function mouseGrab(row, name) {
    const done = () => row.querySelector(".mouse-done") || row.append(el("span", "Smako tog med varan ✓", "mouse-done"));
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return done();
    const stage = el("div", null, "mouse-stage", { "aria-hidden": "true" }), hole = el("span", null, "mouse-hole");
    const mouse = el("span", null, "mouse"), item = el("span", name, "mouse-item");
    mouse.innerHTML = MOUSE; stage.append(hole, item, mouse); row.append(stage);
    const width = stage.clientWidth, run = Math.max(40, width - item.offsetWidth - mouse.offsetWidth - 24);
    stage.style.setProperty("--run", `${run}px`); stage.style.setProperty("--carry", `${-(width - item.offsetWidth - 28)}px`);
    stage.classList.add("go");
    mouse.addEventListener("animationend", event => { if (event.animationName === "mouse-trip") { stage.remove(); done(); } });
  }
  function receiptDialog(onPoints) {
    const dialog = el("dialog", null, "receipt-dialog"), body = el("div"), status = el("p", null, "hint", { role: "status" });
    const head = el("div", null, "dialog-head"); head.append(el("h2", "Skanna kvitto"), button("Stäng", () => dialog.close(), "btn small"));
    dialog.append(head, body, status); document.body.append(dialog);
    dialog.addEventListener("close", () => { cancelScan?.(); scanner?.stop?.(); scanner = null; dialog.remove(); });
    let result = null, store = "", day = null;
    const planId = S.plan?.plan_id;
    const busy = async (text, work) => { status.textContent = text; try { await work(); } catch (error) { status.textContent = error.message; } };
    function choose() {
      const photo = el("input", null, null, { type: "file", accept: "image/*", capture: "environment", hidden: true });
      const pdf = el("input", null, null, { type: "file", accept: "application/pdf", hidden: true });
      photo.addEventListener("change", () => photo.files[0] && busy("Läser kvittot i telefonen …", async () => preview({ text: await photoText(photo.files[0], status) })));
      pdf.addEventListener("change", () => pdf.files[0] && busy("Läser PDF:en …", async () => preview({ text: await pdfText(pdf.files[0]) })));
      body.replaceChildren(el("p", "Fota hela kvittot rakt uppifrån i bra ljus, eller välj ett digitalt kvitto som PDF. Bilden lämnar inte telefonen; Smako sparar bara raderna du godkänner."),
        photo, pdf, button("Fota kvittot", () => photo.click(), "btn primary cta"), button("Välj PDF-kvitto", () => pdf.click(), "btn"));
    }
    async function preview(input) {
      result = await api("/api/member/receipts/preview", { plan_id: planId, ...input });
      store = result.store_text; day = result.purchased_on; status.textContent = ""; draw();
    }
    const lines = () => result.lines.filter(l => !l.removed).map(({ description, price, quantity, unit, unit_price, gtin }) => ({ description, price, quantity, unit, unit_price, gtin }));
    const again = () => busy("Räknar om …", () => preview({ store_text: store, purchased_on: day, lines: lines() }));
    function draw() {
      const storeInput = el("input", null, null, { value: store, maxlength: "120", "aria-label": "Butik" }); storeInput.addEventListener("change", () => { store = storeInput.value; void again(); });
      const field = el("label", "Butik", "field"); field.append(storeInput);
      const list = el("div", null, "receipt-lines");
      result.lines.forEach((line, index) => {
        if (line.removed) return;
        const row = el("div", null, `receipt-line${line.item ? " matched" : ""}`, { "data-line": String(index) }), price = el("input", null, null, { type: "number", step: "0.01", min: "0.01", value: String(line.price), "aria-label": `Pris för ${line.description}` });
        price.addEventListener("change", () => { line.price = Number(price.value); void again(); });
        const tags = [line.unsure ? `Osäker: är det ${line.smako_product}? Skanna streckkoden för poäng.` : line.price_differs ? `Smako: ${N.money(line.planned_price)} för ${line.smako_product}` : line.smako_product ? `Samma pris som i Smako` : null,
          line.missing_in_smako ? (line.learned_item ? "Finns redan i Smako tack vare ett kvitto" : line.new_item ? "Ny vara i Smako" : result.store_known ? "Finns inte i Smako" : "Butiken saknas i Smako") : null,
          line.needs_barcode && line.missing_in_smako ? "Skanna streckkoden för poäng" : null,
          line.local_price ? "Smako lär sig butikens pris" : line.learned_item && line.price_differs ? "Smako känner redan till priset tack vare ett kvitto" : null,
          line.item ? `på handlingslistan` : null, line.points ? `+${line.points} poäng` : null, line.gtin ? `streckkod ${line.gtin}` : null].filter(Boolean).join(" · ");
        const tools = el("div", null, "links");
        tools.append(button("Ta bort raden", () => { line.removed = true; void again(); }, "text-link"));
        // A price Smako does not know: the barcode lets Smako learn the store's price (owner correction 2026-11-24).
        const teach = line.price_differs && !line.gtin;
        if (line.needs_barcode || teach) tools.append(button(teach ? "Skanna streckkoden så lär sig Smako priset" : "Skanna varans streckkod", () => {
          if (row.querySelector("video")) return;
          const accept = async gtin => {
            line.gtin = gtin; await again();
            // Owner request 2026-11-24: a mouse fetches every item Smako accepts.
            const accepted = result.lines.findIndex(l => !l.removed && l.gtin === gtin && (l.new_item || l.local_price));
            const target = accepted >= 0 && list.querySelector(`[data-line="${accepted}"]`);
            if (target) mouseGrab(target, result.lines[accepted].description);
          };
          const video = el("video", null, null, { playsinline: "", muted: "", autoplay: "" });
          const cancel = button("Avbryt skanningen", () => cancelScan?.(), "text-link");
          row.append(video, cancel);
          void busy("Startar kameran …", async () => {
            let gtin = null;
            try { gtin = await scanBarcode(video, status); }
            catch (error) {
              video.remove(); cancel.remove();
              if (error.cancelled) { status.textContent = ""; return; }
              status.textContent = error.message;
              typeBarcode(row, status, typed => void busy("Räknar om …", () => accept(typed)));
              return;
            }
            video.remove(); cancel.remove(); await accept(gtin);
          });
        }, "text-link"));
        row.append(el("strong", line.description), price, el("span", tags, "tags"), tools); list.append(row);
      });
      const differs = result.lines.filter(l => !l.removed && l.price_differs).length, missing = result.lines.filter(l => !l.removed && l.missing_in_smako && l.points).length;
      const scan = result.needs_barcode ? ` Skanna streckkoden på ${result.needs_barcode === 1 ? "varan" : `de ${result.needs_barcode} varorna`} som Smako saknar eller är osäker på, så får du poäng för ${result.needs_barcode === 1 ? "den" : "dem"} också.` : "";
      const summary = result.qualifies ? `Kvittot ger ${result.points} poäng${differs || missing ? `: ${[differs ? `${differs} ${differs === 1 ? "vara" : "varor"} med annat pris än Smakos` : null, missing ? `${missing} ${missing === 1 ? "vara" : "varor"} som saknas i Smako` : null].filter(Boolean).join(" och ")}` : ""}.${result.points >= result.max_points ? " Det är högsta poängen för ett kvitto." : ""}${scan}`
        : `Vi kunde bara läsa ${result.lines.length} varor. Det behövs minst ${result.needed} för poäng. Fota kvittot igen.`;
      body.replaceChildren(field, el("p", result.store_known ? `Butiken finns i Smako: ${result.store}.` : "Smako har inga priser för den här butiken. Skanna streckkoden på varorna så ger de extra poäng.", "hint"),
        list, el("p", summary), button(`Ta ${result.points} poäng`, () => busy("Sparar …", async () => {
          const done = await api("/api/member/receipts", { plan_id: planId, store_text: store, purchased_on: day, lines: lines() });
          points.data = { balance: done.balance, history: done.history };
          const learnt = [done.new_items?.length ? `${done.new_items.length === 1 ? "En ny vara" : `${done.new_items.length} nya varor`} finns nu i Smako för ${result.store}.` : null,
            done.new_prices?.length ? `Smako vet nu butikens pris på ${done.new_prices.join(", ")}.` : null,
            done.bonus_points ? `Du bekräftade att ${done.persistent_items.join(", ")} finns kvar i butiken: +${done.bonus_points} poäng.` : null].filter(Boolean).join(" ");
          body.replaceChildren(el("h3", `+${done.points} poäng`), el("p", `Du har nu ${number(done.balance)} poäng. Tack för att du hjälper Smako med priserna!`), ...(learnt ? [el("p", learnt)] : []), button("Klar", () => dialog.close(), "btn primary"));
          status.textContent = ""; onPoints?.(); emit();
        }), "btn primary cta", { disabled: !result.qualifies }), button("Börja om", () => { result = null; choose(); }, "btn quiet"));
    }
    if (!planId) { body.append(el("p", "Skapa en handlingslista först.")); }
    else choose();
    dialog.showModal();
  }

  // ---- Pantry --------------------------------------------------------------
  // Typed goods count as uncooked; the server decides which recipes they fit. A
  // chosen product is kept as the amount recipes can use (a can as its drained
  // weight), the way "Jag har handlat" keeps it.
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
      const [fits, uses, drained = 0] = use.usable || [0, 0], narrow = use.food && uses > 0 && fits < uses / 2, wrongUnit = use.food && use.unit && use.unit !== row.unit;
      const eggs = use.egg_grams && row.unit === "st" && use.unit === "g";
      if (!narrow && !wrongUnit) { await save(); return; }
      // Step 5: count eggs by size, and name the kind when the word is too broad for the recipes.
      const saveAs = (name, quantity, unit, text) => guard(() => addToPantry({ name: name.slice(0, 120), quantity, unit, food: use.food }).then(() => done(text)));
      const draw = () => {
        confirm.replaceChildren(el("h3", `${capital(row.query)} · ${amount(row.quantity, row.unit)}`));
        if (eggs) {
          const sizes = el("div", null, "chips"), names = { S: "Small", M: "Medium", L: "Large" };
          for (const [size, grams] of Object.entries(use.egg_grams)) {
            const total = Math.round(row.quantity * grams);
            sizes.append(button(`${names[size] || size} (${size})`, saveAs(row.query, total, "g", `${capital(row.query)} · ${amount(row.quantity, "st")} ${size}, ungefär ${amount(total, "g")}`), "chip"));
          }
          confirm.append(el("p", "Hur stora är äggen? Recepten räknar ägg i gram, så Smako räknar om med en vanlig vikt per ägg utan skal.", "hint"), sizes);
        } else {
          if (narrow && use.kinds?.length && !(use.unit && use.unit !== row.unit)) {
            const kinds = el("div", null, "chips");
            for (const kind of use.kinds) kinds.append(button(capital(kind.name), saveAs(kind.name, row.quantity, row.unit, `${capital(kind.name)} · ${amount(row.quantity, row.unit)}`), "chip"));
            confirm.append(el("p", `Vilken sorts ${row.query} har du? Då kan recepten använda den.`, "hint"), kinds);
          }
          if (use.unit && use.unit !== row.unit) confirm.append(el("p", `Recepten räknar ${row.query} i ${UNITS[use.unit]}. Skriv mängden så om recepten ska kunna använda varan.`, "hint"));
          // Recipes that want it drained need the can's drained weight; others need the kind (which rice, which cut).
          else if (narrow && drained >= uses / 2) confirm.append(el("p", `Recepten använder ${row.query} avrunnen, till exempel från burk. Välj varan du har. Smako räknar med vikten utan spad när förpackningen anger den, annars med förpackningens vikt.`, "hint"));
          else if (narrow) confirm.append(el("p", fits ? `Bara några recept kan använda ${row.query} när varan är skriven så här. De flesta behöver veta precis vilken sort det är.` : `Recepten behöver veta precis vilken sorts ${row.query} det är.`, "hint"));
          if (narrow && products.length) {
            const exact = el("div", null, "pantry-exact"); exact.append(el("p", "Välj den vara du har hemma, så kan recepten använda den:"));
            for (const product of products.slice(0, 6)) { const b = button(null, guard(() => addProduct(product, row.query)), "result"); b.append(el("span", product.display_name || product.name, "result-name"), el("span", product.package, "result-note")); exact.append(b); }
            confirm.append(exact);
          } else if (narrow) confirm.append(el("p", "Sök på varans namn och märke och välj en bestämd vara, så kan recepten använda den.", "hint"));
        }
        const actions = el("div", null, "links");
        actions.append(button(narrow || eggs ? "Lägg in den ändå" : "Lägg i skafferiet", guard(save), "btn primary"),
          button("Avbryt", () => { confirm.hidden = true; confirm.replaceChildren(); }, "btn quiet"));
        confirm.append(actions);
      };
      draw(); confirm.hidden = false;
    }
    async function addProduct(product, typed = "") {
      if (product.purchase_units || product.campaign_choice) throw new Error("Vi vet inte hur mycket förpackningen innehåller. Skriv varan med mängd i stället, till exempel 500 g.");
      const name = (product.display_name || product.name).slice(0, 120);
      const facts = await api(`/api/personal/pantry-product?product_key=${product.product_key}&postal_code=${encodeURIComponent(N.areaCode())}&name=${encodeURIComponent(typed.slice(0, 120))}`);
      if (!facts.usable_quantity || !facts.usable_unit) throw new Error("Vi vet inte hur mycket förpackningen innehåller. Skriv varan med mängd i stället, till exempel 500 g.");
      await addToPantry({ name, quantity: facts.usable_quantity, unit: facts.usable_unit, product_key: product.product_key, food: facts.food });
      done(facts.less_than_package ? `${name} · ${facts.estimated ? "ungefär " : ""}${amount(facts.usable_quantity, facts.usable_unit)} utan spad`
        : facts.drained_from_package ? `${name} · förpackningen anger ingen vikt utan spad, så Smako räknar med ${amount(facts.usable_quantity, facts.usable_unit)}. Utan spad kan det bli mindre.` : name);
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
          for (const product of products.slice(0, 12)) { const b = button(null, guard(() => addProduct(product, text)), "result");
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
        const kind = item.unusable ? "Går inte att använda" : item.product_key ? "Bestämd vara" : item.food ? null : "Inte mat";
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
    const home = N.atHomeView(); if (home) box.append(home);
    box.append(el("h2", "När du har handlat"));
    if (!purchased()) {
      box.append(el("p", "Tryck här när varorna är hemma. De läggs i skafferiet, så räknar Smako med dem nästa gång.", "hint"),
        button("Jag har handlat", () => { const rows = toMeasure(); if (rows.length) measureDialog(rows); else void register(); }, "btn primary"));
      if (signedIn()) box.append(button("Skanna kvitto och få poäng", () => receiptDialog(), "btn"));
      return box;
    }
    box.append(el("p", "Inköpet ligger i skafferiet."));
    if (N.planHasRecipes()) {
      if (consumed()) box.append(el("p", "Det som gick åt till maten är borttaget ur skafferiet.", "hint"));
      else box.append(el("p", "När maten är lagad tar Smako bort det som gick åt ur skafferiet.", "hint"), button("Maten är lagad", () => void N.change("Uppdaterar skafferiet", "consume", {}), "btn"));
    }
    if (signedIn()) box.append(el("p", "Skanna kvittot så får du poäng, och extra poäng för varor med andra priser än i Smako eller som saknas i Smako.", "hint"), button("Skanna kvitto och få poäng", () => receiptDialog(), "btn"));
    if (onPantry) box.append(button("Öppna skafferiet", onPantry, "text-link"));
    return box;
  }

  Object.assign(N, { signedIn, accountLabel, accountView, pantryView, pantrySummary, pantryUsed, afterShopping, receiptDialog, pointsView });
})();

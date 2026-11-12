/* Alternativ A: five tabs. Home shows the two ways to use Smako: write a
   shopping list, or plan meals. Both end on the Handla tab, store by store.
   The pantry has its own tab and the account is reached from the top. */
(() => {
  "use strict";
  const N = window.SmakoNext, { el, button, S, saved } = N;
  const main = document.getElementById("main"), busy = document.getElementById("busy"), placeButton = document.getElementById("place"), accountLink = document.getElementById("account"), dialog = document.getElementById("place-dialog");
  let disposers = [];
  // A part of the page that is rebuilt whenever something changes.
  const live = (node, build) => { const draw = () => node.replaceChildren(...[build()].flat().filter(Boolean)); draw(); disposers.push(N.on(draw)); return node; };
  const go = hash => { if (location.hash === hash) render(); else location.hash = hash; };
  const link = (text, hash, cls) => el("a", text, cls, { href: hash });

  function placePanel() {
    return live(el("div"), () => S.location ? null : (() => { const p = el("section", null, "panel"); p.append(el("h2", "Var handlar du?"), N.postcodeBox()); return p; })());
  }
  function sticky(...nodes) { const bar = el("div", null, "sticky"), inner = el("div"); inner.append(...nodes); bar.append(inner); return bar; }

  const screens = {
    hem() {
      const head = el("div"); head.append(el("h1", "Vad vill du göra?"), el("p", "Smako jämför priserna i butikerna nära dig och visar var du handlar vad.", "lead"));
      const ways = el("div", null, "ways");
      const way = (icon, title, note, hash, cls = "") => { const a = el("a", null, `way ${cls}`, { href: hash }), text = el("span"); text.append(el("span", title, "way-title"), el("br"), el("span", note, "way-note")); a.append(el("span", icon, "way-icon", { "aria-hidden": "true" }), text, el("span", "›", "way-go", { "aria-hidden": "true" })); return a; };
      ways.append(way("1", "Skriv en inköpslista", "Lägg till det du behöver. Smako letar upp de butiker där hela listan blir billigast.", "#lista", "main"),
        way("2", "Planera veckans mat", "Få recept efter dina val och en inköpslista för alltihop.", "#mat"));
      const current = live(el("div"), () => { if (!S.plan) return null; const p = el("section", null, "panel"), b = N.basket(), recipes = S.plan.plan.personal.slots.filter(s => s.recipe).length;
        p.append(el("p", "Senast", "eyebrow"), el("h2", recipes ? `${recipes} recept och inköpslista` : "Din inköpslista"), el("p", `${N.totalText()} i ${b.store_count} ${b.store_count === 1 ? "butik" : "butiker"}`, "meta"));
        const row = el("div", null, "links"); if (recipes) row.append(link("Visa recepten", "#mat")); row.append(link("Öppna handlingslistan", "#handla")); p.append(row); return p; });
      const mine = live(el("section", null, "panel"), () => { const row = el("div", null, "links"); row.append(link(`Skafferi: ${N.pantrySummary().toLowerCase()}`, "#skafferi"), link(N.signedIn() ? "Mitt konto" : "Logga in eller skapa konto", "#konto"));
        return [el("h2", "Skafferi och konto"), el("p", N.signedIn() ? "Skafferiet och dina val sparas på kontot." : "Lägg in det du har hemma, så handlar du mindre. Med ett konto sparas det och du får fler recept.", "meta"), row]; });
      return [head, ways, current, placePanel(), mine];
    },
    lista() {
      const head = el("div"); head.append(el("h1", "Inköpslista"), el("p", "Skriv varan som du brukar säga den. Vill du ha ett visst märke väljer du en bestämd vara.", "lead"));
      const cta = live(el("div"), () => {
        const withRecipes = N.planHasRecipes(), n = S.items.length;
        const main = button(withRecipes ? "Räkna om planen med mina varor" : n ? `Hitta billigaste butikerna för ${n} ${n === 1 ? "vara" : "varor"}` : "Lägg till en vara först", async () => { if (await (withRecipes ? N.updateListInPlan() : N.calculateList())) go("#handla"); }, "btn primary cta", { disabled: !n || !S.location });
        const nodes = [main];
        if (withRecipes) nodes.push(button("Räkna bara mina varor, utan recepten", async () => { if (await N.calculateList()) go("#handla"); }, "btn quiet small", { disabled: !n }));
        if (!S.location) nodes.push(el("p", "Ange postnummer högst upp först.", "hint"));
        return nodes;
      });
      return [head, placePanel(), N.itemsEditor(), sticky(cta)];
    },
    mat() {
      if (N.planHasRecipes() && !screens.mat.editing) {
        const head = el("div"); head.append(el("h1", "Din matplan"), live(el("p", null, "lead"), () => document.createTextNode(`${N.totalText()} för recepten och dina egna varor.`)));
        const links = el("div", null, "links"); links.append(button("Ändra val och skapa en ny plan", () => { screens.mat.editing = true; render(); }, "btn small"));
        return [head, links, live(el("div"), () => N.recipesView()), sticky(button("Till handlingslistan", () => go("#handla"), "btn primary cta"))];
      }
      const head = el("div"); head.append(el("h1", "Planera veckans mat"), el("p", "Välj hur mycket och vad ni äter. Smako föreslår recept som blir billiga att handla till just nu.", "lead"));
      const basic = live(el("section", null, "panel"), () => N.settings("basic"));
      const more = el("details", null, "panel more"); more.append(el("summary", "Fler val: allergier, butiker, matkök och ekologiskt"), live(el("div"), () => N.settings("advanced")));
      const own = live(el("section", null, "panel"), () => [el("h2", "Egna varor"), el("p", S.items.length ? `${S.items.length} egna varor räknas ihop med recepten.` : "Behöver du något mer än maten? Lägg till det i inköpslistan, så räknas allt ihop.", "meta"), link(S.items.length ? "Ändra egna varor" : "Lägg till egna varor", "#lista")]);
      const cta = live(el("div"), () => [button("Skapa matplan", async () => { if (await N.createPlan()) { screens.mat.editing = false; go("#mat"); render(); } }, "btn primary cta", { disabled: !S.location }), S.location ? null : el("p", "Ange postnummer först.", "hint")]);
      const nodes = [head, placePanel(), basic, more, own, sticky(cta)];
      if (N.planHasRecipes()) nodes.splice(1, 0, button("‹ Tillbaka till recepten", () => { screens.mat.editing = false; render(); }, "btn quiet small"));
      return nodes;
    },
    handla() {
      if (!S.plan) { const head = el("div"); head.append(el("h1", "Handla"), el("p", "Här hamnar din handlingslista, uppdelad per butik, när du har räknat ut en inköpslista eller skapat en matplan.", "lead")); const ways = el("div", null, "links"); ways.append(link("Skriv en inköpslista", "#lista"), link("Planera veckans mat", "#mat")); return [head, ways]; }
      const head = live(el("div"), () => { const b = N.basket(), box = el("div", null, "total"), text = el("div"); text.append(el("h1", "Handla"), el("p", `${b.store_count} ${b.store_count === 1 ? "butik" : "butiker"} · det billigaste vi hittade för hela listan`, "meta")); box.append(text, el("strong", N.totalText())); return box; });
      const changed = live(el("div"), () => N.itemsChanged() ? (() => { const p = el("section", null, "panel"); p.append(el("p", "Du har ändrat dina varor sedan listan räknades ut."), link("Räkna om i Inköpslista", "#lista")); return p; })() : null);
      const after = live(el("div"), () => N.afterShopping({ onPantry: () => go("#skafferi") }));
      const tools = el("div", null, "links"); tools.append(button("Börja om med en tom lista", () => { if (confirm("Ta bort den här handlingslistan?")) { N.forgetPlan(); go("#hem"); } }, "btn quiet small"));
      return [head, changed, live(el("div"), () => N.storesView()), after, tools];
    },
    skafferi() {
      const head = el("div"); head.append(el("h1", "Skafferi"), el("p", "Det du har hemma. Recepten använder det först, så du handlar mindre.", "lead"));
      return [head, N.pantryView()];
    },
    konto() {
      const head = el("div"); head.append(el("h1", "Konto"));
      return [head, N.accountView({ onPantry: () => go("#skafferi") })];
    },
  };

  function render() {
    for (const off of disposers) off(); disposers = [];
    for (const node of main.querySelectorAll(".items")) node.dispose?.();
    const name = (location.hash || "#hem").slice(1), screen = screens[name] ? name : "hem";
    main.replaceChildren(live(el("div"), () => N.errorView()), ...screens[screen]().flat().filter(Boolean));
    for (const tab of document.querySelectorAll(".tabs a")) { if (tab.dataset.tab === screen) tab.setAttribute("aria-current", "page"); else tab.removeAttribute("aria-current"); }
    window.scrollTo(0, 0);
  }
  function chrome() {
    placeButton.textContent = N.placeText();
    accountLink.textContent = N.accountLabel();
    busy.replaceChildren(N.busyView());
    const tab = document.querySelector('.tabs a[data-tab="lista"]'); tab.querySelector(".badge")?.remove();
    if (S.items.length) tab.append(el("span", String(S.items.length), "badge", { "aria-label": `${S.items.length} varor` }));
  }
  placeButton.addEventListener("click", () => {
    const head = el("div", null, "dialog-head"); head.append(el("h2", "Var handlar du?", null, { id: "place-title" }), button("Klar", () => dialog.close(), "btn small primary"));
    const body = el("div"); const draw = () => body.replaceChildren(N.storePicker()); draw(); const off = N.on(draw);
    dialog.replaceChildren(head, N.postcodeBox(), el("h4", "Butiker att jämföra"), body);
    dialog.addEventListener("close", off, { once: true }); dialog.showModal();
  });
  window.addEventListener("hashchange", render);
  N.on(chrome);
  N.start().then(() => { render(); chrome(); });
  render(); chrome();
})();

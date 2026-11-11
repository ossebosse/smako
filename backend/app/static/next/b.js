/* Alternativ B: a guide with one question per screen and one button to go on.
   The first answer decides the route: only a shopping list, or meals and a
   shopping list. "Fler val" opens everything else Smako can take into account. */
(() => {
  "use strict";
  const N = window.SmakoNext, { el, button, S, saved } = N;
  const main = document.getElementById("main"), next = document.getElementById("next"), back = document.getElementById("back"), busy = document.getElementById("busy");
  const stepLabel = document.getElementById("step"), bar = document.getElementById("bar"), dialog = document.getElementById("more-dialog");
  let disposers = [];
  const live = (node, build) => { const draw = () => node.replaceChildren(...[build()].flat().filter(Boolean)); draw(); disposers.push(N.on(draw)); return node; };
  const go = name => { if (location.hash === `#${name}`) render(); else location.hash = `#${name}`; };
  const head = (title, lead) => { const box = el("div"); box.append(el("h1", title)); if (lead) box.append(el("p", lead, "lead")); return box; };
  const flow = () => saved.flow === "mat" ? ["plats", "maltider", "mat", "varor"] : ["plats", "varor"];
  const results = () => N.planHasRecipes() ? ["recept", "handla"] : ["handla"];
  const setFlow = value => { saved.flow = value; N.persist(); go("plats"); };

  function openMore() {
    const top = el("div", null, "dialog-head"); top.append(el("h2", "Fler val", null, { id: "more-title" }), button("Klar", () => dialog.close(), "btn small primary"));
    const body = el("div"); const draw = () => body.replaceChildren(N.settings("advanced")); draw(); const off = N.on(draw);
    dialog.replaceChildren(top, body); dialog.addEventListener("close", off, { once: true }); dialog.showModal();
  }
  async function finish() { const ok = saved.flow === "mat" ? await N.createPlan() : await N.calculateList(); if (ok) go(results()[0]); }

  const screens = {
    start() {
      const options = el("div", null, "options");
      const option = (title, note, action, value) => { const b = button(null, () => setFlow(value), "option"); b.append(el("span", title, "option-title"), el("span", note, "option-note"), el("span", action, "option-go")); return b; };
      options.append(option("Bara handla", "Skriv vad du behöver. Smako letar upp de butiker där hela listan blir billigast.", "Skriv inköpslista ›", "handla"),
        option("Planera mat och handla", "Svara på ett par frågor och få recept för veckan och en inköpslista för alltihop.", "Planera veckans mat ›", "mat"));
      const resume = live(el("div"), () => { if (!S.plan) return null; const box = el("div", null, "summary"), recipes = S.plan.plan.personal.slots.filter(s => s.recipe).length;
        box.append(el("p", "Senast", "eyebrow"), el("p", `${recipes ? `${recipes} recept och inköpslista` : "Din inköpslista"} · ${N.totalText()}`), button("Öppna igen", () => go(results()[0]), "text-link")); return box; });
      const foot = el("p", null, "hint"); foot.append(el("a", "Skafferi, konto och sök varor finns i vanliga Smako", null, { href: "/personal?ui=standard" }));
      return { nodes: [head("Vad vill du göra?", "Smako jämför priserna i butikerna nära dig."), options, resume, foot] };
    },
    plats() {
      const stores = live(el("div"), () => { if (!S.location) return null; const more = el("details"); more.append(el("summary", "Välj butiker själv", "text-link"), N.storePicker()); more.open = screens.plats.open === true; more.addEventListener("toggle", () => { screens.plats.open = more.open; }); return more; });
      return { nodes: [head("Var handlar du?", "Vi jämför butikerna inom några kilometer från ditt postnummer."), N.postcodeBox(), stores], ready: () => Boolean(S.location), hint: "Ange postnummer och tryck Hitta butiker." };
    },
    maltider() {
      return { nodes: [head("Hur mycket mat?", "Middagar för veckan och hur många som äter."), live(el("div", null, "settings"), () => { const all = N.settings("basic"); return [...all.children].filter(n => n.classList.contains("counter") || n.classList.contains("hint")); })] };
    },
    mat() {
      const basics = live(el("div", null, "settings"), () => { const all = N.settings("basic"); return [...all.children].filter(n => !n.classList.contains("counter") && !n.classList.contains("hint")); });
      const allergy = live(el("div"), () => { const s = saved.settings, n = s.allergies.length + s.avoid.length; return el("p", n ? `Väljs bort: ${[...s.allergies, ...s.avoid].join(", ")}.` : "Inget är bortvalt.", "hint"); });
      return { nodes: [head("Vilken sorts mat?", "Smako väljer bland recepten som passar."), basics, allergy, button("Fler val: allergier, butiker, matkök och ekologiskt", openMore, "text-link")] };
    },
    varor() {
      const withMeals = saved.flow === "mat";
      return { nodes: [head(withMeals ? "Något mer att handla?" : "Vad behöver du?", withMeals ? "Lägg till det som inte hör till recepten, till exempel kaffe eller mjölk. Hoppa över om du inte behöver något." : "Skriv varan som du brukar säga den. Vill du ha ett visst märke väljer du en bestämd vara."), N.itemsEditor()],
        ready: () => withMeals || S.items.length > 0, hint: "Lägg till minst en vara.", action: withMeals ? "Skapa matplan" : "Hitta billigaste butikerna", onNext: finish };
    },
    recept() {
      if (!N.planHasRecipes()) return screens.handla();
      return { result: true, nodes: [head("Veckans recept", "Byt de rätter du inte vill ha. Inköpen räknas om varje gång."), live(el("div"), () => N.recipesView())], action: "Visa handlingslistan", onNext: () => go("handla") };
    },
    handla() {
      if (!S.plan) return screens.start();
      const top = live(el("div", null, "summary"), () => { const b = N.basket(); return [el("p", "Det billigaste vi hittade för hela listan", "eyebrow"), el("p", N.totalText(), "sum"), el("p", `${b.store_count} ${b.store_count === 1 ? "butik" : "butiker"} · bocka av medan du handlar`, "meta")]; });
      const links = el("div", null, "links"); links.append(button("Ändra varor", () => go("varor"), "text-link"), button("Börja om", () => { if (confirm("Ta bort den här handlingslistan?")) { N.forgetPlan(); go("start"); } }, "text-link"));
      return { result: true, nodes: [head("Handla"), top, live(el("div"), () => N.storesView()), links] };
    },
  };

  function render() {
    for (const off of disposers) off(); disposers = [];
    for (const node of main.querySelectorAll(".items")) node.dispose?.();
    let name = (location.hash || "#start").slice(1); if (!screens[name]) name = "start";
    if (!["start", "recept", "handla"].includes(name) && !saved.flow) name = "start";
    const screen = screens[name](), steps = flow(), index = steps.indexOf(name), resultSteps = results(), resultIndex = resultSteps.indexOf(name);
    main.replaceChildren(live(el("div"), () => N.errorView()), ...screen.nodes.flat().filter(Boolean));
    back.hidden = name === "start";
    back.onclick = () => go(index > 0 ? steps[index - 1] : resultIndex > 0 ? resultSteps[resultIndex - 1] : screen.result ? "varor" : "start");
    stepLabel.textContent = index >= 0 ? `Steg ${index + 1} av ${steps.length}` : screen.result ? "Klart" : "";
    bar.style.width = name === "start" ? "0" : index >= 0 ? `${Math.round(((index + 1) / (steps.length + 1)) * 100)}%` : "100%";
    next.replaceChildren();
    if (name !== "start" && (index >= 0 || screen.action)) {
      const box = live(el("div"), () => { const ready = screen.ready ? screen.ready() : true;
        return [button(screen.action || "Nästa", () => (screen.onNext ? screen.onNext() : go(steps[index + 1])), "btn primary cta", { disabled: !ready }), ready || !screen.hint ? null : el("p", screen.hint, "hint")]; });
      next.append(box);
    }
    window.scrollTo(0, 0);
  }
  window.addEventListener("hashchange", render);
  N.on(() => busy.replaceChildren(N.busyView()));
  N.start().then(render);
  render();
})();

"use strict";
(() => {
  const $ = (id) => document.getElementById(id);
  const form = $("product-search-form"), input = $("product-query"), results = $("product-search-results");
  const status = $("product-search-status"), more = $("product-search-more"), view = $("product-search-view");
  const coverage = $("product-search-coverage");
  let controller, sequence = 0, next = null, detailKey = null;
  const money = (value) => value == null ? "Inte jämförd" : `${Number(value).toLocaleString("sv-SE", {minimumFractionDigits: 2, maximumFractionDigits: 2})} kr`;
  const displayed = (price) => `${money(price.display_price ?? price.effective_price)}${price.display_price_unit ? `/${price.display_price_unit}` : ""}`;
  function node(tag, text, className) {
    const item = document.createElement(tag);
    if (text != null) item.textContent = text;
    if (className) item.className = className;
    return item;
  }
  function settings() {
    const memberships = [...document.querySelectorAll('input[name="membership"]:checked')].map((el) => el.value);
    const postal = $("postal-code").value.replace(/ /g, "");
    $("product-search-area").textContent = `${postal} · Medlemspriser ingår · Ändra`;
    return {postal_code: postal, memberships, membership_price_policy:"all_advertised"};
  }
  function priceLine(price) {
    const block = node("div", null, "product-context");
    block.append(node("strong", `${price.store_name} · ${displayed(price)}`));
    block.append(node("p", `${price.context_label}${price.membership_required ? ` · Medlemspris · ${price.membership_label}` : ""}`));
    if (price.unit_price != null) block.append(node("p", `${money(price.unit_price)}/${price.unit}`));
    if (price.comparison_reason) block.append(node("p", price.comparison_label));
    if (price.purchase_terms) {
      block.append(node("p", `Belagt varupris: ${money(price.quoted_price)}${["kg","l"].includes(price.quoted_price_unit) ? `/${price.quoted_price_unit}` : ` för ${price.quoted_quantity || 1} förpackning(ar)/styck`}.`));
      if (price.purchase_terms.variant_selection === "required") block.append(node("p", "Välj en kampanjmärkt variant i butiken. Inte närings- eller allergigodkänd som specifik produkt."));
      if (price.purchase_terms.deposit_status === "unknown") block.append(node("p", "Pant är inte fastställd. Ingen komplett köptotal visas."));
      if (price.purchase_terms.exclusions.length) block.append(node("p", `Undantag: ${price.purchase_terms.exclusions.join("; ")}`));
    }
    block.append(node("p", `Rapporterat grundpris (kan inkludera kampanj): ${money(price.regular_price)}${["kg","l"].includes(price.quoted_price_unit) ? `/${price.quoted_price_unit}` : ""}`));
    for (const offer of price.promotions) {
      const label = offer.membership_required ? `Medlemskampanj · ${offer.membership_label}` : "Kampanj";
      block.append(node("p", `${label}: ${offer.required_packages > 1 ? `${offer.required_packages} för ` : ""}${money(offer.price)}${["kg","l"].includes(price.quoted_price_unit) ? `/${price.quoted_price_unit}` : ""} · ${offer.description}${offer.membership_required ? " · Kräver angivet medlemskap" : ""}${offer.max_quantity ? ` · Max ${offer.max_quantity} ${offer.required_packages > 1 ? "köpgrupper" : "förpackningar"}` : ""}${offer.valid_from || offer.valid_to ? ` · Gäller ${offer.valid_from || "?"}–${offer.valid_to || "?"}` : " · Giltighetsdatum saknas"}`));
    }
    const source = node("details");
    source.append(node("summary", "Prisets källa och aktualitet"));
    source.append(node("p", price.availability_label));
    source.append(node("p", `${price.freshness === "AGING" ? "Äldre, fortfarande jämförbart underlag" : "Aktuellt underlag"} · Observerat ${price.observed_at ? new Date(price.observed_at).toLocaleString("sv-SE") : "okänt"}`));
    source.append(node("p", `Källa: ${price.source_provider || "saknas"}`));
    block.append(source);
    return block;
  }
  function showCoverage(chains) {
    coverage.replaceChildren();
    coverage.hidden = !chains.length;
    const current = chains.filter((chain) => chain.current_contexts > 0);
    coverage.append(node("p", current.length ? `Jämför just nu: ${current.map((chain) => chain.label).join(", ")}.` : "Inga kedjor har aktuellt jämförbart prisunderlag."));
    const missing = chains.filter((chain) => !chain.current_contexts);
    const reasons = new Map();
    missing.forEach((chain) => reasons.set(chain.status_label, [...(reasons.get(chain.status_label) || []), chain.label]));
    if (missing.length) coverage.append(node("p", [...reasons].map(([reason, labels]) => `${labels.join(", ")} jämförs inte: ${reason.toLocaleLowerCase("sv-SE")}.`).join(" ")));
    const details = node("details");
    details.append(node("summary", "Träffar och täckning per kedja"));
    chains.forEach((chain) => details.append(node("p", `${chain.label}: ${chain.status_label}.${chain.current_contexts && chain.stale_contexts ? " Äldre prisunderlag från ytterligare inköpsställen har uteslutits." : ""}`)));
    coverage.append(details);
  }
  function card(product, expanded) {
    const article = node("article", null, "product-result");
    const best = product.prices[0];
    article.append(node("h3", product.name), node("p", [product.brand, product.package].filter(Boolean).join(" · ")));
    article.append(node("strong", displayed({...best, display_price:product.display_price ?? product.best_price}), "product-result-price"));
    article.append(node("p", `${best.store_name} · ${best.context_label}`));
    if (best.membership_required) article.append(node("span", `Medlemspris · ${best.membership_label}`, "product-offer-badge"));
    else if (product.has_campaign) article.append(node("span", "Kampanj finns · se villkor", "product-offer-badge"));
    const details = node("details");
    details.open = expanded;
    details.append(node("summary", product.prices.length > 1 ? `Jämför samma produkt · ${product.prices.length} inköpsställen` : "Visa pris, kampanjer och källa"));
    if (product.prices.length > 1) details.append(node("p", "Samma verifierade streckkod och förpackning. Billigast just nu visas först."));
    else details.append(node("p", "Ingen ytterligare aktuell jämförelse för denna exakta produkt."));
    product.prices.forEach((price) => details.append(priceLine(price)));
    const link = node("a", "Öppna produktjämförelse");
    const url = new URL(location.href);
    url.searchParams.set("product", product.product_key);
    url.searchParams.set("q", product.gtin || product.name);
    url.hash = "product-search";
    link.href = url.pathname + url.search + url.hash;
    link.addEventListener("click", (event) => {
      event.preventDefault();
      history.pushState({}, "", link.href);
      detailKey = product.product_key;
      input.value = product.gtin || product.name;
      view.value = "relevance";
      void search();
    });
    details.append(link);
    if (expanded) {
      const alternatives = node("button", "Liknande produkter", "text-button");
      alternatives.type = "button";
      alternatives.addEventListener("click", () => {
        detailKey = null;
        input.value = product.name;
        history.pushState({}, "", `/?q=${encodeURIComponent(product.name)}#product-search`);
        void search();
      });
      details.append(alternatives);
    }
    article.append(details);
    if (window.SmakoPersonal) article.append(window.SmakoPersonal.productActions(product));
    return article;
  }
  async function search(append = false) {
    if (!input.value.trim()) return;
    controller?.abort();
    controller = new AbortController();
    const current = ++sequence;
    more.hidden = true;
    coverage.hidden = true;
    if (!append) results.replaceChildren();
    status.textContent = "Söker bland aktuella prisdata…";
    form.setAttribute("aria-busy", "true");
    const [selection, unit] = view.value.split(":");
    const payload = {query: input.value.trim(), ...settings(), limit: 20, offset: append ? next : 0,
      view: selection, unit: unit || null, product_key: detailKey};
    try {
      const response = await fetch("/api/product-search", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload), signal: controller.signal});
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Kontrollera söktext, streckkod och postnummer.");
      if (current !== sequence) return;
      showCoverage(data.chain_coverage || []);
      status.textContent = data.total ? `${data.total} produkter. ${data.semantics === "exact_identity" ? "Exakt produktjämförelse." : "Liknande alternativ – olika produkter jämförs inte som samma vara."}` : `${data.exact_gtin ? "Ingen exakt träff" : "Inga aktuella träffar"}. Prova ett annat produktnamn.`;
      data.results.forEach((product) => results.append(card(product, Boolean(detailKey) || data.semantics === "exact_identity")));
      next = data.next_offset;
      more.hidden = next == null;
    } catch (error) {
      if (error.name !== "AbortError" && current === sequence) status.textContent = error.message || "Sökningen kunde inte slutföras. Försök igen.";
    } finally {
      if (current === sequence) form.setAttribute("aria-busy", "false");
    }
  }
  form.addEventListener("submit", (event) => {event.preventDefault(); detailKey = null; void search();});
  view.addEventListener("change", () => {detailKey = null; void search();});
  more.addEventListener("click", () => void search(true));
  document.querySelectorAll('input[name="membership"], #postal-code').forEach((el) => el.addEventListener("change", () => {settings(); void search();}));
  function fromUrl() {
    const params = new URLSearchParams(location.search);
    if (!params.has("q")) return;
    input.value = params.get("q").slice(0, 120);
    detailKey = params.get("product");
    void search();
  }
  window.addEventListener("popstate", fromUrl);
  window.addEventListener("smako:compare-gtin", (event) => {
    detailKey = null;
    input.value = event.detail.gtin;
    view.value = "relevance";
    $("product-search").scrollIntoView({block: "start"});
    void search();
  });
  settings();
  fromUrl();
})();

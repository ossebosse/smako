const connectorRoot = document.querySelector("#connectors");
const summary = document.querySelector("#summary");
const errorBox = document.querySelector("#error");
const coverageRoot = document.querySelector("#store-coverage");
const coverageSummary = document.querySelector("#store-coverage-summary");
const physicalValidationRoot = document.querySelector("#physical-validation");
const priceContextRoot = document.querySelector("#price-contexts");
const priceContextSummary = document.querySelector("#price-context-summary");
const dailyRefreshRoot = document.querySelector("#daily-refresh");
const dailyRefreshSummary = document.querySelector("#daily-refresh-summary");
const priceUniverseSummary = document.querySelector("#price-universe-summary");

const formatTime = (value) => value ? new Date(value).toLocaleString("sv-SE") : "Aldrig";
const formatAge = (value) => value == null ? "Ingen aktiv snapshot" : `${value.toFixed(1)} h gammal`;

async function loadStatus() {
  try {
    const response = await fetch("/health/connectors", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const result = await response.json();
    summary.textContent = `${result.count} connectors · övergripande ${result.connector_status}`;
    connectorRoot.replaceChildren(...result.items.map((connector) => {
      const link = document.createElement("a");
      link.className = `card ${connector.status}`;
      link.href = `/admin/connectors/${encodeURIComponent(connector.chain)}`;

      const title = document.createElement("h2");
      title.textContent = connector.chain;
      const status = document.createElement("p");
      status.className = "status";
      const dot = document.createElement("span");
      dot.className = "dot";
      dot.setAttribute("aria-hidden", "true");
      status.append(dot, document.createTextNode(connector.status.toUpperCase()));
      const source = document.createElement("p");
      const strategy = connector.source_strategy || {};
      const basket = strategy.basket_primary;
      const offer = strategy.offers_primary;
      const enrichment = strategy.enrichment;
      source.textContent = basket
        ? `Basket source: ${basket.provider.toUpperCase()} · ${basket.channel}`
        : "Basket source saknas";
      const ownConnector = document.createElement("p");
      ownConnector.textContent = `OWN connector: ${connector.coverage || "okänd coverage"} · ${connector.metrics.products_parsed || 0} produkter`;
      const ownRoles = [
        basket?.provider === "own" ? "basket" : null,
        offer?.provider === "own" ? "offers" : null,
        enrichment?.provider === "own" ? "enrichment" : null,
      ].filter(Boolean);
      const ownRoleText = document.createElement("p");
      ownRoleText.className = "muted";
      ownRoleText.textContent = `OWN roller: ${ownRoles.length ? ownRoles.join(" + ") : "inga"}`;
      const offerText = document.createElement("p");
      offerText.className = "muted";
      offerText.textContent = offer
        ? `Offers source: ${offer.provider.toUpperCase()} · ${offer.channel} · fallback ${strategy.fallback_enabled ? "explicit tillåten" : "av"}`
        : `Offers source: ej konfigurerad · fallback ${strategy.fallback_enabled ? "explicit tillåten" : "av"}`;
      const age = document.createElement("p");
      age.className = "muted";
      age.textContent = `${formatAge(connector.data_age_hours)} · senast lyckad ${formatTime(connector.last_success_at)}`;
      link.append(title, status, source, ownConnector, ownRoleText, offerText, age);
      return link;
    }));
  } catch (error) {
    errorBox.hidden = false;
    errorBox.textContent = `Kunde inte läsa connectorstatus: ${error.message}`;
    summary.textContent = "Status otillgänglig";
  }
}

function metricCard(title, values) {
  const card = document.createElement("article");
  card.className = "metric-card";
  const heading = document.createElement("h3");
  heading.textContent = title;
  card.append(heading);
  for (const value of values) {
    const row = document.createElement("p");
    row.textContent = value;
    card.append(row);
  }
  return card;
}

async function loadStoreCoverage() {
  try {
    const response = await fetch("/stores/coverage?city=Lund", {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const report = await response.json();
    const evidenceLabel = report.official_evidence === "fresh_discovery"
      ? "färsk official discovery"
      : "senast sparade official discovery";
    coverageSummary.textContent = `${report.known_physical_stores} / ${report.physical_stores} fysiska butiker kända · ${report.basket_capable} basket-contexts · ${report.missing} saknade mappningar · ${evidenceLabel} ${formatTime(report.official_last_seen_at)}`;
    coverageRoot.replaceChildren(...Object.values(report.chains).map((chain) => metricCard(
      chain.chain.toUpperCase(),
      [
        `Fysiska: ${chain.known_physical_stores} / ${chain.official_physical_stores}`,
        `Basket: ${chain.basket_capable_contexts} · offers: ${chain.offers_only_contexts}`,
        `Saknade mappningar: ${chain.missing_mappings}`,
        `Locator health: ${report.discovery_health?.[chain.chain]?.status || "okänd"}`,
      ],
    )));
  } catch (caught) {
    coverageSummary.textContent = `Butikstäckning otillgänglig: ${caught.message}`;
  }
}

async function loadPhysicalValidation() {
  try {
    const response = await fetch("/physical-check/stores?city=Lund", {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const result = await response.json();
    const sampled = result.items.filter((store) => store.physical_observations > 0);
    physicalValidationRoot.replaceChildren(...(
      sampled.length
        ? sampled.map((store) => metricCard(
          `${store.chain.toUpperCase()} · ${store.name}`,
          [
            `Fysiska observationer: ${store.physical_observations}`,
            store.accuracy_score_available
              ? `Confidence: ${store.physical_sample_confidence}`
              : `Accuracy: otillräckligt stickprov (< ${store.minimum_sample_for_accuracy_score})`,
          ],
        ))
        : [metricCard("Inga stickprov ännu", ["Detta påverkar inte basket-eligibility."])]
    ));
  } catch (caught) {
    physicalValidationRoot.replaceChildren(
      metricCard("Status otillgänglig", [caught.message]),
    );
  }
}

async function loadDailyRefresh() {
  try {
    const response = await fetch("/operations/daily-refresh/status?city=Lund", {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const report = await response.json();
    dailyRefreshSummary.textContent = `${report.status.toUpperCase()} · ${report.basket_capable} basket-contexts · äldsta pris ${report.oldest_basket_price_age_hours?.toFixed(1) ?? "?"} h · varning ${report.warning_age_hours} h / stale ${report.stale_age_hours} h`;
    dailyRefreshRoot.replaceChildren(...Object.entries(report.chains).map(([chain, value]) => metricCard(
      chain.toUpperCase(),
      [
        `Fysiska: ${value.physical_stores}`,
        `Fresh full: ${value.fresh_full_basket_contexts} · aging full: ${value.aging_full_basket_contexts}`,
        `Stale/broken: ${value.stale_or_broken}`,
        value.alert || "Inget särskilt source-gaplarm",
      ],
    )));
  } catch (caught) {
    dailyRefreshSummary.textContent = `Daglig driftstatus otillgänglig: ${caught.message}`;
  }
}

async function loadPriceUniverse() {
  try {
    const response = await fetch("/price-universe/status?city=Lund", {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const status = await response.json();
    priceUniverseSummary.textContent = status.active
      ? `${status.status.toUpperCase()} · ${status.universe_id || "okänt ID"} · ${status.product_count ?? "?"} produkter · byggt ${formatTime(status.built_at)}`
      : "Inget aktivt prebuilt universe i denna process; meal requests bygger aldrig här.";
  } catch (caught) {
    priceUniverseSummary.textContent = `Universe-status otillgänglig: ${caught.message}`;
  }
}

async function loadPriceContexts() {
  try {
    const response = await fetch("/stores/price-contexts?city=Lund", {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const report = await response.json();
    priceContextSummary.textContent = `${report.explained_states} / ${report.physical_stores} butiker förklarade · unknown ${report.unknown} · ${report.basket_capable} basket-capable`;
    const stores = Object.values(report.chains).flatMap((chain) => chain.stores);
    priceContextRoot.replaceChildren(...stores.map((store) => {
      const row = document.createElement("tr");
      const name = document.createElement("td");
      name.textContent = `${store.chain.toUpperCase()} · ${store.name}`;
      const physical = document.createElement("td");
      physical.textContent = store.physical_status.toUpperCase();
      const state = document.createElement("td");
      state.textContent = store.state.toUpperCase();
      const source = document.createElement("td");
      const sourceName = store.price_source?.toUpperCase() || "Ingen";
      source.textContent = `${sourceName} · ${store.context_name || store.grocery_context_id || "inget context"}`;
      const coverage = document.createElement("td");
      coverage.textContent = store.coverage || "–";
      const freshness = document.createElement("td");
      freshness.textContent = store.fresh
        ? `${store.age_hours?.toFixed(1) ?? "?"} h`
        : (store.observed_at ? `stale · ${formatTime(store.observed_at)}` : "ingen prisobservation");
      const basket = document.createElement("td");
      basket.textContent = store.basket_eligible ? "JA" : "NEJ";
      const reason = document.createElement("td");
      reason.textContent = store.reason;
      row.append(name, physical, state, source, coverage, freshness, basket, reason);
      return row;
    }));
  } catch (caught) {
    priceContextSummary.textContent = `Pris-context-audit otillgänglig: ${caught.message}`;
  }
}

Promise.all([
  loadStatus(),
  loadDailyRefresh(),
  loadPriceUniverse(),
  loadStoreCoverage(),
  loadPriceContexts(),
  loadPhysicalValidation(),
]);

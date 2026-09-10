const chain = decodeURIComponent(location.pathname.split("/").filter(Boolean).at(-1) || "");
const title = document.querySelector("#title");
const statusText = document.querySelector("#status");
const metricRoot = document.querySelector("#metrics");
const warningsRoot = document.querySelector("#warnings");
const schemaFingerprint = document.querySelector("#schema-fingerprint");
const schemaDiff = document.querySelector("#schema-diff");
const runsTable = document.querySelector("#runs");
const errorsTable = document.querySelector("#errors");
const errorBox = document.querySelector("#error-message");
const sourceStrategy = document.querySelector("#source-strategy");

const formatTime = (value) => value ? new Date(value).toLocaleString("sv-SE") : "—";
const metricLabels = {
  products_parsed: "Produkter",
  parse_success_rate: "Parse success",
  price_coverage: "Priscoverage",
  package_quantity_coverage: "Paketcoverage",
  request_count: "Requests",
  runtime_ms: "Körtid (ms)",
};

function table(element, headers, rows) {
  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  headers.forEach(([label]) => {
    const th = document.createElement("th");
    th.textContent = label;
    headerRow.append(th);
  });
  thead.append(headerRow);
  const tbody = document.createElement("tbody");
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    headers.forEach(([, field, formatter]) => {
      const td = document.createElement("td");
      td.textContent = formatter ? formatter(row[field]) : (row[field] ?? "—");
      tr.append(td);
    });
    tbody.append(tr);
  });
  element.replaceChildren(thead, tbody);
}

async function loadConnector() {
  try {
    const response = await fetch(`/health/connectors/${encodeURIComponent(chain)}`, {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const result = await response.json();
    title.textContent = result.chain;
    document.title = `${result.chain} | Grocery Data`;
    statusText.textContent = `${result.status.toUpperCase()} · ${result.coverage || "coverage okänd"} · snapshot ${result.snapshot_id || "saknas"}`;

    const strategy = result.source_strategy || {};
    const formatSource = (source) => source
      ? `${String(source.provider).toUpperCase()} / ${source.channel}`
      : "—";
    const sourceRows = [
      ["Basket primary", formatSource(strategy.basket_primary)],
      ["Basket fallbacks", (strategy.basket_fallbacks || []).map(formatSource).join(", ") || "—"],
      ["Offers", formatSource(strategy.offers_primary)],
      ["Enrichment", formatSource(strategy.enrichment)],
      ["Basket eligible", strategy.basket_eligible == null ? "runtime-kontroll krävs" : (strategy.basket_eligible ? "ja" : "nej")],
      ["Fallback", strategy.fallback_enabled ? "explicit tillåten" : "av"],
      ["Vald provider", strategy.selected_provider || "ingen runtime-selection"],
    ];
    sourceStrategy.replaceChildren(...sourceRows.flatMap(([label, value]) => {
      const term = document.createElement("dt");
      term.textContent = label;
      const definition = document.createElement("dd");
      definition.textContent = value;
      return [term, definition];
    }));

    metricRoot.replaceChildren(...Object.entries(metricLabels).map(([field, label]) => {
      const card = document.createElement("article");
      card.className = "metric";
      const value = document.createElement("strong");
      const raw = result.metrics[field];
      value.textContent = field.endsWith("rate") || field.endsWith("coverage")
        ? `${((raw || 0) * 100).toFixed(1)} %`
        : (raw ?? 0).toLocaleString("sv-SE");
      const caption = document.createElement("p");
      caption.className = "muted";
      caption.textContent = label;
      card.append(value, caption);
      return card;
    }));

    const warnings = result.warnings.length ? result.warnings : ["Inga varningar"];
    warningsRoot.replaceChildren(...warnings.map((message) => {
      const item = document.createElement("li");
      item.textContent = message;
      return item;
    }));

    schemaFingerprint.textContent = `Fingerprint: ${result.schema_fingerprint || "saknas"}`;
    schemaDiff.hidden = !result.schema_diff;
    schemaDiff.textContent = result.schema_diff
      ? JSON.stringify(result.schema_diff, null, 2)
      : "";

    table(runsTable, [
      ["Start", "started_at", formatTime],
      ["Status", "status"],
      ["Produkter", "metrics", (metrics) => metrics?.products_parsed ?? 0],
      ["Fel", "error_summary"],
    ], result.recent_runs);
    table(errorsTable, [
      ["Felkod", "error_code"],
      ["Antal", "count"],
      ["Senast", "latest_at", formatTime],
      ["Exempel", "examples", (examples) => (examples || [])
        .map((example) => Object.entries(example)
          .map(([field, value]) => `${field}: ${value}`)
          .join(", "))
        .join(" · ") || "—"],
    ], result.recent_errors);
  } catch (error) {
    errorBox.hidden = false;
    errorBox.textContent = `Kunde inte läsa connectorn: ${error.message}`;
  }
}

loadConnector();

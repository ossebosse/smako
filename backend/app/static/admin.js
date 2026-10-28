"use strict";
(() => {
  const $ = id => document.getElementById(id);
  const number = value => new Intl.NumberFormat("sv-SE").format(value);
  const date = value => value ? new Intl.DateTimeFormat("sv-SE", {dateStyle:"short", timeStyle:"short", timeZone:"Europe/Stockholm"}).format(new Date(value)) : "Saknas";
  const labels = {fresh:"Färskt underlag", aging:"Äldre underlag", stale:"För gammalt underlag", missing:"Priser saknas", broken:"Fel i underlaget", succeeded:"Lyckades", failed:"Insamling misslyckad", running:"Pågår enligt körloggen", unknown:"Körhistorik saknas", attention:"Behöver tillsyn", campaign:"Giltiga kampanjer", expired:"Kampanjpriser saknas"};
  const scope = value => ({online_price:"Onlinepris", online_fulfillment:"Online / leverans", regional_online:"Regionalt onlinepris", regional:"Regionala erbjudanden", regional_context:"Regionala erbjudanden", physical_store:"Butikskopplat pris", store_specific:"Butikskopplat pris", store_linked:"Butikskopplat pris"}[String(value).toLowerCase()] || value || "Omfattning okänd");
  const node = (tag, text, cls) => {const n = document.createElement(tag); if (text != null) n.textContent = text; if (cls) n.className = cls; return n;};
  const badge = status => node("span", labels[status] || status, `badge ${status}`);
  let city = "Lund", data, busy = false, generation = 0;
  function field(list, title, value) {const div = node("div");div.append(node("dt", title), node("dd", value));list.append(div);}
  function context(c) {
    const box = node("div", null, "context"), head = node("div", null, "context-head");
    head.append(node("h3", c.name), badge(c.price_status));box.append(head);
    box.append(node("span", `${scope(c.scope)} · ${c.source || "Källa saknas"}`, "sub"));
    const list = node("dl");
    field(list, "Tillgängliga i Smako", `${number(c.available_prices)} priser`);
    field(list, "Tillgängliga baspriser", c.available_base_prices == null ? "Antal saknas" : number(c.available_base_prices));
    if(c.available_campaign_prices) field(list, "Verifierade kampanjpriser", number(c.available_campaign_prices));
    if(c.next_campaign_end) field(list, "Nästa kampanjslut (inklusive)", c.next_campaign_end);
    field(list, "Insamlade i aktiv snapshot", c.collected_prices == null ? "Antal saknas" : number(c.collected_prices));
    field(list, "Sparade i aktiv prisversion", number(c.retained_prices));
    field(list, "Prisunderlag observerat", date(c.observed_at));
    field(list, "Prisernas ålder", c.age_hours == null ? "Okänd" : `${number(Math.round(c.age_hours * 10) / 10)} timmar`);
    field(list, "Senaste insamling", labels[c.collection.status] || "Körhistorik saknas");
    field(list, "Senaste försök", date(c.collection.last_attempt_at || c.collection.started_at));
    field(list, "Senaste lyckade insamling", date(c.collection.last_success_at || (c.collection.status === "succeeded" ? c.collection.finished_at : null)));
    if(c.collection.next_fetch_at) field(list, "Nästa hämtning tidigast", date(c.collection.next_fetch_at));
    if(c.collection.failed_attempts) field(list, "Misslyckade försök i följd", number(c.collection.failed_attempts));
    if(c.collection.finished_at) field(list, "Insamling avslutad", date(c.collection.finished_at));
    if(c.collection.duration_seconds != null) field(list, "Tidsåtgång", `${number(Math.round(c.collection.duration_seconds / 60))} min`);
    box.append(list);
    if(c.attention_reasons.length) box.append(node("p", c.attention_reasons.join(" "), "reason"));
    if(c.collection.retained_snapshot) box.append(node("p", "Tidigare godkänt underlag finns kvar. Kvalificerade baspriser behålls tills de ersätts; kampanjpriser följer sina verifierade giltighetsdatum.", "sub"));
    if(c.campaign_valid) box.append(node("p", "Verifierade kampanjpriser följer erbjudandenas giltighetsdatum. Åldern visas separat och betyder i sig inte att insamlingen har misslyckats.", "sub"));
    if(c.collection.status === "unknown") box.append(node("p", "Ett verifierat insamlingsresultat saknas för detta underlag. Det betyder inte att insamlingen har misslyckats.", "sub"));
    if(c.collection.next_fetch_at) box.append(node("p", "Planerad tid är tidigaste nästa försök. En pågående insamling eller väntan efter ett fel kan påverka starttiden.", "sub"));
    if(!c.runtime_active) box.append(node("p", "Detta prisunderlag är inte aktivt i kommunens prisversion i Smako.", "sub"));
    box.append(node("p", c.context_id, "context-id"));return box;
  }
  function renderStores() {
    if (!data) return;
    const expanded = new Set([...$("stores").querySelectorAll("details[open]")].map(n => n.dataset.id));
    const query = $("search").value.toLocaleLowerCase("sv"), chain = $("chain").value;
    const rows = data.stores.filter(s => (!chain || s.chain === chain) && (!$("attention").checked || s.needs_attention) && `${s.name} ${s.chain} ${s.address || ""}`.toLocaleLowerCase("sv").includes(query));
    const fragment = document.createDocumentFragment();
    for (const s of rows) {
      const row = node("details", null, "store");row.dataset.id = s.id;row.open = expanded.has(s.id);
      const summary = node("summary"), name = node("span", s.name, "store-name");
      name.append(node("span", `${s.chain.toUpperCase()}${s.address ? ` · ${s.address}` : ""}`, "sub"));
      if(s.attention_reasons.length) name.append(node("span", s.attention_reasons.join(" "), "sub reason"));
      const prices = node("span", number(s.contexts.reduce((total,c) => total+c.available_prices,0)), "price-total");prices.append(node("span", "tillgängliga priser", "sub"));
      summary.append(node("span", "›", "arrow"), name, badge(s.status), prices);row.append(summary);
      if (!s.contexts.length) row.append(node("p", "Ingen verifierad priskälla är kopplad till butiken ännu.", "context"));
      for (const c of s.contexts) row.append(context(c));fragment.append(row);
    }
    if (!rows.length) fragment.append(node("p", data.stores.length ? "Inga butiker matchar filtret." : "Inga fysiska butiker finns registrerade för kommunen i denna databas.", "empty"));
    $("stores").replaceChildren(fragment);$("visible-count").textContent = `${rows.length} av ${data.stores.length} butiker`;
  }
  function render(payload) {
    data = payload;$("city-title").textContent = `i ${data.city}`;
    const previous = $("chain").value, chains = [...new Set(data.stores.map(s => s.chain))].sort();
    $("chain").replaceChildren(new Option("Alla kedjor", ""), ...chains.map(c => new Option(c.toUpperCase(),c)));
    if (chains.includes(previous)) $("chain").value = previous;
    $("metrics").replaceChildren(...[
      ["Tillgängliga priser", data.summary.available_prices, "Delade prisunderlag räknas en gång", "primary"],
      ["Fysiska butiker", data.summary.physical_stores, `Register och aktiva underlag i ${data.city}`, ""],
      ["Butiker med priser", data.summary.stores_with_prices, "Har ett tillgängligt prisunderlag", ""],
      ["Behöver tillsyn", data.summary.requiring_attention, "Insamlingsfel, åldersvarningar eller saknade priser", ""],
    ].map(([label, value, help, cls]) => {const n=node("div", null, `metric ${cls}`);n.append(node("span", label),node("strong",number(value)),node("small",help));return n;}));
    $("runtime-note").hidden = data.runtime_active;
    $("runtime-note").textContent = `Ingen aktiv prisversion är laddad för ${data.city} i denna applikation. Insamlade underlag visas separat och räknas inte som tillgängliga priser.`;
    $("other-panel").hidden = !data.other_contexts.length;$("other").replaceChildren(...data.other_contexts.map(context));
    $("policy").textContent = `Prisernas ålder varnas från ${data.warning_age_hours} timmar och markeras som gammal från ${data.stale_age_hours} timmar. Kvalificerade baspriser behålls tills de ersätts. Kampanjpriser i alla kedjor följer sina verifierade giltighetsdatum. Serverns ordinarie hämtning: ${data.server_collection_schedule || "Schema saknas"}. Willys-kataloger hämtas via Windowsreläets separata uppgift. Insamlingsfel visas separat även om priser fortfarande är giltiga. Uppdateras automatiskt var 60:e sekund. Tider visas i svensk tid.`;
    renderStores();$("updated").textContent = `Senast kontrollerat ${date(data.checked_at)} · ${data.city}`;
  }
  async function get(url, signal) {const response=await fetch(url,{credentials:"same-origin",cache:"no-store",signal});if(!response.ok) throw new Error(response.status===401 || response.status===403 ? "Admininloggningen behöver förnyas. Ladda om sidan för att logga in." : "Kunde inte hämta driftstatus. Försök igen.");return response.json();}
  async function refresh() {
    const current = ++generation, selected = city;
    busy=true;$("refresh").disabled=true;
    try {
      const payload = await get(`/api/admin/stores?city=${encodeURIComponent(selected)}`, AbortSignal.timeout(25000));
      if(current!==generation) return;
      render(payload);$("error").hidden=true;
      try {
        const ops=await get("/api/admin/status", AbortSignal.timeout(25000));
        if(current!==generation) return;
        $("technical").textContent=JSON.stringify(ops,null,2);
        $("operations").replaceChildren(...[
          ["Prisversion", ops.price_universe.status || "Okänd"],
          ["Senaste gemensamma refresh", date(ops.refresh.completed_at)],
          ["Nästa schemalagda refresh", date(ops.refresh.next_scheduled_at_utc)],
        ].map(([label,value])=>{const n=node("div");n.append(node("span",label,"sub"),node("strong",value));return n;}));
      } catch(error) {if(current===generation){$("operations").replaceChildren(node("p",error.message));$("technical").textContent="Driftöversikten kunde inte uppdateras.";}}
    } catch(error) {
      if(current!==generation) return;
      $("error").textContent=`${error.name === "TimeoutError" ? "Hämtningen tog för lång tid. Försök igen." : error.message} ${data ? "Visade uppgifter är från senaste lyckade hämtningen." : ""}`;$("error").hidden=false;
    } finally {if(current===generation){busy=false;$("refresh").disabled=false;}}
  }
  $("cities").addEventListener("click", event => {const button=event.target.closest("button[data-city]");if(!button || button.dataset.city===city)return;city=button.dataset.city;data=null;$("search").value="";$("chain").value="";$("stores").replaceChildren(node("p","Laddar butiker…","empty"));$("metrics").replaceChildren();$("other-panel").hidden=true;$("runtime-note").hidden=true;$("city-title").textContent=`i ${city}`;$("visible-count").textContent="";$("updated").textContent=`Hämtar ${city}…`;document.querySelectorAll("[data-city]").forEach(b=>b.setAttribute("aria-pressed",String(b.dataset.city===city)));refresh();});
  for(const id of ["search","chain","attention"]) $(id).addEventListener("input",renderStores);
  $("refresh").addEventListener("click",refresh);
  setInterval(()=>{if(!busy && !document.hidden) refresh();},60000);
  refresh();
})();

/* Smako UI-referens. Ren lokal demo: inga nätverksanrop, inga API-nycklar,
 * ingen persistens och ingen optimerare. Fältnamnen är INTE backendens DTO.
 * DOM skrivs med escapade värden; användartekst sätts med textContent/value.
 */
'use strict';
(() => {
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const clone = (obj) => JSON.parse(JSON.stringify(obj));
  const escape = (value) => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const icons = {
    pin: '<path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>',
    dinner: '<path d="M4 3v7m3-7v7M1 3v7c0 3 6 3 6 0M4 13v8M16 3v18m0-18c-5 3-5 10 0 10"/>',
    breakfast: '<path d="M3 9h14v5a6 6 0 0 1-6 6H9a6 6 0 0 1-6-6V9Zm14 1h2a3 3 0 0 1 0 6h-2M6 3v3m4-3v3m4-3v3M2 22h18"/>',
    snack: '<path d="M3 11h18a9 9 0 0 1-18 0Zm4-4 2 4m7-7-2 7M7 21h10"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
    chevron: '<path d="m9 5 7 7-7 7"/>',
    close: '<path d="m6 6 12 12M18 6 6 18"/>',
    pie: '<path d="M12 3v9h9A9 9 0 1 1 12 3Z"/><path d="M15 2a9 9 0 0 1 7 7h-7Z"/>',
    weight: '<path d="M7 8h10l4 13H3L7 8Z"/><circle cx="12" cy="5" r="3"/>',
    nutrition: '<path d="M4 21V11h3v10M11 21V4h3v17M18 21V8h3v13"/>',
    spark: '<path d="m13 2-9 12h7l-1 8 10-13h-7l1-7Z"/>',
    sliders: '<path d="M4 3v18M12 3v18M20 3v18M1 8h6m2 8h6m2-9h6"/>'
  };
  const svg = (name) => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${icons[name] || icons.sliders}</svg>`;
  function hydrateIcons(root = document) { $$('[data-icon]', root).forEach(el => { el.innerHTML = svg(el.dataset.icon); el.removeAttribute('data-icon'); }); }

  const mealNames = { dinner: 'Middag', breakfast: 'Frukost', snack: 'Mellanmål' };
  const categories = { vegetarian: 'Vegetarisk', chicken: 'Kyckling', fish: 'Fisk / skaldjur' };
  // Protein, kolhydrater och portionsvikt: skala synlig i användarens screenshots.
  // Fett och energi: enbart illustration från designbilden; verifiera mot projektet.
  const nutrientMeta = {
    protein: { label: 'Protein', unit: 'g', domainMax: 100 },
    carbs: { label: 'Kolhydrater', unit: 'g', domainMax: 400 },
    fat: { label: 'Fett', unit: 'g', domainMax: 100 },
    energy: { label: 'Energi', unit: 'kcal', domainMax: 1500 }
  };
  const weightMeta = { weight: { label: 'Portionsvikt', unit: 'g', domainMax: 3000 } };
  const emptyRange = () => ({ min: null, max: null });
  function newMeal(enabled, portions) {
    return { enabled, count: 5, portions, distribution: { diet: 'mixed', counts: { vegetarian: null, chicken: null, fish: null } }, weight: emptyRange(), nutrition: Object.fromEntries(Object.keys(nutrientMeta).map(k => [k, emptyRange()])) };
  }
  const stores = [
    { id: 'demo-w', name: 'Willys · exempelbutik', chain: 'Willys', km: 0.8, channel: 'Butikspris (demo)' },
    { id: 'demo-i', name: 'ICA · exempelbutik', chain: 'ICA', km: 1.6, channel: 'Butikspris (demo)' },
    { id: 'demo-c', name: 'Coop · exempelbutik', chain: 'Coop', km: 2.4, channel: 'Butikspris (demo)' },
    { id: 'demo-l', name: 'Lidl · exempelbutik', chain: 'Lidl', km: 4.2, channel: 'Butikspris (demo)' },
    { id: 'demo-o', name: 'Online · exempelbutik', chain: 'Online', km: null, channel: 'Onlinepris (demo)' }
  ];
  const preferenceLabels = { likes: 'Gillar / föredrar', dislikes: 'Ogillar · mjukt önskemål', excluded: 'Uteslut ingredienser · hårt krav', allergies: 'Allergier · hårt krav' };
  const state = {
    location: { ready: false, postcode: null, scope: 'radius', radiusKm: 3, manualIds: [] },
    maxStores: 2,
    meals: { dinner: newMeal(true, 4), breakfast: newMeal(false, 1), snack: newMeal(false, 1) },
    preferences: { likes: [], dislikes: [], excluded: [], allergies: [] },
    recipeStyle: 'existing-demo', ecoCostPercent: 0, organicAnimal: false, surplus: 'minimize-demo'
  };
  const fieldErrors = new Map();
  const fieldDrafts = new Map();
  const mealError = key => [...fieldErrors.entries()].filter(([k]) => k.startsWith(`${key}|`)).map(([,v]) => v).join(" ");
  const dialog = $('#settings-dialog');
  let modal = null;
  let returnFocus = null;
  let scrollY = 0;
  let lookupVersion = 0;
  let locationPending = false;
  const announce = (text) => { $('#live-message').textContent = text; };

  function availableStores() {
    if (!state.location.ready) return [];
    if (state.location.scope === 'manual') return stores.filter(s => state.location.manualIds.includes(s.id));
    if (state.location.scope === 'municipality') return stores;
    return stores.filter(s => s.km !== null && s.km <= state.location.radiusKm);
  }
  function rangeCount(meal) {
    return Object.values(meal.nutrition).reduce((n, r) => n + (r.min !== null || r.max !== null ? 1 : 0), 0);
  }
  function distributionError(config, total) {
    const counts = Object.values(config.counts);
    if (counts.some(v => v !== null && (!Number.isInteger(v) || v < 0 || v > total))) return `Ange heltal mellan 0 och ${total}, eller lämna tomt för Standard.`;
    const sum = counts.reduce((n, v) => n + (v ?? 0), 0);
    if (sum > total) return `Du har fördelat ${sum} av ${total} måltider. Minska antalen med ${sum - total}.`;
    if (config.diet !== 'mixed' && ((config.counts.chicken ?? 0) > 0 || (config.counts.fish ?? 0) > 0)) return 'Kostvalet kan inte kombineras med ett positivt antal kyckling- eller fiskrätter. Ändra kostval eller antal.';
    return '';
  }
  function stepper(mealKey, field, label, value, min, max) {
    const key = `${mealKey}-${field}`;
    return `<div class="stepper-row"><label for="${key}">${label}</label><div class="stepper"><button type="button" data-step="${mealKey}|${field}|-1" aria-label="Minska ${label.toLowerCase()} för ${mealNames[mealKey]}" ${value <= min ? 'disabled' : ''}>−</button><input id="${key}" data-meal-number="${mealKey}|${field}" type="number" min="${min}" max="${max}" step="1" value="${escape(fieldDrafts.get(`${mealKey}|${field}`) ?? value)}" aria-describedby="${mealKey}-field-error"><button type="button" data-step="${mealKey}|${field}|1" aria-label="Öka ${label.toLowerCase()} för ${mealNames[mealKey]}" ${value >= max ? 'disabled' : ''}>+</button></div></div>`;
  }
  function renderMeals() {
    $('#meals').innerHTML = Object.entries(state.meals).filter(([,m]) => m.enabled).map(([key,m]) => {
      const allocated = Object.values(m.distribution.counts).reduce((a, v) => a + (v ?? 0), 0);
      const distCustomized = m.distribution.diet !== 'mixed' || Object.values(m.distribution.counts).some(v => v !== null);
      return `<section class="card meal-card" id="meal-${key}" aria-labelledby="heading-${key}"><div class="meal-header"><div class="section-heading">${svg(key)}<h2 id="heading-${key}">${mealNames[key]}</h2></div><span class="small">${m.count * m.portions} portioner</span></div>
      ${stepper(key, 'count', key === 'dinner' ? 'Antal middagar' : 'Antal tillfällen', m.count, key === 'dinner' ? 0 : 1, 7)}
      ${stepper(key, 'portions', 'Portioner per rätt', m.portions, 1, 6)}
      <p class="error" id="${key}-field-error" role="alert">${escape(mealError(key))}</p>
      <p class="error" id="${key}-distribution-error" role="alert">${escape(distributionError(m.distribution, m.count))}</p>
      <div class="meal-actions">
        <button type="button" class="btn meal-action" data-modal="${key}|distribution"><span class="action-name">${svg('pie')} Fördelning</span><span class="action-state">${distCustomized ? `${allocated} av ${m.count} valda` : 'Standard'}</span></button>
        <button type="button" class="btn meal-action" data-modal="${key}|weight"><span class="action-name">${svg('weight')} Portionsvikt</span><span class="action-state">${m.weight.min === null && m.weight.max === null ? 'Standard' : `${m.weight.min ?? '–'}–${m.weight.max ?? '–'} g`}</span></button>
        <button type="button" class="btn meal-action" data-modal="${key}|nutrition"><span class="action-name">${svg('nutrition')} Näringsvärden</span><span class="action-state">${rangeCount(m) ? `${rangeCount(m)} egna intervall` : 'Standard'}</span></button>
      </div></section>`;
    }).join('');
  }
  function renderLocation() {
    $('#location-details').hidden = !state.location.ready;
    $('#radius-field').hidden = state.location.scope !== 'radius';
    const selected = availableStores();
    $('#store-chips').innerHTML = [...new Set(selected.map(s => s.chain))].map(chain => `<span class="store-chip">${escape(chain)}</span>`).join('') || '<span class="help">Inga butiker valda</span>';
    $('#store-count').textContent = `${selected.length} exempelbutiker ingår i jämförelsen. Det är inte antalet butiker du måste besöka.`;
  }
  function renderSummary() {
    const lines = [
      ['Område', state.location.ready ? 'Lund · demo' : 'Välj postnummer'],
      ['Jämför', `${availableStores().length} butiker`],
      ['Handla i', `Max ${state.maxStores} ${state.maxStores === 1 ? 'butik' : 'butiker'}`],
      ...Object.entries(state.meals).filter(([,m]) => m.enabled).map(([key,m]) => [mealNames[key], `${m.count} × ${m.portions} portioner`]),
      ['Ekologisk kostnadsandel', `Minst ${state.ecoCostPercent} %`]
    ];
    $('#summary-lines').innerHTML = lines.map(([label, value]) => `<div class="summary-line"><span>${escape(label)}</span><strong>${escape(value)}</strong></div>`).join('');
  }
  function updateNumber(mealKey, field, value) {
    const min = field === 'count' && mealKey === 'dinner' ? 0 : 1;
    const max = field === 'count' ? 7 : 6;
    if (value === '' || !Number.isInteger(Number(value)) || Number(value) < min || Number(value) > max) {
      fieldErrors.set(`${mealKey}|${field}`, `${field === 'count' ? 'Antal' : 'Portioner'}: ange heltal mellan ${min} och ${max}.`);
      fieldDrafts.set(`${mealKey}|${field}`, value);
      $(`#${mealKey}-field-error`).textContent = mealError(mealKey);
      return false;
    }
    fieldErrors.delete(`${mealKey}|${field}`);
    fieldDrafts.delete(`${mealKey}|${field}`);
    $(`#${mealKey}-field-error`).textContent = mealError(mealKey);
    state.meals[mealKey][field] = Number(value);
    return true;
  }
  function renderPreferences() {
    $('#preference-tags').innerHTML = Object.entries(state.preferences).flatMap(([key, values]) => values.map(v => `<span class="preference-tag ${['excluded','allergies'].includes(key) ? 'hard' : ''}">${escape(preferenceLabels[key].split(' · ')[0])}: ${escape(v)}</span>`)).join('');
  }
  function preferenceFields(values, prefix) {
    return Object.entries(preferenceLabels).map(([key, label]) => `<div class="field"><label for="${prefix}-${key}">${label}</label><input id="${prefix}-${key}" data-preference="${key}" value="${escape(values[key].join(', '))}" placeholder="Separera med kommatecken"></div>`).join('');
  }
  const parseList = text => [...new Set(text.split(',').map(x => x.trim()).filter(Boolean))];

  function showDialog(title, description, body, footer) {
    returnFocus = document.activeElement;
    dialog.innerHTML = `<div class="dialog-layout"><header class="dialog-header"><div><h2 id="dialog-title" tabindex="-1">${escape(title)}</h2><p class="help" id="dialog-description">${escape(description)}</p></div><button type="button" class="icon-btn" data-cancel aria-label="Stäng utan att spara">${svg('close')}</button></header><div class="dialog-body">${body}</div><footer class="dialog-footer">${footer}</footer></div>`;
    // Native dialog gör bakgrunden inert och hanterar fokusgränsen. Lås även sidskroll.
    scrollY = window.scrollY;
    document.body.style.position = 'fixed';
    document.body.style.top = `-${scrollY}px`;
    document.body.style.width = '100%';
    dialog.showModal();
    $('#dialog-title', dialog).focus();
  }
  function closeDialog() {
    if (!dialog.open) return;
    dialog.close();
    document.body.style.position = '';
    document.body.style.top = '';
    document.body.style.width = '';
    window.scrollTo(0, scrollY);
    if (returnFocus?.isConnected) returnFocus.focus({ preventScroll: true });
    modal = null;
  }
  const defaultFooter = '<button class="btn" type="button" data-cancel>Avbryt</button><button class="btn primary" id="modal-save" type="button">Klart</button>';
  function rangeMarkup(key, meta, value) {
    return `<section class="range-card" data-range-key="${key}"><div class="range-card-heading"><h3>${meta.label}</h3><span class="range-status">Standard</span></div><div class="range-fields">${['min','max'].map(bound => `<div><label for="${key}-${bound}">${bound === 'min' ? 'Min' : 'Max'}</label><div class="unit-input"><input type="number" id="${key}-${bound}" data-range-number="${key}|${bound}" min="0" max="${meta.domainMax}" step="1" value="${value[bound] ?? ''}" placeholder="Ingen ${bound}" aria-describedby="${key}-range-help ${key}-range-error"><span>${meta.unit}</span></div></div>`).join('')}</div>
      <div class="range-track" style="--low:0;--high:100"><div class="range-active"></div>${['min','max'].map(bound => `<input type="range" class="dual-range" data-range-slider="${key}|${bound}" min="0" max="${meta.domainMax}" step="1" value="${value[bound] ?? (bound === 'min' ? 0 : meta.domainMax)}" aria-label="${meta.label}, ${bound === 'min' ? 'lägsta' : 'högsta'} gräns i ${meta.unit}">`).join('')}</div><div class="range-ends"><span>0 ${meta.unit}</span><span>${meta.domainMax} ${meta.unit}</span></div><div class="range-bottom"><span class="help" id="${key}-range-help">Tomt fält = standard.</span><button class="btn text" data-range-reset="${key}" type="button">Återställ standard</button></div><p class="error" id="${key}-range-error" role="alert"></p></section>`;
  }
  function rangeErrors(key, r, meta) {
    const group = $(`[data-range-key="${key}"]`, dialog);
    if ($$('input[type="number"]', group).some(el => el.validity.badInput)) return 'Ange ett tal eller lämna fältet tomt.';
    if (Object.values(r).some(v => v !== null && (!Number.isFinite(v) || v < 0 || v > meta.domainMax || !Number.isInteger(v)))) return `Ange heltal mellan 0 och ${meta.domainMax} ${meta.unit}, eller lämna tomt.`;
    if (r.min !== null && r.max !== null && r.min > r.max) return 'Min får inte vara större än max.';
    return '';
  }
  function updateRangeVisual(key) {
    const r = modal.draft[key];
    const meta = modal.meta[key];
    const group = $(`[data-range-key="${key}"]`, dialog);
    const lo = Math.max(0, Math.min(meta.domainMax, r.min ?? 0));
    const hi = Math.max(0, Math.min(meta.domainMax, r.max ?? meta.domainMax));
    const track = $('.range-track', group);
    track.style.setProperty('--low', (lo / meta.domainMax) * 100);
    track.style.setProperty('--high', (hi / meta.domainMax) * 100);
    $$('[data-range-slider]', group).forEach(input => {
      const bound = input.dataset.rangeSlider.split('|')[1];
      input.value = bound === 'min' ? lo : hi;
      input.setAttribute('aria-valuetext', r[bound] === null ? `Standard, ingen ${bound}-gräns` : `${r[bound]} ${meta.unit}`);
    });
    $('.range-status', group).textContent = r.min === null && r.max === null ? 'Standard' : 'Eget intervall';
    const error = rangeErrors(key, r, meta);
    $(`#${key}-range-error`, group).textContent = error;
    $$('[data-range-number]', group).forEach(input => input.setAttribute('aria-invalid', error ? 'true' : 'false'));
    $('#modal-save', dialog).disabled = Object.entries(modal.meta).some(([k, m]) => Boolean(rangeErrors(k, modal.draft[k], m)));
  }
  function distributionMarkup() {
    const d = modal.draft;
    return `<div class="field"><label for="diet">Kostval</label><select id="diet"><option value="mixed" ${d.diet === 'mixed' ? 'selected' : ''}>Blandat</option><option value="vegetarian" ${d.diet === 'vegetarian' ? 'selected' : ''}>Vegetariskt</option><option value="vegan" ${d.diet === 'vegan' ? 'selected' : ''}>Veganskt</option></select></div><p class="help" style="margin-top:12px">Standard låter planeraren välja återstående rätter. Ett eget antal 0 betyder inga rätter av den typen. Vegetariskt tillåter ägg och mejeri; veganskt utesluter animalier.</p><div class="distribution-intro"><strong id="allocation-status"></strong><div class="distribution-meter"><span id="allocation-meter"></span></div></div>
    ${Object.entries(categories).map(([key,label]) => `<div class="distribution-row"><div><label for="dist-${key}">${label}</label><button type="button" class="btn text" data-dist-reset="${key}">Återställ standard</button></div><div class="stepper"><button type="button" data-dist-step="${key}|-1" aria-label="Minska antal ${label}">−</button><input type="number" id="dist-${key}" data-dist-number="${key}" min="0" max="${modal.total}" step="1" placeholder="Standard" value="${d.counts[key] ?? ''}"><button type="button" data-dist-step="${key}|1" aria-label="Öka antal ${label}">+</button></div></div>`).join('')}<p class="error" id="allocation-error" role="alert"></p><p class="help" style="margin-top:14px">Egna antal delar på totalt ${modal.total} måltider. Standard är inte samma sak som 0.</p><button type="button" class="btn text full" id="reset-distribution">Återställ hela fördelningen</button>`;
  }
  function updateDistribution() {
    const sum = Object.values(modal.draft.counts).reduce((n,v) => n + (v ?? 0), 0);
    $('#allocation-status', dialog).textContent = `${sum} av ${modal.total} måltider fördelade · ${Math.max(0, modal.total - sum)} kvar`;
    $('#allocation-meter', dialog).style.width = `${modal.total ? Math.min(100, (sum / modal.total) * 100) : 0}%`;
    const error = distributionError(modal.draft, modal.total);
    $('#allocation-error', dialog).textContent = error;
    $('#modal-save', dialog).disabled = Boolean(error);
  }
  function openMealModal(meal, kind) {
    const m = state.meals[meal];
    if (kind === 'distribution') {
      modal = { meal, kind, draft: clone(m.distribution), total: m.count };
      showDialog(`${mealNames[meal]} · Fördelning`, 'Välj kost och hur måltiderna ska fördelas. Ändringar sparas med Klart.', distributionMarkup(), defaultFooter);
      updateDistribution();
    } else {
      const isWeight = kind === 'weight';
      modal = { meal, kind, meta: isWeight ? weightMeta : nutrientMeta, draft: isWeight ? { weight: clone(m.weight) } : clone(m.nutrition) };
      showDialog(`${mealNames[meal]} · ${isWeight ? 'Portionsvikt' : 'Näringsvärden'}`, isWeight ? 'Uppskattad tillagad, ätbar vikt per portion. Dra i reglagen eller skriv min och max.' : 'Egna gränser per portion. Dra i reglagen eller skriv min och max. Tomma fält behåller standard.', Object.entries(modal.meta).map(([key, meta]) => rangeMarkup(key, meta, modal.draft[key])).join(''), defaultFooter);
      Object.keys(modal.meta).forEach(updateRangeVisual);
    }
  }
  function openStoreModal() {
    const selected = availableStores().map(s => s.id);
    modal = { kind: 'stores', draft: new Set(selected) };
    showDialog('Välj specifika butiker', 'Illustrativa butiker, inte en verklig butikskartläggning. Klart byter till egna butiksval.', stores.map(s => `<label class="store-row"><span><strong>${escape(s.name)}</strong><span class="help">${s.km === null ? 'Position saknas' : `cirka ${s.km.toLocaleString('sv-SE')} km`} · ${s.channel}</span></span><input type="checkbox" data-store="${s.id}" ${selected.includes(s.id) ? 'checked' : ''}></label>`).join('') + '<p class="error" id="selection-error" role="alert"></p>', defaultFooter);
    $('#modal-save', dialog).disabled = selected.length === 0;
  }
  function uiOnlySnapshot() {
    return {
      _notice: 'Endast prototypens UI-modell. Inte ett befintligt API-kontrakt.',
      location: { ...clone(state.location), selectedDemoStoreIds: availableStores().map(s => s.id) },
      maxStores: state.maxStores,
      meals: Object.fromEntries(Object.entries(state.meals).filter(([,m]) => m.enabled).map(([key,m]) => [key, clone(m)])),
      preferences: clone(state.preferences), recipeStyle: state.recipeStyle,
      ecoCostPercent: state.ecoCostPercent, organicAnimal: state.organicAnimal, surplus: state.surplus
    };
  }
  function planError() {
    if (locationPending) return 'Vänta tills butikssökningen är klar.';
    if (!state.location.ready) return 'Sök fram butiker för ditt postnummer först.';
    if (!availableStores().length) return 'Välj minst en butik.';
    for (const [key, m] of Object.entries(state.meals)) {
      if (!m.enabled) continue;
      if (mealError(key)) return `${mealNames[key]}: ${mealError(key)}`;
      const err = distributionError(m.distribution, m.count);
      if (err) return `${mealNames[key]}: ${err}`;
    }
    if (!Object.values(state.meals).filter(m => m.enabled).some(m => m.count > 0)) return 'Välj minst en måltid.';
    if ($('#eco-error').textContent) return 'Kontrollera den ekologiska kostnadsandelen.';
    return '';
  }

  $('#location-form').addEventListener('submit', async event => {
    event.preventDefault();
    const version = ++lookupVersion;
    const value = $('#postcode').value.replace(/\s/g, '');
    state.location.ready = false;
    renderLocation(); renderSummary();
    if (!/^\d{5}$/.test(value)) { $('#location-error').textContent = 'Ange fem siffror, till exempel 222 25.'; $('#postcode').setAttribute('aria-invalid','true'); return; }
    $('#location-error').textContent = '';
    $('#postcode').setAttribute('aria-invalid','false');
    const button = $('#find-stores');
    locationPending = true;
    button.disabled = true; button.textContent = 'Söker…';
    $('#location-form').setAttribute('aria-busy','true');
    await new Promise(resolve => setTimeout(resolve, 320)); // Endast illustrerad laddning.
    if (version !== lookupVersion) return;
    locationPending = false;
    button.disabled = false; button.textContent = 'Hitta butiker';
    $('#location-form').removeAttribute('aria-busy');
    if (value !== '22225') { $('#location-error').textContent = 'Prototypen har bara exempeldata för 222 25. Detta säger inget om Smakos verkliga täckning.'; return; }
    state.location.ready = true; state.location.postcode = value;
    $('#postcode').value = '222 25';
    renderLocation(); renderSummary();
    $('#plan-error').textContent = '';
    announce(`${availableStores().length} exempelbutiker visas.`);
  });
  $('#postcode').addEventListener('input', () => {
    ++lookupVersion; locationPending = false;
    $('#find-stores').disabled = false; $('#find-stores').textContent = 'Hitta butiker';
    $('#location-form').removeAttribute('aria-busy');
    state.location.ready = false;
    state.location.manualIds = []; state.location.postcode = null;
    $('#location-error').textContent = '';
    renderLocation(); renderSummary();
  });
  $('#scope').addEventListener('change', event => { state.location.scope = event.target.value; renderLocation(); renderSummary(); });
  $('#radius').addEventListener('change', event => { state.location.radiusKm = Number(event.target.value); renderLocation(); renderSummary(); });
  $('#choose-stores').addEventListener('click', openStoreModal);
  $('#store-limit').addEventListener('click', event => {
    const button = event.target.closest('[data-limit]'); if (!button) return;
    state.maxStores = Number(button.dataset.limit);
    $$('[data-limit]').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
    renderSummary();
  });
  $('#meals').addEventListener('click', event => {
    const open = event.target.closest('[data-modal]');
    if (open) { openMealModal(...open.dataset.modal.split('|')); return; }
    const button = event.target.closest('[data-step]'); if (!button) return;
    const [meal, field, change] = button.dataset.step.split('|');
    if (updateNumber(meal, field, state.meals[meal][field] + Number(change))) {
      const selector = `[data-step="${button.dataset.step}"]`;
      renderMeals(); renderSummary();
      const replacement = $(selector); if (replacement && !replacement.disabled) replacement.focus({ preventScroll: true });
      else $(`#${meal}-${field}`).focus({ preventScroll: true });
    }
  });
  $('#meals').addEventListener('input', event => {
    if (!event.target.matches('[data-meal-number]')) return;
    const [meal, field] = event.target.dataset.mealNumber.split('|');
    if (updateNumber(meal, field, event.target.value)) {
      const m = state.meals[meal];
      const card = $(`#meal-${meal}`);
      $('.meal-header .small', card).textContent = `${m.count * m.portions} portioner`;
      $(`#${meal}-distribution-error`).textContent = distributionError(m.distribution, m.count);
      const hasOwn = m.distribution.diet !== 'mixed' || Object.values(m.distribution.counts).some(v => v !== null);
      $(`[data-modal="${meal}|distribution"] .action-state`).textContent = hasOwn ? `${Object.values(m.distribution.counts).reduce((n,v) => n + (v ?? 0), 0)} av ${m.count} valda` : 'Standard';
      $$('[data-step]', card).forEach(button => {
        const [, f, delta] = button.dataset.step.split('|');
        const min = f === 'count' && meal === 'dinner' ? 0 : 1;
        const max = f === 'count' ? 7 : 6;
        button.disabled = Number(delta) < 0 ? m[f] <= min : m[f] >= max;
      });
      renderSummary();
    }
  });
  $$('[data-enable]').forEach(input => input.addEventListener('change', () => {
    const key = input.dataset.enable;
    state.meals[key].enabled = input.checked;
    renderMeals(); renderSummary();
    announce(`${mealNames[key]} ${input.checked ? 'tillagd under middag. Egna inställningar visas där.' : 'borttagen från planen. Dina inställningar finns kvar under denna session.'}`);
  }));
  $$('[data-jump]').forEach(button => button.addEventListener('click', () => {
    if (button.dataset.jump !== 'meals') $('#extras').open = true;
    const target = $(`#${button.dataset.jump}`);
    target.scrollIntoView({ block: 'start', behavior: 'instant' });
    target.setAttribute('tabindex', '-1'); target.focus({ preventScroll: true });
  }));
  $('#manual-preference-fields').innerHTML = preferenceFields(state.preferences, 'manual');
  $('#manual-preference-fields').addEventListener('input', event => {
    if (!event.target.dataset.preference) return;
    state.preferences[event.target.dataset.preference] = parseList(event.target.value);
    renderPreferences();
  });
  const exampleText = 'Gillar kyckling, ogillar koriander, måste undvika jordnötter';
  $('#use-example').addEventListener('click', () => { $('#taste-text').value = exampleText; $('#taste-text').focus(); });
  $('#interpret').addEventListener('click', () => {
    const exactExample = $('#taste-text').value.trim().toLocaleLowerCase('sv-SE') === exampleText.toLocaleLowerCase('sv-SE');
    modal = { kind: 'preferences', draft: exactExample ? { likes: ['kyckling'], dislikes: ['koriander'], excluded: ['jordnötter'], allergies: [] } : clone(state.preferences) };
    showDialog('Granska dina val', exactExample ? 'DEMOEXEMPEL – inte en faktisk AI-tolkning. Jordnötter är här ett uttryckligt uteslutningskrav, inte en automatiskt antagen allergi.' : 'Ingen tolkningsmotor är ansluten i prototypen. Redigera fälten manuellt eller använd den fasta exempeltexten.', `<div class="flow">${preferenceFields(modal.draft, 'review')}<p class="warning">Kontrollera särskilt uteslutningar och allergier före tillämpning. Ogillar får aldrig ersätta ett hårt krav.</p></div>`, '<button class="btn" data-cancel type="button">Avbryt</button><button class="btn primary" id="modal-save" type="button">Tillämpa granskade val</button>');
  });
  function setEco(value) {
    if (value === '' || !Number.isInteger(Number(value)) || Number(value) < 0 || Number(value) > 100) { $('#eco-error').textContent = 'Ange ett heltal mellan 0 och 100 %.'; return; }
    $('#eco-error').textContent = ''; state.ecoCostPercent = Number(value); $('#eco-number').value = value; $('#eco-range').value = value; renderSummary();
  }
  $('#eco-number').addEventListener('input', event => setEco(event.target.value));
  $('#eco-range').addEventListener('input', event => setEco(event.target.value));
  $('#organic-animal').addEventListener('change', event => { state.organicAnimal = event.target.checked; });
  $('#recipe-style').addEventListener('change', event => { state.recipeStyle = event.target.value; });
  $('#surplus').addEventListener('change', event => { state.surplus = event.target.value; });
  $('#generate').addEventListener('click', () => {
    const error = planError(); $('#plan-error').textContent = error;
    if (error) return;
    modal = { kind: 'preview' };
    showDialog('Dina val är redo · demo', 'Detta är endast prototypens UI-modell. Ingen matplan har optimerats, inga priser har hämtats och ingenting har skickats eller sparats.', '<p>Vid integration kopplar Codex denna knapp till Smakos befintliga flöde för plan och inköpslista.</p><details class="disclosure" open><summary>Visa UI-testdata, inte API-payload</summary><pre id="snapshot"></pre></details>', '<button class="btn primary" data-cancel type="button">Tillbaka till mina val</button>');
    $('#snapshot', dialog).textContent = JSON.stringify(uiOnlySnapshot(), null, 2);
  });
  $$('[data-info]').forEach(button => button.addEventListener('click', () => {
    modal = { kind: 'info' };
    showDialog(button.dataset.info, 'Befintlig navigation ska bevaras.', '<p>Detta är en fristående designreferens. Vid integration ska länken behålla sin verkliga destination i Smako, inte öppna denna dialog.</p>', '<button class="btn primary" data-cancel type="button">Stäng</button>');
  }));

  // Håll Tab/Shift+Tab inom dialogen även när webbläsaren annars skulle
  // skicka fokus till sin adressrad efter sista kontrollen.
  dialog.addEventListener('keydown', event => {
    if (event.key !== 'Tab') return;
    const controls = $$('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], summary, [tabindex]:not([tabindex="-1"])', dialog)
      .filter(el => el.getClientRects().length > 0 && el.tabIndex >= 0);
    const first = controls[0];
    const last = controls[controls.length - 1];
    if (!first) { event.preventDefault(); $('#dialog-title', dialog).focus(); return; }
    if (event.shiftKey && (document.activeElement === first || !controls.includes(document.activeElement))) {
      event.preventDefault(); last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault(); first.focus();
    }
  });
  dialog.addEventListener('cancel', event => { event.preventDefault(); closeDialog(); });
  dialog.addEventListener('click', event => {
    if (event.target === dialog) { const r = dialog.getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) closeDialog(); return; }
    if (event.target.closest('[data-cancel]')) { closeDialog(); return; }
    const reset = event.target.closest('[data-range-reset]');
    if (reset) { const key = reset.dataset.rangeReset; modal.draft[key] = emptyRange(); $$(`[data-range-key="${key}"] input[type="number"]`, dialog).forEach(el => { el.value = ''; }); updateRangeVisual(key); return; }
    const distReset = event.target.closest('[data-dist-reset]');
    if (distReset) { const key = distReset.dataset.distReset; modal.draft.counts[key] = null; $(`#dist-${key}`, dialog).value = ''; updateDistribution(); return; }
    const distStep = event.target.closest('[data-dist-step]');
    if (distStep) { const [key, delta] = distStep.dataset.distStep.split('|'); modal.draft.counts[key] = Math.max(0, Math.min(modal.total, (modal.draft.counts[key] ?? 0) + Number(delta))); $(`#dist-${key}`, dialog).value = modal.draft.counts[key]; updateDistribution(); return; }
    if (event.target.id === 'reset-distribution') { modal.draft = { diet: 'mixed', counts: { vegetarian: null, chicken: null, fish: null } }; $('#diet', dialog).value = 'mixed'; $$('[data-dist-number]', dialog).forEach(el => { el.value = ''; }); updateDistribution(); return; }
    if (event.target.id !== 'modal-save' || event.target.disabled) return;
    const kind = modal.kind;
    const meal = modal.meal;
    if (kind === 'nutrition') state.meals[meal].nutrition = clone(modal.draft);
    if (kind === 'weight') state.meals[meal].weight = clone(modal.draft.weight);
    if (kind === 'distribution') state.meals[meal].distribution = clone(modal.draft);
    if (kind === 'stores') { state.location.manualIds = [...modal.draft]; state.location.scope = 'manual'; $('#scope').value = 'manual'; }
    if (kind === 'preferences') {
      state.preferences = Object.fromEntries(Object.keys(preferenceLabels).map(key => [key, parseList($(`#review-${key}`, dialog).value)]));
      $('#manual-preference-fields').innerHTML = preferenceFields(state.preferences, 'manual'); renderPreferences();
    }
    // Stäng före omrendering och återställ fokus till den nya motsvarande knappen.
    closeDialog(); renderMeals(); renderLocation(); renderSummary();
    if (meal) $(`[data-modal="${meal}|${kind}"]`).focus({ preventScroll: true });
    announce('Dina val har uppdaterats.');
  });
  dialog.addEventListener('input', event => {
    const target = event.target;
    if (target.dataset.rangeNumber) {
      const [key, bound] = target.dataset.rangeNumber.split('|');
      modal.draft[key][bound] = target.value === '' ? null : Number(target.value);
      updateRangeVisual(key);
    }
    if (target.dataset.rangeSlider) {
      const [key, bound] = target.dataset.rangeSlider.split('|');
      const other = bound === 'min' ? 'max' : 'min';
      let value = Number(target.value);
      if (modal.draft[key][other] !== null) value = bound === 'min' ? Math.min(value, modal.draft[key][other]) : Math.max(value, modal.draft[key][other]);
      modal.draft[key][bound] = value;
      $(`#${key}-${bound}`, dialog).value = value;
      updateRangeVisual(key);
    }
    if (target.dataset.distNumber) { modal.draft.counts[target.dataset.distNumber] = target.value === '' ? null : Number(target.value); updateDistribution(); }
  });
  dialog.addEventListener('change', event => {
    if (event.target.id === 'diet') { modal.draft.diet = event.target.value; updateDistribution(); }
    if (event.target.dataset.store) {
      if (event.target.checked) modal.draft.add(event.target.dataset.store); else modal.draft.delete(event.target.dataset.store);
      $('#selection-error', dialog).textContent = modal.draft.size ? '' : 'Välj minst en butik.';
      $('#modal-save', dialog).disabled = modal.draft.size === 0;
    }
  });
  hydrateIcons(); renderMeals(); renderLocation(); renderSummary(); renderPreferences();
})();

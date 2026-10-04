"use strict";

(() => {

  const $ = (id) => document.getElementById(id);

  const money = (v) => `${Number(v).toLocaleString("sv-SE", {minimumFractionDigits:2, maximumFractionDigits:2})} kr`;

  const number = (v) => v==null||v===""||!Number.isFinite(Number(v))?"okänd":Number(v).toLocaleString("sv-SE", {maximumFractionDigits:2});

  const names = {dinner:"Middag", breakfast:"Frukost", snack:"Mellanmål"};

  const profileLabels = {likes:"Gillar / föredrar", dislikes:"Ogillar – mjukt önskemål", exclusions:"Uteslut ingredienser – hårt matval", allergies:"Allergier – även deklarerade spår"};

  const proteinNames = {vegetarian:"Vegetarisk", chicken:"Kyckling", fish:"Fisk / skaldjur", meat:"Övrigt kött"};

  let privateState = null, saved = null, extras = [], busy = false, parsedText = "", scanner = null, swapTarget = null;
  const recipeControls = window.SmakoRecipes.controls($('complete-recipe-controls'),{personal:true});

  function el(tag, text, cls) { const n=document.createElement(tag); if(text != null)n.textContent=text; if(cls)n.className=cls; return n; }

  function button(text, action, primary=false) {const b=el("button",text,primary?"primary-button":"secondary-button");b.type="button";b.addEventListener("click",()=>void task(()=>action(b)));return b;}

  function field(label, input) {input.setAttribute("aria-label",label);const l=el("label",label);l.append(input);return l;}

  function input(type, value, attrs={}) {const n=el("input");n.type=type;n.value=value??"";Object.assign(n,attrs);return n;}

  function select(values,value) {const n=el("select");for(const [v,label] of values){const o=el("option",label);o.value=v;n.append(o);}n.value=value;return n;}

  function details(title, child) {const n=el("details");n.append(el("summary",title),child);return n;}

  function focusView(){const target=document.querySelector('[data-view]:not([hidden]) .personal-total, [data-view]:not([hidden]) h1');if(target){target.tabIndex=-1;target.focus({preventScroll:true});}}

  function notify(text) {$('personal-status').textContent=text;}

  function show(view) {document.querySelectorAll("[data-view]").forEach(n=>n.hidden=n.dataset.view!==view);document.querySelectorAll(".personal-nav [data-open]").forEach(n=>{if(n.dataset.open===view)n.setAttribute("aria-current","page");else n.removeAttribute("aria-current");});window.scrollTo({top:0,behavior:"instant"});}

  document.querySelectorAll("[data-open]").forEach(n=>n.addEventListener("click",e=>{e.preventDefault();show(n.dataset.open);}));

  async function api(url,payload,method="POST") {
    const planning=payload!==undefined&&((url==="/api/plans"&&payload.personal)||/^\/api\/personal\/plans\/[^/]+\/change$/.test(url));
    const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),planning||url.startsWith("/api/plan-jobs/")?600000:90000);
    try {
      const pending=planning?window.SmakoRecipes.pendingJob("personal"):null;
      let r=await fetch(pending?.url||url,{method:pending||payload===undefined?"GET":method,headers:{"Content-Type":"application/json",...(planning?{Prefer:"respond-async","X-Request-ID":crypto.randomUUID()}:{})},body:pending||payload===undefined?undefined:JSON.stringify(payload),signal:controller.signal,cache:"no-store"});
      if(planning||url.startsWith("/api/plan-jobs/"))r=await window.SmakoRecipes.poll(r,{scope:"personal",signal:controller.signal,onProgress:notify,context:planning?{kind:url==="/api/plans"?"create":"change"}:null});
      const d=await r.json();
      if(!r.ok){const message=typeof d.detail==="string"?d.detail:Array.isArray(d.detail)?d.detail.map(e=>e.msg).join(" · "):"Begäran kunde inte genomföras.";const error=new Error(`${d.code==="DATA_BLOCKED"?"Underlag saknas: ":""}${message}${r.headers.get("X-Request-ID")?` Fel-ID: ${r.headers.get("X-Request-ID")}`:""}`);error.code=d.code;error.diagnostics=d.planning_diagnostics;throw error;}
      return d;
    } catch(e){if(e.name==="AbortError")throw new Error("Svarstiden överskreds. Ladda om för att återansluta till samma beräkning. Dina val och tidigare plan finns kvar.");throw e;} finally{clearTimeout(timer);}
  }

  function renderDiagnostics(d) {
    const box=window.SmakoRecipes.diagnostics(d);if(!box)return;box.id="planning-diagnostics";
    if(d.estimate_alternatives?.length){box.append(el("p","Näringsuppskattningar är av. Ett separat prov fann enskilda alternativ med sådant underlag; detta innebär inte att hela menyn är genomförbar."),button("Visa valet för näringsuppskattningar",async()=>{show("choices");$('allow-nutrition-estimates').scrollIntoView({block:"center"});$('allow-nutrition-estimates').focus();}));}
    $("personal-status").after(box);
  }
  async function task(work) {

    if(busy)return;busy=true;$("data-blocked-actions")?.remove();$("planning-diagnostics")?.remove();notify("Arbetar…");

    const controls=[...document.querySelectorAll("button")].filter(n=>!n.disabled);controls.forEach(n=>n.disabled=true);

    try {await work();notify("");} catch(e){notify(e.message||"Åtgärden kunde inte slutföras.");if(e.diagnostics)renderDiagnostics(e.diagnostics);if(e.code==="DATA_BLOCKED"){const choices=el("div",null,"personal-actions");choices.id="data-blocked-actions";choices.append(button("Ändra mina val",async()=>show("choices")),button("Granska berörda behov",async()=>{const box=el("div");box.append(el("h2","Underlag för berörda ingrediensbehov"));const rows=e.diagnostics?.missing_needs||[];for(const row of rows)box.append(el("p",`${names[row.meal_type]} · ${row.recipe}: ${row.ingredient}, ${number(row.quantity)} ${row.unit}. ${row.reason}`));if(!rows.length)box.append(el("p","Se receptens beredningshinder i blockeringsfördelningen. Ingen produktändring har gjorts."));openDialog(box);}),button("Gå tillbaka",async()=>show(saved?"plan":"choices")));$("personal-status").after(choices);}$('personal-status').scrollIntoView({block:"nearest"});}

    finally {busy=false;controls.forEach(n=>{if(n.isConnected)n.disabled=false;});$('generate-plan').textContent="Skapa plan och inköpslista";requestAnimationFrame(()=>{if(document.activeElement?.matches('.skip-link'))focusView();});}

  }

  async function refreshState(){privateState=await api("/api/personal/state");renderPantry();}

  function listText(value){return value.split(/[,;\n]/).map(v=>v.trim()).filter(Boolean);}

  function profile(prefix="profile") {return Object.fromEntries(Object.keys(profileLabels).map(k=>[k,listText($(`${prefix}-${k}`).value)]));}

  function putProfile(value,prefix="profile"){Object.keys(profileLabels).forEach(k=>$(`${prefix}-${k}`).value=(value?.[k]||[]).join(", "));}

  function profileFields(container,prefix) {for(const [k,label] of Object.entries(profileLabels)){const n=input("text","");n.id=`${prefix}-${k}`;n.maxLength=1500;container.append(field(`${label} (kommaseparerat)`,n));}}

  profileFields($('profile-fields'),"profile");

  const limitLabels = {min_weight_g:"Min tillagad portionsvikt (g)",max_weight_g:"Max tillagad portionsvikt (g)",min_protein_g:"Min protein (g)",max_protein_g:"Max protein (g)",min_carbs_g:"Min kolhydrater (g)",max_carbs_g:"Max kolhydrater (g)",min_fat_g:"Min fett (g)",max_fat_g:"Max fett (g)",max_kcal:"Max energi (kcal)"};

  for(const [type,label] of Object.entries(names)){

    const box=el("div",null,"personal-card");box.append(el("h2",label));const grid=el("div",null,"personal-grid");

    const count=input("number",type==="dinner"?5:0,{min:"0",max:"7",required:true});count.id=`${type}-count`;

    const servings=input("number",type==="dinner"?4:1,{min:"1",max:"8",required:true});servings.id=`${type}-servings`;

    const diet=select([["mixed","Blandat"],["vegetarian","Vegetariskt (ägg/mejeri tillåts)"],["vegan","Veganskt"]],"mixed");diet.id=`${type}-diet`;

    grid.append(field("Antal tillfällen (0–7)",count),field("Portioner per tillfälle",servings),field("Kostval",diet));box.append(grid);

    const options=el("div");const distribution=el("div",null,"personal-grid");

    for(const [key,title] of Object.entries(proteinNames)){const n=input("number","",{min:"0",max:"7"});n.id=`${type}-${key}`;distribution.append(field(`${title} – antal`,n));}

    options.append(el("p","Tomma delval är fria. Angivna antal ska rymmas i måltidstypens tillfällen. Huvudproteinkällan visas för varje recept."),distribution);

    const taste=el("div",null,"personal-grid");profileFields(taste,type);options.append(details("Egna smakval och ytterligare hårda uteslutningar",taste));

    const limits=el("div");limits.append(el("p","Frivilliga gränser per portion av denna måltidstyp. Portionsvikt betyder uppskattad tillagad ätbar vikt. Råvikt, tillagningsutbyte och näring hålls separata."),el("p","Utan uppskattningsläge krävs kvalificerade produktdeklarationer och granskad kall beredning. Med det uttryckliga valet nedan kan även dokumenterade kokta middagar och bekräftade generiska skafferivaror beräknas. Saknad slutvikt, fel beredningsform eller olösta ingredienser stoppar berörda krav.","data-note"));const lg=el("div",null,"personal-grid");for(const [key,title] of Object.entries(limitLabels)){const n=input("number","",{min:"0",max:key.includes("kcal")?"4000":key.includes("weight")?"3000":"500",step:"any"});n.id=`${type}-${key}`;lg.append(field(title,n));}limits.append(lg);options.append(details("Portionsvikt och näringsgränser",limits));

    const organic=input("checkbox","");organic.id=`${type}-organic`;options.append(field("Kräv ekologiska animalier för denna måltidstyp",organic));

    box.append(details("Fördelning, egna smakval och gränser",options));$('meal-settings').append(box);

  }

  for(const [v,label] of [["ICA_STAMMIS","ICA Stammis"],["COOP_MEMBER","Coop"],["WILLYS_PLUS","Willys Plus"],["HEMKOP_MEMBER","Hemköp"],["CITYGROSS_MEMBER","City Gross"],["LIDL_PLUS","Lidl Plus"]]){const n=input("checkbox",v);n.name="membership";const f=field(label,n);f.className="check-label";$('memberships').append(f);}

  function readMeals(){return Object.keys(names).map(t=>({meal_type:t,count:Number($(`${t}-count`).value),servings:Number($(`${t}-servings`).value),diet:$(`${t}-diet`).value,profile:profile(t),distribution:Object.fromEntries(Object.keys(proteinNames).filter(k=>$(`${t}-${k}`).value!=="").map(k=>[k,Number($(`${t}-${k}`).value)])),limits:Object.fromEntries(Object.keys(limitLabels).map(k=>[k,$(`${t}-${k}`).value===""?null:Number($(`${t}-${k}`).value)])),organic_animals:$(`${t}-organic`).checked}));}

  function requestPayload({standalone=false}={}) {

    if(!privateState)throw new Error("Gästskafferiet måste kunna läsas innan beräkning.");

    if($('profile-text').value.trim()!==parsedText)throw new Error("Tolka och granska beskrivningen före tillämpning, eller töm fritexten och redigera fälten direkt.");

    if($('unresolved-text').value.trim())throw new Error("Beskrivningen innehåller otolkade val. För in dem i rätt fält före tillämpning.");

    const meals=standalone?[]:readMeals();
    if(!recipeControls.validate()){$('personal-form').reportValidity();throw new Error("Kontrollera receptvalens intervall.");}

    return {...(standalone?{}:recipeControls.values()),purchase_planning_mode:$("purchase-planning-mode").value,postal_code:$('postal-code').value.trim(),recipes:meals.find(m=>m.meal_type==="dinner")?.count||0,servings:meals.find(m=>m.meal_type==="dinner")?.servings||1,max_stores:Number($('max-stores').value),memberships:[...document.querySelectorAll('input[name="membership"]:checked')].map(n=>n.value),diversity_mode:$('mode').value,varied_budget_percent:Number($('varied-budget').value),strategy:"optimized",personal:{profile:profile(),meals,extras,pantry_revision:privateState.revision,allow_nutrition_estimates:$('allow-nutrition-estimates').checked,organic_percent:Number($('organic-percent').value),organic_animals:$('organic-animals').checked,surplus_mode:$('surplus-mode').value}};

  }

  function putChoices(request){recipeControls.restore(request);$("purchase-planning-mode").value=request.purchase_planning_mode||"exact";const spec=request.personal;if(!spec)return;$('allow-nutrition-estimates').checked=spec.allow_nutrition_estimates===true;putProfile(spec.profile);$('profile-text').value="";parsedText="";for(const meal of spec.meals){const t=meal.meal_type;$(`${t}-count`).value=meal.count;$(`${t}-servings`).value=meal.servings;$(`${t}-diet`).value=meal.diet;putProfile(meal.profile,t);Object.keys(proteinNames).forEach(k=>$(`${t}-${k}`).value=meal.distribution[k]??"");Object.keys(limitLabels).forEach(k=>$(`${t}-${k}`).value=meal.limits[k]??"");$(`${t}-organic`).checked=meal.organic_animals;}$('organic-percent').value=spec.organic_percent;$('organic-animals').checked=spec.organic_animals;$('surplus-mode').value=spec.surplus_mode;$('mode').value=request.diversity_mode;$('max-stores').value=request.max_stores;$('postal-code').value=request.postal_code;$('varied-budget').value=request.varied_budget_percent;document.querySelectorAll('input[name="membership"]').forEach(n=>n.checked=request.membership_programs.includes(n.value));}

  $('personal-form').addEventListener("submit",e=>{e.preventDefault();void task(async()=>{const payload=requestPayload();window.SmakoRecipes.storage.set("smako.personal.requestDraft",payload);$('generate-plan').textContent="Skapar din gemensamma plan…";notify("Alla måltider räknas mot samma korg. En stor plan kan ta flera minuter. Dina krav och senaste sparade plan behålls medan du väntar.");const result=await api("/api/plans",payload);await accept(result.saved||result);show("plan");});});

  $('interpret-profile').addEventListener("click",()=>void task(async()=>{const parsed=await api("/api/personal/interpret-profile",{text:$('profile-text').value});putProfile(parsed.profile);parsedText=$('profile-text').value.trim();$('unresolved-label').hidden=!parsed.unresolved.length;$('unresolved-text').value=parsed.unresolved.join("\n");}));

  $('save-profile').addEventListener("click",()=>void task(async()=>{requestPayload();privateState=await api("/api/personal/profile",{revision:privateState.revision,profile:profile(),save_explicitly:true},"PUT");renderPantry();}));

  function openDialog(content){$('dialog-body').replaceChildren(content);if(!$('personal-dialog').open)$('personal-dialog').showModal();}

  function stopScanner(){if(scanner){scanner.stop();scanner=null;}}

  $('dialog-close').addEventListener("click",()=>{$('personal-dialog').close();stopScanner();});$('personal-dialog').addEventListener("close",stopScanner);window.addEventListener("pagehide",stopScanner);document.addEventListener("visibilitychange",()=>{if(document.hidden)stopScanner();});

  function extraDialog(product=null,campaign=false){const box=el("div");box.append(el("h2",campaign?"Villkorat kampanjval":product?"Lägg till exakt vara":"Lägg till generisk vara"));const query=input("text",product?.name||"",{maxLength:120,required:true});if(product)query.readOnly=true;const amount=input("number",(campaign?1:product?.package_quantity||1),{min:"0.001",max:"100000",step:"any",required:true});const unit=select([["g","gram"],["ml","milliliter"],["st","stycken"]],(campaign?"st":product?.package_unit||"g"));if(campaign)unit.disabled=true;const properties=input("text","");const use=input("checkbox","");const explanation=el("p","Mängden är ett ytterligare behov. Hela förpackningar väljs vid beräkningen.");box.append(field("Vara",query),field("Önskad mängd",amount),field("Enhet",unit),explanation,field("Bekräftade egenskaper (semikolon mellan val)",properties),field("Använd även skafferi för denna extrarad",use));if(campaign){use.disabled=true;explanation.textContent="Välj en kampanjmärkt variant i butiken enligt erbjudandets undantag och villkor. Hela kampanjgrupper debiteras. Näring och allergener är inte godkända.";}let interpreted=Boolean(product),original=query.value;

    if(!product)box.append(button("Tolka egenskaper",async()=>{const d=await api("/api/personal/interpret-extra",{text:query.value});properties.value=d.properties.join("; ");interpreted=true;original=query.value;}));

    box.append(button("Bekräfta och lägg till",async()=>{if(!interpreted||original!==query.value)throw new Error("Tolka egenskaperna innan du bekräftar varan.");if(!amount.checkValidity()||!query.checkValidity())throw new Error("Ange varunamn och en positiv mängd.");extras.push({id:crypto.randomUUID(),kind:campaign?"campaign":product?"exact":"generic",query:query.value,quantity:Number(amount.value),unit:unit.value,product_key:product?.product_key||null,properties:properties.value.split(/[;\n]/).map(s=>s.trim()).filter(Boolean),confirmed:true,use_pantry:campaign?false:use.checked,food:!/(servett|toalettpapper|hushållspapper|diskmedel|diskborste|bakplåtspapper|avfallspåsar|soppåsar)/i.test(query.value)});renderExtras();$('personal-dialog').close();show("shopping");},true));openDialog(box);}

  $('generic-extra').addEventListener("click",()=>extraDialog());

  function renderExtras(){const out=$('extras-list');out.replaceChildren();for(const row of extras){const card=el("article",null,"personal-card");card.append(el("strong",`${row.query} · ${number(row.quantity)} ${row.unit}`),el("p",`${row.kind==="campaign"?"Villkorat kampanjval":row.kind==="exact"?"Exakt produkt låst":"Generisk vara"}${row.properties.length?` · ${row.properties.join(" · ")}`:""} · ${row.use_pantry?"Skafferi får användas":"Ska köpas utöver recepten"}`));card.append(button("Ta bort extrarad",async()=>{extras=extras.filter(e=>e.id!==row.id);renderExtras();}));out.append(card);} }

  $('calculate-extras').addEventListener("click",()=>void task(async()=>{if(saved){await change("extras",{extras});}else{await accept(await api("/api/plans",requestPayload({standalone:true})));}show("shopping");}));

  async function accept(envelope){saved=envelope;extras=structuredClone(saved.request.personal.extras);putChoices(saved.request);try{localStorage.setItem("smako.personal.lastPlan",saved.plan_id);}catch(_){}history.replaceState({},"",`/personal#plan=${encodeURIComponent(saved.plan_id)}`);await refreshState();renderPlan();renderExtras();}

  async function change(action,fields={}){if(!saved)throw new Error("Skapa en plan först.");const result=await api(`/api/personal/plans/${encodeURIComponent(saved.plan_id)}/change`,{revision:saved.revision,pantry_revision:privateState.revision,action,...fields});saved=result.saved;privateState=result.state;extras=structuredClone(saved.request.personal.extras);renderPlan();renderPantry();renderExtras();if(!document.querySelector("dialog[open]"))focusView();}

  function renderPlan(){const plan=saved.plan, personal=plan.personal;if(!personal)return;const out=$('plan-content');out.replaceChildren();document.querySelector('.personal-intro').hidden=true;const top=el("div",null,"personal-card");const filled=personal.slots.filter(s=>s.recipe),dinners=filled.filter(s=>s.meal_type==="dinner").length;top.append(el("h1","Din plan"),el("p",`${dinners} middagar · ${filled.length-dinners} övriga måltider · ${plan.portions} portioner${personal.empty_slots?` · ${personal.empty_slots} tomma tillfällen`:""}`),el("div",`${plan.optimized_basket.verification_status==="VERIFIED_WITH_ESTIMATES"?"ca ":""}${money(plan.optimized_basket.total)}`,"personal-total"),el("p",`${plan.optimized_basket.verification_status==="VERIFIED_WITH_ESTIMATES"?"Uppskattad full inköpskostnad":"Beräknad full inköpskostnad"} · ${plan.optimized_basket.store_count} av max ${saved.request.max_stores} inköpsställen`));plan.optimized_basket.stores.forEach(g=>top.append(el("p",`${g.store_name}: ${money(g.subtotal)}`)));const actions=el("div",null,"personal-actions");actions.append(button("Öppna inköpslistan",async()=>show("shopping"),true),button("Räkna om med aktuellt skafferi/pris",()=>change("recalculate")),button("Ny plan",async()=>show("choices")));top.append(actions,el("p",`Revision ${saved.revision}. Receptbyte och uttrycklig omräkning sparar en ny revision. Tidigare resultat bevaras.`,"recipe-plan-revision"));const searchNotice=window.SmakoRecipes.searchNotice(plan,saved.request.diversity_mode);if(searchNotice)top.append(searchNotice);if(plan.optimized_basket.stores.some(g=>g.items.some(i=>i.conditional_variant_choice)))top.append(el("p","Villkorad inköpsplan: välj kampanjmärkta varianter enligt radernas villkor. Inte ett verifierat slutkvitto."));if(saved.prices_changed_since_creation||saved.price_contexts_changed_since_creation)top.append(el("p","Sparade priser visas. Prisunderlaget har ändrats; räkna om för aktuell korg.","data-note"));out.append(top);const comparison=el("div");for(const row of personal.checks.same_menu_comparisons||[]){comparison.append(el("p",row.status==="FEASIBLE"?`Samma recept, skafferibidrag och extrabehov med max ${row.max_stores} inköpsställen: ${money(row.total)}. ${row.stores.map(s=>s.name).join(" · ")}`:`Samma meny med max ${row.max_stores} inköpsställen: ingen genomförbar korg hittades med dina krav.`));}if(comparison.children.length)out.append(details("Samma meny i färre butiker",comparison));

    const summary=el("p",`Skafferibidrag: ${personal.allocations.length?personal.allocations.map(a=>`${number(a.quantity)} ${a.unit} ${a.name}`).join(" · "):"Inget allokerat"}. Detta är mängder från verkligt lager, ingen påhittad besparing.`);out.append(summary);

    [...personal.slots].sort((a,b)=>a.day-b.day||Object.keys(names).indexOf(a.meal_type)-Object.keys(names).indexOf(b.meal_type)).forEach(slot=>{const card=el("article",null,"personal-card");card.append(el("p",`Dag ${slot.day} · ${names[slot.meal_type]}`,"eyebrow"),el("h2",slot.recipe?.name||"Tomt måltidstillfälle"));if(slot.recipe){const protein=personal.checks.distribution.find(d=>d.slot_id===slot.id)?.protein;const mealLabel=window.SmakoRecipes.mealDescription(slot.recipe,protein);card.append(el("p",`${slot.recipe.servings} portioner${mealLabel?` · ${mealLabel}`:""}`));const nutrition=personal.checks.nutrition.find(n=>n.slot_id===slot.id);if(nutrition?.values?.protein_g!=null){card.append(el("p",`${window.SmakoRecipes.nutritionNumber(nutrition.values.protein_g,nutrition.status)} g protein per portion · ${nutrition.status==="ESTIMATED"?"spårbar uppskattning":"produktdeklarationer"}`));if(!slot.recipe.design)card.append(window.SmakoRecipes.nutritionInformation(nutrition));}const content=el("div");if(slot.recipe.preparation){content.append(el("p",`Receptversion: ${slot.recipe.preparation.version} · ${slot.recipe.preparation.origin==="smako_recipe_design"?"Smakos receptutformning":"Separat anpassad version"}.`),el("p","Mängderna avser använda ätbara ingredienser för hela receptet. Näring per portion är en uppskattning från dessa insatser; tillagad slutvikt och näring per 100 g färdig rätt är inte verifierade.","data-note"));}const ingredients=el("ul");slot.recipe.ingredients.forEach(i=>ingredients.append(el("li",`${number(i.quantity)} ${i.unit} ${i.name}`)));const steps=el("ol");slot.recipe.instructions.forEach(s=>steps.append(el("li",s.replace(/\bas_sold\b/g,"som såld").replace(/\braw_edible\b/g,"rå ätbar mängd").replace(/\bcooked_drained\b/g,"kokt och avrunnen").replace(/\bdry\b/g,"torr"))));content.append(ingredients,steps);if(slot.recipe.design)content.replaceChildren(window.SmakoRecipes.renderRecipe(slot.recipe,{nutrition,personal,slotId:slot.id}));card.append(details("Öppna recept",content));}const buttons=el("div",null,"personal-actions");buttons.append(button(slot.recipe?"Redigera":"Fyll med eget recept",async()=>editRecipe(slot)),button(slot.recipe?.design?"Byt recept och räkna om inköpen":slot.recipe?"Byt recept":"Föreslå recept",()=>change("replace",{slot_id:slot.id})));if(slot.recipe){buttons.append(button("Ta bort",()=>change("remove",{slot_id:slot.id})));if(slot.recipe.design)buttons.append(button("Så blev rätten",async()=>window.SmakoRecipes.recipeFeedback({recipe:slot.recipe,recipeIndex:personal.slots.filter(s=>s.recipe).findIndex(s=>s.id===slot.id),planId:saved.plan_id,revision:saved.revision})));}card.append(buttons);out.append(card);});

    const checks=el("div");checks.append(el("p",`Inköpsmängder: kontrollerade. Allergier: ${personal.checks.allergy==="VERIFIED"?"verifierade mot spårbara deklarationer":"ingen verifierad allergikontroll begärd"}.`));checks.append(el("p",`${personal.checks.organic_definition} Beräknad verifierad kostnadsandel: ${personal.checks.organic_cost_percent==null?"inget matinköp":`${number(personal.checks.organic_cost_percent)} %`}. Okänd status räknas inte positivt.`));const eco=personal.checks.organic_evidence;if(eco){checks.append(el("p",eco.status==="NO_NEW_FOOD_PURCHASES"?"Inga nya matinköp: ekoandelen är inte tillämplig. Detta räknas inte som 100 % ekologiskt.":`${money(eco.organic_food_cost)} verifierat ekologiskt av ${money(eco.food_cost)} i matinköp efter rabatter. Skafferi, avgifter och andra varor ingår inte.`));for(const line of eco.lines||[])checks.append(el("p",`${line.name}: ${money(line.cost)} · ${line.organic===true?"verifierat ekologisk":line.organic===false?"källan anger ej ekologisk":"ekostatus okänd"}`));}checks.append(el("p",`Animaliskt eko: ${personal.checks.organic_animals==="VERIFIED"?"kontrollerat mot produktunderlaget":"ej kontrollerat"}.`));personal.checks.nutrition.forEach(n=>{checks.append(el("p",`${n.slot_id}: ${["VERIFIED","ESTIMATED"].includes(n.status)?Object.entries(n.values).map(([k,v])=>`${({protein_g:"Protein",carbs_g:"Kolhydrater",fat_g:"Fett",kcal:"Energi",weight_g:"Tillagad portionsvikt"})[k]||k}: ${window.SmakoRecipes.nutritionNumber(v,n.status)} ${k==="kcal"?"kcal":"g"}`).join(" · "):"näringsgränser ej valda; full produktnäring och tillagad vikt är inte verifierade"}`));if(n.status==="ESTIMATED")checks.append(el("p","Gränser uppfyllda enligt beräkningen · spårbara uppskattningar används."));if(n.calculation_basis)checks.append(el("p",n.calculation_basis.description));for(const source of n.sources||[])if(source.basis)checks.append(el("p",`${source.ingredient||""} · ${source.evidence_kind&&source.evidence_kind!=="qualified_product_declaration"?"UPPSKATTNING · ":"Produktdeklaration · "}${source.origin==="pantry"?"Skafferibidrag":"Receptingrediens"}: ${number(source.quantity)} ${source.unit}. ${source.basis}. Källa: ${source.source.split(":")[0]}.`,"small"));});out.append(details("Krav och databegränsningar",checks));const ingredientChecks=personal.checks.ingredient_exclusions||[];if(ingredientChecks.length){const box=el("div");box.append(el("p","Hårt matval: inga uteslutna ingredienser enligt granskat källunderlag. Detta är ingen allergisäkerhetskontroll."));for(const row of ingredientChecks){box.append(el("p",`${row.name}: ${row.ingredients.join("; ")} · ${row.evidence_kind==="reviewed_single_unprocessed_crop"?"granskad eningrediensråvara, produktbeskrivning och råvarukategori":"granskad ingrediensdeklaration"}`));}out.append(details("Ingredienskontroll för dina matval",box));}const audit=el("div");audit.append(el("p",`Planrevision ${saved.revision} · ${plan.app_version} · ${plan.build_id}`),el("p",`Prisunderlag: ${plan.data?.price_universe_id||"saknas"}`),el("p",`Personlig beräkningsversion: ${personal.version}`));out.append(details("Tekniska detaljer",audit));$('personal-version').textContent=plan.app_version;renderShopping();renderSuggestions();}

  function renderShopping(){const out=$('shopping-content'),plan=saved.plan;out.replaceChildren();const booked=(privateState.ledger||[]).some(e=>e.plan_id===saved.plan_id&&e.revision===saved.revision&&e.action==="purchase");out.append(el("p",`${plan.optimized_basket.verification_status==="VERIFIED_WITH_ESTIMATES"?"ca ":""}${money(plan.optimized_basket.total)} · ${booked?"bokförda köp i denna revision":"hela förpackningar för hela korgen"}`,"personal-total"));if(booked)out.append(el("p","Köpet är bokfört. Räkna om planen för att se aktuella återstående köpbehov."));const financials=window.SmakoRecipes.financials(plan);if(financials)out.append(financials);for(const store of plan.optimized_basket.stores){out.append(el("h2",`${store.store_name} · ${money(store.subtotal)}`));for(const row of store.items){const card=el("article",null,"personal-card");const need=plan.personal.needs.find(n=>n.key===row.ingredient);const applied=row.applied_offer;let type=row.group_applications?.length?"Kampanjgrupp (fördelad kostnad)":row.price_mechanism==="multibuy"?"Flerköp":row.membership_required?"Medlemspris":row.price_mechanism==="regular"?"Ordinarie / rapporterat grundpris":"Kampanjpris";card.append(el("h3",row.product_name),el("strong",`${row.sale_model==="sold_by_weight"?`${number(row.purchased_quantity)} ${row.purchased_unit} lösvikt`:`${row.packages_needed} förpackning${row.packages_needed===1?"":"ar"}`} · ${row.quantity_confidence==="estimated"?"ca ":""}${money(row.total_price)}`),el("p",`${type} används. Användbar mängd ${row.quantity_confidence==="estimated"?"ca ":""}${number(row.purchased_usable_quantity)} ${row.unit}; recept-/inköpsbehov ${number(row.required_quantity)} ${row.unit}.`));if(Number.isFinite(row.purchased_quantity)&&row.purchased_unit&&(row.purchased_unit!==row.unit||Math.abs(row.purchased_quantity-row.purchased_usable_quantity)>0.000001))card.append(el("p",`Planerad inköpt mängd: ${number(row.purchased_quantity)} ${row.purchased_unit}. Användbar mängd redovisas separat.`));if(row.quantity_confidence==="estimated")card.append(el("p",`Den användbara mängden är uppskattad. Kontrollväg minst ${number(row.required_quantity)} ${row.unit} användbar mängd för recepten; komplettera inköpet om den inte räcker. Beräknade rester är också uppskattade.`,"data-note"));if(row.membership_required)card.append(el("p",`Kräver medlemskap: ${row.membership_program}.`));if(applied&&!row.group_applications?.length)card.append(el("p",`${applied.description} · ${applied.price_basis_unit==="kg"?`${money(applied.price)}/kg`:`${applied.required_packages} för ${money(applied.price)}`} · köpantal ${applied.required_packages}${applied.max_quantity?` · max ${applied.max_quantity} rabattgrupper`:""}. Gäller ${applied.valid_from||"startdatum saknas"} – ${applied.valid_to||"slutdatum saknas"}.`));else if(!row.group_applications?.length)card.append(el("p","Ingen villkorad rabatt används av denna rad."));if(row.group_applications?.length&&row.group_residual_packages)card.append(el("p",`${row.group_residual_packages} övriga förpackningar: ${money(row.group_residual_total)} enligt radens övriga prisvillkor.`));for(const application of row.group_applications||[]){const g=application.group;card.append(el("p",g.pricing_rule==="fixed_total"?`${g.required_packages} valfria i kampanjen för ${money(g.amount)}`:`${g.required_packages} valfria i kampanjen ger ${money(g.amount)} rabatt på ordinarie paketpris`),el("p",`Bidrar: ${application.contributors.map(c=>`${c.packages} × ${c.product_name}`).join(" · ")}. Gäller ${g.valid_from} – ${g.valid_to}${g.membership_program?` · Kräver ${g.membership_program}`:""}${g.max_groups?` · Max ${g.max_groups} kampanjgrupper`:""}. Varje förpackning räknas bara en gång.`));}card.append(el("p",row.price_context_type?.toLowerCase().includes("online")?"Onlinepris – ingen verifierad fysisk prisobservation.":"Digitalt prisunderlag – ingen garanti för fysisk hyllkostnad eller lagerstatus.","small"));if(need?.unused_source_offers?.length){const offers=el("div");for(const offer of need.unused_source_offers){offers.append(el("p",`${offer.description}: ${offer.required_packages} för ${money(offer.price)}. ${offer.membership_program?`Kräver ${offer.membership_program}. `:""}Gäller ${offer.valid_from||"startdatum saknas"} – ${offer.valid_to||"slutdatum saknas"}. Används inte i denna radsumma.`));}card.append(details("Andra erbjudanden i källan – används inte",offers));}if(row.deposit_total>0)card.append(el("p",`Varor ${money(row.merchandise_total)} + pant ${money(row.deposit_total)} = ${money(row.total_price)}.`));const declaration=window.SmakoRecipes.productDetails(plan.personal.checks.ingredient_product_details?.find(d=>d.ingredient===row.ingredient&&d.product_name===row.product_name));if(declaration)card.append(declaration);if(row.purchase_warning)card.append(el("p",row.purchase_warning));if(row.waste_quantity)card.append(el("p",`Beräknat framtida överskott: ${number(row.waste_quantity)} ${row.unit}.`));card.append(button("Välj annan produkt",async()=>{swapTarget=row.ingredient;$('product-query').value=need?.name||row.product_name;show("product-search");$('product-search-form').requestSubmit();}));out.append(card);}}

    const ledger=(privateState.ledger||[]).filter(e=>e.plan_id===saved.plan_id);const ev={purchase:ledger.some(e=>e.action==="purchase"&&e.revision===saved.revision),consume:ledger.some(e=>e.action==="consume"&&e.operation_id===`consume:${saved.revision}`)};const actions=el("div",null,"personal-actions");actions.append(button(ev.purchase?"Inköpet är bokfört":"Bekräfta att jag har köpt varorna",async()=>{const rows=plan.optimized_basket.stores.flatMap(g=>g.items).filter(i=>i.quantity_confidence==="estimated");if(!rows.length)return change("purchase");const dialog=el("dialog"),inputs=[];dialog.append(el("h2","Bekräfta uppmätta inköp"),el("p","Ange verklig användbar mängd i angiven enhet. Planens kostnader förblir uppskattade."));for(const row of rows){const value=input("number","",{min:row.required_quantity,step:"any"});inputs.push([row,value]);dialog.append(field(`${row.product_name}: minst ${number(row.required_quantity)} ${row.unit} användbar mängd`,value));}dialog.append(button("Bokför uppmätt mängd",async()=>{const quantities={};for(const [row,value] of inputs){const q=Number(value.value);if(!Number.isFinite(q)||q<row.required_quantity)throw new Error("Mät inköpet och ange mängd som täcker behovet, eller räkna om planen.");quantities[row.store_id+"|"+row.product_id+"|"+row.ingredient]=q;}await change("purchase",{measured_purchase_quantities:quantities});dialog.close();dialog.remove();}),button("Avbryt",async()=>{dialog.close();dialog.remove();}));document.body.append(dialog);dialog.showModal();},true),button(ev.consume?"Förbrukningen är bokförd":"Bekräfta planens förbrukning",()=>change("consume")),button("Bekräfta delvis förbrukning",async()=>{const d=el("dialog");const percent=input("number",50,{min:1,max:100});d.append(el("h2","Bekräfta verklig förbrukning"),field("Andel av kvarvarande reserverade mängder, procent",percent),el("p","Använd detta när samma andel av planens reserverade ingredienser har förbrukats. Räkna om efter bokföringen."),button("Bokför förbrukning",async()=>{const value=Number(percent.value);if(!Number.isFinite(value)||value<=0||value>100)throw new Error("Ange 1–100 procent.");await change("consume",{consume_fraction:value/100,operation_id:crypto.randomUUID()});d.close();d.remove();}),button("Avbryt",async()=>{d.close();d.remove();}));document.body.append(d);d.showModal();}),button("Frigör planens reservationer",()=>change("release")));out.append(actions);const history=el("div");for(const event of ledger){history.append(el("h3",`${event.action==="purchase"?"Bokfört inköp":event.action==="consume"?"Bokförd förbrukning":"Frigjord reservation"} · planrevision ${event.revision}${event.total!=null?` · ${money(event.total)}`:""}`));for(const row of event.rows){history.append(el("p",`${row.checkout?.product_name||row.name}: ${number(row.quantity)} ${row.unit}${row.checkout?` · ${money(row.checkout.total_price)}`:""}`));}}if(ledger.length)out.append(details("Oföränderlig inköps- och förbrukningshistorik",history));for(const row of plan.personal.available_surplus||[])out.append(el("p",`Disponibelt befintligt överskott efter reservation: ${row.name} ${number(row.quantity)} ${row.unit}.`));if(saved.revision>1){const previous=input("number",saved.revision-1,{min:1,max:saved.revision-1});const restore=el("div");restore.append(field("Tidigare receptrevision",previous),el("p","Skapar en ny revision med tidigare recept. Aktuella hårda krav och extravaror behålls. Bokförda köp och förbrukning ändras aldrig."),button("Återställ recept och beräkna nya behov",()=>change("restore_revision",{restore_revision:Number(previous.value)})));out.append(details("Återanvänd tidigare receptrevision",restore));}out.append(el("p","Bekräfta bara genomförda inköp och verklig förbrukning. Upprepade bekräftelser bokförs bara en gång. Att frigöra en plan ändrar inte verkligt lager.","small"));out.append(el("p",`Strategiska extraköp: ${money(plan.personal.larger_purchase_cost)} i merkostnad. Förpackningsöverskott bokförs som lager först efter bekräftat inköp.`));}

  function editRecipe(slot){const box=el("div");box.append(el("h2",slot.recipe?"Redigera recept":"Fyll tillfället"));const name=input("text",slot.recipe?.name||"",{maxLength:150});const servings=input("number",slot.recipe?.servings||1,{min:"1",max:"8"});const rows=el("div");function ingredientRow(i={name:"",quantity:1,unit:"g"}){const row=el("div",null,"ingredient-edit");const n=input("text",i.name,{maxLength:120}),q=input("number",i.quantity,{min:"0.001",step:"any"}),u=select([["g","g"],["ml","ml"],["st","st"],["kg","kg"],["l","l"]],i.unit);n.setAttribute("aria-label","Ingrediens");q.setAttribute("aria-label","Mängd");u.setAttribute("aria-label","Enhet");row.append(n,q,u,button("×",async()=>row.remove()));rows.append(row);} (slot.recipe?.ingredients||[{}]).forEach(i=>ingredientRow(i));const instructions=el("textarea");instructions.value=slot.recipe?.instructions.join("\n")||"";box.append(field("Receptnamn",name),field("Portioner (mängderna nedan är för hela receptet)",servings),el("p","Alla ingredienser måste kunna lösas till verkliga köpbara behov. Okända ingredienser stoppar uppdateringen."),rows,button("Lägg till ingrediens",async()=>ingredientRow()),field("Tillagningssteg – ett per rad",instructions),button("Spara och räkna om hela korgen",async()=>{const recipe={name:name.value,servings:Number(servings.value),ingredients:[...rows.children].map(r=>({name:r.children[0].value,quantity:Number(r.children[1].value),unit:r.children[2].value})),instructions:instructions.value.split("\n").map(s=>s.trim()).filter(Boolean)};await change("edit",{slot_id:slot.id,recipe});$('personal-dialog').close();focusView();},true));openDialog(box);}

  async function pantryDialog(item=null,product=null){const box=el("div");box.append(el("h2",item?"Ändra verkligt lager":"Lägg till verkligt lager"));const name=input("text",item?.name||product?.name||"",{maxLength:120}),amount=input("number",item?.quantity??product?.package_quantity??1,{min:"0",step:"any",max:"100000"}),unit=select([["g","gram"],["ml","milliliter"],["st","stycken"]],item?.unit||product?.package_unit||"g"),unusable=input("checkbox","");unusable.checked=item?.unusable||false;const formChoice=select([["","Okänd / ej angiven"],["raw_edible","Rå, ätbar mängd"],["dry","Torr råvara"],["as_sold","Som såld"],["cooked_drained","Kokt och avrunnen"],["preserved_drained","Avrunnen konserverad vara"]],item?.form||"");const reference=select([["","Ingen generisk näringsreferens bekräftad"]],"");if(!product&&!item?.product_key){const refs=await api("/api/personal/nutrition-references");for(const option of refs.options){const o=el("option",`${option.name} · ${option.preparation_label} · gram`);o.value=option.id;reference.append(o);}reference.value=item?.nutrition_reference||"";box.append(field("Bekräfta livsmedel och rå/torr/avrunnen form för näringsuppskattning",reference),el("p","Välj bara en referens som stämmer med varan hemma, inklusive fetthalt och beredning. Detta ändrar inte lagermängden. Kräver även uttryckligt uppskattningsläge i Mina val."));}if(product||item?.product_key)name.readOnly=true;box.append(field("Vara",name),field("Faktisk mängd hemma",amount),field("Enhet",unit),field("Obrukbar – får inte användas",unusable),field("Råvaruform (för genomarbetade recept)",formChoice),el("p","Generiska skafferivaror behöver dokumenterad form som passar receptet. En produktidentitet ger mer underlag om exempelvis tjock yoghurt eller fast tofu.","small"),el("p",product||item?.product_key?"Exakt produktidentitet bevaras.":"Generisk vara. Ingen allergendeklaration eller vikt-/volymomräkning antas."),button("Spara skafferivara",async()=>{const clean=privateState.items.map(({available,reserved,...i})=>i);const newItem={...(formChoice.value?{form:formChoice.value}:{}),nutrition_reference:reference.value||null,id:item?.id||crypto.randomUUID(),name:name.value,quantity:Number(amount.value),unit:unit.value,unusable:unusable.checked,product_key:item?.product_key||product?.product_key||null,food:!/(servett|toalettpapper|hushållspapper|diskmedel)/i.test(name.value)};privateState=await api("/api/personal/pantry",{revision:privateState.revision,profile:profile(),items:[...clean.filter(i=>i.id!==newItem.id),newItem]},"PUT");renderPantry();$('personal-dialog').close();show("pantry");},true));openDialog(box);}

  $('add-pantry').addEventListener("click",()=>void task(()=>pantryDialog()));

  function renderPantry(){if(!privateState)return;const out=$('pantry-list');out.replaceChildren();$('account-status').textContent=privateState.account.message;for(const item of privateState.items){const card=el("article",null,"personal-card");card.append(el("h2",item.name),el("p",`Faktiskt lager ${number(item.quantity)} ${item.unit} · Reserverat ${number(item.reserved)} ${item.unit} · Disponibelt ${number(item.available)} ${item.unit}${item.unusable?" · OBRUKBAR":""}`),button("Ändra",async()=>pantryDialog(item)),button("Ta bort",async()=>{privateState=await api("/api/personal/pantry",{revision:privateState.revision,profile:profile(),items:privateState.items.filter(i=>i.id!==item.id).map(({available,reserved,...i})=>i)},"PUT");renderPantry();}));for(const check of privateState.pantry_checks||[]){if(check.item_id===item.id)card.append(el("p",check.message,"data-note"));}out.append(card);}if(!privateState.items.length)out.append(el("p","Skafferiet är tomt. Lägg till det som faktiskt finns hemma."));const reservations=$('reservation-list');reservations.replaceChildren();for(const [id,rows] of Object.entries(privateState.reservations)){if(!rows.length)continue;const p=el("p",`${rows.length} reservationer för en aktiv plan. `);p.append(button("Öppna berörd plan",async()=>{await accept(await api(`/api/plans/${encodeURIComponent(id)}`));show("plan");}));reservations.append(p);}}

  window.SmakoPersonal={productActions(product){const box=el("div",null,"personal-actions");const usages=product.prices.map(p=>p.purchase_usage);if(usages.every(u=>u==="blocked")){box.append(el("p","Varupriset är bevarat. Komplettera kritiska köp-/pantuppgifter före beräkning."));return box;}if(usages.includes("variant_selection_required")){box.append(button("Lägg till som villkorat kampanjval",async()=>extraDialog(product,true)));return box;}box.append(button("Lägg till i inköpslistan",async()=>extraDialog(product)),button("Lägg till i skafferiet",async()=>pantryDialog(null,product)));if(swapTarget)box.append(button("Byt vald inköpsrad till denna produkt",async()=>{await change("product",{ingredient:swapTarget,product_key:product.product_key});swapTarget=null;show("shopping");}));return box;}};

  $('personal-scan').addEventListener("click",()=>{const box=el("div");box.append(el("h2","Skanna vara"));const video=el("video");video.setAttribute("playsinline","");video.muted=true;const status=el("p","Kameran startar först när du väljer Starta kamera.");const manual=input("text","",{inputMode:"numeric",maxLength:18});function found(value){stopScanner();$('personal-dialog').close();$('product-query').value=value;show("product-search");window.dispatchEvent(new CustomEvent("smako:compare-gtin",{detail:{gtin:value}}));}box.append(video,status,button("Starta kamera",async()=>{try{scanner=await GroceryBarcodeScanner.createBarcodeScanner({videoElement:video,onResult:result=>found(result.normalized_gtin),onError:(error,detail={})=>{status.textContent=detail.recoverable?"Håll hela koden i bild.":"Kameran kunde inte läsa koden. Ange GTIN manuellt.";}});await scanner.start();status.textContent="Håll streckkoden i bild.";}catch(e){stopScanner();throw new Error("Kameran kunde inte startas. Tillåt kameraåtkomst eller ange GTIN manuellt.");}}),field("GTIN manuellt",manual),button("Sök streckkod",async()=>found(GroceryBarcodeScanner.normalizeGtin(manual.value).normalized_gtin)));openDialog(box);});

  async function resumePersonalJob() {
    const pending=window.SmakoRecipes.pendingJob("personal");if(!pending)return false;
    notify("Återansluter till din pågående menyberäkning…");
    const result=await api(pending.url);await accept(result.saved||result);show("plan");return true;
  }
  void task(async()=>{
    try {const metadata=await api("/api/recipe-library");recipeControls.enabled(metadata.enabled===true);}catch(_){recipeControls.enabled(false);}
    await refreshState();putProfile(privateState.profile);
    const draft=window.SmakoRecipes.storage.get("smako.personal.requestDraft");
    if(draft){extras=structuredClone(draft.personal?.extras||[]);putChoices({...draft,membership_programs:draft.membership_programs||draft.memberships||[]});}
    if(await resumePersonalJob())return;
    const fromHash=new URLSearchParams(location.hash.slice(1)).get("plan");let last=fromHash;try{last ||= localStorage.getItem("smako.personal.lastPlan");}catch(_){}
    if(last){const loaded=await api(`/api/plans/${encodeURIComponent(last)}`);if(loaded.plan.personal)await accept(loaded);else notify("Detta är en tidigare middagsplan. Öppna den i den tidigare planeringen.");}
    if(location.hash==="#pantry")show("pantry");renderExtras();
  });
  window.addEventListener("online",()=>{if(!busy&&window.SmakoRecipes.pendingJob("personal"))void task(async()=>{try{const metadata=await api("/api/recipe-library");recipeControls.enabled(metadata.enabled===true);}catch(_){/* A saved pending job can still reconnect. */}await resumePersonalJob();});});

  function renderSuggestions(){

    if(!saved?.plan.personal.future_surplus.length)return;

    const box=el("div",null,"personal-card");box.append(el("h2","Använd beräknade rester"),el("p","Förslagen räknar på framtida överskott. De ändrar varken lager eller korg förrän du väljer ett recept. Hållbarhet är okänd."));

    const output=el("div");box.append(button("Föreslå användning av resten",async()=>{

      const result=await api(`/api/personal/plans/${encodeURIComponent(saved.plan_id)}/surplus-suggestions`);

      output.replaceChildren();

      if(!result.suggestions.length)output.append(el("p","Inget verifierbart restrecept hittades med aktuella varor och krav."));

      for(const suggestion of result.suggestions){const card=el("article",null,"personal-card");card.append(el("h3",suggestion.recipe.name),el("p",`Ytterligare full inköpskostnad i detta framtidsscenario: ${money(suggestion.new_cost)}.`));for(const group of suggestion.additional_purchases.stores)for(const item of group.items)card.append(el("p",`${item.product_name} · ${item.packages_needed} förpackningar · ${money(item.total_price)}`));card.append(button("Välj recept och räkna om planen",async()=>{await change("add_recipe",{recipe:suggestion.recipe});show("plan");},true));output.append(card);}

    }),output);$('plan-content').append(box);

  }

  async function renderAccount(){

    const state=await api("/api/account/status"),out=$('account-actions');out.replaceChildren();

    if(state.status==="SIGN_IN_AVAILABLE"){const a=el("a","Logga in med verifierat Smakokonto","primary-button");a.href="/api/account/login";out.append(a);}

    if(state.status==="SIGNED_IN"){

      out.append(button("Logga ut",async()=>{await api("/api/account/logout",{});window.SmakoRecipes.clearPrivateDrafts();location.assign("/personal#account");}));

      const preview=await api("/api/account/guest-migration-preview");

      if(preview.can_move)out.append(button(`Flytta mitt gästskafferi (${preview.guest_items} varor) och mina gästplaner till kontot`,async()=>{

        await api("/api/account/migrate-guest",{guest_revision:preview.guest_revision,account_revision:preview.account_revision,confirm_move_to_verified_account:true});await refreshState();out.replaceChildren(el("p","Gästdata har flyttats till det verifierade kontot."));

      }));

      else if(preview.guest_items)out.append(el("p","Kontot har redan data. Gästskafferiet är bevarat separat; automatisk sammanslagning stöds inte."));

    }

  }

  void renderAccount().catch(()=>{});

})();

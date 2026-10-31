"use strict";

(() => {

  const $ = (id) => document.getElementById(id);

  const money = (v) => `${Number(v).toLocaleString("sv-SE", {minimumFractionDigits:2, maximumFractionDigits:2})} kr`;

  const number = (v) => v==null||v===""||!Number.isFinite(Number(v))?"okänd":Number(v).toLocaleString("sv-SE", {maximumFractionDigits:2});

  const names = {dinner:"Middag", breakfast:"Frukost", snack:"Mellanmål"};

  const profileLabels = {likes:"Gillar / föredrar", dislikes:"Ogillar – mjukt önskemål", exclusions:"Uteslut ingredienser – hårt matval", allergies:"Allergier – även deklarerade spår"};

  const proteinNames = {vegetarian:"Vegetarisk", chicken:"Kyckling", fish:"Fisk / skaldjur", meat:"Övrigt kött"};

  let privateState = null, saved = null, extras = [], busy = false, parsedText = "", scanner = null, swapTarget = null, alternativeTarget = null, searchGeneration = 0, searchAbort = null, searchTimer = null, shoppingGenerics = [];
  const recipeControls = window.SmakoRecipes.controls($('complete-recipe-controls'),{personal:true});
  const locationControls = window.SmakoLocation.create();

  function el(tag, text, cls) { const n=document.createElement(tag); if(text != null)n.textContent=text; if(cls)n.className=cls; return n; }

  function button(text, action, primary=false) {const b=el("button",text,primary?"primary-button":"secondary-button");b.type="button";b.addEventListener("click",()=>void task(()=>action(b)));return b;}

  function field(label, input) {input.setAttribute("aria-label",label);const l=el("label",label);l.append(input);return l;}

  function input(type, value, attrs={}) {const n=el("input");n.type=type;n.value=value??"";Object.assign(n,attrs);return n;}

  function select(values,value) {const n=el("select");for(const [v,label] of values){const o=el("option",label);o.value=v;n.append(o);}n.value=value;return n;}

  function details(title, child) {const n=el("details");n.append(el("summary",title),child);return n;}

  function focusView(){const target=document.querySelector('[data-view]:not([hidden]) .personal-total, [data-view]:not([hidden]) h1');if(target){target.tabIndex=-1;target.focus({preventScroll:true});}}

  function notify(text) {$('personal-status').textContent=text;}
  // Creating a plan shows its progress where the create button was (plan-progress.js).
  const progress=window.SmakoPlanProgress,CANCELLED="Beräkningen avbröts. Dina val och din senaste plan finns kvar.";let cancelRequested=false;
  function startProgress(anchor){
    if(!progress||progress.active)return;cancelRequested=false;
    progress.start({anchor,since:window.SmakoRecipes.pendingJob("personal")?.started_at,cancellable:()=>!!window.SmakoRecipes.pendingJob("personal")?.url,
      cancelAction:async()=>{cancelRequested=true;try{await window.SmakoRecipes.cancelJob("personal");}catch(error){cancelRequested=false;throw error;}}});
  }

  function show(view) {document.querySelectorAll("[data-view]").forEach(n=>n.hidden=n.dataset.view!==view);document.querySelectorAll(".personal-nav [data-open]").forEach(n=>{if(n.dataset.open===view)n.setAttribute("aria-current","page");else n.removeAttribute("aria-current");});window.scrollTo({top:0,behavior:"instant"});}

  document.querySelectorAll("[data-open]").forEach(n=>n.addEventListener("click",e=>{e.preventDefault();show(n.dataset.open);}));

  async function api(url,payload,method="POST") {
    const planning=payload!==undefined&&((url==="/api/plans"&&payload.personal)||/^\/api\/personal\/plans\/[^/]+\/change$/.test(url));
    const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),planning||url.startsWith("/api/plan-jobs/")?600000:90000);
    try {
      let r;
      if(planning||url.startsWith("/api/plan-jobs/")||url.startsWith("/api/plan-job-requests/"))r=await window.SmakoRecipes.jobRequest({scope:"personal",url,payload,signal:controller.signal,onProgress:(text,data)=>{notify(text);progress?.update(text,data);},context:planning?{kind:url==="/api/plans"?"create":"change"}:null});
      else r=await fetch(url,{method:payload===undefined?"GET":method,headers:{"Content-Type":"application/json"},body:payload===undefined?undefined:JSON.stringify(payload),signal:controller.signal,cache:"no-store"});
      const d=await r.json();
      r.smakoCheck?.();
      if(!r.ok){const message=typeof d.detail==="string"?d.detail:Array.isArray(d.detail)?d.detail.map(e=>e.msg).join(" · "):"Begäran kunde inte genomföras.";const error=new Error(r.smakoPlanningBlock||`${d.code==="DATA_BLOCKED"?"Underlag saknas: ":""}${message}${r.headers.get("X-Request-ID")?` Fel-ID: ${r.headers.get("X-Request-ID")}`:""}`);error.status=r.status;error.code=d.code||r.headers.get("X-Error-Code");error.diagnostics=d.planning_diagnostics;throw error;}
      return d;
    } catch(e){if(e.lifecycle)throw e;if(e.name==="AbortError")throw new Error("Svarstiden överskreds. Ladda om för att återansluta till samma beräkning. Dina val och tidigare plan finns kvar.");throw e;} finally{clearTimeout(timer);}
  }

  function renderDiagnostics(d) {
    const box=window.SmakoRecipes.diagnostics(d);if(!box)return;box.id="planning-diagnostics";

    $("personal-status").after(box);
  }
  async function task(work) {

    if(busy)return;busy=true;$("plan-reconnect-actions")?.remove();$("data-blocked-actions")?.remove();$("planning-diagnostics")?.remove();notify("Arbetar…");

    const controls=[...document.querySelectorAll("button")].filter(n=>!n.disabled&&!n.matches("[data-open]"));controls.forEach(n=>n.disabled=true);

    try {await work();notify("");} catch(e){if(e.lifecycle)return;if(cancelRequested&&e.code==="planner_job_expired")e.message=CANCELLED;progress?.fail(e.message||"Åtgärden kunde inte slutföras.",{cancelled:e.message===CANCELLED});notify(e.message||"Åtgärden kunde inte slutföras.");if(e.code==="membership_required"){document.querySelectorAll("dialog[open]").forEach(dialog=>dialog.close());show("account");void renderAccount().catch(error=>notify(error.message));}if(e.diagnostics)renderDiagnostics(e.diagnostics);if(e.code==="DATA_BLOCKED"){const choices=el("div",null,"personal-actions");choices.id="data-blocked-actions";choices.append(button("Ändra mina val",async()=>show("choices")),button("Granska berörda behov",async()=>{const box=el("div");box.append(el("h2","Underlag för berörda ingrediensbehov"));const rows=e.diagnostics?.missing_needs||[];for(const row of rows)box.append(el("p",`${names[row.meal_type]} · ${row.recipe}: ${row.ingredient}, ${number(row.quantity)} ${row.unit}. ${row.reason}`));if(!rows.length)box.append(el("p","Se receptens beredningshinder i blockeringsfördelningen. Ingen produktändring har gjorts."));openDialog(box);}),button("Gå tillbaka",async()=>show(saved?"plan":"choices")));$("personal-status").after(choices);}$('personal-status').scrollIntoView({block:"nearest"});}

    finally {busy=false;progress?.settle();controls.forEach(n=>{if(n.isConnected)n.disabled=false;});updateChoiceSummary();$('generate-plan').textContent=window.SmakoRecipes.pendingJob('personal')?'Återuppta statuskontrollen':'Skapa plan och inköpslista';
      if(window.SmakoRecipes.pendingJob('personal')&&!document.hidden){const actions=el('div',null,'personal-actions');actions.id='plan-reconnect-actions';actions.append(button('Återuppta statuskontrollen',resumePersonalJob),button('Skapa en ny meny',async()=>{window.SmakoRecipes.forgetJob('personal');actions.remove();show('choices');}));$('personal-status').after(actions);}
      requestAnimationFrame(()=>{if(document.activeElement?.matches('.skip-link'))focusView();});}

  }

  async function refreshState(){privateState=await api("/api/personal/state");renderPantry();renderCommon();}

  function listText(value){return value.split(/[,;\n]/).map(v=>v.trim()).filter(Boolean);}

  function profile(prefix="profile") {return Object.fromEntries(Object.keys(profileLabels).map(k=>[k,listText($(`${prefix}-${k}`).value)]));}

  function putProfile(value,prefix="profile"){Object.keys(profileLabels).forEach(k=>$(`${prefix}-${k}`).value=(value?.[k]||[]).join(", "));}

  function profileFields(container,prefix) {for(const [k,label] of Object.entries(profileLabels)){const n=input("text","");n.id=`${prefix}-${k}`;n.maxLength=1500;container.append(field(`${label} (kommaseparerat)`,n));}}

  profileFields($('profile-fields'),"profile");

  const limitLabels = {min_weight_g:"Min tillagad portionsvikt (g)",max_weight_g:"Max tillagad portionsvikt (g)",min_protein_g:"Min protein (g)",max_protein_g:"Max protein (g)",min_carbs_g:"Min kolhydrater (g)",max_carbs_g:"Max kolhydrater (g)",min_fat_g:"Min fett (g)",max_fat_g:"Max fett (g)",max_kcal:"Max energi (kcal)"};

  const {controls:sliders,slider,interval}=window.SmakoChoiceUI;
  const sliderValue=id=>sliders.get(id).read();
  const setSlider=(id,value)=>sliders.get(id).set(value);
  function mealDialog(type,key,title,content,actions){
    return window.SmakoChoiceUI.dialog({id:`${type}-${key}-dialog`,title:`${names[type]} · ${title}`,content,actions,host:$('personal-form'),validate:()=>key!=="distribution"||distributionSync[type](),onApplied:updateChoiceSummary});
  }
  const mealCards={},mealExtras={},distributionSync={};
  function syncMeal(type){
    const enabled=type==="dinner"||$(`enable-${type}`).checked;
    mealCards[type].hidden=!enabled;
    mealExtras[type].disabled=!enabled;
  }
  for(const [type,label] of Object.entries(names)){
    const box=el("fieldset",null,"choices-primary");box.append(el("legend",label));
    const grid=el("div",null,"personal-grid");
    grid.append(slider(`${type}-count`,type==="dinner"?"Antal middagar":"Antal tillfällen",3,{min:type==="dinner"?0:1,max:7}),slider(`${type}-servings`,"Portioner per rätt",type==="dinner"?2:1,{min:1,max:8}));
    box.id=`${type}-meals`;box.append(grid);mealCards[type]=box;$('meal-settings').append(box);
    const actions=el("div",null,"personal-actions meal-settings-actions");box.append(actions);
    const options=el("fieldset");mealExtras[type]=options;
    const diet=select([["mixed","Blandat"],["vegetarian","Vegetariskt (ägg/mejeri tillåts)"],["vegan","Veganskt"]],"mixed");diet.id=`${type}-diet`;options.append(field("Kostval",diet));
    const distribution=el("div",null,"personal-grid");
    for(const [key,title] of Object.entries(proteinNames))distribution.append(slider(`${type}-${key}`,`${title} – antal`,null,{optional:true,max:7}));
    const remaining=el("p");remaining.setAttribute("role","status");
    options.append(el("p","Standard låter planeraren välja återstående rätter. Egna antal delar på antalet måltider. Vegetariskt tillåter ägg och mejeri; veganskt utesluter animalier."),remaining,distribution);
    const conflict=el("p",null,"choice-error");conflict.id=`${type}-conflict`;conflict.setAttribute("role","status");box.append(conflict);
    distributionSync[type]=()=>{
      const count=sliderValue(`${type}-count`),values=Object.fromEntries(Object.keys(proteinNames).map(k=>[k,sliderValue(`${type}-${k}`)]));
      const total=Object.values(values).reduce((sum,v)=>sum+(v??0),0);
      let message=total>count?`${total} fördelade men bara ${count} tillfällen. Öppna Fördelning och justera dina antal.`:"";
      if(diet.value!=="mixed"&&(Object.entries(values).some(([k,v])=>k!=="vegetarian"&&v>0)||(values.vegetarian!==null&&values.vegetarian!==count)))message="Kostvalet kräver vegetariska rätter vid alla tillfällen. Justera egna antal eller välj Standard.";
      remaining.textContent=`${total} av ${count} måltider fördelade · ${Math.max(0,count-total)} kvar${message?` · ${message}`:""}`;
      conflict.textContent=message;return !message;
    };
    distribution.addEventListener("input",distributionSync[type]);diet.addEventListener("change",distributionSync[type]);$(`${type}-count`).addEventListener("input",distributionSync[type]);
    const weight=el("div");weight.append(el("p","Dra i intervallets ändar för lägsta och högsta portionsvikt. Gäller tillagad eller serveringsfärdig, ätbar vikt per portion. Med tillåtna näringsuppskattningar används källbelagt tillagningsutbyte eller hela den uppvägda mängden i granskade kalla rätter. Recept utan viktunderlag kan inte väljas med en viktgräns."),interval(type,"weight_g","Portionsvikt",3000));
    const nutrition=el("div");nutrition.append(el("p","Dra i intervallets ändar för egna gränser per portion. Standard behåller matplanerarens befintliga beräkning."));
    for(const [key,title,max,contractMax] of [["protein_g","Protein",100,300],["carbs_g","Kolhydrater",400,500],["fat_g","Fett",300,300]])nutrition.append(interval(type,key,title,max,contractMax));
    nutrition.append(slider(`${type}-max_kcal`,"Högsta energi",null,{optional:true,max:4000,unit:"kcal"}),el("p","Energi kan begränsas med ett maxvärde. Tomt behåller Standard.","small"));
    const organic=input("checkbox","");organic.id=`${type}-organic`;options.append(field("Kräv ekologiska animalier för denna måltidstyp",organic));
    mealDialog(type,"distribution","Fördelning",options,actions);mealDialog(type,"weight","Portionsvikt",weight,actions);mealDialog(type,"nutrition","Näringsvärden",nutrition,actions);
    if(type!=="dinner"){
      const toggle=input("checkbox","");toggle.id=`enable-${type}`;toggle.setAttribute("role","switch");toggle.setAttribute("aria-controls",`${type}-meals`);box.id=`${type}-meals`;
      const row=field(`Lägg till ${label.toLowerCase()}`,toggle);row.className="check-label";$('extra-meal-toggles').append(row);
      toggle.addEventListener("change",()=>{syncMeal(type);$("meal-announcement").textContent=`${label} ${toggle.checked?"visas nu under Middag":"är avaktiverad; dina inställningar finns kvar"}.`;updateChoiceSummary();$(`${type}-count`).dispatchEvent(new Event("input",{bubbles:true}));});
    }
    syncMeal(type);distributionSync[type]();
  }
  $('store-count-control').append(slider("max-stores","Max inköpsställen för hela korgen",2,{min:1,max:3}));
  $('organic-percent-control').append(slider("organic-percent","Minsta verifierade ekologiska kostnadsandel",0,{max:100,unit:"%"}));

  for(const [v,label] of [["ICA_STAMMIS","ICA Stammis"],["COOP_MEMBER","Coop"],["WILLYS_PLUS","Willys Plus"],["HEMKOP_MEMBER","Hemköp"],["CITYGROSS_MEMBER","City Gross"],["LIDL_PLUS","Lidl Plus"]]){const n=input("checkbox",v);n.name="membership";const f=field(label,n);f.className="check-label";$('memberships').append(f);}

  function updateChoiceSummary(){
    const out=$('choice-summary-lines');if(!out)return;out.replaceChildren();
    const add=(label,value)=>{out.append(el("dt",label),el("dd",value));};
    add("Område",$('location-selection-status').textContent||"Kontrollera ditt postnummer");
    for(const [type,label] of Object.entries(names))if(type==="dinner"||$(`enable-${type}`).checked){
      add(label,`${sliderValue(`${type}-count`)} × ${sliderValue(`${type}-servings`)} portioner`);
      for(const kind of ["distribution","weight","nutrition"]){
        const keys=kind==="distribution"?Object.keys(proteinNames):Object.keys(limitLabels).filter(k=>kind==="weight"?k.includes("weight"):!k.includes("weight"));
        const n=keys.filter(k=>sliderValue(`${type}-${k}`)!==null).length;
        const text=kind==="distribution"&&$(`${type}-diet`).value!=="mixed"?$(`${type}-diet`).selectedOptions[0].text:n?`${n} egna val`:"Standard";
        $(`${type}-${kind}-open`).querySelector('.meal-button-summary').textContent=text;
      }
    }
    add("Handla i",`Max ${sliderValue("max-stores")} inköpsställen`);
    add("Egna varor",extras.length?`${extras.length} ${extras.length===1?"vara":"varor"}, optimeras med recepten`:"Inga ännu");
    $('choice-submit').disabled=$('planning-choices').disabled||busy;
    const submitLabel=window.SmakoRecipes.pendingJob('personal')?'Återuppta statuskontrollen':'Skapa plan och inköpslista';
    // A blur/change can occur between pointer-down and click. Keep the button's
    // text node stable in WebKit so a summary refresh cannot swallow that click.
    if($('choice-submit').textContent!==submitLabel)$('choice-submit').textContent=submitLabel;
  }
  $('personal-form').addEventListener("input",event=>{if(!event.target.closest('dialog'))updateChoiceSummary();});
  $('personal-form').addEventListener("change",event=>{if(!event.target.closest('dialog'))updateChoiceSummary();});
  new MutationObserver(updateChoiceSummary).observe($('planning-choices'),{attributes:true,attributeFilter:["disabled"]});
  new MutationObserver(updateChoiceSummary).observe($('location-selection-status'),{childList:true});
  $('choice-submit').addEventListener("click",()=>$('generate-plan').click());
  $('go-to-meals').addEventListener("click",()=>{$('meal-settings').scrollIntoView({block:"start"});$('dinner-count-value').focus({preventScroll:true});});
  document.querySelectorAll('[data-choice-jump]').forEach(node=>node.addEventListener('click',()=>{$('extra-choices').open=true;const target=$(node.dataset.choiceJump);target.scrollIntoView({block:"start"});target.querySelector('input,textarea,select')?.focus({preventScroll:true});}));
  updateChoiceSummary();

  function readMeals(){return Object.keys(names).map(t=>{
    const active=t==="dinner"||$(`enable-${t}`).checked;
    return {meal_type:t,count:active?sliderValue(`${t}-count`):0,servings:sliderValue(`${t}-servings`),diet:$(`${t}-diet`).value,
      profile:{},distribution:active?Object.fromEntries(Object.keys(proteinNames).map(k=>[k,sliderValue(`${t}-${k}`)]).filter(([,v])=>v!==null)):{},
      limits:active?Object.fromEntries(Object.keys(limitLabels).map(k=>[k,sliderValue(`${t}-${k}`)])):{},organic_animals:$(`${t}-organic`).checked};
  });}

  function requestPayload({standalone=false}={}) {

    if(!privateState)throw new Error("Gästskafferiet måste kunna läsas innan beräkning.");

    if($('profile-text').value.trim()!==parsedText)throw new Error("Tolka och granska beskrivningen före tillämpning, eller töm fritexten och redigera fälten direkt.");

    if($('unresolved-text').value.trim())throw new Error("Beskrivningen innehåller otolkade val. För in dem i rätt fält före tillämpning.");

    if(!standalone){
      const active=Object.keys(names).filter(t=>t==="dinner"||$(`enable-${t}`).checked);
      for(const t of active)if(!distributionSync[t]())throw new Error(`${names[t]}: kontrollera Fördelning.`);
      if(!active.some(t=>sliderValue(`${t}-count`)>0))throw new Error("Välj minst ett måltidstillfälle, eller beräkna bara dina varor under Inköpslista.");
    }
    const meals=standalone?[]:recipeControls.mealValues(readMeals());
    if(!standalone&&!recipeControls.validate()){$('personal-form').reportValidity();throw new Error("Kontrollera receptvalens intervall.");}

    return {...(standalone?recipeControls.storeValues():recipeControls.values()),...locationControls.values(),membership_price_policy:"all_advertised",purchase_planning_mode:"estimated",recipes:meals.find(m=>m.meal_type==="dinner")?.count||0,servings:meals.find(m=>m.meal_type==="dinner")?.servings||1,max_stores:Number($('max-stores').value),memberships:[...document.querySelectorAll('input[name="membership"]:checked')].map(n=>n.value),diversity_mode:"balanced",varied_budget_percent:25,strategy:"optimized",personal:{profile:profile(),meals,extras,pantry_revision:privateState.revision,use_pantry:$('planning-use-pantry').checked,allow_nutrition_estimates:true,organic_percent:Number($('organic-percent').value),organic_animals:$('organic-animals').checked,surplus_mode:$('surplus-mode').value}};

  }

  function putChoices(request){
    $('planning-use-pantry').checked=request.personal?request.personal.use_pantry!==false:request.use_pantry!==false;
    locationControls.restore(request);
    const spec=request.personal;if(!spec){recipeControls.restore(request);return;}
    // Consolidate older per-meal profiles so exclusions and allergies are not lost.
    const merged=Object.fromEntries(Object.keys(profileLabels).map(k=>[k,[...new Set([...(spec.profile?.[k]||[]),...(spec.meals||[]).flatMap(m=>m.profile?.[k]||[])])]]));
    putProfile(merged);$('profile-text').value="";parsedText="";$('unresolved-text').value="";$('unresolved-label').hidden=true;
    const migrated=(spec.meals||[]).some(m=>Object.values(m.profile||{}).some(v=>v.length));
    $('profile-migration-note')?.remove();
    if(migrated){const note=el("p","Tidigare smakval, uteslutningar och allergier per måltid har samlats här och gäller hela nästa plan. Granska dem innan du skapar en ny plan.","data-note");note.id="profile-migration-note";$('profile-fields').before(note);}
    for(const t of Object.keys(names)){
      const meal=spec.meals?.find(m=>m.meal_type===t)||{};
      setSlider(`${t}-count`,meal.count|| (t==="dinner"?0:5));setSlider(`${t}-servings`,meal.servings??1);
      if(t!=="dinner")$(`enable-${t}`).checked=meal.count>0;
      $(`${t}-diet`).value=meal.diet||"mixed";
      Object.keys(proteinNames).forEach(k=>{sliders.get(`${t}-${k}`).maximum(7);setSlider(`${t}-${k}`,meal.distribution?.[k]);});
      Object.keys(limitLabels).forEach(k=>setSlider(`${t}-${k}`,meal.limits?.[k]));
      if(t==="dinner"&&request.recipe_preferences?.min_protein_g!=null)setSlider(`${t}-min_protein_g`,Math.max(meal.limits?.min_protein_g??0,request.recipe_preferences.min_protein_g));
      $(`${t}-organic`).checked=meal.organic_animals===true;syncMeal(t);distributionSync[t]();
    }
    setSlider('organic-percent',spec.organic_percent??0);$('organic-animals').checked=spec.organic_animals===true;$('surplus-mode').value=spec.surplus_mode||"minimize";
    setSlider('max-stores',request.max_stores??2);$('postal-code').value=request.postal_code||"";
    document.querySelectorAll('input[name="membership"]').forEach(n=>n.checked=(request.membership_programs||request.memberships||[]).includes(n.value));recipeControls.restore(request);updateChoiceSummary();
  }

  $('personal-form').addEventListener("submit",e=>{e.preventDefault();void task(async()=>{if(window.SmakoRecipes.pendingJob("personal")){await resumePersonalJob();return;}const payload=requestPayload();window.SmakoRecipes.storage.set("smako.personal.requestDraft",payload);$('generate-plan').textContent="Skapar din gemensamma plan…";notify("Alla måltider räknas mot samma korg. En stor plan kan ta flera minuter. Dina krav och senaste sparade plan behålls medan du väntar.");startProgress($('choice-submit'));const result=await api("/api/plans",payload);await progress?.finish();await accept(result.saved||result);show("plan");});});

  $('interpret-profile').addEventListener("click",()=>void task(async()=>{
    const source=$('profile-text').value;
    const parsed=await api("/api/personal/interpret-profile",{text:source});
    if($('profile-text').value!==source)throw new Error("Texten ändrades under tolkningen. Tolka den nya texten igen.");
    const box=el("div");box.append(el("h2","Granska tolkade val"),el("p","Kontrollera och korrigera förslaget. Befintliga hårda krav följer med; ändra dem uttryckligen i fälten om det behövs."));
    const fields=el("div",null,"personal-grid");profileFields(fields,"review");box.append(fields);
    openDialog(box);
    const current=profile(),proposed={...parsed.profile};
    for(const key of ["exclusions","allergies"])proposed[key]=[...new Set([...(current[key]||[]),...(proposed[key]||[])])];
    putProfile(proposed,"review");
    if(parsed.unresolved.length)box.append(el("p",`Inte tolkat: ${parsed.unresolved.join("; ")}`,"data-note"));
    box.append(button("Tillämpa granskade val",async()=>{
      if($('profile-text').value!==source)throw new Error("Texten har ändrats. Stäng och tolka igen.");
      putProfile(profile("review"));parsedText=source.trim();$('unresolved-label').hidden=!parsed.unresolved.length;$('unresolved-text').value=parsed.unresolved.join("\n");$('personal-dialog').close();
    },true));
  }));

  $('save-profile').addEventListener("click",()=>void task(async()=>{requestPayload();privateState=await api("/api/personal/profile",{revision:privateState.revision,profile:profile(),save_explicitly:true},"PUT");renderPantry();}));

  function openDialog(content){$('dialog-body').replaceChildren(content);if(!$('personal-dialog').open)$('personal-dialog').showModal();}

  function stopScanner(){if(scanner){scanner.stop();scanner=null;}}

  $('dialog-close').addEventListener("click",()=>{$('personal-dialog').close();stopScanner();});$('personal-dialog').addEventListener("close",stopScanner);window.addEventListener("pagehide",stopScanner);document.addEventListener("visibilitychange",()=>{if(document.hidden)stopScanner();});

  const NONFOOD=/(servett|toalettpapper|hushållspapper|diskmedel|diskborste|bakplåtspapper|avfallspåsar|soppåsar|blöj)/i;
  const amountText=(quantity,unit)=>unit==="g"&&quantity>=1000?`${number(quantity/1000)} kg`:unit==="ml"&&quantity>=1000?`${number(quantity/1000)} l`:`${number(quantity)} ${unit}`;
  const itemLabel=item=>`${item.query.charAt(0).toUpperCase()}${item.query.slice(1)} · ${amountText(item.quantity,item.unit)}`;
  // Generic items are the main path: shown interpretation, one tap, optimised with the recipes.
  async function quickAdd(item){const row={id:crypto.randomUUID(),kind:"generic",query:item.query.slice(0,120),quantity:item.quantity,unit:item.unit,properties:item.properties||[],confirmed:true,use_pantry:false,food:item.food??!NONFOOD.test(item.query)};extras.push(row);await saveShopping();renderExtras();closeShoppingSuggestions();$('shopping-query').value="";$('shopping-search-status').textContent=`Lagt till: ${itemLabel(row)}. Billigaste varianten väljs tillsammans med resten av korgen.`;}
  const quickAddButton=(item,primary=false)=>button(`Lägg till ${itemLabel(item)}`,()=>quickAdd(item),primary);
  // Every exact choice falls under a generic; the server checks it as the planner does.
  function productGeneric(keys,generic=null,fallback="vara"){const typed=($('product-search').hidden?$('shopping-query'):$('product-query')).value.trim()||fallback;return api("/api/personal/product-generic",{query:typed.slice(0,120),postal_code:$('postal-code').value.trim()||"22350",product_keys:keys,...(generic?{generic}:{})});}
  function extraDialog(product=null,campaign=false,generic=null,editId=null){const salesUnit=Boolean(product?.purchase_units||product?.prices?.every(p=>p.purchase_usage==="sales_unit_only"));const box=el("div");box.append(el("h2",campaign?"Villkorat kampanjval":product?"Lägg till exakt vara":"Lägg till generisk vara"));const query=input("text",product?.display_name?.slice(0,120)||product?.name?.slice(0,120)||generic?.query||"",{maxLength:120,required:true});if(product)query.readOnly=true;const amount=input("number",(campaign?1:product?.package_quantity||generic?.quantity||1),{min:"0.001",max:"100000",step:"any",required:true});const unit=select(salesUnit?[["pack","köpförpackningar – innehållsmängd okänd"]]:[["g","gram"],["ml","milliliter"],["st","stycken"]],salesUnit?"pack":(campaign?"st":product?.package_unit||generic?.unit||"g"));if(campaign||salesUnit)unit.disabled=true;const properties=input("text",generic?.properties?.join("; ")||(product?[...product.name.matchAll(/(\d+(?:[.,]\d+)?)\s*%/g)].map(m=>`${Number(m[1].replace(",","."))} %`.replace(".",",")).join("; "):""));const use=input("checkbox","");use.checked=generic?.use_pantry===true;const explanation=el("p","Mängden är ett ytterligare behov. Hela förpackningar väljs vid beräkningen.");box.append(field("Vara",query),field("Önskad mängd",amount),field("Enhet",unit),explanation,field("Bekräftade egenskaper (semikolon mellan val)",properties),field("Använd även skafferi för denna extrarad",use));if(salesUnit){use.disabled=true;amount.min="1";amount.step="1";explanation.textContent="Du köper hela prissatta förpackningar. Innehållets gram/liter är okända och får inte räknas som receptmängd eller användas från skafferiet.";}if(campaign){use.disabled=true;explanation.textContent="Välj en kampanjmärkt variant i butiken enligt erbjudandets undantag och villkor. Hela kampanjgrupper debiteras. Näring och allergener är inte godkända.";}let interpreted=Boolean(product||generic),original=query.value;
    const productKeys=product?(product.matches?.length>1?product.matches.map(m=>m.product_key):[product.product_key]):[];
    const belongs=el("p",product?"Hör till: kontrolleras…":"","small"),link=product?productGeneric(productKeys,null,product.name||"vara"):null;
    if(product){box.append(belongs);link.then(d=>{belongs.textContent=`Hör till: ${d.name||d.generic.query}. Planeraren jämför den med övriga varor i korgen.`;}).catch(e=>{belongs.textContent=e.message;});}
    if(product&&!campaign){
      if((product.matches?.length||0)>1)box.append(el("p","Godkänn varuvalen med just detta namn, varumärke och denna förpackning. De har separata produktidentiteter i underlaget; Smako väljer bland dem när hela listan beräknas. Inga andra varianter ingår."));
      box.append(button("Tillbaka till generisk vara",()=>{const fallback=shoppingGenerics[0];extraDialog(null,false,{query:fallback?.query||$('shopping-query').value,quantity:salesUnit?(fallback?.quantity||1):Number(amount.value),unit:salesUnit?(fallback?.unit||"g"):unit.value,properties:fallback?.properties||[]},editId);}));
    }

    if(!product)box.append(button("Tolka egenskaper",async()=>{const d=await api("/api/personal/interpret-extra",{text:query.value});query.value=d.query;if(d.quantity!=null){amount.value=d.quantity;unit.value=d.unit;}properties.value=d.properties.join("; ");interpreted=true;original=query.value;}));

    box.append(button(editId?"Spara vara":"Bekräfta och lägg till",async()=>{if(!interpreted||original!==query.value)throw new Error("Tolka egenskaperna innan du bekräftar varan.");if(!amount.checkValidity()||!query.checkValidity())throw new Error("Ange varunamn och en positiv mängd.");const matches=product?.matches||[];if(matches.length>8)throw new Error("Precisera varan; för många skilda produktposter matchar.");const parent=link?(await link).generic:null;const item={id:editId||crypto.randomUUID(),kind:campaign?"campaign":matches.length>1?"one_of":product?"exact":"generic",query:query.value,quantity:Number(amount.value),unit:salesUnit?"st":unit.value,...(salesUnit?{purchase_units:true}:{}),product_key:matches.length>1?null:product?.product_key||null,...(matches.length>1?{alternatives:matches.map(m=>m.product_key),alternative_names:matches.map(m=>m.display_name.slice(0,200))}:{}),properties:properties.value.split(/[;\n]/).map(s=>s.trim()).filter(Boolean),confirmed:true,use_pantry:campaign||salesUnit?false:use.checked,food:!NONFOOD.test(query.value),...(parent?{generic:parent}:{})};if(editId)extras=extras.map(row=>row.id===editId?item:row);else extras.push(item);await saveShopping();renderExtras();closeShoppingSuggestions();$('personal-dialog').close();if($('personal-choices').hidden)show("shopping");},true));openDialog(box);}

  $('add-shopping-item').addEventListener("click",()=>{$('shopping-query').focus();if($('shopping-query').value.trim())void searchShopping();});

  function renderExtras(){const out=$('extras-list');out.replaceChildren();for(const row of extras){const card=el("article",null,"personal-card");card.append(el("strong",row.purchase_units?`${row.query} · ${number(row.quantity)} köpförpackningar`:itemLabel(row)),el("p",`${row.kind==="campaign"?"Villkorat kampanjval":row.kind==="exact"?"Exakt produkt låst":row.kind==="one_of"?"Antingen eller – väljs i hela korgen":"Generisk vara"}${row.properties.length?` · ${row.properties.join(" · ")}`:""} · ${row.use_pantry?"Skafferi får användas":"Ska köpas utöver recepten"}`));card.append(button("Ta bort extrarad",async()=>{extras=extras.filter(e=>e.id!==row.id);await saveShopping();renderExtras();}));if(row.kind==="one_of")card.append(el("p",`Antingen ${row.alternative_names?.join(" eller ")||`${row.alternatives.length} valda produkter`}. Minst ${number(row.quantity)} ${row.unit} totalt av den valda produkten.`));
      if(row.kind!=="generic")card.append(el("p",row.generic?`Hör till: ${row.generic.query}${row.generic.properties?.length?` (${row.generic.properties.join(", ")})`:""}`:"Sparad innan varor kopplades till en generisk vara. Lägg till den igen för att koppla den.","small"));
      if(row.kind==="generic")card.append(button("Ändra vara",()=>extraDialog(null,false,row,row.id)));
      if(["exact","one_of"].includes(row.kind))card.append(button("Lägg till ett antingen-eller-alternativ",async()=>{alternativeTarget=row.id;$('cancel-alternative').hidden=false;$('shopping-search-status').textContent=`Välj en annan exakt produkt för minst ${number(row.quantity)} ${row.unit}.`;$('shopping-query').focus();}));
      card.append(button("Ändra mängd",async()=>{const box=el("div"),amount=input("number",row.quantity,{min:row.purchase_units?"1":"0.001",max:"100000",step:row.purchase_units?"1":"any",required:true});box.append(field(`Minsta mängd (${row.purchase_units?"köpförpackningar":row.unit})`,amount),button("Spara mängd",async()=>{if(!amount.checkValidity())throw new Error("Ange en positiv mängd.");row.quantity=Number(amount.value);await saveShopping();renderExtras();$('personal-dialog').close();},true));openDialog(box);}));out.append(card);} updateChoiceSummary();}

  $('calculate-extras').addEventListener("click",()=>void task(async()=>{await saveShopping();if(saved){await change("extras",{extras});}else{await accept(await api("/api/plans",requestPayload({standalone:true})));}show("shopping");}));

  async function saveShopping(){
    $('shopping-draft-status').textContent="Sparar dina varor…";
    try{privateState=await api("/api/personal/shopping-list",{revision:privateState.revision,items:extras},"PUT");$('shopping-draft-status').textContent="Varuval sparade privat. Beräkna inköpslistan för att uppdatera korgen.";renderCommon();}
    catch(e){$('shopping-draft-status').textContent="Varuvalen kunde inte sparas. Dina ändringar finns kvar på sidan. Läs om vid revisionskonflikt.";throw e;}
  }
  function renderCommon(){const out=$('shopping-common');out.replaceChildren();for(const choice of privateState?.shopping_common||[]){out.append(button(`${choice.item.kind==="one_of"?(choice.item.alternative_names?.join(" eller ")||`${choice.item.query} – godkända alternativ`):choice.item.query} · ${number(choice.item.quantity)} ${choice.item.unit}`,async()=>{extras.push({...structuredClone(choice.item),id:crypto.randomUUID()});await saveShopping();renderExtras();}));}if(!out.children.length)out.append(el("p","Dina tidigare varuval visas här när du har lagt till varor."));}
  async function chooseProduct(product){
    if(!alternativeTarget){extraDialog(product,Boolean(product.campaign_choice));return;}
    if(product.campaign_choice)throw new Error("Välj kampanjen som en separat rad. Exakta alternativ kräver känd variant.");
    const row=extras.find(r=>r.id===alternativeTarget);if(!row)throw new Error("Raden finns inte längre.");
    if(Boolean(product.purchase_units)!==Boolean(row.purchase_units)||(product.purchase_units?"st":product.package_unit)!==row.unit)throw new Error("Alternativen måste kunna täcka samma enhet. Ingen omräkning mellan gram, milliliter och styck görs.");
    const keys=row.alternatives||[row.product_key],labels=keys.map((key,index)=>row.alternative_names?.[index]||(index===0?row.query:`Tidigare valt alternativ ${index+1}`));
    if(keys.includes(product.product_key))throw new Error("Produkten är redan vald på raden.");
    if(keys.length>=8)throw new Error("Välj högst åtta alternativ på en rad.");
    const box=el("div");box.append(el("h2","Bekräfta antingen eller"),el("p",`${labels.join(" eller ")} eller ${product.name} (${product.package}). Minst ${number(row.quantity)} ${row.unit}; vid mindre förpackning kan flera behövas. De exakta produkterna ersätter radens egenskapsfilter. Dina allergier och övriga gemensamma krav gäller fortfarande.`),button("Godkänn alternativet",async()=>{row.generic=(await productGeneric([...keys,product.product_key],row.generic||null)).generic;row.kind="one_of";row.properties=[];row.alternatives=[...keys,product.product_key];row.alternative_names=[...labels,product.display_name||product.name];row.product_key=null;alternativeTarget=null;$('cancel-alternative').hidden=true;await saveShopping();renderExtras();$('personal-dialog').close();},true));openDialog(box);
  }
  async function chooseSuggestion(product){
    if(!product.selectable)throw new Error("Förpackningsstorlek saknas för denna vara. Välj en annan produkt eller en generisk vara.");
    closeShoppingSuggestions();
    if(!alternativeTarget){extraDialog(product,Boolean(product.campaign_choice));return;}
    if(product.matches.length===1)return chooseProduct(product.matches[0]);
    if(product.campaign_choice)throw new Error("Välj kampanjen som en separat rad. Exakta alternativ kräver känd variant.");
    const row=extras.find(r=>r.id===alternativeTarget);if(!row)throw new Error("Raden finns inte längre.");
    if(Boolean(product.purchase_units)!==Boolean(row.purchase_units)||(product.purchase_units?"st":product.package_unit)!==row.unit)throw new Error("Alternativen måste täcka samma enhet.");
    const keys=row.alternatives?.length?row.alternatives:[row.product_key];
    const additions=product.matches.filter(m=>!keys.includes(m.product_key));
    if(!additions.length)throw new Error("Produkten är redan vald.");
    if(keys.length+additions.length>8)throw new Error("Välj högst åtta alternativ på en rad.");
    const box=el("div");box.append(el("h2","Bekräfta antingen eller"),el("p",`${row.query} eller ${product.display_name} · ${product.package}. Minst ${number(row.quantity)} ${row.unit}. Produktvalet omfattar separata varuval med detta namn, varumärke och förpackning. Butik väljs i hela korgen. De exakta valen ersätter radens egenskapsfilter; dina allergier och gemensamma krav gäller fortfarande.`),button("Godkänn alternativet",async()=>{row.generic=(await productGeneric([...keys,...additions.map(m=>m.product_key)],row.generic||null)).generic;row.kind="one_of";row.properties=[];row.alternatives=[...keys,...additions.map(m=>m.product_key)];row.alternative_names=[...(row.alternative_names?.length?row.alternative_names:[row.query]),...additions.map(m=>m.display_name.slice(0,200))];row.product_key=null;alternativeTarget=null;$('cancel-alternative').hidden=true;await saveShopping();renderExtras();$('personal-dialog').close();},true));openDialog(box);
  }
  function closeShoppingSuggestions(){ $('shopping-suggestions').hidden=true;$('shopping-query').setAttribute("aria-expanded","false"); }
  async function searchShopping(){
    const text=$('shopping-query').value.trim();
    if(!text){++searchGeneration;searchAbort?.abort();shoppingGenerics=[];closeShoppingSuggestions();return;}
    const generation=++searchGeneration;searchAbort?.abort();const controller=new AbortController();searchAbort=controller;
    const parsedPromise=alternativeTarget?null:api("/api/personal/interpret-extra",{text}).catch(e=>({error:e.message}));
    try{const response=await fetch(`/api/personal/shopping-suggestions?q=${encodeURIComponent($('shopping-query').value)}&postal_code=${encodeURIComponent($('postal-code').value.trim())}`,{signal:controller.signal,cache:"no-store"});const data=await response.json();if(generation!==searchGeneration)return;if(!response.ok)throw new Error(typeof data.detail==="string"?data.detail:"Sökningen kunde inte läsas.");
      const out=$('shopping-suggestions');shoppingGenerics=data.generics;out.replaceChildren();out.hidden=false;$('shopping-query').setAttribute("aria-expanded","true");const generic=el("div"),specific=el("div");generic.id="shopping-generic-results";specific.id="shopping-specific-results";out.append(generic,specific);
      const parsed=parsedPromise?await parsedPromise:null;if(generation!==searchGeneration)return;
      if(!alternativeTarget){
        generic.append(el("h3","Lägg till vara"));
        // The typed text first: with an amount it is added as read; a curated
        // item with the same name brings its usual amount; otherwise ask.
        const same=parsed&&!parsed.error&&parsed.quantity==null?data.generics.find(g=>g.query.toLowerCase()===parsed.query.toLowerCase()):null;
        const main=parsed?.quantity!=null?{query:parsed.query,quantity:parsed.quantity,unit:parsed.unit,properties:parsed.properties}:same;
        if(main)generic.append(quickAddButton(main,true));
        else if(parsed?.error)generic.append(el("p",parsed.error,"small"));
        else if(parsed)generic.append(button(`Lägg till ”${parsed.query}” – välj mängd`,async()=>{closeShoppingSuggestions();extraDialog(null,false,{...parsed,quantity:1,unit:"g"});},true));
        const shown=main?`${main.query.toLowerCase()}|${main.quantity}|${main.unit}`:null;
        for(const row of data.generics)if(`${row.query.toLowerCase()}|${row.quantity}|${row.unit}`!==shown)generic.append(quickAddButton(row));
        if(parsed&&!parsed.error)generic.append(button("Annan mängd eller egenskap…",async()=>{closeShoppingSuggestions();extraDialog(null,false,main||{...parsed,quantity:1,unit:"g"});}));
        if(data.products.length){const toggle=el("button",`Välj en exakt produkt i stället (${data.products.length})`,"shopping-exact-toggle");toggle.type="button";toggle.setAttribute("aria-expanded","false");toggle.setAttribute("aria-controls","shopping-specific-results");toggle.addEventListener("click",()=>{specific.hidden=!specific.hidden;toggle.setAttribute("aria-expanded",String(!specific.hidden));});generic.append(toggle);specific.hidden=true;}
      }
      specific.append(el("h3","Specifika produkter"));for(const row of data.products){const choice=button(`${row.display_name} · ${row.package}`,()=>chooseSuggestion(row));choice.disabled=!row.selectable;if(!row.selectable)choice.title="Förpackningsstorlek saknas i underlaget.";specific.append(choice);}
      $('shopping-search-status').textContent=data.status==="no_area_data"?"Produktunderlag saknas för valt postnummer.":alternativeTarget?"Välj en exakt alternativ produkt. Mängden på raden behålls.":"Priser räknas först för hela listan. Samma verifierade produkt visas en gång.";
    }catch(e){if(controller.signal.aborted||generation!==searchGeneration)return;closeShoppingSuggestions();$('shopping-search-status').textContent=e.message||"Varuförslagen kunde inte hämtas.";}
  }
  $('shopping-query').addEventListener("keydown",e=>{if(e.key==="Enter"){e.preventDefault();if(!$('shopping-suggestions').hidden)$('shopping-generic-results')?.querySelector("button.primary-button")?.click();}if(e.key==="Escape"){closeShoppingSuggestions();}if(e.key==="ArrowDown"&&!$('shopping-suggestions').hidden){e.preventDefault();$('shopping-suggestions').querySelector("button")?.focus();}});
  $('shopping-suggestions').addEventListener("keydown",e=>{const buttons=[...$('shopping-suggestions').querySelectorAll("button")];const i=buttons.indexOf(document.activeElement);if(e.key==="Escape"){closeShoppingSuggestions();$('shopping-query').focus();}if(e.key==="ArrowDown"||e.key==="ArrowUp"){e.preventDefault();buttons[(i+(e.key==="ArrowDown"?1:-1)+buttons.length)%buttons.length]?.focus();}});
  document.addEventListener("click",e=>{if(!$('shopping-search-box').contains(e.target)&&!$('add-shopping-item').contains(e.target))closeShoppingSuggestions();});
  $('cancel-alternative').addEventListener("click",()=>{alternativeTarget=null;$('cancel-alternative').hidden=true;void searchShopping();});
  $('shopping-query').addEventListener("input",()=>{clearTimeout(searchTimer);++searchGeneration;searchAbort?.abort();closeShoppingSuggestions();searchTimer=setTimeout(()=>void searchShopping(),250);});
  document.querySelectorAll('[data-open="shopping"]').forEach(b=>b.addEventListener("click",()=>void searchShopping()));
  window.addEventListener("pagehide",()=>{clearTimeout(searchTimer);++searchGeneration;searchAbort?.abort();});
  $('calculate-own-list').addEventListener("click",()=>void task(async()=>{if(!extras.length)throw new Error("Lägg till minst en vara.");if(window.SmakoRecipes.pendingJob("personal")){await resumePersonalJob();return;}await saveShopping();startProgress($('calculate-own-list'));const result=await api("/api/plans",requestPayload({standalone:true}));await progress?.finish();await accept(result);show("shopping");}));

  async function accept(envelope,{clearJob=true}={}){saved=envelope;extras=structuredClone(saved.request.personal.extras);putChoices(saved.request);try{localStorage.setItem("smako.personal.lastPlan",saved.plan_id);}catch(_){}if(clearJob)window.SmakoRecipes.forgetJob("personal");history.replaceState({},"",`/personal#plan=${encodeURIComponent(saved.plan_id)}`);renderPlan();renderExtras();await refreshState();}

  async function change(action,fields={}){if(!saved)throw new Error("Skapa en plan först.");if(["extras","recalculate"].includes(action))fields={...fields,purchase_planning_mode:"estimated",allow_nutrition_estimates:true};const result=await api(`/api/personal/plans/${encodeURIComponent(saved.plan_id)}/change`,{revision:saved.revision,pantry_revision:privateState.revision,action,...fields});saved=result.saved;window.SmakoRecipes.forgetJob("personal");privateState=result.state;extras=structuredClone(saved.request.personal.extras);renderPlan();renderPantry();renderExtras();if(!document.querySelector("dialog[open]"))focusView();}

  function renderPlan(){const plan=saved.plan, personal=plan.personal;if(!personal)return;const out=$('plan-content');out.replaceChildren();document.querySelector('.personal-intro').hidden=true;const top=el("section",null,"plan-hero");const filled=personal.slots.filter(s=>s.recipe),dinners=filled.filter(s=>s.meal_type==="dinner").length;top.append(el("h1","Din plan"),el("p",`${dinners} middagar · ${filled.length-dinners} övriga måltider · ${plan.portions} portioner${personal.empty_slots?` · ${personal.empty_slots} tomma tillfällen`:""}`,"plan-hero-sub"),el("div",`${plan.optimized_basket.verification_status==="VERIFIED_WITH_ESTIMATES"?"ca ":""}${money(plan.optimized_basket.total)}`,"personal-total"),el("p",`${plan.optimized_basket.verification_status==="VERIFIED_WITH_ESTIMATES"?"Uppskattad full inköpskostnad":"Beräknad full inköpskostnad"} · ${plan.optimized_basket.store_count} av max ${saved.request.max_stores} inköpsställen`));const membership=window.SmakoRecipes.membershipSummary(plan);if(membership)top.append(el("p",membership,"membership-plan-summary"));const storeList=el("ul",null,"plan-hero-stores");plan.optimized_basket.stores.forEach(g=>{const li=el("li");li.append(el("span",g.store_name),el("strong",money(g.subtotal)));storeList.append(li);});top.append(storeList);const actions=el("div",null,"personal-actions plan-hero-actions");actions.append(button("Öppna inköpslistan",async()=>show("shopping"),true),button("Ny plan",async()=>show("choices")));top.append(actions);
    // Meals first, then everything about the plan in a quieter section below.
    const meals=el("section",null,"plan-meals"),about=el("section",null,"plan-about");meals.append(el("h2","Måltider"));const aboutActions=el("div",null,"personal-actions");aboutActions.append(button("Räkna om med aktuellt skafferi/pris",()=>change("recalculate")));about.append(el("h2","Om planen"),aboutActions,el("p",`Revision ${saved.revision}. Receptbyte och uttrycklig omräkning sparar en ny revision. Tidigare resultat bevaras.`,"recipe-plan-revision"));const searchNotice=window.SmakoRecipes.searchNotice(plan,saved.request.diversity_mode);if(searchNotice)top.append(searchNotice);if(plan.optimized_basket.stores.some(g=>g.items.some(i=>i.conditional_variant_choice)))top.append(el("p","Villkorad inköpsplan: välj kampanjmärkta varianter enligt radernas villkor. Inte ett verifierat slutkvitto."));if(saved.prices_changed_since_creation||saved.price_contexts_changed_since_creation)top.append(el("p","Sparade priser visas. Prisunderlaget har ändrats; räkna om för aktuell korg.","data-note"));out.append(top);const comparison=el("div");for(const row of personal.checks.same_menu_comparisons||[]){comparison.append(el("p",row.status==="FEASIBLE"?`Samma recept, skafferibidrag och extrabehov med max ${row.max_stores} inköpsställen: ${money(row.total)}. ${row.stores.map(s=>s.name).join(" · ")}`:`Samma meny med max ${row.max_stores} inköpsställen: ingen genomförbar korg hittades med dina krav.`));}if(comparison.children.length)about.append(details("Samma meny i färre butiker",comparison));

    const summary=el("p",`Skafferibidrag: ${personal.allocations.length?personal.allocations.map(a=>`${number(a.quantity)} ${a.unit} ${a.name}`).join(" · "):"Inget allokerat"}. Detta är mängder från verkligt lager, ingen påhittad besparing.`);about.append(summary);

    [...personal.slots].sort((a,b)=>a.day-b.day||Object.keys(names).indexOf(a.meal_type)-Object.keys(names).indexOf(b.meal_type)).forEach(slot=>{const card=el("article",null,`plan-meal${slot.recipe?"":" is-empty"}`);card.append(el("p",`Dag ${slot.day} · ${names[slot.meal_type]}`,"eyebrow plan-meal-day"),el("h3",slot.recipe?.name||"Tomt måltidstillfälle"));if(slot.recipe){const protein=personal.checks.distribution.find(d=>d.slot_id===slot.id)?.protein;const mealLabel=window.SmakoRecipes.mealDescription(slot.recipe,protein);card.append(el("p",`${slot.recipe.servings} portioner${mealLabel?` · ${mealLabel}`:""}`));const nutrition=personal.checks.nutrition.find(n=>n.slot_id===slot.id);if(nutrition?.values?.protein_g!=null){card.append(el("p",`${window.SmakoRecipes.nutritionNumber(nutrition.values.protein_g,nutrition.status)} g protein per portion · ${nutrition.status==="ESTIMATED"?"spårbar uppskattning":"produktdeklarationer"}`));if(!slot.recipe.design)card.append(window.SmakoRecipes.nutritionInformation(nutrition));}const content=el("div");if(slot.recipe.preparation){content.append(el("p",`Receptversion: ${slot.recipe.preparation.version} · ${slot.recipe.preparation.origin==="smako_recipe_design"?"Smakos receptutformning":"Separat anpassad version"}.`),el("p","Mängderna avser använda ätbara ingredienser för hela receptet. Näring per portion är en uppskattning från dessa insatser; tillagad slutvikt och näring per 100 g färdig rätt är inte verifierade.","data-note"));}const ingredients=el("ul");slot.recipe.ingredients.forEach(i=>ingredients.append(el("li",`${number(i.quantity)} ${i.unit} ${i.name}`)));const steps=el("ol");slot.recipe.instructions.forEach(s=>steps.append(el("li",s.replace(/\bas_sold\b/g,"som såld").replace(/\braw_edible\b/g,"rå ätbar mängd").replace(/\bcooked_drained\b/g,"kokt och avrunnen").replace(/\bdry\b/g,"torr"))));content.append(ingredients,steps);if(slot.recipe.design)content.replaceChildren(window.SmakoRecipes.renderRecipe(slot.recipe,{nutrition,personal,slotId:slot.id}));card.append(details("Öppna recept",content));}const buttons=el("div",null,"personal-actions plan-meal-actions");buttons.append(button(slot.recipe?"Redigera":"Fyll med eget recept",async()=>editRecipe(slot)),button(slot.recipe?.design?"Byt recept och räkna om inköpen":slot.recipe?"Byt recept":"Föreslå recept",()=>change("replace",{slot_id:slot.id})));if(slot.recipe){buttons.append(button("Ta bort",()=>change("remove",{slot_id:slot.id})));if(slot.recipe.design)buttons.append(button("Så blev rätten",async()=>window.SmakoRecipes.recipeFeedback({recipe:slot.recipe,recipeIndex:personal.slots.filter(s=>s.recipe).findIndex(s=>s.id===slot.id),planId:saved.plan_id,revision:saved.revision})));}card.append(buttons);meals.append(card);});

    const checks=el("div");checks.append(el("p",`Inköpsmängder: kontrollerade. Allergier: ${personal.checks.allergy==="VERIFIED"?"verifierade mot spårbara deklarationer":"ingen verifierad allergikontroll begärd"}.`));checks.append(el("p",`${personal.checks.organic_definition} Beräknad verifierad kostnadsandel: ${personal.checks.organic_cost_percent==null?"inget matinköp":`${number(personal.checks.organic_cost_percent)} %`}. Okänd status räknas inte positivt.`));const eco=personal.checks.organic_evidence;if(eco){checks.append(el("p",eco.status==="NO_NEW_FOOD_PURCHASES"?"Inga nya matinköp: ekoandelen är inte tillämplig. Detta räknas inte som 100 % ekologiskt.":`${money(eco.organic_food_cost)} verifierat ekologiskt av ${money(eco.food_cost)} i matinköp efter rabatter. Skafferi, avgifter och andra varor ingår inte.`));for(const line of eco.lines||[])checks.append(el("p",`${line.name}: ${money(line.cost)} · ${line.organic===true?"verifierat ekologisk":line.organic===false?"källan anger ej ekologisk":"ekostatus okänd"}`));}checks.append(el("p",`Animaliskt eko: ${personal.checks.organic_animals==="VERIFIED"?"kontrollerat mot produktunderlaget":"ej kontrollerat"}.`));personal.checks.nutrition.forEach(n=>{checks.append(el("p",`${n.slot_id}: ${["VERIFIED","ESTIMATED"].includes(n.status)?Object.entries(n.values).map(([k,v])=>`${({protein_g:"Protein",carbs_g:"Kolhydrater",fat_g:"Fett",kcal:"Energi",weight_g:"Tillagad portionsvikt"})[k]||k}: ${window.SmakoRecipes.nutritionNumber(v,n.status)} ${k==="kcal"?"kcal":"g"}`).join(" · "):"näringsgränser ej valda; full produktnäring och tillagad vikt är inte verifierade"}`));if(n.status==="ESTIMATED")checks.append(el("p","Gränser uppfyllda enligt beräkningen · spårbara uppskattningar används."));if(n.calculation_basis)checks.append(el("p",n.calculation_basis.description));for(const source of n.sources||[])if(source.basis)checks.append(el("p",source.evidence_kind==="served_weight_estimate"?`UPPSKATTNING · Tillagad/serverad portionsvikt: ${number(source.total_g/source.servings)} g. ${source.basis} Källa: ${source.source}.`:`${source.ingredient||""} · ${source.evidence_kind&&source.evidence_kind!=="qualified_product_declaration"?"UPPSKATTNING · ":"Produktdeklaration · "}${source.origin==="pantry"?"Skafferibidrag":"Receptingrediens"}: ${number(source.quantity)} ${source.unit}. ${source.basis}. Källa: ${source.source.split(":")[0]}.`,"small"));});about.append(details("Krav och databegränsningar",checks));const ingredientChecks=personal.checks.ingredient_exclusions||[];if(ingredientChecks.length){const box=el("div");box.append(el("p","Hårt matval: inga uteslutna ingredienser enligt granskat källunderlag. Detta är ingen allergisäkerhetskontroll."));for(const row of ingredientChecks){box.append(el("p",`${row.name}: ${row.ingredients.join("; ")} · ${row.evidence_kind==="reviewed_single_unprocessed_crop"?"granskad eningrediensråvara, produktbeskrivning och råvarukategori":"granskad ingrediensdeklaration"}`));}about.append(details("Ingredienskontroll för dina matval",box));}const audit=el("div");audit.append(el("p",`Planrevision ${saved.revision} · ${plan.app_version} · ${plan.build_id}`),el("p",`Prisunderlag: ${plan.data?.price_universe_id||"saknas"}`),el("p",`Personlig beräkningsversion: ${personal.version}`));about.append(details("Tekniska detaljer",audit));out.append(meals,about);$('personal-version').textContent=plan.app_version;renderShopping();renderSuggestions();}

  // Shopping list: one row per product, in aisle order within each store. Picked
  // and struck rows are a per-viewer note in this browser; they never change the
  // plan, its total or its bookkeeping.
  const AISLES=[["produce","Frukt & grönt"],["bread","Bröd"],["protein","Kött, fågel & fisk"],["dairy","Mejeri & ägg"],["pantry","Skafferi"],["frozen","Fryst"],["other","Övrigt"]];
  // Display order only, from the product's own food family, else a few common words.
  function aisleOf(row){
    const family=row.food_family,text=`${row.ingredient} ${row.product_name}`.toLowerCase();
    if(/fryst|frozen/.test(`${row.product_form||""} ${text}`))return "frozen";
    if(row.product_role==="bread"||/bröd|tortilla|pita|baguette|bagel|bulle/.test(text))return "bread";
    if(["vegetable","fruit","allium","fungus","herb"].includes(family))return "produce";
    if(["meat","poultry","fish","seafood"].includes(family))return "protein";
    if(["dairy","egg"].includes(family))return "dairy";
    if(["grain","legume","condiment","broth","fat","spice","nut","seed","sugar"].includes(family))return "pantry";
    if(/kyckling|fläsk|nötkött|färs|lax|torsk|fisk|räk|bacon|korv|skinka|kött/.test(text))return "protein";
    if(/mjölk|grädde|yoghurt|\bost|smör|ägg|filmjölk|crème|kvarg|keso/.test(text))return "dairy";
    if(/lök|tomat|gurka|paprika|morot|potatis|sallad|spenat|kål|broccoli|äpple|banan|citron|lime|ingefära|persilja|koriander|basilika|dill|mynta|svamp|champinjon|zucchini|aubergine|avokado|purjo|selleri|bär|frukt/.test(text))return "produce";
    if(/ris|pasta|mjöl|socker|olja|vinäger|buljong|krossade|bönor|linser|kikärt|krydd|salt|peppar|nudlar|havre|sås|konserv/.test(text))return "pantry";
    return "other";
  }
  const picksKey=()=>`smako.shopping.${saved.plan_id}.${saved.revision}`;
  // Kept in localStorage so the ticks survive until the shop; cleared on sign-out.
  const picksStore={get(){try{return JSON.parse(localStorage.getItem(picksKey())||"{}")||{};}catch(_){return {};}},set(value){try{localStorage.setItem(picksKey(),JSON.stringify(value));}catch(_){/* Optional per-viewer note. */}}};
  const rowKey=row=>`${row.store_id}|${row.product_id}|${row.ingredient}`;
  function setPick(row,item,state){
    const picks=picksStore.get();
    if(state)picks[rowKey(row)]=state;else delete picks[rowKey(row)];picksStore.set(picks);
    paintRow(item,state);updateShopProgress();
  }
  function paintRow(item,state){
    item.dataset.state=state||"";const name=item.querySelector(".shop-name").textContent;
    const check=item.querySelector(".shop-check"),remove=item.querySelector(".shop-remove");
    check.setAttribute("aria-checked",String(state==="picked"));check.disabled=state==="removed";
    remove.setAttribute("aria-pressed",String(state==="removed"));remove.textContent=state==="removed"?"↺":"×";
    remove.setAttribute("aria-label",state==="removed"?`Ångra överstrykning av ${name}`:`Stryk ${name} från listan`);
  }
  function updateShopProgress(){
    const out=$('shopping-content');
    for(const box of [out,...out.querySelectorAll(".shop-store")]){
      const rows=[...box.querySelectorAll(".shop-row")].filter(r=>r.dataset.state!=="removed"),picked=rows.filter(r=>r.dataset.state==="picked").length;
      const label=box===out?out.querySelector(".shop-progress-text"):box.querySelector(".shop-store-count");
      if(label)label.textContent=box===out?(rows.length&&picked===rows.length?"Allt plockat – bra jobbat!":`${picked} av ${rows.length} varor plockade`):`${picked}/${rows.length}`;
      if(box===out){const bar=out.querySelector(".shop-progress-fill");if(bar)bar.style.width=`${rows.length?100*picked/rows.length:0}%`;}
      else box.classList.toggle("is-done",!!rows.length&&picked===rows.length);
    }
  }
  function shopRow(row,body,{type,estimated}){
    const item=el("li",null,"shop-row");item.dataset.aisle=aisleOf(row);
    const check=el("button",null,"shop-check");check.type="button";check.setAttribute("role","checkbox");
    const more=el("details",null,"shop-more"),summary=el("summary",null,"shop-summary"),main=el("span",null,"shop-main");
    const amount=row.sale_model==="sold_by_weight"?`${estimated?"ca ":""}${number(row.purchased_quantity)} ${row.purchased_unit}`:`${row.packages_needed} st${row.package_quantity&&row.package_unit?` × ${number(row.package_quantity)} ${row.package_unit}`:""}`;
    main.append(el("span",row.product_name,"shop-name"),el("span",[amount,row.price_mechanism!=="regular"||row.group_applications?.length?type:null,row.membership_required?row.membership_program:null].filter(Boolean).join(" · "),"shop-meta"));
    summary.append(main,el("span",`${estimated?"ca ":""}${money(row.total_price)}`,"shop-price"));more.append(summary,body);
    const remove=el("button",null,"shop-remove");remove.type="button";
    item.append(check,more,remove);
    check.setAttribute("aria-label",`Plockad: ${row.product_name}`);
    check.addEventListener("click",()=>setPick(row,item,item.dataset.state==="picked"?null:"picked"));
    remove.addEventListener("click",()=>setPick(row,item,item.dataset.state==="removed"?null:"removed"));
    paintRow(item,picksStore.get()[rowKey(row)]||null);
    return item;
  }
  function shopStore(store){
    const section=el("section",null,"shop-store"),head=el("header",null,"shop-store-head");
    head.append(el("h2",store.store_name),el("span",null,"shop-store-count"),el("span",money(store.subtotal),"shop-store-total"));section.append(head);
    const order=Object.fromEntries(AISLES.map(([key],i)=>[key,i]));
    const rows=[...store.items].sort((a,b)=>order[aisleOf(a)]-order[aisleOf(b)]||a.product_name.localeCompare(b.product_name,"sv"));
    let list=null,current=null;
    return {section,rows,add(item){
      if(item.dataset.aisle!==current){current=item.dataset.aisle;section.append(el("h3",AISLES[order[current]][1],"shop-aisle"));list=el("ul",null,"shop-list");section.append(list);}
      list.append(item);
    }};
  }

  function renderShopping(){const out=$('shopping-content'),plan=saved.plan;out.replaceChildren();const booked=(privateState.ledger||[]).some(e=>e.plan_id===saved.plan_id&&e.revision===saved.revision&&e.action==="purchase");const total=el("p",`${plan.optimized_basket.verification_status==="VERIFIED_WITH_ESTIMATES"?"ca ":""}${money(plan.optimized_basket.total)}`,"personal-total");total.append(el("span",` · ${booked?"bokförda köp i denna revision":"hela förpackningar för hela korgen"}`,"shop-total-note"));out.append(total);const membership=window.SmakoRecipes.membershipSummary(plan);if(membership)out.append(el("p",membership,"membership-plan-summary"));const progressBox=el("div",null,"shop-progress"),meter=el("div",null,"shop-progress-meter");meter.append(el("span",null,"shop-progress-fill"));
    progressBox.append(el("p",null,"shop-progress-text"),meter,el("p","Bocka av det du har plockat och stryk det du inte ska köpa. Det sparas bara i den här webbläsaren; totalen och planen ändras inte – räkna om planen för att ta bort varor ur korgen.","shop-progress-hint"));out.append(progressBox);
    if(booked)out.append(el("p","Köpet är bokfört. Räkna om planen för att se aktuella återstående köpbehov."));const financials=window.SmakoRecipes.financials(plan);if(financials)out.append(financials);for(const store of plan.optimized_basket.stores){const group=shopStore(store);out.append(group.section);for(const row of group.rows){const card=el("div",null,"shop-more-body");const need=plan.personal.needs.find(n=>n.key===row.ingredient);const applied=row.applied_offer;let type=row.group_applications?.length?"Kampanjgrupp (fördelad kostnad)":row.price_mechanism==="multibuy"?"Flerköp":row.membership_required?"Medlemspris":row.price_mechanism==="regular"?"Ordinarie / rapporterat grundpris":"Kampanjpris";card.append(el("strong",`${row.sale_model==="sold_by_weight"?`${number(row.purchased_quantity)} ${row.purchased_unit} lösvikt`:`${row.packages_needed} förpackning${row.packages_needed===1?"":"ar"}`} · ${row.quantity_confidence==="estimated"?"ca ":""}${money(row.total_price)}`),el("p",`${type} används. Användbar mängd ${row.quantity_confidence==="estimated"?"ca ":""}${number(row.purchased_usable_quantity)} ${row.unit}; recept-/inköpsbehov ${number(row.required_quantity)} ${row.unit}.`));if(Number.isFinite(row.purchased_quantity)&&row.purchased_unit&&(row.purchased_unit!==row.unit||Math.abs(row.purchased_quantity-row.purchased_usable_quantity)>0.000001))card.append(el("p",`Planerad inköpt mängd: ${number(row.purchased_quantity)} ${row.purchased_unit}. Användbar mängd redovisas separat.`));if(row.quantity_confidence==="estimated")card.append(el("p",`Den användbara mängden är uppskattad. Kontrollväg minst ${number(row.required_quantity)} ${row.unit} användbar mängd för recepten; komplettera inköpet om den inte räcker. Beräknade rester är också uppskattade.`,"data-note"));if(row.membership_required)card.append(el("p",`Kräver medlemskap: ${row.membership_program}.`));if(applied&&!row.group_applications?.length)card.append(el("p",`${applied.description} · ${applied.price_basis_unit==="kg"?`${money(applied.price)}/kg`:`${applied.required_packages} för ${money(applied.price)}`} · köpantal ${applied.required_packages}${applied.max_quantity?` · max ${applied.max_quantity} rabattgrupper`:""}. Gäller ${applied.valid_from||"startdatum saknas"} – ${applied.valid_to||"slutdatum saknas"}.`));else if(!row.group_applications?.length)card.append(el("p","Ingen villkorad rabatt används av denna rad."));if(row.group_applications?.length&&row.group_residual_packages)card.append(el("p",`${row.group_residual_packages} övriga förpackningar: ${money(row.group_residual_total)} enligt radens övriga prisvillkor.`));for(const application of row.group_applications||[]){const g=application.group;card.append(el("p",g.pricing_rule==="fixed_total"?`${g.required_packages} valfria i kampanjen för ${money(g.amount)}`:`${g.required_packages} valfria i kampanjen ger ${money(g.amount)} rabatt på ordinarie paketpris`),el("p",`Bidrar: ${application.contributors.map(c=>`${c.packages} × ${c.product_name}`).join(" · ")}. Gäller ${g.valid_from} – ${g.valid_to}${g.membership_program?` · Kräver ${g.membership_program}`:""}${g.max_groups?` · Max ${g.max_groups} kampanjgrupper`:""}. Varje förpackning räknas bara en gång.`));}card.append(el("p",row.price_context_type?.toLowerCase().includes("online")?"Onlinepris – ingen verifierad fysisk prisobservation.":"Digitalt prisunderlag – ingen garanti för fysisk hyllkostnad eller lagerstatus.","small"));if(need?.unused_source_offers?.length){const offers=el("div");for(const offer of need.unused_source_offers){offers.append(el("p",`${offer.description}: ${offer.required_packages} för ${money(offer.price)}. ${offer.membership_program?`Kräver ${offer.membership_program}. `:""}Gäller ${offer.valid_from||"startdatum saknas"} – ${offer.valid_to||"slutdatum saknas"}. Används inte i denna radsumma.`));}card.append(details("Andra erbjudanden i källan – används inte",offers));}if(row.deposit_total>0)card.append(el("p",`Varor ${money(row.merchandise_total)} + pant ${money(row.deposit_total)} = ${money(row.total_price)}.`));const declaration=window.SmakoRecipes.productDetails(plan.personal.checks.ingredient_product_details?.find(d=>d.ingredient===row.ingredient&&d.product_name===row.product_name));if(declaration)card.append(declaration);if(row.purchase_warning)card.append(el("p",row.purchase_warning));if(row.waste_quantity)card.append(el("p",`Beräknat framtida överskott: ${number(row.waste_quantity)} ${row.unit}.`));card.append(button("Välj annan produkt",async()=>{swapTarget=row.ingredient;$('product-query').value=need?.name||row.product_name;show("product-search");$('product-search-form').requestSubmit();}));group.add(shopRow(row,card,{type,estimated:row.quantity_confidence==="estimated"}));}}updateShopProgress();

    renderPreparations(out,plan);
    const ledger=(privateState.ledger||[]).filter(e=>e.plan_id===saved.plan_id);const ev={purchase:ledger.some(e=>e.action==="purchase"&&e.revision===saved.revision),consume:ledger.some(e=>e.action==="consume"&&e.operation_id===`consume:${saved.revision}`)};const actions=el("div",null,"personal-actions");actions.append(button(ev.purchase?"Inköpet är bokfört":"Bekräfta att jag har köpt varorna",async()=>{const rows=plan.optimized_basket.stores.flatMap(g=>g.items).filter(i=>i.quantity_confidence==="estimated"||i.unit!==i.purchased_unit||plan.personal.needs.find(n=>n.key===i.ingredient)?.preparation);if(!rows.length)return change("purchase");const dialog=el("dialog"),inputs=[];dialog.append(el("h2","Bekräfta uppmätta inköp"),el("p","Ange verklig användbar mängd i angiven enhet. Planens kostnader förblir uppskattade."));for(const row of rows){const value=input("number","",{min:row.required_quantity,step:"any"});inputs.push([row,value]);dialog.append(field(`${row.product_name}: minst ${number(row.required_quantity)} ${row.unit} användbar mängd`,value));}dialog.append(button("Bokför uppmätt mängd",async()=>{const quantities={};for(const [row,value] of inputs){const q=Number(value.value);if(!Number.isFinite(q)||q<row.required_quantity)throw new Error("Mät inköpet och ange mängd som täcker behovet, eller räkna om planen.");quantities[row.store_id+"|"+row.product_id+"|"+row.ingredient]=q;}await change("purchase",{measured_purchase_quantities:quantities});dialog.close();dialog.remove();}),button("Avbryt",async()=>{dialog.close();dialog.remove();}));document.body.append(dialog);dialog.showModal();},true),button(ev.consume?"Förbrukningen är bokförd":"Bekräfta planens förbrukning",()=>change("consume")),button("Bekräfta delvis förbrukning",async()=>{const d=el("dialog");const percent=input("number",50,{min:1,max:100});d.append(el("h2","Bekräfta verklig förbrukning"),field("Andel av kvarvarande reserverade mängder, procent",percent),el("p","Använd detta när samma andel av planens reserverade ingredienser har förbrukats. Räkna om efter bokföringen."),button("Bokför förbrukning",async()=>{const value=Number(percent.value);if(!Number.isFinite(value)||value<=0||value>100)throw new Error("Ange 1–100 procent.");await change("consume",{consume_fraction:value/100,operation_id:crypto.randomUUID()});d.close();d.remove();}),button("Avbryt",async()=>{d.close();d.remove();}));document.body.append(d);d.showModal();}),button("Frigör planens reservationer",()=>change("release")));out.append(el("h2","När du har handlat","shop-after-title"),actions);const history=el("div");for(const event of ledger){history.append(el("h3",`${event.action==="purchase"?"Bokfört inköp":event.action==="consume"?"Bokförd förbrukning":event.action==="prepare"?"Bokförd beredning":"Frigjord reservation"} · planrevision ${event.revision}${event.total!=null?` · ${money(event.total)}`:""}`));for(const row of event.rows){history.append(el("p",`${row.checkout?.product_name||row.name}: ${number(row.quantity)} ${row.unit}${row.checkout?` · ${money(row.checkout.total_price)}`:""}`));}}if(ledger.length)out.append(details("Oföränderlig inköps- och förbrukningshistorik",history));for(const row of plan.personal.available_surplus||[])out.append(el("p",`Disponibelt befintligt överskott efter reservation: ${row.name} ${number(row.quantity)} ${row.unit}.`));if(saved.revision>1){const previous=input("number",saved.revision-1,{min:1,max:saved.revision-1});const restore=el("div");restore.append(field("Tidigare receptrevision",previous),el("p","Skapar en ny revision med tidigare recept. Aktuella hårda krav och extravaror behålls. Bokförda köp och förbrukning ändras aldrig."),button("Återställ recept och beräkna nya behov",()=>change("restore_revision",{restore_revision:Number(previous.value)})));out.append(details("Återanvänd tidigare receptrevision",restore));}out.append(el("p","Bekräfta bara genomförda inköp och verklig förbrukning. Upprepade bekräftelser bokförs bara en gång. Att frigöra en plan ändrar inte verkligt lager.","small"));out.append(el("p",`Strategiska extraköp: ${money(plan.personal.larger_purchase_cost)} i merkostnad. Förpackningsöverskott bokförs som lager först efter bekräftat inköp.`));}

  function renderPreparations(out,plan){
    if(!plan.personal.preparations?.length)return;
    const box=el("div",null,"personal-card");
    for(const method of new Set(plan.personal.preparations.map(p=>p.method))){
      const mint=method==="mint_leaf_trimming_estimate_v1";
      if(!mint&&method!=="hen_egg_separation_estimate_v1")continue;
      const preparations=plan.personal.preparations.filter(p=>p.method===method);
      box.append(el("h3",mint?"Plocka och väg myntablad":"Separera och väg ägg"),el("p",mint?"Bladutbytet är en uppskattning från ett begränsat studieexempel. Vid inköpsbokning väger du ätbar råmynta efter grov rensning, med blad och mjuka delar. Plocka sedan bort alla stjälkar och bokför uppmätt råinsats och blad före förbrukning. Komplettera vid för litet utbyte. Ingen hållbarhet är fastställd här.":"Inköpet av hela ägg delas mellan gula och vita. Utbytet är uppskattat. Bokför faktisk ätbar insats utan skal och båda uppmätta utfallen före förbrukning. Ingen hållbarhet är fastställd här."));
      for(const prep of preparations){box.append(el("p",mint?`Beräknad ätbar råmynta före bladplockning: ${number(prep.input_quantity_g)} g. Beräknade myntablad: ${number(prep.estimated_outputs_g.mynta)} g.`:`Beräknad separeringsinsats: ${number(prep.input_quantity_g)} g helt ägg utan skal. Beräknade utfall: ${number(prep.estimated_outputs_g["äggula"])} g gula och ${number(prep.estimated_outputs_g["äggvita"])} g vita.`));for(const [name,q] of Object.entries(prep.estimated_surplus_g))if(q>1e-8)box.append(el("p",`Beräknad separat rest: ${mint?"myntablad":name} ${number(q)} g. Faktisk rest fastställs först efter vägning.`));}
      box.append(button(mint?"Bokför uppmätt bladplockning":"Bokför uppmätt äggberedning",async()=>{
      const d=el("dialog"),entries=[];d.append(el("h2",mint?"Uppmätt bladplockning":"Uppmätt rå äggberedning"),el("p",mint?"Gör en omgång per produktidentitet. Väg ätbar råmynta med blad och mjuka delar före bladplockningen. Väg därefter bara de plockade bladen. Skillnaden bokförs som förlust; bladen får egen lageridentitet.":"Gör en omgång per produktidentitet. Väg utan skal. Summan av gula och vita får inte överstiga insatsen; skillnaden bokförs som förlust."));
      const allowed=new Set(preparations.flatMap(p=>p.input_allocations.map(a=>a.product_key)));
      for(const need of plan.personal.needs)if(need.preparation?.method===method)allowed.add(need.selected_product_key);
      const reservations=privateState.reservations?.[saved.plan_id]||[];
      for(const item of privateState.items){if(!allowed.has(item.product_key)||item.prepared_origin||item.unusable||item.unit!=="g")continue;const own=reservations.filter(r=>r.item_id===item.id&&r.kind==="preparation_input"&&r.method===method).reduce((n,r)=>n+r.quantity,0),available=item.available+own;if(available<=0)continue;const value=input("number","",{min:0,max:available,step:"any"});entries.push([item,value]);d.append(field(`${item.name}, disponibelt för ${mint?"bladplockning":"separering"} högst ${number(available)} g`,value));}
      const fields=(mint?[["leaf_g","Faktiska uppmätta myntablad, g"]]:[["yolk_g","Faktisk uppmätt äggula, g"],["white_g","Faktisk uppmätt äggvita, g"]]).map(([key,label])=>{const value=input("number","",{min:0,step:"any"});d.append(field(label,value));return[key,value];});
      if(!entries.length)d.append(el("p",mint?"Bokför det verkliga inköpet först, eller räkna om med disponibel råmynta.":"Bokför det verkliga inköpet först, eller räkna om med disponibla hela ägg i skafferiet."));
      d.append(button(mint?"Bokför insats och myntablad":"Bokför insats och båda utfall",async()=>{const inputs={};for(const [item,value] of entries){const q=Number(value.value);if(!Number.isFinite(q)||q<0||!value.checkValidity())throw new Error("Ange en disponibel uppmätt insats.");if(q>0)inputs[item.id]=q;}const outputs={};for(const[key,value]of fields){if(!value.value||!value.checkValidity())throw new Error("Ange uppmätta utfall, även noll om en äggdel saknas.");outputs[key]=Number(value.value);}await change("prepare",{operation_id:crypto.randomUUID(),preparation:{method,inputs,...outputs}});d.close();d.remove();}),button("Avbryt",async()=>{d.close();d.remove();}));document.body.append(d);d.showModal();
      }));
    }
    for(const event of privateState.ledger||[]){if(event.plan_id===saved.plan_id&&event.action==="prepare"){const p=event.preparation;box.append(el("p",`Bokförd beredning: ${number(p.inputs.reduce((n,r)=>n+r.quantity,0))} g ätbar insats; ${p.outputs.map(r=>`${r.name} ${number(r.quantity)} g`).join(", ")}. Uppmätt förlust ${number(p.loss_g)} g.`));}}
    out.append(box);
  }

  function editRecipe(slot){const box=el("div");box.append(el("h2",slot.recipe?"Redigera recept":"Fyll tillfället"));const name=input("text",slot.recipe?.name||"",{maxLength:150});const servings=input("number",slot.recipe?.servings||1,{min:"1",max:"8"});const rows=el("div");function ingredientRow(i={name:"",quantity:1,unit:"g"}){const row=el("div",null,"ingredient-edit");const n=input("text",i.name,{maxLength:120}),q=input("number",i.quantity,{min:"0.001",step:"any"}),u=select([["g","g"],["ml","ml"],["st","st"],["kg","kg"],["l","l"]],i.unit);n.setAttribute("aria-label","Ingrediens");q.setAttribute("aria-label","Mängd");u.setAttribute("aria-label","Enhet");row.append(n,q,u,button("×",async()=>row.remove()));rows.append(row);} (slot.recipe?.ingredients||[{}]).forEach(i=>ingredientRow(i));const instructions=el("textarea");instructions.value=slot.recipe?.instructions.join("\n")||"";box.append(field("Receptnamn",name),field("Portioner (mängderna nedan är för hela receptet)",servings),el("p","Alla ingredienser måste kunna lösas till verkliga köpbara behov. Okända ingredienser stoppar uppdateringen."),rows,button("Lägg till ingrediens",async()=>ingredientRow()),field("Tillagningssteg – ett per rad",instructions),button("Spara och räkna om hela korgen",async()=>{const recipe={name:name.value,servings:Number(servings.value),ingredients:[...rows.children].map(r=>({name:r.children[0].value,quantity:Number(r.children[1].value),unit:r.children[2].value})),instructions:instructions.value.split("\n").map(s=>s.trim()).filter(Boolean)};await change("edit",{slot_id:slot.id,recipe});$('personal-dialog').close();focusView();},true));openDialog(box);}

  async function pantryDialog(item=null,product=null){const box=el("div");box.append(el("h2",item?"Ändra verkligt lager":"Lägg till verkligt lager"));const name=input("text",item?.name||product?.display_name?.slice(0,120)||product?.name?.slice(0,120)||"",{maxLength:120}),amount=input("number",item?.quantity??product?.package_quantity??1,{min:"0",step:"any",max:"100000"}),unit=select([["g","gram"],["ml","milliliter"],["st","stycken"]],item?.unit||product?.package_unit||"g"),unusable=input("checkbox","");unusable.checked=item?.unusable||false;const formChoice=select([["","Okänd / ej angiven"],["raw_edible","Rå, ätbar mängd"],["dry","Torr råvara"],["as_sold","Som såld"],["cooked_drained","Kokt och avrunnen"],["preserved_drained","Avrunnen konserverad vara"]],item?.form||"");const reference=select([["","Ingen generisk näringsreferens bekräftad"]],"");if(!product&&!item?.product_key&&!item?.prepared_origin){const refs=await api("/api/personal/nutrition-references");for(const option of refs.options){const o=el("option",`${option.name} · ${option.preparation_label} · gram`);o.value=option.id;reference.append(o);}reference.value=item?.nutrition_reference||"";box.append(field("Bekräfta livsmedel och rå/torr/avrunnen form för näringsuppskattning",reference),el("p","Välj bara en referens som stämmer med varan hemma, inklusive fetthalt och beredning. Detta ändrar inte lagermängden. Spårbara näringsuppskattningar tillåts i nya planer."));}if(product||item?.product_key||item?.prepared_origin)name.readOnly=true;if(item?.prepared_origin){unit.disabled=true;formChoice.disabled=true;reference.disabled=true;}box.append(field("Vara",name),field("Faktisk mängd hemma",amount),field("Enhet",unit),field("Obrukbar – får inte användas",unusable),field("Råvaruform (för genomarbetade recept)",formChoice),el("p","Generiska skafferivaror behöver dokumenterad form som passar receptet. En produktidentitet ger mer underlag om exempelvis tjock yoghurt eller fast tofu.","small"),el("p",item?.prepared_origin?"Uppmätt berett livsmedel med bokfört ursprung. Produkt och beredning bevaras.":product||item?.product_key?"Exakt produktidentitet bevaras.":"Generisk vara. Ingen allergendeklaration eller vikt-/volymomräkning antas."),button("Spara skafferivara",async()=>{const clean=privateState.items.map(({available,reserved,...i})=>i);const newItem={...(item?.prepared_origin?{prepared_origin:item.prepared_origin}:{}),...(formChoice.value?{form:formChoice.value}:{}),nutrition_reference:reference.value||null,id:item?.id||crypto.randomUUID(),name:name.value,quantity:Number(amount.value),unit:unit.value,unusable:unusable.checked,product_key:item?.product_key||product?.product_key||null,food:!/(servett|toalettpapper|hushållspapper|diskmedel)/i.test(name.value)};privateState=await api("/api/personal/pantry",{revision:privateState.revision,profile:profile(),items:[...clean.filter(i=>i.id!==newItem.id),newItem]},"PUT");renderPantry();$('personal-dialog').close();show("pantry");},true));openDialog(box);}

  $('add-pantry').addEventListener("click",()=>void task(()=>pantryDialog()));

  function renderPantry(){if(!privateState)return;const out=$('pantry-list');out.replaceChildren();$('account-status').textContent=privateState.account.message;for(const item of privateState.items){const card=el("article",null,"personal-card");card.append(el("h2",item.name),el("p",`Faktiskt lager ${number(item.quantity)} ${item.unit} · Reserverat ${number(item.reserved)} ${item.unit} · Disponibelt ${number(item.available)} ${item.unit}${item.unusable?" · OBRUKBAR":""}`),button("Ändra",async()=>pantryDialog(item)),button("Ta bort",async()=>{privateState=await api("/api/personal/pantry",{revision:privateState.revision,profile:profile(),items:privateState.items.filter(i=>i.id!==item.id).map(({available,reserved,...i})=>i)},"PUT");renderPantry();}));for(const check of privateState.pantry_checks||[]){if(check.item_id===item.id)card.append(el("p",check.message,"data-note"));}out.append(card);}if(!privateState.items.length)out.append(el("p","Skafferiet är tomt. Lägg till det som faktiskt finns hemma."));const reservations=$('reservation-list');reservations.replaceChildren();for(const [id,rows] of Object.entries(privateState.reservations)){if(!rows.length)continue;const p=el("p",`${rows.length} reservationer för en aktiv plan. `);p.append(button("Öppna berörd plan",async()=>{await accept(await api(`/api/plans/${encodeURIComponent(id)}`));show("plan");}));reservations.append(p);}}

  window.SmakoPersonal={productActions(product){const box=el("div",null,"personal-actions");const usages=product.prices.map(p=>p.purchase_usage);if(usages.every(u=>u==="blocked")){box.append(el("p","Varupriset är bevarat. Komplettera kritiska köp-/pantuppgifter före beräkning."));return box;}if(usages.includes("variant_selection_required")){box.append(button("Lägg till som villkorat kampanjval",async()=>extraDialog(product,true)));return box;}box.append(button("Lägg till i inköpslistan",async()=>extraDialog(product)),...(usages.includes("sales_unit_only")?[]:[button("Lägg till i skafferiet",async()=>pantryDialog(null,product))]));if(swapTarget)box.append(button("Byt vald inköpsrad till denna produkt",async()=>{await change("product",{ingredient:swapTarget,product_key:product.product_key});swapTarget=null;show("shopping");}));return box;}};

  $('personal-scan').addEventListener("click",()=>{const box=el("div");box.append(el("h2","Skanna vara"));const video=el("video");video.setAttribute("playsinline","");video.muted=true;const status=el("p","Kameran startar först när du väljer Starta kamera.");const manual=input("text","",{inputMode:"numeric",maxLength:18});function found(value){stopScanner();$('personal-dialog').close();$('product-query').value=value;show("product-search");window.dispatchEvent(new CustomEvent("smako:compare-gtin",{detail:{gtin:value}}));}box.append(video,status,button("Starta kamera",async()=>{try{scanner=await GroceryBarcodeScanner.createBarcodeScanner({videoElement:video,onResult:result=>found(result.normalized_gtin),onError:(error,detail={})=>{status.textContent=detail.recoverable?"Håll hela koden i bild.":"Kameran kunde inte läsa koden. Ange GTIN manuellt.";}});await scanner.start();status.textContent="Håll streckkoden i bild.";}catch(e){stopScanner();throw new Error("Kameran kunde inte startas. Tillåt kameraåtkomst eller ange GTIN manuellt.");}}),field("GTIN manuellt",manual),button("Sök streckkod",async()=>found(GroceryBarcodeScanner.normalizeGtin(manual.value).normalized_gtin)));openDialog(box);});

  async function resumePersonalJob() {
    const pending=window.SmakoRecipes.pendingJob("personal");if(!pending)return false;
    notify("Återansluter till din pågående menyberäkning…");
    startProgress([$('choice-submit'),$('calculate-own-list')].find(n=>n&&!n.closest("[hidden]")));
    try{const result=await api(pending.url||`/api/plan-job-requests/${pending.requestId}`);await progress?.finish();await accept(result.saved||result);show(saved.plan.recipes.length?"plan":"shopping");return true;}
    catch(error){if(error.code==="planner_job_expired"){window.SmakoRecipes.forgetJob("personal");error.message=cancelRequested?CANCELLED:saved?"Det tidigare beräkningsjobbet har gått ut. Din sparade plan visas fortfarande.":"Det tidigare beräkningsjobbet har gått ut. Dina sparade varuval finns kvar; du kan starta en ny beräkning.";}throw error;}
  }
  void task(async()=>{
    try {const metadata=await api("/api/recipe-library");recipeControls.enabled(metadata.enabled===true,{variationIntent:metadata.variation_intent_enabled});}catch(_){recipeControls.enabled(false);}
    await refreshState();putProfile(privateState.profile);const shoppingInitialized=privateState.shopping_initialized;const shoppingDraft=structuredClone(privateState.shopping_items||[]);
    const draft=window.SmakoRecipes.storage.get("smako.personal.requestDraft");
    if(draft){extras=structuredClone(draft.personal?.extras||[]);putChoices({...draft,membership_programs:draft.membership_programs||draft.memberships||[]});}
    // Restore durable data before reconnecting a process-memory job. The old
    // saved plan must not clear a different, still-running request marker.
    const wantedAccount=location.hash==="#account";const wantedShopping=location.hash==="#shopping"||new URLSearchParams(location.hash.slice(1)).get("view")==="shopping";const fromHash=new URLSearchParams(location.hash.slice(1)).get("plan");let last=fromHash;try{last ||= localStorage.getItem("smako.personal.lastPlan");}catch(_){}
    if(last){try{const loaded=await api(`/api/plans/${encodeURIComponent(last)}`);if(loaded.plan.personal)await accept(loaded,{clearJob:false});else notify("Detta är en tidigare middagsplan. Öppna den i den tidigare planeringen.");}catch(error){if(![401,403,404].includes(error.status))throw error;notify("Den tidigare planen kan inte öppnas i denna session. Dina tillgängliga varuval visas.");}}
    if(shoppingInitialized)extras=shoppingDraft;if(wantedAccount)show("account");if(location.hash==="#pantry")show("pantry");if(location.hash==="#choices")show("choices");if(wantedShopping){show("shopping");void searchShopping();}renderExtras();
    if(window.SmakoRecipes.pendingJob("personal"))setTimeout(()=>{if(!busy)void task(resumePersonalJob);},0);
  });
  const resume=()=>{if(!busy&&window.SmakoRecipes.pendingJob("personal"))void task(resumePersonalJob);};
  window.addEventListener("pageshow",()=>setTimeout(resume,0));document.addEventListener("visibilitychange",()=>{if(!document.hidden)resume();});
  window.addEventListener("online",()=>{if(!busy&&window.SmakoRecipes.pendingJob("personal"))void task(async()=>{try{const metadata=await api("/api/recipe-library");recipeControls.enabled(metadata.enabled===true,{variationIntent:metadata.variation_intent_enabled});}catch(_){/* A saved pending job can still reconnect. */}await resumePersonalJob();});});

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

  function reloadAccount(){history.replaceState({},"","/personal#account");location.reload();}

  function authForm(mode="login") {
    const out=$('account-actions');out.replaceChildren();
    const register=mode==="register",recover=mode==="recover";
    const form=el("form",null,"personal-card member-form");
    const email=input("email","",{required:true,maxLength:254,autocomplete:"username"});email.name="email";
    const password=input("password","",{required:true,minLength:12,maxLength:128,autocomplete:register||recover?"new-password":"current-password"});password.name="password";
    form.append(el("h2",register?"Skapa ditt konto":recover?"Återställ ditt konto":"Logga in"),field("E-postadress",email),field(recover?"Nytt lösenord (minst 12 tecken)":"Lösenord (minst 12 tecken)",password));
    let recovery;
    if(recover){recovery=input("text","",{required:true,maxLength:128,autocomplete:"off"});form.append(field("Återställningskod",recovery));}
    if(register)form.append(el("p","Efter registreringen får du en återställningskod. Spara den säkert; den behövs om du glömmer lösenordet. E-postadressen används för inloggning. Ingen e-post skickas."));
    const submit=el("button",register?"Skapa konto":recover?"Byt lösenord":"Logga in","primary-button");submit.type="submit";
    const feedback=el("p");feedback.setAttribute("role","status");form.append(submit,feedback);
    form.addEventListener("submit",async event=>{
      event.preventDefault();submit.disabled=true;feedback.textContent="Arbetar…";
      try{
        const result=await api(`/api/account/${register?"register":recover?"recover":"login"}`,{email:email.value,password:password.value,...(recover?{recovery_code:recovery.value}:{})});
        password.value="";window.SmakoRecipes.clearPrivateDrafts();
        saved=null;privateState=null;extras=[];$("plan-content").replaceChildren();$("pantry-list").replaceChildren();renderExtras();
        if(result.recovery_code){
          out.replaceChildren(el("h2",recover?"Lösenordet har ändrats":"Välkommen som medlem!"),el("p","Spara återställningskoden i din lösenordshanterare. Den visas bara nu. En ny kod ersätter alltid den gamla."));
          const code=input("text",result.recovery_code,{readOnly:true,autocomplete:"off"});code.setAttribute("aria-label","Din återställningskod");out.append(code,button("Jag har sparat koden – fortsätt",async()=>reloadAccount(),true));
        }else reloadAccount();
        await refreshState();extras=structuredClone(privateState.shopping_items||[]);putProfile(privateState.profile);renderExtras();
      }catch(error){feedback.textContent=error.message;}finally{submit.disabled=false;}
    });
    out.append(form);
    if(!register)out.append(button("Skapa ett konto",async()=>authForm("register"),true));
    if(register||recover)out.append(button("Jag har ett konto – logga in",async()=>authForm("login")));
    if(!recover)out.append(button("Glömt lösenordet?",async()=>authForm("recover")));
    out.append(button("Fortsätt som gäst",async()=>show("choices")));
  }

  async function renderAccount(){
    const state=await api("/api/account/status"),out=$('account-actions');out.replaceChildren();
    $('member-status').textContent=state.message||"";
    $('member-heading').textContent=state.status==="SIGNED_IN"?"Ditt Smakokonto":"Mer plats för din matvecka";
    $('member-intro').hidden=state.status==="SIGNED_IN";
    $('account-nav').textContent=state.status==="SIGNED_IN"?"Mitt konto":"Bli medlem / Logga in";
    document.querySelectorAll('.membership-note').forEach(n=>n.hidden=state.status==="SIGNED_IN");
    if(state.status!=="SIGNED_IN"){
      authForm();
      if(state.oidc_available){const a=el("a","Logga in via extern kontoleverantör","secondary-button");a.href="/api/account/login";out.append(a);}
      return;
    }
    out.append(el("p","När du ändrar ditt skafferi sparas det automatiskt på kontot."),button("Öppna mitt skafferi",async()=>show("pantry"),true),button("Logga ut",async()=>{await api("/api/account/logout",{});window.SmakoRecipes.clearPrivateDrafts();reloadAccount();}));
    const preview=await api("/api/account/guest-migration-preview");
    if(preview.can_move)out.append(button(`Spara mitt gästskafferi (${preview.guest_items} varor) och mina gästplaner på kontot`,async()=>{
      await api("/api/account/migrate-guest",{guest_revision:preview.guest_revision,account_revision:preview.account_revision,confirm_move_to_verified_account:true});await refreshState();await renderAccount();
    },true));
    else if(preview.guest_items)out.append(el("p","Kontot har redan ett sparat skafferi. Ditt gästskafferi finns kvar när du loggar ut och ersätter inte kontots varor."));
  }
  document.querySelectorAll('[data-open="account"]').forEach(n=>n.addEventListener("click",()=>void renderAccount().catch(e=>notify(e.message))));
  void renderAccount().catch(e=>{$('member-status').textContent=e.message;});

})();

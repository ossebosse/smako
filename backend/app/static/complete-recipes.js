/* Shared complete-dinner controls, recipe presentation and resumable plan jobs. */
(() => {
  "use strict";
  const cuisines = {greek:"Grekiskt", italian:"Italienskt", mexican:"Mexikanskt", indian:"Indiskt", thai:"Thailändskt", swedish:"Svenskt"};
  const number = value => Number(value).toLocaleString("sv-SE", {maximumFractionDigits:2});
  const storage = {
    get(key) { try { return JSON.parse(sessionStorage.getItem(key) || "null"); } catch (_) { return null; } },
    set(key, value) { try { sessionStorage.setItem(key, JSON.stringify(value)); } catch (_) { /* Optional tab-local recovery. */ } },
    remove(key) { try { sessionStorage.removeItem(key); } catch (_) { /* Optional. */ } },
  };
  function el(tag, text, className) { const node=document.createElement(tag); if(text != null)node.textContent=text; if(className)node.className=className; return node; }
  function field(label, control) { const node=el("label",label); node.append(control); return node; }
  function input(id,type,value,attrs={}) { const node=el("input"); Object.assign(node,{id,type,value,...attrs}); return node; }
  function select(id,choices,value) { const node=el("select"); node.id=id; for(const [v,label] of choices){const option=el("option",label);option.value=v;node.append(option);}node.value=value;return node; }

  function controls(host, {personal=false}={}) {
    if(!host)throw new Error("Receptvalens fält saknas.");
    const key=`smako.recipeChoices.${personal?"personal":"public"}`;
    const box=el("fieldset",null,"complete-recipe-options");box.hidden=true;box.disabled=true;
    box.append(el("legend","Receptstil"));
    const mode=select("recipe-style",[["legacy","Befintliga vardagsrecept"],["complete","Genomarbetade middagar"]],"legacy");
    box.append(field("Välj receptläge",mode),el("p","Receptstilen gäller middagar. Billigast, Balanserad och Varierad behåller sina mål.","field-hint"));
    const advanced=el("fieldset",null,"complete-recipe-fields");advanced.hidden=true;advanced.disabled=true;
    advanced.append(el("legend","Dina middagar"));
    const cuisineField=el("fieldset",null,"recipe-cuisines");cuisineField.append(el("legend","Matkök och inspiration"));
    const cuisineInputs=Object.entries(cuisines).map(([value,label])=>{const checkbox=input(`cuisine-${value}`,"checkbox",value);const row=field(label,checkbox);row.className="check-label";cuisineField.append(row);return checkbox;});
    cuisineField.append(el("p","Välj ett eller flera. Inget markerat betyder alla matkök. Rätterna är inspirerade av matkökens smaker.","field-hint"));advanced.append(cuisineField);
    const grid=el("div",null,"complete-recipe-grid");
    const preset=select("recipe-ingredient-preset",[["10-15","10–15 ingredienser"],["6-10","6–10 ingredienser"],["10-20","10–20 ingredienser"],["custom","Eget intervall"]],"10-15");
    const min=input("recipe-min-ingredients","number",10,{min:"3",max:"20",step:"1",required:true});
    const max=input("recipe-max-ingredients","number",15,{min:"3",max:"20",step:"1",required:true});
    const custom=el("div",null,"complete-recipe-grid");custom.hidden=true;custom.append(field("Minst antal (3–20)",min),field("Högst antal (3–20)",max));
    const minutes=input("recipe-max-minutes","number","",{min:"10",max:"180",step:"1",placeholder:"Ingen gräns"});
    const protein=input("recipe-min-protein","number","",{min:"0",max:"200",step:"any",placeholder:"Inget extra mål"});
    const adaptation=select("recipe-adaptation",[["products","Bara lämpliga produkt- och märkesbyten"],["approved","Även godkända receptvariationer"]],"approved");
    const fish=input("recipe-allow-fish","checkbox","",{checked:true});
    grid.append(field("Ingrediensantal",preset),field("Högsta tillagningstid (min)",minutes),field("Minst protein per portion (g)",protein),field("Tillåtna anpassningar",adaptation));
    advanced.append(grid,custom,el("p","Alla rättens komponenter räknas tillsammans. Salt, peppar och vatten visas separat. Olja, kryddor och såser räknas. Skafferiet minskar inköpen, inte ingrediensantalet.","field-hint"),field("Tillåt fisk när övriga kostval medger det",fish));
    const contexts=el("fieldset",null,"recipe-contexts");contexts.id="recipe-price-contexts";contexts.append(el("legend","Butiker och priskanaler"),el("p","Inget markerat betyder alla tillåtna inköpsställen i ditt prisområde. Valda butiker och onlinekanaler begränsar sökningen; ditt butikstak gäller fortfarande.","field-hint"));
    const contextOptions=el("div");const contextStatus=el("p",null,"field-hint");contextStatus.setAttribute("role","status");contexts.append(contextOptions,contextStatus);advanced.append(contexts);
    let selectedContexts=[],contextEpoch=0;
    async function loadContexts(){
      if(!enabled||mode.value!=="complete")return;
      const postal=document.getElementById("postal-code")?.value.replace(/\s/g,"");if(!/^\d{5}$/.test(postal||""))return;
      const epoch=++contextEpoch;contextStatus.textContent="Hämtar inköpsställen i ditt prisområde…";
      try {const response=await fetch(`/api/price-contexts?postal_code=${encodeURIComponent(postal)}`,{headers:{Accept:"application/json"},cache:"no-store"});const data=await response.json();if(epoch!==contextEpoch)return;if(!response.ok)throw new Error(typeof data.detail==="string"?data.detail:"Inköpsställena kunde inte hämtas. Dina val är kvar.");
        contextOptions.replaceChildren();const available=new Set();
        for(const row of data.contexts||[]){available.add(row.context_id);const option=input(`context-${row.context_id}`,"checkbox",row.context_id,{checked:selectedContexts.includes(row.context_id)});const label=field(`${row.display_name}${row.price_scope_label?` · ${row.price_scope_label}`:row.price_semantics?` · ${row.price_semantics}`:""}`,option);label.className="check-label";contextOptions.append(label);}
        for(const id of selectedContexts.filter(id=>!available.has(id))){const option=input(`context-${id}`,"checkbox",id,{checked:true});contextOptions.append(field(`Tidigare valt inköpsställe saknas i detta aktuella underlag (${id}). Avmarkera för att ändra ditt val.`,option));}
        contextStatus.textContent=data.contexts?.length?`${data.contexts.length} tillgängliga inköpsställen. Onlinepriser är skilda från fysiska butikspriser.`:"Inga aktuella inköpsställen kunde visas för området.";
      }catch(error){if(epoch===contextEpoch)contextStatus.textContent=error.message;}
    }
    contextOptions.addEventListener("change",()=>{selectedContexts=[...contextOptions.querySelectorAll("input:checked")].map(node=>node.value);storage.set(key,values());});
    document.getElementById("postal-code")?.addEventListener("change",()=>void loadContexts());
    let estimates=null,pantry=null;
    if(!personal){
      estimates=input("recipe-nutrition-estimates","checkbox","");pantry=input("recipe-use-pantry","checkbox","",{checked:true});
      advanced.append(field("Tillåt spårbara näringsuppskattningar",estimates),el("p","Separat från uppskattade köp: tillåt dokumenterade generiska näringsreferenser och granskad varm beredning. Källor och status visas i resultatet.","field-hint"),field("Använd mitt faktiskt angivna skafferi",pantry));
      const link=el("a","Öppna och ändra mitt skafferi");link.href="/personal#pantry";advanced.append(link);
    } else advanced.append(el("p","Näringsunderlag, kostinriktning, uteslutningar och skafferi följer dina övriga personliga val. Både middagens näringsgränser och målet ovan gäller.","field-hint"));
    const feedback=el("p",null,"field-hint");feedback.setAttribute("role","status");advanced.append(feedback);box.append(advanced);host.replaceChildren(box);
    let enabled=false;
    function sync() {
      advanced.hidden=mode.value!=="complete";advanced.disabled=!enabled||advanced.hidden;
      custom.hidden=preset.value!=="custom";min.disabled=custom.hidden;max.disabled=custom.hidden;
      min.setCustomValidity("");max.setCustomValidity("");
      if(preset.value==="custom"&&Number(min.value)>Number(max.value))max.setCustomValidity("Högsta antalet måste vara minst lika stort som lägsta antalet.");
      feedback.textContent="";
    }
    function values() {
      if(mode.value!=="complete")return {};
      const [lo,hi]=preset.value==="custom"?[Number(min.value),Number(max.value)]:preset.value.split("-").map(Number);
      const result={recipe_preferences:{mode:"complete",cuisines:cuisineInputs.filter(n=>n.checked).map(n=>n.value),min_ingredients:lo,max_ingredients:hi,max_minutes:minutes.value===""?null:Number(minutes.value),adaptation:adaptation.value,min_protein_g:protein.value===""?null:Number(protein.value),allow_fish:fish.checked}};
      if(selectedContexts.length)result.allowed_store_ids=selectedContexts.slice();
      if(!personal)Object.assign(result,{allow_nutrition_estimates:estimates.checked,use_pantry:pantry.checked});
      return result;
    }
    function restore(request={}) {
      const preferences=request?.recipe_preferences||{};mode.value=preferences.mode==="complete"?"complete":"legacy";
      selectedContexts=[...(request.allowed_store_ids||[])];
      cuisineInputs.forEach(n=>n.checked=(preferences.cuisines||[]).includes(n.value));
      min.value=preferences.min_ingredients??10;max.value=preferences.max_ingredients??15;
      const pair=`${min.value}-${max.value}`;preset.value=["10-15","6-10","10-20"].includes(pair)?pair:"custom";
      minutes.value=preferences.max_minutes??"";protein.value=preferences.min_protein_g??"";adaptation.value=preferences.adaptation||"approved";fish.checked=preferences.allow_fish!==false;
      if(estimates)estimates.checked=request.allow_nutrition_estimates===true;
      if(pantry)pantry.checked=request.use_pantry!==false;
      sync();
      if(enabled)void loadContexts();
    }
    box.addEventListener("input",()=>{sync();storage.set(key,values());});
    box.addEventListener("change",()=>{sync();storage.set(key,values());});
    mode.addEventListener("change",()=>void loadContexts());
    restore(storage.get(key)||{});
    return {
      values(){return enabled?values():{};}, restore,
      enabled(value){enabled=value===true;box.hidden=!enabled;box.disabled=!enabled;sync();if(enabled)void loadContexts();},
      reset(){restore({});storage.remove(key);},
      validate(){sync();return !enabled||advanced.hidden||[...advanced.querySelectorAll("input,select")].every(node=>node.disabled||node.checkValidity());},
    };
  }

  function ingredientCount(recipe) {
    return new Set((recipe.ingredients||[]).filter(i=>!["salt","peppar","svartpeppar","vitpeppar","vatten"].includes(String(i.canonical_name||i.name).toLowerCase())).map(i=>`${i.canonical_name||i.name}|${i.form||""}`)).size;
  }
  function renderRecipe(recipe,{nutrition=null,personal=null,slotId=null}={}) {
    const design=recipe.design;if(!design)return null;
    const out=el("div",null,"complete-recipe-content");
    const intro=el("div",null,"complete-recipe-intro");
    intro.append(el("p",(design.cuisines||[]).map(c=>`${(cuisines[c]||c).toLowerCase()} inspirerad`).join(" · "),"recipe-cuisine-label"));
    const count=design.ingredient_count??ingredientCount(recipe);
    intro.append(el("p",`${recipe.servings} portioner · ${count} ingredienser · uppskattad tid ${number(design.estimated_minutes)} min`,"complete-recipe-facts"));
    const demands=(personal?.remaining_demands||[]).filter(row=>row.source===slotId&&!['salt','peppar','svartpeppar','vitpeppar','vatten'].includes(row.name));
    if(demands.length===count){
      let home=0,partial=0;
      for(const demand of demands){const used=(personal.allocations||[]).filter(row=>row.demand_key===demand.demand_key).reduce((sum,row)=>sum+row.quantity,0);if(used>=demand.quantity-0.000001)home++;else if(used>0)partial++;}
      intro.append(el("p",`${count} ingredienser, ${count-home} behöver köpas, ${home} finns helt hemma${partial?`; ytterligare ${partial} finns delvis hemma`:""}.`));
    }
    intro.append(el("p",`Recept ${design.base_id} · version ${design.version} · ${design.variant_id==="base"?"grundrecept":`variation ${design.variant_id}`}`,"small"));
    if(nutrition){
      const values=nutrition.values||nutrition;const parts=[];
      for(const [key,alt,label] of [["protein_g","protein_g_per_serving","g protein"],["kcal","kcal_per_serving","kcal"],["carbs_g","carbs_g_per_serving","g kolhydrater"],["fat_g","fat_g_per_serving","g fett"]]){const value=values[key]??values[alt];if(value!=null)parts.push(`${number(value)} ${label}`);}
      intro.append(el("p",`${parts.length?`${parts.join(" · ")} per portion. `:""}Näring: ${{VERIFIED:"produktdeklarationer",ESTIMATED:"spårbar uppskattning",UNKNOWN:"okänd",FAILED:"ej kvalificerad"}[nutrition.status]||nutrition.status||"okänd"}.`));
    } else intro.append(el("p","Näring: se planens kvalitetsunderlag. Saknade näringsvärden är okända."));
    if(personal)intro.append(el("p",`Allergenstatus: ${personal.checks?.allergy==="VERIFIED"?"kontrollerad mot källdeklarationer enligt dina krav":"ingen verifierad allergikontroll begärd"}. Köpstatus och näringsstatus bedöms separat.`,"small"));
    if(nutrition?.sources?.length){const sources=el("details");sources.append(el("summary","Näringskällor och mängdgrund"));if(nutrition.calculation_basis?.description)sources.append(el("p",nutrition.calculation_basis.description));for(const source of nutrition.sources)sources.append(el("p",`${source.ingredient||"Ingrediens"}: ${number(source.quantity)} ${source.unit||""}. ${source.basis||"Mängdgrund inte angiven"}. Källa: ${source.source||"saknas"}. ${source.evidence_kind==="qualified_product_declaration"?"Produktdeklaration":"Spårbar uppskattning"}.`,"small"));intro.append(sources);}
    const provenance=design.provenance||{};
    intro.append(el("p",`Innehåll: ${provenance.content_review==="reviewed"?"granskat":"granskningsstatus saknas"}. Maskinell validering: ${provenance.machine_validation==="passed"?"godkänd":"status saknas"}. Provlagning: ${provenance.cooking_test==="not_cooked"?"inte genomförd":provenance.cooking_test||"underlag saknas"}.`,"recipe-quality-note"));
    if(design.equipment?.length)intro.append(el("p",`Utrustning: ${design.equipment.join(", ")}.`));out.append(intro);
    const ingredients=el("section",null,"complete-recipe-ingredients");ingredients.append(el("h3","Ingredienser för hela receptet"));
    const componentRows=design.components||[];const mapped=new Set(componentRows.map(c=>c.id));
    const groups=[...componentRows];if((recipe.ingredients||[]).some(i=>!mapped.has(i.component)))groups.push({id:null,name:"Övriga ingredienser"});
    for(const component of groups){const rows=(recipe.ingredients||[]).filter(i=>component.id?i.component===component.id:!mapped.has(i.component));if(!rows.length)continue;
      const group=el("div",null,"recipe-component");group.append(el("h4",component.name));const list=el("ul",null,"recipe-ingredients");
      for(const row of rows){const item=el("li");item.append(el("span",row.name),el("span",`${number(row.quantity)} ${row.unit}`,"ingredient-amount"));list.append(item);}group.append(list);ingredients.append(group);
    }
    ingredients.append(el("p","Mängderna avser receptets använda ingredienser. Samma ingrediens och form räknas en gång även när den används i flera komponenter. Salt, peppar och vatten ingår i listan men inte i det valda antalet.","field-hint"));
    const allocations=(personal?.allocations||[]).filter(a=>slotId && (a.source===slotId||a.slot_id===slotId));
    if(allocations.length){ingredients.append(el("h4","Skafferi används"));for(const row of allocations)ingredients.append(el("p",`${row.name||row.ingredient||"Skafferivara"}: ${number(row.quantity)} ${row.unit||""}.`));}
    out.append(ingredients);
    const method=el("section");method.append(el("h3","Gör så här"));const steps=el("ol",null,"instructions-list complete-recipe-steps");
    const timing=new Map((design.steps||[]).map((s,i)=>[s.id,{step:s,index:i+1}]));
    const instructions=recipe.instructions||[];
    instructions.forEach((instruction,index)=>{
      const item=el("li");const step=design.steps?.[index];item.append(el("p",typeof instruction==="string"?instruction:instruction.text));
      if(step){const after=(step.depends_on||[]).map(id=>timing.get(id)?.index).filter(Boolean);const parts=[step.duration_minutes!=null?`cirka ${number(step.duration_minutes)} min`:null,after.length?`efter steg ${after.join(", ")}`:null,step.parallel_group?"kan överlappa andra oberoende moment":null].filter(Boolean);if(parts.length)item.append(el("span",parts.join(" · "),"step-timing"));}steps.append(item);
    });method.append(steps,el("p","Tiderna är uppskattningar. Följ stegens beroenden; oberoende moment kan göras parallellt.","field-hint"));out.append(method);return out;
  }

  function recipeFeedback({recipe,recipeIndex,planId,revision}) {
    const dialog=el("dialog",null,"consumer-dialog complete-feedback-dialog");const form=el("form",null,"dialog-card");
    const heading=el("h2",`Hur blev ${recipe.name}?`);heading.id="recipe-feedback-title";dialog.setAttribute("aria-labelledby",heading.id);form.append(heading);
    if(recipe.design)form.append(el("p",`Återkopplingen hör till ${recipe.design.base_id}, version ${recipe.design.version}, ${recipe.design.variant_id}.`));
    const taste=select("recipe-feedback-taste",[["","Välj smakbetyg"],...[1,2,3,4,5].map(n=>[String(n),`${n} av 5`])],"");
    const difficulty=select("recipe-feedback-difficulty",[["","Välj svårighetsgrad"],["1","1 · Mycket enkel"],["2","2 · Enkel"],["3","3 · Medel"],["4","4 · Svår"],["5","5 · Mycket svår"]],"");
    const portion=select("recipe-feedback-portion",[["","Välj portionsstorlek"],["small","För liten"],["right","Lagom"],["large","För stor"]],"");
    const minutes=input("recipe-feedback-minutes","number","",{min:"1",max:"600",step:"1"});
    const message=el("textarea");message.maxLength=2000;message.rows=3;
    form.append(field("Smak",taste),field("Svårighetsgrad",difficulty),field("Portionsstorlek",portion),field("Faktisk tillagningstid (min, valfritt)",minutes),field("Kommentar (valfritt)",message));
    const status=el("p");status.setAttribute("role","status");const actions=el("div",null,"dialog-actions");const close=el("button","Stäng","secondary-button");close.type="button";close.onclick=()=>dialog.close();const submit=el("button","Spara återkoppling","primary-button");submit.type="submit";actions.append(close,submit);form.append(status,actions);dialog.append(form);document.body.append(dialog);
    dialog.addEventListener("close",()=>dialog.remove());dialog.addEventListener("click",e=>{if(e.target===dialog)dialog.close();});
    form.addEventListener("submit",async event=>{
      event.preventDefault();if(!form.checkValidity()){form.reportValidity();return;}
      if(!taste.value&&!difficulty.value&&!portion.value&&!minutes.value){status.textContent="Ange minst ett betyg, en portionsstorlek eller en faktisk tillagningstid.";return;}
      submit.disabled=true;status.textContent="Sparar…";
      const ratings={revision,recipe_index:recipeIndex,taste:taste.value?Number(taste.value):null,difficulty:difficulty.value?Number(difficulty.value):null,portion_size:portion.value||null,actual_minutes:minutes.value?Number(minutes.value):null};
      try { const response=await fetch("/api/feedback",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({category:"suggestion",message:message.value.trim()||`Receptåterkoppling för ${recipe.name}`,page_context:location.pathname,plan_id:planId,recipe_feedback:ratings})});const data=await response.json();if(!response.ok)throw new Error(typeof data.detail==="string"?data.detail:"Återkopplingen kunde inte sparas.");status.textContent="Tack! Återkopplingen är sparad till den här receptversionen.";submit.hidden=true;}catch(error){status.textContent=error.message;}finally{submit.disabled=false;}
    });dialog.showModal();taste.focus();
  }

  function financials(plan) {
    const checks=plan.personal?.checks;if(!checks||!("used_ingredient_cost" in checks))return null;
    const money=value=>`${number(value)} kr`;const out=el("section",null,"recipe-purchase-explanation");out.append(el("h3","Inköp och förbrukning"));
    const estimated=checks.used_cost_basis?.quantity_status==="ESTIMATED";
    out.append(el("p",`${plan.optimized_basket.verification_status==="VERIFIED_WITH_ESTIMATES"?"Uppskattat belopp att betala":"Belopp att betala"}: ${money(plan.optimized_basket.total)}. Hela köp, inklusive eventuell pant.`));
    out.append(el("p",checks.used_ingredient_cost==null?"Kostnaden för allt som används är okänd eftersom skafferiets tidigare inköpspris saknas.":`${estimated?"Uppskattad kostnad":"Kostnad"} för mängderna som används: ${money(checks.used_ingredient_cost)} (utan pant).`));
    if(checks.used_ingredient_cost==null&&checks.new_purchase_used_cost!=null)out.append(el("p",`Använd andel av de nya matinköpen: ${estimated?"cirka ":""}${money(checks.new_purchase_used_cost)}. Skafferiets historiska kostnad ingår inte.`));
    if(plan.personal.allocations?.length){out.append(el("h4","Från ditt faktiska skafferi"));const list=el("ul");for(const row of plan.personal.allocations)list.append(el("li",`${row.name}: ${number(row.quantity)} ${row.unit}`));out.append(list);}
    if(checks.used_cost_basis?.description)out.append(el("p",checks.used_cost_basis.description,"field-hint"));
    out.append(el("p","Resterna i inköpslistan är planerade mängder. De bokförs inte automatiskt som lager och deras framtida värde minskar inte beloppet att betala.","field-hint"));return out;
  }

  function productDetails(detail) {
    if(!detail)return null;const out=el("details",null,"recipe-product-declaration");out.append(el("summary","Sammansättning och allergenunderlag"));
    out.append(el("p",detail.ingredients?.length?`Ingrediensunderlag: ${detail.ingredients.join(", ")}.`:"Ingrediensdeklaration saknas i detta underlag."));
    if(!detail.ingredients_complete)out.append(el("p","Ingrediensunderlaget är inte komplett.","field-hint"));
    out.append(el("p",detail.allergens_present?.length?`Angivna allergener: ${detail.allergens_present.join(", ")}.`:"Inga allergener anges i detta underlag. Detta bevisar inte frånvaro."));
    out.append(el("p",detail.allergens_trace?.length?`Angivna spår: ${detail.allergens_trace.join(", ")}.`:"Inga spår anges i detta underlag. Följ planens separata allergenkontroll."));
    if(detail.source)out.append(el("p",`Källreferens: ${detail.source}`,"small"));return out;
  }

  function diagnostics(data) {
    if(!data)return null;const out=el("details",null,"recipe-planning-diagnostics");out.open=true;out.append(el("summary","Blockeringsfördelning"));
    out.append(el("p",`${data.raw_recipe_pool??"Okänt antal"} receptkandidater ingick i underlaget. ${data.singleton_passed??"Okänt antal"} klarade den enskilda kontrollen; ${data.not_singleton_evaluated??"okänt antal"} blev inte enskilt prövade. Ett enskilt godkännande innebär inte att rätterna tillsammans bildar en giltig veckomeny.`));
    const counts=el("ul");for(const row of data.candidate_rejections||[])if(row.rejected)counts.append(el("li",`${row.label}: ${row.rejected} avslag.`));out.append(counts);
    const examples=el("ul");const seen=new Set();for(const row of data.candidate_details||[]){
      const reason=String(row.reason||"").startsWith("Befintlig strukturell måltidskontroll")?"Rättens grundkontroll saknar tillräckligt näringsunderlag. Detta är inte i sig ett avslag på ditt valda proteinmål.":String(row.reason||"").replace(/\bprotein_g\b/g,"protein").replace(/\bas_sold\b/g,"som såld").replace(/\braw_edible\b/g,"rå ätbar mängd").replace(/\bcooked_drained\b/g,"kokt och avrunnen");
      const text=`${row.recipe}: ${reason}`;if(seen.has(text))continue;seen.add(text);if(examples.children.length<8)examples.append(el("li",text));
    }if(examples.children.length){out.append(el("h3","Exempel på vad som stoppade recepten"),examples);if(seen.size>8)out.append(el("p",`Visar 8 av ${seen.size} skilda exempel.`));}
    if((data.search||[]).some(row=>row.rejections?.variation))out.append(el("p","Veckans variationskrav stoppade kombinationer av de kvarvarande rätterna. Ett alternativ är att välja fler matkök eller längre tillagningstid för att ge fler rätter möjlighet att prövas."));
    else if((data.candidate_details||[]).some(row=>row.stage==="nutrition_bound"))out.append(el("p","Ett alternativ är att tillåta godkända receptvariationer eller välja fler matkök. Du kan också uttryckligen ändra proteinmålet. Inget av dina val ändras automatiskt."));
    else out.append(el("p","Prova fler matkök eller längre tillagningstid för att låta fler rätter prövas. Saknat produktunderlag behöver kompletteras; ändrade val garanterar inte en lösning."));
    out.append(el("p",data.counting||"Sökningen är begränsad och bevisar inte att alla möjliga menyer är omöjliga.","field-hint"));return out;
  }

  const validJobUrl=url=>/^\/api\/plan-jobs\/[a-f0-9]{32}$/.test(url||"");
  const stages={queued:"Din menyberäkning väntar på en ledig plats.",product_facts:"Kontrollerar produktfakta och aktuella prisvillkor.",candidate_qualification:"Prövar rätternas produkter, mängder och näringskrav.",week_search:"Söker efter en samordnad veckomeny och inköpskorg.",final_audit:"Slutkontrollerar hela inköpslistan och dina krav.",saving:"Sparar den färdiga planrevisionen."};
  const jobKey=scope=>`smako.planJob.${scope}`;
  function clearPrivateDrafts(){for(const key of ["smako.planJob.public","smako.planJob.personal","smako.recipeChoices.public","smako.recipeChoices.personal","smako.personal.requestDraft"])storage.remove(key);}
  function pendingJob(scope) { const saved=storage.get(jobKey(scope));return validJobUrl(saved?.url)?saved:null; }
  function forgetJob(scope) {storage.remove(jobKey(scope));}
  async function poll(response,{scope,signal,onProgress=()=>{},context=null}={}) {
    let statusUrl=pendingJob(scope)?.url||null;
    while(response.status===202){
      const pending=await response.json();if(pending.status!=="pending"||!validJobUrl(pending.status_url)||(statusUrl&&statusUrl!==pending.status_url))throw new Error("Servern skickade ett ogiltigt planeringssvar.");
      statusUrl=pending.status_url;storage.set(jobKey(scope),{url:statusUrl,context:context||pendingJob(scope)?.context,started_at:pendingJob(scope)?.started_at||Date.now()});
      onProgress(typeof pending.stage_label==="string"?pending.stage_label:stages[pending.stage]||typeof pending.progress?.label==="string"&&pending.progress.label||typeof pending.message==="string"&&pending.message||"Servern arbetar med din meny. Du kan ladda om och återansluta till samma beräkning.");
      await new Promise((resolve,reject)=>{const abort=()=>{clearTimeout(timer);reject(signal?.reason||new DOMException("Avbruten","AbortError"));};const timer=setTimeout(()=>{signal?.removeEventListener("abort",abort);resolve();},2000);signal?.addEventListener("abort",abort,{once:true});if(signal?.aborted)abort();});
      while(true){
        const controller=new AbortController();const abort=()=>controller.abort(signal.reason);signal?.addEventListener("abort",abort,{once:true});if(signal?.aborted)abort();const timeout=setTimeout(()=>controller.abort(),20000);
        try { response=await fetch(statusUrl,{headers:{Accept:"application/json"},cache:"no-store",signal:controller.signal});break; }
        catch(error){if(signal?.aborted)throw error;onProgress("Anslutningen avbröts. Återansluter till samma menyberäkning…");await new Promise(resolve=>setTimeout(resolve,3000));}
        finally{clearTimeout(timeout);signal?.removeEventListener("abort",abort);}
      }
    }
    forgetJob(scope);return response;
  }
  window.SmakoRecipes=Object.freeze({controls,renderRecipe,recipeFeedback,financials,productDetails,diagnostics,ingredientCount,cuisines,poll,pendingJob,forgetJob,clearPrivateDrafts,storage});
})();

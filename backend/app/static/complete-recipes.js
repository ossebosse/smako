/* Shared complete-dinner controls, recipe presentation and resumable plan jobs. */
(() => {
  "use strict";
  const cuisines = {greek:"Grekiskt", italian:"Italienskt", mexican:"Mexikanskt", indian:"Indiskt", thai:"Thailändskt", swedish:"Svenskt"};
  const ingredientForms = {raw_edible:"rå, ätbar mängd",dry:"torr råvara",as_sold:"mängd som såld",cooked_drained:"kokt och avrunnen mängd",preserved_drained:"avrunnen konserverad vara"};
  const ingredientRequirements = {plain:"naturell",frozen:"fryst",red_split:"röda, delade",ground:"malen",firm:"fast",thick:"tjock yoghurt, 5–10 % fetthalt",white_rice:"vitt ris",white_beans:"vita bönor",pure_juice:"ren juice",dried_leaf:"torkade blad"};
  const number = value => value==null||value===""||!Number.isFinite(Number(value))?"okänd":Number(value).toLocaleString("sv-SE", {maximumFractionDigits:2});
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
    const mode=select("recipe-style",[["legacy","Befintliga vardagsrecept"],["complete","Genomarbetade middagar"],["library","Måltidsbibliotek: middag, frukost och mellanmål"]],"legacy");
    box.append(field("Välj receptläge",mode),el("p","Receptstilen gäller middagar. Billigast, Balanserad och Varierad behåller sina mål.","field-hint"));
    const advanced=el("fieldset",null,"complete-recipe-fields");advanced.hidden=true;advanced.disabled=true;
    advanced.append(el("legend","Dina middagar"));
    const cuisineField=el("fieldset",null,"recipe-cuisines");cuisineField.append(el("legend","Matkök och inspiration"));
    const cuisineInputs=Object.entries(cuisines).map(([value,label])=>{const checkbox=input(`cuisine-${value}`,"checkbox",value);const row=field(label,checkbox);row.className="check-label";cuisineField.append(row);return checkbox;});
    cuisineField.append(el("p","Välj ett eller flera. Inget markerat betyder alla matkök. Rätterna är inspirerade av matkökens smaker.","field-hint"));advanced.append(cuisineField);
    const cuisineDistribution=select("recipe-cuisine-distribution",[["free","Välj fritt bland valda matkök"],["minimum","Minst X olika matkök"],["each_selected","Minst en rätt från varje valt matkök"]],"free");
    const minCuisines=input("recipe-min-cuisines","number",3,{min:"1",max:"6",step:"1"});
    const proteinCap=input("recipe-main-protein-cap","number","",{min:"1",max:"7",step:"1",placeholder:"Inget extra tak"});
    const moreVariety=el("button","Mer omväxling: minst 3 matkök, högst 2 middagar per huvudprotein");moreVariety.type="button";
    const variation=el("div",null,"complete-recipe-grid");variation.append(field("Köksfördelning",cuisineDistribution),field("Minsta antal olika matkök",minCuisines),field("Högst middagar per huvudproteinkälla",proteinCap));
    advanced.append(variation,moreVariety,el("p","Valen ovan är frivilliga krav för hela veckans middagar. En blandrätt räknas en gång för varje huvudsaklig proteinkälla som ingår. Billigast, Balanserad och Varierad behåller sina ekonomiska mål.","field-hint"));
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
      if(!enabled||!["complete","library"].includes(mode.value))return;
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
    const mealFields=el("fieldset",null,"complete-recipe-fields");
    mealFields.append(el("legend","Val för varje måltidstyp"),el("p","Antal tillfällen och portioner är olika val. Proteinmål är frivilliga. Middagens köksfördelning gäller bara middagar.","field-hint"));
    const level=select("meal-dinner-level",[["simple","Enkla middagar"],["crafted","Genomarbetade middagar"],["mixed","Blandning av enkla och genomarbetade"]],"simple");
    mealFields.append(field("Middagsnivå",level));
    const mealRows={};
    for(const [type,label] of [["dinner","Middag"],["breakfast","Frukost"],["snack","Mellanmål"]]){
      const group=el("fieldset",null,"complete-recipe-grid");group.append(el("legend",label));
      const row={};
      if(!personal&&type!=="dinner"){
        row.count=input(`meal-${type}-count`,"number",0,{min:"0",max:"7",step:"1",required:true});
        row.servings=input(`meal-${type}-servings`,"number",1,{min:"1",max:"8",step:"1",required:true});
        group.append(field("Antal tillfällen",row.count),field("Portioner per tillfälle",row.servings));
      }
      for(const [key,label,max] of [["min_ingredients","Minst ingredienser",40],["max_ingredients","Högst ingredienser",40],["max_active_minutes","Högst aktiv tid (min)",180],["max_total_minutes","Högst total tid (min)",2880],["max_waiting_minutes","Högst väntetid (min)",1440],["max_same_base_meals","Högst tillfällen med samma grundrätt",7]]){
        row[key]=input(`meal-${type}-${key}`,"number","",{min:key==="max_waiting_minutes"?"0":"1",max:String(max),step:"1",placeholder:"Ingen extra gräns"});group.append(field(label,row[key]));
      }
      if(!personal){row.min_protein_g=input(`meal-${type}-min-protein`,"number","",{min:"0",max:"300",step:"any",placeholder:"Inget mål"});group.append(field("Minst protein per portion (g)",row.min_protein_g));}
      mealRows[type]=row;mealFields.append(group);
    }
    advanced.append(mealFields);
    function mealValues(meals){
      if(mode.value!=="library"||!enabled)return meals;
      return meals.map(meal=>{
        if(!meal.count)return {...meal,recipe_choices:null,max_same_base_meals:null,limits:{},distribution:{}};
        const row=mealRows[meal.meal_type],choices={};
        for(const key of ["min_ingredients","max_ingredients","max_active_minutes","max_total_minutes","max_waiting_minutes"])choices[key]=row[key].value===""?null:Number(row[key].value);
        if(meal.meal_type==="dinner")choices.dinner_level=level.value;
        const result={...meal,recipe_choices:choices,max_same_base_meals:row.max_same_base_meals.value===""?null:Number(row.max_same_base_meals.value)};
        if(row.min_protein_g)result.limits={...(meal.limits||{}),min_protein_g:row.min_protein_g.value===""?null:Number(row.min_protein_g.value)};
        return result;
      });
    }
    const feedback=el("p",null,"field-hint");feedback.setAttribute("role","status");advanced.append(feedback);box.append(advanced);host.replaceChildren(box);
    let enabled=false;
    function sync() {
      advanced.hidden=!["complete","library"].includes(mode.value);advanced.disabled=!enabled||advanced.hidden;
      mealFields.hidden=mode.value!=="library";mealFields.disabled=advanced.disabled||mealFields.hidden;
      grid.hidden=mode.value==="library";grid.querySelectorAll("input,select").forEach(n=>n.disabled=grid.hidden);
      if(!personal){const count=document.getElementById("recipes");if(count){for(let n=0;n<3;n++){let option=[...count.options].find(o=>o.value===String(n));if(!option){option=el("option",String(n));option.value=String(n);count.prepend(option);}option.disabled=mode.value!=="library";option.hidden=mode.value!=="library";}}}
      for(const [type,row] of Object.entries(mealRows)){
        const count=document.getElementById(personal?`${type}-count`:type==="dinner"?"recipes":`meal-${type}-count`);
        const inactive=mode.value==="library"&&Number(count?.value??0)===0;
        for(const [key,node] of Object.entries(row))if(key!=="count")node.disabled=inactive||mealFields.disabled;
        row.max_ingredients.setCustomValidity(!inactive&&row.min_ingredients.value!==""&&row.max_ingredients.value!==""&&Number(row.min_ingredients.value)>Number(row.max_ingredients.value)?"Högsta ingrediensantalet är lägre än det minsta.":"");
      }
      custom.hidden=mode.value==="library"||preset.value!=="custom";min.disabled=custom.hidden;max.disabled=custom.hidden;
      min.setCustomValidity("");max.setCustomValidity("");
      if(preset.value==="custom"&&Number(min.value)>Number(max.value))max.setCustomValidity("Högsta antalet måste vara minst lika stort som lägsta antalet.");
      const selected=cuisineInputs.filter(n=>n.checked).length;
      const dinners=Number(document.getElementById(personal?"dinner-count":"recipes")?.value||5);
      const inactiveDinner=mode.value==="library"&&dinners===0;
      cuisineDistribution.disabled=inactiveDinner||advanced.disabled;
      minCuisines.disabled=inactiveDinner||cuisineDistribution.value!=="minimum"||advanced.disabled;
      proteinCap.disabled=inactiveDinner||advanced.disabled;
      level.disabled=inactiveDinner||mealFields.disabled;
      for(const node of cuisineInputs)node.disabled=inactiveDinner||advanced.disabled;
      moreVariety.disabled=advanced.disabled||dinners<3||(selected>0&&selected<3);
      moreVariety.title=moreVariety.disabled&&enabled&&["complete","library"].includes(mode.value)?"Välj minst tre middagar och tre tillåtna matkök för detta förslag.":"";
      const required=cuisineDistribution.value==="each_selected"?selected:cuisineDistribution.value==="minimum"?Number(minCuisines.value):0;
      cuisineDistribution.setCustomValidity(inactiveDinner?"":cuisineDistribution.value==="each_selected"&&!selected?"Välj minst ett matkök.":required>dinners?"Fler obligatoriska matkök än middagar.":cuisineDistribution.value==="minimum"&&required>(selected||6)?"Välj fler tillåtna matkök eller sänk minimiantalet.":"");
      feedback.textContent=inactiveDinner?"Middagsvalen tillämpas när du lägger till middagar.":"";
    }
    function values() {
      if(!["complete","library"].includes(mode.value))return {};
      const [lo,hi]=preset.value==="custom"?[Number(min.value),Number(max.value)]:preset.value.split("-").map(Number);
      const result={recipe_preferences:{mode:"complete",cuisines:cuisineInputs.filter(n=>n.checked).map(n=>n.value),cuisine_distribution:cuisineDistribution.value,min_distinct_cuisines:cuisineDistribution.value==="minimum"?Number(minCuisines.value):null,max_same_main_protein_dinners:proteinCap.value===""?null:Number(proteinCap.value),min_ingredients:lo,max_ingredients:hi,max_minutes:minutes.value===""?null:Number(minutes.value),adaptation:adaptation.value,min_protein_g:mode.value==="library"||protein.value===""?null:Number(protein.value),allow_fish:fish.checked}};
      if(mode.value==="library"&&Number(document.getElementById(personal?"dinner-count":"recipes")?.value??0)===0)Object.assign(result.recipe_preferences,{cuisines:[],cuisine_distribution:"free",min_distinct_cuisines:null,max_same_main_protein_dinners:null,max_minutes:null});
      if(selectedContexts.length)result.allowed_store_ids=selectedContexts.slice();
      if(!personal)Object.assign(result,{allow_nutrition_estimates:estimates.checked,use_pantry:pantry.checked});
      if(mode.value==="library"&&!personal){
        const dinner={meal_type:"dinner",count:Number(document.getElementById("recipes").value),servings:Number(document.getElementById("servings").value)};
        const meals=[dinner,...["breakfast","snack"].map(type=>({meal_type:type,count:Number(mealRows[type].count.value),servings:Number(mealRows[type].servings.value)}))];
        const diet=document.getElementById("diet-preference")?.value;
        result.personal={meals:mealValues(meals).map(m=>({...m,diet:["vegetarian","vegan"].includes(diet)?diet:"mixed"})),use_pantry:pantry.checked,allow_nutrition_estimates:estimates.checked,profile:{exclusions:(document.getElementById("excluded-ingredients")?.value||"").split(",").map(v=>v.trim()).filter(Boolean)}};
      }
      return result;
    }
    function restore(request={}) {
      const preferences=request?.recipe_preferences||{};mode.value=preferences.mode==="complete"?"complete":"legacy";
      if(request.personal?.meals?.some(m=>m.recipe_choices!=null))mode.value="library";
      for(const [type,row] of Object.entries(mealRows)){
        const meal=request.personal?.meals?.find(m=>m.meal_type===type)||{};
        for(const [key,node] of Object.entries(row))node.value=key==="count"?(meal.count??0):key==="servings"?(meal.servings??1):key==="min_protein_g"?(meal.limits?.min_protein_g??""):(meal.recipe_choices?.[key]??meal[key]??"");
        if(type==="dinner")level.value=meal.recipe_choices?.dinner_level||"simple";
      }
      selectedContexts=[...(request.allowed_store_ids||[])];
      cuisineInputs.forEach(n=>n.checked=(preferences.cuisines||[]).includes(n.value));
      min.value=preferences.min_ingredients??10;max.value=preferences.max_ingredients??15;
      const pair=`${min.value}-${max.value}`;preset.value=["10-15","6-10","10-20"].includes(pair)?pair:"custom";
      minutes.value=preferences.max_minutes??"";protein.value=preferences.min_protein_g??"";adaptation.value=preferences.adaptation||"approved";fish.checked=preferences.allow_fish!==false;
      cuisineDistribution.value=preferences.cuisine_distribution||"free";minCuisines.value=preferences.min_distinct_cuisines??3;proteinCap.value=preferences.max_same_main_protein_dinners??"";
      if(estimates)estimates.checked=request.allow_nutrition_estimates===true;
      if(pantry)pantry.checked=request.use_pantry!==false;
      sync();
      if(enabled)void loadContexts();
    }
    box.addEventListener("input",()=>{sync();storage.set(key,values());});
    box.addEventListener("change",()=>{sync();storage.set(key,values());});
    const mealCountIds=new Set(personal?["dinner-count","breakfast-count","snack-count"]:["recipes"]);
    document.addEventListener("input",event=>{if(mealCountIds.has(event.target.id))sync();});
    mode.addEventListener("change",()=>void loadContexts());
    moreVariety.addEventListener("click",()=>{cuisineDistribution.value="minimum";minCuisines.value=3;proteinCap.value=2;sync();storage.set(key,values());});
    restore(storage.get(key)||{});
    return {
      values(){return enabled?values():{};}, mealValues, restore,
      enabled(value){enabled=value===true;box.hidden=!enabled;box.disabled=!enabled;sync();if(enabled)void loadContexts();},
      reset(){restore({});storage.remove(key);},
      validate(){sync();return !enabled||advanced.hidden||[...advanced.querySelectorAll("input,select")].every(node=>node.disabled||node.checkValidity());},
    };
  }

  function ingredientCount(recipe) {
    return new Set((recipe.ingredients||[]).filter(i=>!["salt","peppar","svartpeppar","vitpeppar","vatten"].includes(String(i.canonical_name||i.name).toLowerCase())).map(i=>`${i.canonical_name||i.name}|${i.form||""}`)).size;
  }
  function nutritionNumber(value, status) {
    if(value==null||value===""||!Number.isFinite(Number(value)))return "okänd";
    const displayed=Number(value).toLocaleString("sv-SE",{maximumFractionDigits:1});
    return `${status==="ESTIMATED"?"ca ":""}${displayed}`;
  }
  function nutritionInformation(nutrition,{methodNotes=[]}={}) {
    const details=el("details",null,"recipe-nutrition-info");
    details.append(el("summary","Om näringsberäkningen"));
    details.append(el("p","Värdena gäller ingrediensmängderna som används per portion, inte hela inköpta förpackningar. Visningen avrundas; näringsmålen kontrolleras före avrundning."));
    if(nutrition?.status==="ESTIMATED")details.append(el("p","Näringen är en spårbar uppskattning. Märkningen ca gäller näringsvärdena, inte en ändring av ditt näringsmål."));
    for(const note of methodNotes)details.append(el("p",note));
    if(nutrition?.calculation_basis?.description)details.append(el("p",nutrition.calculation_basis.description));
    if(nutrition?.sources?.length){
      const sources=el("details",null,"recipe-nutrition-sources");sources.append(el("summary","Näringskällor och mängdgrund"));
      for(const source of nutrition.sources)sources.append(el("p",`${source.ingredient||"Ingrediens"}: ${number(source.quantity)} ${source.unit||""}. ${source.basis||"Mängdgrund inte angiven"}. Källa: ${source.source||"saknas"}. ${source.evidence_kind==="qualified_product_declaration"?"Produktdeklaration":source.evidence_kind&&source.source?"Spårbar uppskattning":"Källstatus okänd"}.`,"small"));
      details.append(sources);
    }
    return details;
  }
  function mealDescription(recipe, category) {
    const labels={vegetarian:"Vegetarisk",chicken:"Kyckling",fish:"Fisk och skaldjur",meat:"Kött"};
    const main=recipe.design?.primary_ingredient;
    const ingredient=(recipe.ingredients||[]).find(row=>(row.canonical_name||row.name)===main);
    const label=recipe.design?.vegetarian===true?"Vegetarisk":labels[category];
    return [label,ingredient?`Huvudråvara: ${ingredient.name}`:null].filter(Boolean).join(" · ");
  }
  function cookingPresentation(recipe) {
    const instructions=[...(recipe.instructions||[])];
    const original={instructions,methodNotes:[],waterOnly:false};
    const design=recipe.design,preparation=recipe.preparation;
    if(design?.content_source&&preparation?.version==="smako-authored-input-v2")return {...original,methodNotes:[design.content_source.method_note],waterOnly:true};
    // This is a display projection of the server-qualified immutable method.
    // Unknown versions and structurally different recipes keep every original
    // word. The source recipe, its content hash and its amounts are never edited.
    if(!design||!preparation||preparation.version!=="smako-edible-input-v1"||preparation.origin!=="smako_recipe_design")return original;
    if(!["1.0.0","1.1.0","1.2.0","1.3.0","1.4.0"].includes(design.version)||!["bake","oven","pan","pot"].includes(design.method))return original;
    if(!/^[0-9a-f]{64}$/.test(design.content_sha256||"")||preparation.parent_sha256!==design.content_sha256||preparation.family!==design.family)return original;
    if(design.provenance?.authoring!=="model_assisted_original"||design.provenance?.content_review!=="reviewed")return original;
    const forms=preparation.input_forms||{},ingredients=recipe.ingredients||[],steps=design.steps||[];
    if(Object.keys(forms).length!==ingredients.length||!ingredients.every(item=>item.canonical_name&&forms[item.canonical_name]===item.form))return original;
    if(steps.length!==instructions.length||steps.length<2||!steps.every((step,index)=>step.text===instructions[index]))return original;
    const last=steps.at(-1),previous=new Set(steps.slice(0,-1).map(step=>step.id));
    if(previous.size!==steps.length-1||previous.has(last.id)||last.parallel_group||(last.depends_on||[]).length!==previous.size||!last.depends_on.every(id=>previous.has(id)))return original;
    const methodEnding="Fördela rättens komponenter jämnt mellan portionerna. Servera all uppmätt sås, olja och genomhettad sky; skrapa ur pannor och formar. Endast dricksvatten får tillkomma utöver listan. Tiden är en uppskattning, inte ett provlagningsresultat.";
    const prefix=last.text===methodEnding?"":last.text.endsWith(` ${methodEnding}`)?last.text.slice(0,-methodEnding.length):null;
    if(prefix===null)return original;
    instructions[instructions.length-1]=`${prefix}Fördela rätten jämnt mellan portionerna och servera med all sås och genomhettad sky.`;
    return {instructions,waterOnly:true,methodNotes:[
      "Beräkningsmetoden förutsätter att alla angivna mängder, även olja, sås och sky, ingår i portionerna. Endast dricksvatten får tillkomma utöver ingredienslistan.",
      "Tillagningstiden är en uppskattning. Den är inte uppmätt genom provlagning.",
    ]};
  }
  function parallelPlan(steps) {
    const indexed=new Map(steps.map((step,index)=>[step.id,{step,index:index+1}]));
    if(indexed.size!==steps.length)return [];
    const groups=new Map();
    for(const step of steps){
      if(!step.parallel_group)continue;
      const dependencies=step.depends_on||[];
      if(dependencies.some(id=>!indexed.has(id)||indexed.get(id).index>=indexed.get(step.id).index))continue;
      const key=JSON.stringify([step.parallel_group,[...dependencies].sort()]);
      if(!groups.has(key))groups.set(key,{dependencies,indices:[]});
      groups.get(key).indices.push(indexed.get(step.id).index);
    }
    const join=values=>values.length<2?String(values[0]):`${values.slice(0,-1).join(", ")} och ${values.at(-1)}`;
    return [...groups.values()].filter(group=>group.indices.length>1).map(group=>{
      const before=group.dependencies.map(id=>indexed.get(id).index).sort((a,b)=>a-b);
      return `${before.length?`När steg ${join(before)} är ${before.length===1?"klart":"klara"}`:"Från början"} kan du göra steg ${join(group.indices)} parallellt.`;
    });
  }
  function renderRecipe(recipe,{nutrition=null,personal=null,slotId=null}={}) {
    const design=recipe.design;if(!design)return null;
    const presentation=cookingPresentation(recipe);
    const out=el("div",null,"complete-recipe-content");
    const intro=el("div",null,"complete-recipe-intro");
    intro.append(el("p",(design.cuisines||[]).map(c=>`${(cuisines[c]||c).toLowerCase()} inspirerad`).join(" · "),"recipe-cuisine-label"));
    const count=design.ingredient_count??ingredientCount(recipe);
    const timing=design.total_minutes!=null?`uppskattad total tid ${number(design.total_minutes)} min · aktiv ${number(design.active_minutes)} min${design.waiting_minutes?` · väntan ${number(design.waiting_minutes)} min`:""}`:`uppskattad tid ${number(design.estimated_minutes)} min`;
    intro.append(el("p",`${recipe.servings} portioner · ${count} ingredienser · ${timing}`,"complete-recipe-facts"));
    const demands=(personal?.remaining_demands||[]).filter(row=>row.source===slotId&&!['salt','peppar','svartpeppar','vitpeppar','vatten'].includes(row.name));
    if(demands.length===count&&demands.every(row=>row.original_quantity==null||Math.abs(row.original_quantity-row.quantity)<0.000001)){
      let home=0,partial=0;
      for(const demand of demands){const used=(personal.allocations||[]).filter(row=>row.demand_key===demand.demand_key).reduce((sum,row)=>sum+row.quantity,0);if(used>=demand.quantity-0.000001)home++;else if(used>0)partial++;}
      intro.append(el("p",`${count} ingredienser: ${count-home} behöver köpas och ${home} finns helt hemma.${partial?` Av de ${count-home} som behöver köpas finns ${partial} redan delvis hemma.`:""}`));
    } else if(demands.some(row=>row.original_quantity!=null&&row.original_quantity>row.quantity)){
      intro.append(el("p","En del av rättens behov har redan bokförts som förbrukat. Inköpslistan visar återstående behov; receptets ingrediensantal är oförändrat."));
    }
    intro.append(el("p",`Recept ${design.base_id} · version ${design.version} · ${design.variant_id==="base"?"grundrecept":`variation ${design.variant_id}`}`,"small"));
    if(nutrition){
      const values=nutrition.values||nutrition;const parts=[];
      for(const [key,alt,label] of [["protein_g","protein_g_per_serving","g protein"],["kcal","kcal_per_serving","kcal"],["carbs_g","carbs_g_per_serving","g kolhydrater"],["fat_g","fat_g_per_serving","g fett"]]){const value=values[key]??values[alt];if(value!=null&&value!==""&&Number.isFinite(Number(value)))parts.push(`${nutritionNumber(value,nutrition.status)} ${label}`);}
      intro.append(el("p",`${parts.length?`${parts.join(" · ")} per portion. `:""}Näring: ${{VERIFIED:"produktdeklarationer",ESTIMATED:"spårbar uppskattning",NOT_REQUESTED:"inte beräknad – inget näringsmål valt",UNKNOWN:"okänd",FAILED:"ej kvalificerad"}[nutrition.status]||"okänd"}.${parts.length<4?" Saknade näringsvärden är okända.":""}`));
      intro.append(nutritionInformation(nutrition,presentation));
    } else {intro.append(el("p","Näring: se planens kvalitetsunderlag. Saknade näringsvärden är okända."));if(presentation.methodNotes.length)intro.append(nutritionInformation(null,presentation));}
    if(personal)intro.append(el("p",`Allergenstatus: ${personal.checks?.allergy==="VERIFIED"?"kontrollerad mot källdeklarationer enligt dina krav":"ingen verifierad allergikontroll begärd"}. Köpstatus och näringsstatus bedöms separat.`,"small"));
    const provenance=design.provenance||{};
    intro.append(el("p",`Innehåll: ${provenance.content_review==="reviewed"?"granskat":"granskningsstatus saknas"}. Maskinell validering: ${provenance.machine_validation==="passed"?"godkänd":"status saknas"}. Provlagning: ${provenance.cooking_test==="not_cooked"?"inte genomförd":provenance.cooking_test||"underlag saknas"}.`,"recipe-quality-note"));
    if(design.equipment?.length)intro.append(el("p",`Utrustning: ${design.equipment.join(", ")}.`));
    if(design.content_source?.storage_note){const storage=el("details");storage.append(el("summary","Rester och förvaring"),el("p",design.content_source.storage_note));intro.append(storage);}out.append(intro);
    const ingredients=el("section",null,"complete-recipe-ingredients");ingredients.append(el("h3","Ingredienser för hela receptet"));
    if(presentation.waterOnly)ingredients.append(el("p","Använd de angivna mängderna. Utöver listan tillkommer bara dricksvatten.","recipe-method-note"));
    const componentRows=design.components||[];const mapped=new Set(componentRows.map(c=>c.id));
    const groups=[...componentRows];if((recipe.ingredients||[]).some(i=>!mapped.has(i.component)))groups.push({id:null,name:"Övriga ingredienser"});
    for(const component of groups){const rows=component.amounts?.map(amount=>{
        const source=(recipe.ingredients||[]).find(i=>`${i.canonical_name||i.name}|${i.form}`===amount.ingredient_key);
        return {...source,...amount,form:source?.form||"process_water"};
      })||(recipe.ingredients||[]).filter(i=>component.id?i.component===component.id:!mapped.has(i.component));if(!rows.length)continue;
      const group=el("div",null,"recipe-component");group.append(el("h4",component.name));const list=el("ul",null,"recipe-ingredients");
      for(const row of rows){const item=el("li"),name=el("span",row.name);const basis=[ingredientForms[row.form],...(row.product_requirements||[]).map(key=>ingredientRequirements[key])].filter(Boolean);if(basis.length)name.append(el("small",basis.join(" · "),"recipe-ingredient-form"));if(row.note)name.append(el("small",row.note,"recipe-ingredient-form"));item.append(name,el("span",`${number(row.quantity)} ${row.unit}`,"ingredient-amount"));list.append(item);}group.append(list);ingredients.append(group);
    }
    ingredients.append(el("p","Mängderna avser receptets använda ingredienser. Samma ingrediens och form räknas en gång även när den används i flera komponenter. Salt, peppar och vatten ingår i listan men inte i det valda antalet.","field-hint"));
    const allocations=(personal?.allocations||[]).filter(a=>slotId && (a.source===slotId||a.slot_id===slotId));
    if(allocations.length){ingredients.append(el("h4","Skafferi används"));for(const row of allocations)ingredients.append(el("p",`${row.name||row.ingredient||"Skafferivara"}: ${number(row.quantity)} ${row.unit||""}.`));}
    out.append(ingredients);
    const method=el("section",null,"complete-recipe-method");method.append(el("h3","Gör så här"));const steps=el("ol",null,"instructions-list complete-recipe-steps");
    const overlap=design.content_source?[]:parallelPlan(design.steps||[]);
    if(design.content_source)method.append(el("p","Följ tidsankarna i stegen. Total tid är en uppskattning för angiven portionsmängd; flera pannor eller omgångar kan påverka tiden.","field-hint"));
    if(overlap.length){const plan=el("div",null,"recipe-parallel-plan");for(const text of overlap)plan.append(el("p",text));method.append(plan);}
    const instructions=presentation.instructions;
    instructions.forEach((instruction,index)=>{
      const item=el("li");const step=design.steps?.[index];item.append(el("p",typeof instruction==="string"?instruction:instruction.text));
      if(step?.duration_minutes!=null)item.append(el("span",`ca ${number(step.duration_minutes)} min`,"step-timing"));steps.append(item);
    });method.append(steps,el("p","Stegtiderna är uppskattningar. Summera dem inte när moment görs parallellt.","field-hint"));out.append(method);return out;
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
      try {
        // Share the existing beta feedback identity used by privacy erasure.
        // This local capability is never the authority for plan ownership.
        let feedbackSession=localStorage.getItem("grocery-anonymous-session-id");
        if(!feedbackSession){feedbackSession=crypto.randomUUID().replaceAll("-","");localStorage.setItem("grocery-anonymous-session-id",feedbackSession);}
        const response=await fetch("/api/feedback",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({category:"suggestion",anonymous_session_id:feedbackSession,message:message.value.trim()||`Receptåterkoppling för ${recipe.name}`,page_context:location.pathname,plan_id:planId,recipe_feedback:ratings})});const data=await response.json();if(!response.ok)throw new Error(typeof data.detail==="string"?data.detail:"Återkopplingen kunde inte sparas.");status.textContent="Tack! Återkopplingen är sparad till den här receptversionen.";submit.hidden=true;
      }catch(error){status.textContent=error.message;}finally{submit.disabled=false;}
    });dialog.showModal();taste.focus();
  }

  function searchNotice(plan,mode) {
    if(!(plan.recipes||[]).some(recipe=>recipe.design))return null;
    const out=el("div",null,"recipe-search-status data-note");
    out.append(el("p",mode==="cheapest"?"Lägsta hittade inköpskostnad inom dina val. Sökningen bevisar inte global optimalitet.":"Inköpskostnaden följer ditt val av balans mellan pris och variation. Sökningen bevisar inte global optimalitet."));
    const distribution=plan.personal?.checks?.week_distribution;if(distribution){const cuisineCounts=Object.entries(distribution.cuisines||{}).map(([name,count])=>`${cuisines[name]||name} ${count}`);const proteins=Object.entries(distribution.main_proteins||{}).map(([source,count])=>`${source} ${count} ${count===1?"middag":"middagar"}`);out.append(el("p",`${distribution.distinct_cuisines} matkök${cuisineCounts.length?` · ${cuisineCounts.join(" · ")}`:""}${proteins.length?` · ${proteins.join(" · ")}`:""}.`));}
    const budget=plan.personal?.checks?.search_outcome?.budget_message;if(typeof budget==="string"&&budget.trim())out.append(el("p",budget));return out;
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
  function pendingJob(scope) {
    const saved=storage.get(jobKey(scope));
    if(validJobUrl(saved?.url))return saved;
    return /^[a-f0-9-]{32,36}$/.test(saved?.requestId||"")?{...saved,url:null}:null;
  }
  function forgetJob(scope) {storage.remove(jobKey(scope));}
  // One reader per document. Navigation aborts this reader, never the server job.
  const documentId=crypto.randomUUID();
  let reader=null, generation=0, leaving=false;
  function trace(flow,event,extra={}) {
    window.dispatchEvent(new CustomEvent("smako:plan-transport",{detail:{
      event,document_id:documentId,generation:flow?.generation??generation,request_id:flow?.requestId,
      job:flow?.url?.split("/").pop(),at:performance.now(),...extra}}));
  }
  function lifecycle(reason) { const error=new DOMException("Statusläsningen avbröts på denna sida.","AbortError");error.lifecycle=reason;return error; }
  function stopReader(reason) {if(reader){trace(reader,"abort",{reason});reader.controller.abort(lifecycle(reason));}}
  // pagehide can arrive after WebKit has begun a provisional navigation.
  // Stop its timer before another fetch is attempted in that old document.
  window.addEventListener("beforeunload",()=>{trace(reader,"beforeunload");stopReader("beforeunload");});
  window.addEventListener("pagehide",event=>{trace(reader,"pagehide",{persisted:event.persisted});leaving=true;stopReader("pagehide");});
  window.addEventListener("pageshow",event=>{leaving=false;trace(null,"pageshow",{persisted:event.persisted});});
  document.addEventListener("visibilitychange",()=>trace(reader,"visibility",{hidden:document.hidden}));
  function check(flow) {flow.controller.signal.throwIfAborted();if(reader!==flow||leaving)throw lifecycle("superseded");}
  function delay(ms,flow) {
    return new Promise((resolve,reject)=>{
      const signal=flow.controller.signal;
      const abort=()=>{clearTimeout(timer);signal.removeEventListener("abort",abort);reject(signal.reason);};
      const timer=setTimeout(()=>{signal.removeEventListener("abort",abort);resolve();},ms);
      signal.addEventListener("abort",abort,{once:true});if(signal.aborted)abort();
    });
  }
  function reconnectError() {const e=new Error("Statuskontrollen kan inte nå servern just nu. Återuppta statuskontrollen för samma meny; ingen ny beräkning startas.");e.reconnect=true;return e;}
  // These are explicit pre-admission refusals, not uncertain transport failures.
  const planningBlocks={price_universe_unusable:"Prisunderlaget behöver uppdateras innan en ny beräkning kan göras. Din sparade plan och inköpslista finns kvar.",price_universe_unavailable:"Prisunderlaget är tillfälligt otillgängligt. Din sparade plan och inköpslista finns kvar."};
  function schemaError(message) {const error=new Error(message);error.schema=true;return error;}
  async function readResponse(response,flow) {
    const type=response.headers.get("Content-Type")||"";
    if(!/application\/(?:[a-z0-9.-]+\+)?json(?:;|$)/i.test(type))throw schemaError("Servern skickade en oväntad svarstyp vid statuskontrollen.");
    let data;try{data=await response.clone().json();}catch(error){check(flow);if(error instanceof SyntaxError)throw schemaError("Servern skickade ogiltig JSON vid statuskontrollen.");if(error instanceof TypeError)error.transport=true;throw error;}
    check(flow);
    if(!data||typeof data!=="object"||Array.isArray(data))throw schemaError("Servern skickade ett ogiltigt statusformat.");
    if(response.status===202){
      if(data.status!=="pending"||!validJobUrl(data.status_url)||(flow.url&&flow.url!==data.status_url))throw schemaError("Servern skickade ett ogiltigt planeringssvar.");
    }else if(response.ok){
      const saved=data.saved||data;
      if(!saved.plan_id||!Number.isInteger(saved.revision)||!saved.request||!saved.plan||!Array.isArray(saved.plan.recipes)||!Array.isArray(saved.plan.optimized_basket?.stores)
          ||(saved.request.personal&&(!Array.isArray(saved.plan.personal?.slots)||!saved.plan.personal?.checks)))throw schemaError("Servern skickade ett ogiltigt planeringsresultat.");
    }
    return data;
  }
  async function transport(url,options,flow,onProgress) {
    for(;;){
      check(flow);
      const controller=new AbortController(),signal=flow.controller.signal;
      const abort=()=>controller.abort(signal.reason);signal.addEventListener("abort",abort,{once:true});
      const timeout=setTimeout(()=>controller.abort(new DOMException("Statusanropets tidsgräns","TimeoutError")),20000);
      let retryAfter=0,lost=false;
      const reference=crypto.randomUUID();
      try{
        trace(flow,"start",{reference,method:options.method||"GET"});
        let response;try{response=await fetch(url,{...options,headers:{Accept:"application/json",...options.headers,"X-Request-ID":options.method==="POST"?flow.requestId:reference},cache:"no-store",signal:controller.signal});}catch(error){error.transport=true;throw error;}
        trace(flow,"response",{reference,status:response.status,type:response.headers.get("Content-Type"),response_type:response.type,server_request:response.headers.get("X-Request-ID")});
        // Read body under the same timeout; a response with a stalled body is not success.
        const data=await readResponse(response,flow);
        const block=planningBlocks[response.headers.get("X-Error-Code")];
        if(response.status===503&&block){trace(flow,"planning-blocked",{reference,code:response.headers.get("X-Error-Code")});response.smakoPlanningBlock=block;return {response,data};}
        const unconfirmed=response.status===404&&!flow.url&&url.startsWith("/api/plan-job-requests/");
        if(unconfirmed&&Date.now()-flow.startedAt<30000){
          // Reload can race server acceptance of the original POST. This is
          // discovery of an unconfirmed start, not retrying a missing known job.
          retryAfter=2000;
        }else if([429,502,503,504].includes(response.status)&&!response.headers.get("X-Plan-Request-ID")){
          const seconds=Number(response.headers.get("Retry-After"));retryAfter=Number.isFinite(seconds)?Math.min(60000,Math.max(0,seconds*1000)):0;
        }else {response.smakoUnconfirmed=unconfirmed;return {response,data};}
      }catch(error){
        if(flow.controller.signal.aborted)trace(flow,"request-abort",{reference,reason:flow.controller.signal.reason?.lifecycle||"caller"});
        check(flow);
        // Only fetch transport rejection and our own request timeout are retried.
        if(!error.transport&&!controller.signal.aborted){trace(flow,"response-error",{reference,category:error.schema?"schema":"programming"});throw error;}lost=true;
        trace(flow,"transport-error",{reference,category:controller.signal.aborted?"timeout":"network"});
      }finally{clearTimeout(timeout);signal.removeEventListener("abort",abort);}
      flow.failures+=1;flow.disconnectedAt??=Date.now();
      if(flow.failures>=8||Date.now()-flow.disconnectedAt>=120000)throw reconnectError();
      onProgress("Anslutningen avbröts. Återansluter till samma menyberäkning…");
      // A lost POST response is recovered by owned lookup, never another POST.
      if(lost&&options.method==="POST"){url=`/api/plan-job-requests/${flow.requestId}`;options={};}
      await delay(Math.max(retryAfter,Math.min(30000,2000*2**(flow.failures-1))),flow);
    }
  }
  async function jobRequest({scope,url,payload,signal,onProgress=()=>{},context=null,requestId=crypto.randomUUID()}) {
    stopReader("replaced");
    const saved=pendingJob(scope);
    const flow={controller:new AbortController(),generation:++generation,requestId:saved?.requestId||requestId,url:saved?.url||null,startedAt:saved?.started_at||Date.now(),failures:0,disconnectedAt:null};reader=flow;
    const abort=()=>flow.controller.abort(signal.reason);signal?.addEventListener("abort",abort,{once:true});if(signal?.aborted)abort();
    if(!saved){storage.set(jobKey(scope),{requestId:flow.requestId,context,started_at:Date.now()});}
    try{
      let target=saved?.url||(saved?`/api/plan-job-requests/${flow.requestId}`:url);
      let options=!saved&&payload!==undefined?{method:"POST",headers:{"Content-Type":"application/json",Prefer:"respond-async"},body:JSON.stringify(payload)}:{};
      for(;;){
        const {response,data}=await transport(target,options,flow,onProgress);check(flow);
        if(response.status!==202){
          // A final owned lookup 404 also ends an unconfirmed start. Retaining
          // it would force every later click back to an expired request.
          if(!response.ok)forgetJob(scope);
          response.smakoCheck=()=>{flow.controller.signal.throwIfAborted();if(leaving||generation!==flow.generation)throw lifecycle("superseded");};
          trace(flow,"terminal",{status:response.status});return response;
        }
        flow.url=data.status_url;flow.failures=0;flow.disconnectedAt=null;
        storage.set(jobKey(scope),{url:flow.url,requestId:flow.requestId,context:context||saved?.context,started_at:flow.startedAt});
        onProgress(stages[data.stage]||"Servern arbetar med din meny. Du kan återansluta till samma beräkning.");
        await delay(2000,flow);target=flow.url;options={};
      }
    }finally{signal?.removeEventListener("abort",abort);if(reader===flow)reader=null;}
  }
  window.SmakoRecipes=Object.freeze({controls,renderRecipe,recipeFeedback,searchNotice,financials,productDetails,diagnostics,ingredientCount,nutritionNumber,nutritionInformation,mealDescription,cookingPresentation,cuisines,jobRequest,pendingJob,forgetJob,clearPrivateDrafts,storage});
})();

/* "Frågor": the fourth mobile layout of Mina val (configurator.js). After the
   store step, eight questions with large buttons fill in the existing Mina
   val form, then "Din plan i korthet" shows the answers. "Anpassa i detalj"
   opens the whole form. Every answer is read from and written to the
   controls personal.js, complete-recipes.js and choice-controls.js already
   own, so the guide keeps no settings of its own and the request is the same
   as from the form. No API calls; free text goes through the existing Tolka.

   The guide's own numbers (decided 2026-11-09, see docs/CHOICE-GUIDE.md):
   - Snabbt och enkelt: at most 30 min active time and 8 ingredients;
     Vardagsmat: 45 min and 12; Gärna lite mer: no limit.
   - Mycket protein: at least 30 g per dinner portion and 20 g per breakfast
     (Smako's standard is 18 g per dinner).
   - Lättare mat: at most 600 kcal per dinner, 450 per breakfast and 250 per
     snack (standard 900 per dinner).
   - Stora portioner: at least 450 g cooked weight per dinner portion.
   - Mest vegetariskt: at least half of each meal type's dishes vegetarian.
   - Kött: dinners whose main protein is meat or poultry; other meals Allt. */
(() => {
  "use strict";
  const $=id=>document.getElementById(id);
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};
  const MEALS=["dinner","breakfast","snack"],PROTEINS=["vegetarian","chicken","fish","meat"];
  const COOKING={quick:{time:"30",count:"8"},everyday:{time:"45",count:"12"},more:{time:"",count:""}};
  const IMPORTANT={
    protein:{dinner:{"min_protein_g":30},breakfast:{"min_protein_g":20}},
    lighter:{dinner:{max_kcal:600},breakfast:{max_kcal:450},snack:{max_kcal:250}},
    large:{dinner:{"min_weight_g":450}},
  };
  const ALLERGENS=[["jordnötter","Jordnötter"],["nötter","Nötter"],["mjölk","Mjölk"],["ägg","Ägg"],["gluten","Gluten"],["fisk","Fisk"],["skaldjur","Skaldjur"],["soja","Soja"],["sesam","Sesam"]];
  const CUISINES=[["italian","Italienskt"],["greek","Grekiskt"],["mexican","Mexikanskt"],["indian","Indiskt"],["thai","Thailändskt"],["swedish","Svenskt"]];
  const LIKES=[["kyckling","Kyckling"],["lax","Lax"],["nötfärs","Nötfärs"],["pasta","Pasta"],["ris","Ris"],["potatis","Potatis"],["bönor","Bönor"],["tofu","Tofu"]];
  const key=value=>String(value).trim().toLocaleLowerCase("sv-SE").replace(/\s+/g," ");

  // ---- Reading and writing the existing controls ----
  const controls=()=>window.SmakoChoiceUI?.controls;
  const read=id=>controls()?.get(id)?.read()??null;
  // Sliders listen to their own range input; the interval ranges would turn an
  // emptied value into 0 on input, so those are only set.
  function write(id,value){
    const control=controls()?.get(id);if(!control)return;
    control.set(value);
    if(!/-(min|max)_\w+_g$/.test(id))$(id)?.dispatchEvent(new Event("input",{bubbles:true}));
  }
  function check(id,on){const box=$(id);if(!box||box.checked===on)return;box.checked=on;box.dispatchEvent(new Event("input",{bubbles:true}));box.dispatchEvent(new Event("change",{bubbles:true}));}
  function choose(id,value){const node=$(id);if(!node||node.value===value)return;node.value=value;node.dispatchEvent(new Event("input",{bubbles:true}));node.dispatchEvent(new Event("change",{bubbles:true}));}
  const enabled=type=>type==="dinner"||!!$(`enable-${type}`)?.checked;
  const count=type=>read(`${type}-count`)??0;
  const taste=()=>window.SmakoTaste?.get()||{likes:[],dislikes:[],exclusions:[],allergies:[]};
  const half=n=>Math.ceil(n/2);
  const setServings=n=>MEALS.forEach(t=>write(`${t}-servings`,Math.min(8,Math.max(1,n))));

  // Meals that are not planned keep their own portions until they are added.
  function servingsAnswer(){const n=read("dinner-servings");return MEALS.filter(enabled).every(t=>read(`${t}-servings`)===n)?n:null;}
  function addMeal(type,on){
    const n=servingsAnswer();check(`enable-${type}`,on);
    if(on&&n!==null)write(`${type}-servings`,n);
  }
  // Kött applies to dinners; breakfast and snacks stay Allt, as in /ui/a and /ui/b.
  const dietFor=(answer,type)=>answer==="mostly"?"mixed":answer==="meat"?(type==="dinner"?"meat":"mixed"):answer;
  function dietAnswer(){
    const dist=t=>Object.fromEntries(PROTEINS.map(p=>[p,read(`${t}-${p}`)]));
    const noDistribution=MEALS.every(t=>PROTEINS.every(p=>dist(t)[p]===null));
    if(noDistribution&&MEALS.every(t=>$(`${t}-diet`)?.value===dietFor("meat",t)))return "meat";
    const diets=new Set(MEALS.map(t=>$(`${t}-diet`)?.value));if(diets.size!==1)return null;
    const diet=[...diets][0];
    if(diet!=="mixed")return noDistribution?diet:null;
    if(noDistribution)return "mixed";
    const mostly=MEALS.every(t=>{const d=dist(t);return d.vegetarian===half(count(t))&&d.chicken===null&&d.fish===null&&d.meat===null;});
    return mostly?"mostly":null;
  }
  function applyDiet(answer){
    for(const t of MEALS){
      choose(`${t}-diet`,dietFor(answer,t));
      for(const p of PROTEINS)write(`${t}-${p}`,answer==="mostly"&&p==="vegetarian"?half(count(t)):null);
      $(`${t}-diet`)?.dispatchEvent(new Event("change",{bubbles:true}));
    }
  }
  // Changing the number of meals keeps "Mest vegetariskt" at half of the new count.
  function keepingDiet(change){const diet=dietAnswer();change();if(diet==="mostly")applyDiet("mostly");}
  function cookingAnswer(){
    const time=$('recipe-quick-time')?.value,n=$('recipe-quick-ingredients')?.value;
    return Object.entries(COOKING).find(([,v])=>v.time===time&&v.count===n)?.[0]??null;
  }
  function importantOn(name){
    if(name==="organic")return !!$('organic-animals')?.checked;
    return MEALS.every(t=>Object.entries(IMPORTANT[name][t]||{}).every(([k,v])=>read(`${t}-${k}`)===v));
  }
  function setImportant(name,on){
    if(name==="organic"){check("organic-animals",on);return;}
    for(const [t,limits] of Object.entries(IMPORTANT[name]))for(const [k,v] of Object.entries(limits))write(`${t}-${k}`,on?v:null);
  }
  function tasteToggle(name,kind,on){
    const value=taste(),k=key(name),drop=list=>(list||[]).filter(v=>key(v)!==k);
    const next={likes:drop(value.likes),dislikes:drop(value.dislikes),exclusions:drop(value.exclusions),allergies:drop(value.allergies)};
    if(on)next[kind==="allergy"?"allergies":"likes"].push(name);
    window.SmakoTaste?.set(next);
  }
  const has=(list,name)=>(list||[]).some(v=>key(v)===key(name));
  const avoided=name=>{const t=taste();return has(t.allergies,name)||has(t.exclusions,name)||has(t.dislikes,name);};
  const cuisineBox=value=>$(`cuisine-${value}`);
  const selectedCuisines=()=>CUISINES.filter(([v])=>cuisineBox(v)?.checked);
  const guest=()=>document.querySelector(".membership-note")?.hidden===false;

  // ---- Building blocks ----
  function group(label,options,{multi=false,cls=""}={}){
    const box=el("div",null,`guide-options ${cls}`.trim());box.setAttribute("role",multi?"group":"radiogroup");box.setAttribute("aria-label",label);
    for(const o of options){
      const b=el("button",null,"guide-option");b.type="button";
      if(multi)b.setAttribute("aria-pressed",String(!!o.on));else{b.setAttribute("role","radio");b.setAttribute("aria-checked",String(!!o.on));}
      b.append(el("span",o.label,"guide-option-label"));if(o.sub)b.append(el("span",o.sub,"guide-option-sub"));
      if(o.disabled){b.disabled=true;}
      // The form's own summary and the guide redraw on the form's change event.
      b.addEventListener("click",()=>{o.pick();$('personal-form')?.dispatchEvent(new Event("change"));});box.append(b);
    }
    return box;
  }
  const small=(text,cls="guide-note")=>el("p",text,cls);
  const heading=text=>el("h3",text,"guide-subtitle");

  // ---- The questions ----
  const QUESTIONS=[
    {id:"people",title:"Hur många brukar äta?",lead:"Det blir antalet portioner per rätt, för alla måltider.",
      body(){
        const n=servingsAnswer(),parts=[group("Antal personer",[1,2,3,4].map(v=>({label:String(v),on:n===v,pick:()=>setServings(v)})).concat({label:"5 eller fler",on:n!==null&&n>=5,pick:()=>setServings(Math.max(5,n??5))}))];
        if(n!==null&&n>=5){
          const row=el("div",null,"guide-stepper");
          const minus=el("button","−","guide-step");minus.type="button";minus.setAttribute("aria-label","Färre portioner");minus.disabled=n<=5;minus.addEventListener("click",()=>setServings(n-1));
          const plus=el("button","+","guide-step");plus.type="button";plus.setAttribute("aria-label","Fler portioner");plus.disabled=n>=8;plus.addEventListener("click",()=>setServings(n+1));
          const value=el("span",`${n} portioner`,"guide-step-value");value.setAttribute("aria-live","polite");
          row.append(minus,value,plus);parts.push(row);
        }
        if(n===null)parts.push(small("Du har olika antal portioner för olika måltider. Välj ett antal för att använda samma för alla."));
        if(guest())parts.push(small("Som gäst kan du välja högst 2 portioner per rätt. Med ett konto kan du välja fler."));
        return parts;
      },
      summary(){const n=servingsAnswer();return n===null?"Olika för olika måltider":`${n} ${n===1?"portion":"portioner"} per rätt`;}},
    {id:"meals",title:"Vad vill du planera?",lead:"Välj hur många middagar du vill ha. Frukost och mellanmål kan du lägga till.",
      body(){
        const parts=[heading("Middagar i veckan"),group("Middagar i veckan",[3,5,7].map(v=>({label:String(v),on:count("dinner")===v,pick:()=>keepingDiet(()=>write("dinner-count",v))})),{cls:"guide-numbers"})];
        if(![3,5,7].includes(count("dinner")))parts.push(small(`Du har valt ${count("dinner")} middagar. Välj ett antal ovan för att ändra.`));
        for(const [type,label,plural] of [["breakfast","frukost","Frukostar"],["snack","mellanmål","Mellanmål"]]){
          const on=enabled(type);
          parts.push(group(`Lägg till ${label}`,[{label:on?`${label[0].toUpperCase()+label.slice(1)} är med`:`Lägg till ${label}`,on,pick:()=>keepingDiet(()=>addMeal(type,!on))}],{multi:true,cls:"guide-wide"}));
          if(on)parts.push(heading(`${plural} i veckan`),group(`${plural} i veckan`,[3,5,7].map(v=>({label:String(v),on:count(type)===v,pick:()=>keepingDiet(()=>write(`${type}-count`,v))})),{cls:"guide-numbers"}));
        }
        if(guest())parts.push(small("Som gäst får menyn högst 3 recept. Med ett konto kan du välja fler."));
        return parts;
      },
      summary(){
        const list=[`${count("dinner")} ${count("dinner")===1?"middag":"middagar"}`];
        if(enabled("breakfast"))list.push(`${count("breakfast")} ${count("breakfast")===1?"frukost":"frukostar"}`);
        if(enabled("snack"))list.push(`${count("snack")} mellanmål`);
        return list.join(", ");
      }},
    {id:"diet",title:"Hur äter du?",lead:"Valet gäller alla måltider, utom Kött som gäller middagarna.",
      options:[["mixed","Allt"],["meat","Kött","Kött eller fågel till middag"],["mostly","Mest vegetariskt","Minst hälften av rätterna"],["pescetarian","Pescetariskt","Vegetariskt plus fisk och skaldjur"],["vegetarian","Vegetariskt","Ägg och mejeri ingår"],["vegan","Veganskt","Inget från djur"]],
      body(){
        const now=dietAnswer(),parts=[group("Kostval",this.options.map(([v,label,sub])=>({label,sub,on:now===v,pick:()=>applyDiet(v)})))];
        if(now===null)parts.push(small("Du har egna kostval eller en egen fördelning. Välj ett alternativ för att ersätta dem."));
        return parts;
      },
      summary(){const now=dietAnswer();return this.options.find(([v])=>v===now)?.[1]??"Eget val";}},
    {id:"avoid",title:"Finns det något du inte äter eller är allergisk mot?",lead:"Allergier kontrolleras även i ingrediensförteckningar och spår.",
      body(){
        const t=taste(),parts=[heading("Allergier"),group("Allergier",ALLERGENS.map(([name,label])=>({label,on:has(t.allergies,name),pick:()=>tasteToggle(name,"allergy",!has(t.allergies,name))})),{multi:true})];
        parts.push(heading("Något annat du inte äter?"),borrowed.freeText);
        const other=[...(t.exclusions||[]),...(t.dislikes||[])],allergies=(t.allergies||[]).filter(n=>!ALLERGENS.some(([a])=>key(a)===key(n)));
        if(allergies.length||other.length)parts.push(small(`Undviker också: ${[...allergies.map(n=>`${n} (allergi)`),...other].join(", ")}`,"guide-current"));
        return parts;
      },
      summary(){const t=taste(),list=[...(t.allergies||[]).map(n=>`${n} (allergi)`),...(t.exclusions||[]),...(t.dislikes||[])];return list.length?list.join(", "):"Inget";}},
    {id:"likes",title:"Vad tycker du om?",lead:"Smako väljer gärna recept med det du markerar.",
      body(){
        const t=taste(),selected=selectedCuisines().length;
        const parts=[heading("Matkök"),group("Matkök",CUISINES.map(([v,label])=>({label,on:!!cuisineBox(v)?.checked,disabled:!cuisineBox(v)||cuisineBox(v).disabled,pick:()=>check(`cuisine-${v}`,!cuisineBox(v).checked)})),{multi:true})];
        parts.push(small(selected?"Recepten kommer från de matkök du har markerat.":"Inget markerat betyder alla matkök."));
        parts.push(heading("Råvaror"),group("Råvaror",LIKES.map(([name,label])=>({label,on:has(t.likes,name),disabled:avoided(name),pick:()=>tasteToggle(name,"like",!has(t.likes,name))})),{multi:true}));
        const extra=(t.likes||[]).filter(n=>!LIKES.some(([l])=>key(l)===key(n)));
        if(extra.length)parts.push(small(`Gillar också: ${extra.join(", ")}`,"guide-current"));
        return parts;
      },
      summary(){const list=[...selectedCuisines().map(([,l])=>l),...(taste().likes||[])];return list.length?list.join(", "):"Allt möjligt";}},
    {id:"cooking",title:"Hur vill du laga mat en vanlig dag?",lead:"Det sätter hur lång tid du står i köket och hur många ingredienser recepten har.",
      options:[["quick","Snabbt och enkelt","Högst 30 minuter och 8 ingredienser"],["everyday","Vardagsmat","Högst 45 minuter och 12 ingredienser"],["more","Gärna lite mer","Ingen gräns för tid eller ingredienser"]],
      body(){
        const now=cookingAnswer(),parts=[group("Matlagning",this.options.map(([v,label,sub])=>({label,sub,on:now===v,pick:()=>{choose("recipe-quick-time",COOKING[v].time);choose("recipe-quick-ingredients",COOKING[v].count);}})))];
        if(now===null)parts.push(small("Du har egna gränser för tid eller ingredienser. Välj ett alternativ för att ersätta dem."));
        return parts;
      },
      summary(){const now=cookingAnswer();return this.options.find(([v])=>v===now)?.[1]??"Egna gränser";}},
    {id:"variety",title:"Hur mycket omväxling vill du ha?",lead:"Mer omväxling ger fler matkök och färre rätter med samma huvudprotein.",
      options:[["low","Gärna samma favoriter"],["normal","Lagom","Minst tre matkök"],["max","Så varierat som möjligt","Aldrig samma huvudprotein två gånger"]],
      body(){
        const now=$('recipe-variety')?.value,selected=selectedCuisines().length,few=count("dinner")<3||(selected>0&&selected<3);
        const parts=[group("Omväxling",this.options.map(([v,label,sub])=>({label,sub,on:now===v,disabled:v!=="low"&&few&&now!==v,pick:()=>choose("recipe-variety",v)})))];
        if(few)parts.push(small(count("dinner")<3?"Lagom och mer omväxling kräver minst tre middagar.":"Lagom och mer omväxling kräver minst tre matkök. Markera fler eller inga matkök."));
        if(now==="custom")parts.push(small("Du har en egen omväxling. Välj ett alternativ för att ersätta den."));
        return parts;
      },
      summary(){const now=$('recipe-variety')?.value;return this.options.find(([v])=>v===now)?.[1]??"Egen omväxling";}},
    {id:"important",title:"Är något av det här viktigt för dig?",lead:"Välj så många du vill.",
      options:[["protein","Mycket protein","Minst 30 g per middag"],["lighter","Lättare mat","Högst 600 kcal per middag"],["large","Stora portioner","Minst 450 g per middag"],["organic","Ekologiskt kött, ägg och mejeri","Kan göra inköpen dyrare"]],
      body(){
        const on=this.options.filter(([v])=>importantOn(v)).map(([v])=>v);
        const parts=[group("Viktigt för dig",[...this.options.map(([v,label,sub])=>({label,sub,on:on.includes(v),pick:()=>setImportant(v,!on.includes(v))})),
          {label:"Inget särskilt",on:!on.length,pick:()=>this.options.forEach(([v])=>setImportant(v,false))}],{multi:true})];
        if(on.includes("lighter")&&on.includes("large"))parts.push(small("Lättare mat och stora portioner samtidigt ger färre recept att välja bland."));
        return parts;
      },
      summary(){const list=this.options.filter(([v])=>importantOn(v)).map(([,l])=>l);return list.length?list.join(", "):"Inget särskilt";}},
  ];
  const borrowed={};

  function create({view,gate,form,nodes,stepNodes}){
    const panel=el("section",null,"guide");panel.setAttribute("aria-labelledby","guide-title");
    const head=el("div",null,"guide-head"),back=el("button","‹","guide-back"),progressText=el("span",null,"guide-progress");
    back.type="button";back.setAttribute("aria-label","Föregående fråga");head.append(back,progressText);
    const meter=el("div",null,"guide-meter"),meterFill=el("span");meter.setAttribute("aria-hidden","true");meter.append(meterFill);
    const title=el("h2",null,"guide-title");title.id="guide-title";title.tabIndex=-1;
    const lead=el("p",null,"guide-lead"),body=el("div",null,"guide-body"),hint=el("p",null,"guide-hint");hint.setAttribute("role","status");
    panel.append(head,meter,title,lead,body,hint);
    const foot=el("div",null,"guide-foot"),next=el("button",null,"primary-button guide-next"),detailLink=el("button","Anpassa i detalj","guide-detail-link");
    next.type=detailLink.type="button";foot.append(next,detailLink);
    // Steps: 0 = Plats, 1–8 = the questions, 9 = Din plan i korthet.
    const LAST=QUESTIONS.length+1;
    let step=0,detail=false,on=false,mounted=false;
    const slots=new Map();
    function borrow(node){if(!node||slots.has(node))return node;const slot=document.createComment("guide");node.before(slot);slots.set(node,slot);return node;}
    function giveBack(){for(const [node,slot] of slots)slot.replaceWith(node);slots.clear();}

    function summaryList(){
      const dl=el("dl",null,"guide-summary");
      const row=(label,value,target)=>{
        const item=el("div",null,"guide-summary-row"),text=el("div",null,"guide-summary-text");text.append(el("dt",label),el("dd",value));item.append(text);
        if(target!=null){const edit=el("button","Ändra","guide-edit");edit.type="button";edit.setAttribute("aria-label",`Ändra ${label.toLowerCase()}`);edit.addEventListener("click",()=>go(target));item.append(edit);}
        dl.append(item);
      };
      row("Butiker",$('location-selection-status')?.textContent||"Ange postnummer",0);
      const labels=["Portioner","Måltider","Kost","Undvik","Gillar","Matlagning","Omväxling","Viktigt för dig"];
      QUESTIONS.forEach((q,i)=>row(labels[i],q.summary(),i+1));
      const extras=[...document.querySelectorAll('#choice-summary-lines dt')].find(dt=>dt.textContent==="Egna varor")?.nextElementSibling?.textContent;
      if(extras)row("Egna varor",extras,null);
      return dl;
    }

    function render({focus=false}={}){
      if(!on)return;
      const all=nodes();
      panel.classList.toggle("is-detail",detail);document.body.classList.toggle("guide-detail",detail);
      // Show only what the step needs; Anpassa i detalj shows the whole form.
      const visible=new Set(detail?all:step===0?[$('location-step')]:[]);
      all.forEach(n=>n.classList.toggle("config-off",!visible.has(n)));
      giveBack();
      if(!detail&&step===QUESTIONS.findIndex(q=>q.id==="avoid")+1){
        const free=borrow($('profile-free-text')),unresolved=borrow($('unresolved-label'));
        if(free)free.open=true;
        const box=el("div",null,"guide-free");box.append(...[free,unresolved].filter(Boolean));borrowed.freeText=box;
      }
      const question=step>=1&&step<=QUESTIONS.length?QUESTIONS[step-1]:null;
      back.hidden=!detail&&step===0;
      progressText.textContent=detail?"Alla val":question?`Fråga ${step} av ${QUESTIONS.length}`:step===0?"Först: butiker":"Klart";
      meterFill.style.width=`${detail?100:Math.round(step/LAST*100)}%`;meter.hidden=detail;
      title.textContent=detail?"Anpassa i detalj":question?question.title:step===0?"Var vill du handla?":"Din plan i korthet";
      lead.textContent=detail?"Här finns alla val. Det du svarade på frågorna är redan ifyllt.":question?question.lead:step===0?"Ange ditt postnummer och välj butiker. Sedan kommer åtta korta frågor.":"Kontrollera dina svar. Tryck på Ändra för att svara om.";
      body.replaceChildren(...(detail?[]:question?question.body():step===LAST?[summaryList()]:[]));
      const submit=$('choice-submit');
      foot.hidden=detail;detailLink.hidden=step!==LAST;
      if(step===LAST){next.textContent=submit?.textContent||"Skapa plan och inköpslista";next.disabled=!!submit?.disabled;}
      else{next.textContent=step===0&&gate.disabled?"Fortsätt":step===QUESTIONS.length?"Visa sammanfattningen":"Nästa";next.disabled=false;}
      if(focus){window.scrollTo({top:0,behavior:"instant"});title.focus({preventScroll:true});}
    }
    function go(index,{focus=true}={}){
      if(index>0&&gate.disabled){hint.textContent="Ange postnummer, välj butiker och tryck Fortsätt till måltider först.";index=0;}else hint.textContent="";
      step=Math.max(0,Math.min(LAST,index));detail=false;render({focus});
    }
    function openDetail(target){
      detail=true;hint.textContent="";render();
      window.scrollTo({top:target?Math.max(0,target.getBoundingClientRect().top+window.scrollY-12):0,behavior:"instant"});
      if(!target)title.focus({preventScroll:true});
    }
    next.addEventListener("click",()=>{
      if(step===LAST){$('choice-submit')?.click();return;}
      if(step===0&&gate.disabled){
        const confirm=$('confirm-location');
        if(confirm&&!confirm.closest("[hidden]")&&!confirm.disabled)confirm.click();
        else{hint.textContent="Skriv ditt postnummer och tryck på Hitta butiker.";$('customer-postcode')?.focus();}
        return;
      }
      go(step+1);
    });
    back.addEventListener("click",()=>detail?go(LAST):go(step-1));
    detailLink.addEventListener("click",()=>openDetail());

    // Re-read the form after every change, from the guide or elsewhere (Tolka, restore).
    let pending=false;
    const refresh=()=>{if(!on||pending)return;pending=true;requestAnimationFrame(()=>{pending=false;if(!on)return;
      const focused=document.activeElement,label=panel.contains(focused)?focused.closest(".guide-options")?.getAttribute("aria-label"):null,
        index=label?[...focused.closest(".guide-options").children].indexOf(focused.closest(".guide-option")):-1;
      render();
      // Keep focus on the pressed option when the buttons are redrawn.
      if(label){const again=[...panel.querySelectorAll(".guide-options")].find(g=>g.getAttribute("aria-label")===label)?.children[index];again?.focus({preventScroll:true});}
    });};
    form.addEventListener("input",refresh);form.addEventListener("change",refresh);
    new MutationObserver(()=>{if(!on)return;if(gate.disabled&&step>0&&!detail)go(0,{focus:false});else refresh();}).observe(gate,{attributes:true,attributeFilter:["disabled"]});
    const submit=$('choice-submit');if(submit)new MutationObserver(refresh).observe(submit,{attributes:true,attributeFilter:["disabled"],childList:true,characterData:true,subtree:true});
    const status=$('location-selection-status');if(status)new MutationObserver(refresh).observe(status,{childList:true,characterData:true,subtree:true});

    return {
      mount(){if(mounted)return;mounted=true;view.prepend(panel);view.append(foot);},
      unmount(){if(!mounted)return;mounted=false;on=false;giveBack();panel.remove();foot.remove();document.body.classList.remove("guide-detail");},
      activate(){on=true;},
      deactivate(){on=false;giveBack();detail=false;document.body.classList.remove("guide-detail");},
      // Called by configurator.js with its own step numbers.
      route(index,{summary,focus=true}={}){
        if(!on)return;
        if(index===0){go(0,{focus});return;}
        if(index===summary){go(LAST,{focus});return;}
        if(index===1){if(detail)render();else if(step===0)go(1,{focus});else render({focus});return;}
        openDetail(stepNodes(index)[0]);
      },
    };
  }
  window.SmakoChoiceGuide={create,questions:QUESTIONS.map(q=>q.id)};
})();

/* Mobile step-by-step presentation of the existing "Mina val" form. It only
   shows, hides and summarises the controls that personal.js and
   shopping-location.js already own; values, validation and submission stay
   with them. Desktop keeps the full form. No API calls. */
(() => {
  "use strict";
  const $=id=>document.getElementById(id);
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};
  const view=$('personal-choices'),form=$('personal-form'),gate=$('planning-choices'),extra=$('extra-choices');
  if(!view||!form||!gate)return;
  const mobile=window.matchMedia("(max-width: 849px)");
  const fieldsetOf=id=>$(id)?.closest("fieldset");
  const steps=[
    {key:"plats",title:"Plats",lead:"Var vill du handla?",nodes:()=>[$('location-step')]},
    {key:"maltider",title:"Måltider",lead:"Hur många måltider och portioner?",nodes:()=>[gate.querySelector(':scope>p:not(.sr-only)'),$('meal-settings'),fieldsetOf('extra-meal-toggles')]},
    {key:"butiker",title:"Butiker",lead:"Hur många butiker får korgen delas på?",nodes:()=>[fieldsetOf('store-count-control')]},
    {key:"smak",title:"Smak",lead:"Vad gillar du – och vad måste undvikas?",nodes:()=>[$('taste-choices')]},
    {key:"recept",title:"Recept",lead:"Vilka recept passar dig?",nodes:()=>[$('complete-recipe-controls')]},
    {key:"mer",title:"Mer",lead:"Ekologiskt, skafferi och överskott",nodes:()=>[$('organic-choices'),$('pantry-choices'),$('surplus-choices')]},
    {key:"sammanfattning",title:"Sammanfattning",lead:"Din plan i korthet",nodes:()=>[document.querySelector('.choice-summary')]},
  ];
  let active=0,on=false,extraWasOpen=false,awaitingLocation=false;

  const hero=el("div",null,"config-hero");hero.setAttribute("aria-hidden","true");
  const week=el("div",null,"config-week"),headline=el("p",null,"config-headline"),subline=el("p",null,"config-subline");
  const days=["M","T","O","T","F","L","S"].map(d=>{const day=el("span",null,"config-day");day.append(el("span",d,"config-day-label"),el("span",null,"config-plate"),el("span",null,"config-extras"));week.append(day);return day;});
  hero.append(week,headline,subline);
  const tabs=el("nav",null,"config-tabs");tabs.setAttribute("aria-label","Steg i Mina val");
  const tabButtons=steps.map((step,index)=>{const b=el("button",null,"config-tab");b.type="button";b.dataset.step=String(index);b.append(el("span",String(index+1),"config-tab-number"),el("span",step.title));b.addEventListener("click",()=>go(index));tabs.append(b);return b;});
  const head=el("div",null,"config-head");head.append(hero,tabs);
  const stepTitle=el("h2",null,"config-step-title");stepTitle.tabIndex=-1;
  const stepLead=el("p",null,"config-step-lead"),hint=el("p",null,"config-hint");hint.setAttribute("role","status");
  const intro=el("div",null,"config-step-intro");intro.append(stepTitle,stepLead,hint);
  const bar=el("div",null,"config-bar"),back=el("button","‹","config-back"),barText=el("div",null,"config-bar-text"),next=el("button",null,"primary-button config-next");
  back.type="button";back.setAttribute("aria-label","Föregående steg");next.type="button";
  const barStep=el("span",null,"config-bar-step"),barSummary=el("span",null,"config-bar-summary");barText.append(barStep,barSummary);bar.append(back,barText,next);

  const value=id=>{const n=$(`${id}-value`);const v=Number(String(n?.value||"").replace(",","."));return Number.isFinite(v)&&n?.value!==""?v:null;};
  const enabled=type=>type==="dinner"||$(`enable-${type}`)?.checked;
  const locked=index=>index>0&&gate.disabled;

  function updateHero(){
    const dinners=Math.max(0,Math.min(7,Math.round(value("dinner-count")??0))),servings=value("dinner-servings");
    const extras=["breakfast","snack"].filter(enabled).map(t=>({type:t,count:Math.min(7,Math.round(value(`${t}-count`)??0))}));
    days.forEach((day,i)=>{day.classList.toggle("is-planned",i<dinners);day.querySelector(".config-extras").replaceChildren(...extras.filter(e=>i<e.count).map(e=>el("span",null,`config-dot config-dot-${e.type}`)));});
    headline.textContent=`${dinners} ${dinners===1?"middag":"middagar"}${servings?` · ${servings} portioner`:""}`;
    const parts=[];const postcode=$('customer-postcode')?.value.trim();if(postcode&&!gate.disabled)parts.push(`Postnummer ${postcode}`);
    const stores=value("max-stores");if(stores)parts.push(`max ${stores} ${stores===1?"butik":"butiker"}`);
    for(const e of extras)parts.push(`${e.count} ${e.type==="breakfast"?"frukost":"mellanmål"}`);
    subline.textContent=parts.join(" · ")||"Börja med ditt postnummer";
    
  }

  function updateBar(){
    tabButtons.forEach((b,i)=>{if(i===active)b.setAttribute("aria-current","step");else b.removeAttribute("aria-current");b.classList.toggle("is-locked",locked(i));b.classList.toggle("is-done",i<active&&!locked(i));});
    back.disabled=active===0;barStep.textContent=`Steg ${active+1} av ${steps.length}`;barSummary.textContent=steps[active].title;
    const last=active===steps.length-1,submit=$('choice-submit');
    if(last){next.textContent=submit?.textContent||"Skapa plan";next.disabled=!!submit?.disabled;}
    else if(active===0&&gate.disabled){next.textContent="Fortsätt till måltider";next.disabled=false;}
    else{next.textContent=`Nästa: ${steps[active+1].title}`;next.disabled=false;}
  }

  function render(){
    const visible=new Set(steps[active].nodes().filter(Boolean));
    steps.forEach(step=>step.nodes().forEach(n=>n&&n.classList.toggle("config-off",!visible.has(n))));
    stepTitle.textContent=steps[active].title;stepLead.textContent=steps[active].lead;
    updateBar();updateHero();
  }

  function go(index,{focus=true}={}){
    if(index<0||index>=steps.length)return;
    if(locked(index)){hint.textContent="Ange postnummer och välj butiker först.";index=0;}else hint.textContent="";
    active=index;render();
    tabButtons[index].scrollIntoView({block:"nearest",inline:"center",behavior:"instant"});
    window.scrollTo({top:0,behavior:"instant"});
    if(focus)stepTitle.focus({preventScroll:true});
  }

  next.addEventListener("click",()=>{
    if(active===steps.length-1){$('choice-submit')?.click();return;}
    if(active===0&&gate.disabled){
      const confirm=$('confirm-location');
      if(confirm&&!confirm.closest("[hidden]")&&!confirm.disabled){awaitingLocation=true;confirm.click();}
      else{hint.textContent="Skriv ditt postnummer och tryck på Hitta butiker.";$('customer-postcode')?.focus();}
      return;
    }
    go(active+1);
  });
  back.addEventListener("click",()=>go(active-1));
  // shopping-location.js opens the gate on confirm; continue to meals then.
  $('confirm-location')?.addEventListener("click",()=>{awaitingLocation=true;});
  new MutationObserver(()=>{if(!on)return;if(awaitingLocation&&!gate.disabled){awaitingLocation=false;go(1);}else if(locked(active))go(0,{focus:false});else updateBar();}).observe(gate,{attributes:true,attributeFilter:["disabled"]});
  const submit=$('choice-submit');if(submit)new MutationObserver(()=>on&&updateBar()).observe(submit,{attributes:true,attributeFilter:["disabled"],childList:true,characterData:true,subtree:true});
  form.addEventListener("input",()=>on&&updateHero());form.addEventListener("change",()=>on&&updateHero());
  document.addEventListener("click",event=>{if(on&&event.target.closest("dialog"))setTimeout(updateHero);});
  window.addEventListener("scroll",()=>{if(on)head.classList.toggle("is-compact",window.scrollY>48);},{passive:true});

  function enter(){
    if(on)return;on=true;extraWasOpen=extra?.open??false;if(extra)extra.open=true;
    document.body.classList.add("config-mode");view.prepend(head);view.insertBefore(intro,view.querySelector('.choices-workspace'));document.body.append(bar);
    // A confirmed location (e.g. restored) starts at the meals, like a resumed build.
    go(active===0&&!gate.disabled?1:active,{focus:false});
  }
  function exit(){
    if(!on)return;on=false;if(extra)extra.open=extraWasOpen;
    document.body.classList.remove("config-mode");head.remove();intro.remove();bar.remove();
    document.querySelectorAll(".config-off").forEach(n=>n.classList.remove("config-off"));
  }
  const sync=()=>{if(mobile.matches&&!view.hidden)enter();else exit();};
  mobile.addEventListener("change",sync);
  new MutationObserver(sync).observe(view,{attributes:true,attributeFilter:["hidden"]});
  sync();
})();

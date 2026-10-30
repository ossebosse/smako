/* Mobile "build your plan" presentation of the existing "Mina val" form:
   a picture per step, and a sheet with a handle that is pulled up to show
   every choice. It only shows, hides and mirrors the controls that
   personal.js and shopping-location.js already own; values, validation and
   submission stay with them. Desktop keeps the full form. No API calls. */
(() => {
  "use strict";
  const $=id=>document.getElementById(id);
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};
  const view=$('personal-choices'),form=$('personal-form'),gate=$('planning-choices'),extra=$('extra-choices');
  if(!view||!form||!gate)return;
  const mobile=window.matchMedia("(max-width: 849px)");
  const fieldsetOf=id=>$(id)?.closest("fieldset");
  const steps=[
    {title:"Plats",art:"place",nodes:()=>[$('location-step')]},
    {title:"Måltider",art:"meals",nodes:()=>[gate.querySelector(':scope>p:not(.sr-only)'),$('meal-settings'),fieldsetOf('extra-meal-toggles')]},
    {title:"Butiker",art:"stores",nodes:()=>[fieldsetOf('store-count-control')]},
    {title:"Smak",art:"taste",nodes:()=>[$('taste-choices')]},
    {title:"Recept",art:"recipes",nodes:()=>[$('complete-recipe-controls')]},
    {title:"Mer",art:"more",nodes:()=>[$('organic-choices'),$('pantry-choices'),$('surplus-choices')]},
    {title:"Sammanfattning",art:"done",tab:false,nodes:()=>[document.querySelector('.choice-summary')]},
  ];
  const summaryIndex=steps.length-1;
  let active=0,on=false,extraWasOpen=false,awaitingLocation=false,expanded=false;

  // Flat illustrations stand in for the car pictures; no image dependencies.
  const svg=body=>`<svg viewBox="0 0 360 220" preserveAspectRatio="xMidYMid slice" role="presentation" focusable="false" xmlns="http://www.w3.org/2000/svg">${body}</svg>`;
  const art={
    place:svg('<rect width="360" height="220" fill="#e9efe4"/><path d="M-10 150 C80 120 140 190 230 150 S330 90 380 110" stroke="#fff" stroke-width="16" fill="none"/><path d="M90 -10 C110 60 70 120 120 230" stroke="#fff" stroke-width="12" fill="none"/><path d="M250 -10 L280 230" stroke="#fff" stroke-width="10" fill="none"/><rect x="28" y="40" width="44" height="34" rx="6" fill="#cfdcc8"/><rect x="290" y="150" width="50" height="40" rx="6" fill="#cfdcc8"/><rect x="150" y="30" width="60" height="40" rx="6" fill="#d9e3d2"/><circle cx="180" cy="168" r="34" fill="#164b3e" opacity=".12"/><path d="M180 70c-22 0-38 16-38 37 0 27 38 63 38 63s38-36 38-63c0-21-16-37-38-37z" fill="#c5523f"/><circle cx="180" cy="106" r="13" fill="#fff"/>'),
    meals:svg('<rect width="360" height="220" fill="#efe7da"/><circle cx="180" cy="112" r="78" fill="#fff"/><circle cx="180" cy="112" r="60" fill="#f6f1e7"/><path d="M140 118c10-26 70-26 80 0-14 22-66 22-80 0z" fill="#e0a458"/><circle cx="162" cy="106" r="10" fill="#7fa36a"/><circle cx="192" cy="100" r="9" fill="#c5523f"/><circle cx="204" cy="116" r="8" fill="#7fa36a"/><circle cx="176" cy="122" r="7" fill="#c5523f"/><rect x="74" y="50" width="8" height="124" rx="4" fill="#9aa79a"/><path d="M66 50v34a12 12 0 0 0 24 0V50" stroke="#9aa79a" stroke-width="5" fill="none"/><rect x="280" y="50" width="9" height="124" rx="4" fill="#9aa79a"/><path d="M289 50c14 10 14 50 0 60z" fill="#9aa79a"/>'),
    stores:svg('<rect width="360" height="220" fill="#e7edf0"/><rect y="176" width="360" height="44" fill="#d6dfd9"/>'+[[24,"#164b3e"],[134,"#c5523f"],[244,"#e0a458"]].map(([x,c])=>`<rect x="${x}" y="86" width="92" height="90" fill="#fff"/><path d="M${x-6} 86h104l-10-30H${x+4}z" fill="${c}"/><path d="M${x-6} 86h104v12H${x-6}z" fill="${c}" opacity=".75"/><rect x="${x+12}" y="112" width="30" height="64" fill="#cfdcc8"/><rect x="${x+52}" y="112" width="28" height="28" fill="#e9efe4"/>`).join("")),
    taste:svg('<rect width="360" height="220" fill="#eef0e2"/><path d="M90 170c-40-50-10-120 60-130-10 60-20 100-60 130z" fill="#7fa36a"/><path d="M90 170c20-40 40-80 60-130" stroke="#4f7a45" stroke-width="3" fill="none"/><path d="M190 60c30 10 60 50 40 110-40-20-60-70-40-110z" fill="#c5523f"/><path d="M190 60c-4-14 4-24 14-28" stroke="#4f7a45" stroke-width="5" fill="none"/><circle cx="290" cy="150" r="30" fill="#e0a458"/><circle cx="282" cy="142" r="7" fill="#fff" opacity=".5"/><circle cx="270" cy="70" r="14" fill="#7fa36a"/><circle cx="292" cy="62" r="11" fill="#9cc086"/>'),
    recipes:svg('<rect width="360" height="220" fill="#f3ead9"/><rect x="96" y="28" width="168" height="168" rx="10" fill="#fff" transform="rotate(-4 180 112)"/><rect x="120" y="54" width="90" height="12" rx="6" fill="#164b3e" transform="rotate(-4 180 112)"/>'+[84,104,124,144,164].map(y=>`<rect x="122" y="${y}" width="${y%40?110:80}" height="7" rx="3.5" fill="#d9dfd6" transform="rotate(-4 180 112)"/>`).join("")+'<circle cx="270" cy="160" r="30" fill="#c5523f"/><rect x="246" y="150" width="48" height="10" rx="5" fill="#a3402f"/>'),
    more:svg('<rect width="360" height="220" fill="#e6efe6"/><rect x="58" y="70" width="80" height="110" rx="14" fill="#fff"/><rect x="66" y="56" width="64" height="20" rx="6" fill="#c5523f"/><rect x="72" y="110" width="52" height="40" rx="6" fill="#e0a458" opacity=".6"/><path d="M240 180c-70-10-80-90-20-130 40 50 60 90 20 130z" fill="#7fa36a"/><path d="M240 180c-10-40-20-80-20-130" stroke="#4f7a45" stroke-width="3" fill="none"/><circle cx="300" cy="80" r="22" fill="#e0a458"/>'),
    done:svg('<rect width="360" height="220" fill="#e9efe4"/><path d="M118 80h124l-12 112H130z" fill="#164b3e"/><path d="M146 80c0-46 68-46 68 0" stroke="#164b3e" stroke-width="9" fill="none"/><circle cx="160" cy="56" r="20" fill="#7fa36a"/><circle cx="196" cy="50" r="16" fill="#c5523f"/><circle cx="180" cy="66" r="14" fill="#e0a458"/><path d="M160 136l14 14 28-30" stroke="#fff" stroke-width="9" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'),
  };

  const top=el("div",null,"config-top"),done=el("button","Klar","config-done"),topText=el("div",null,"config-top-text"),close=el("button","×","config-close");
  done.type="button";close.type="button";close.setAttribute("aria-label","Stäng Mina val");
  const topTitle=el("span","Mina val","config-top-title"),topArea=el("span",null,"config-top-area");topText.append(topTitle,topArea);top.append(done,topText,close);
  const hero=el("div",null,"config-hero");hero.setAttribute("aria-hidden","true");
  const handle=el("button",null,"config-handle");handle.type="button";handle.append(el("span",null,"config-handle-bar"));
  const tabs=el("nav",null,"config-tabs");tabs.setAttribute("aria-label","Steg i Mina val");
  const tabButtons=steps.map((step,index)=>{if(step.tab===false)return null;const b=el("button",step.title,"config-tab");b.type="button";b.addEventListener("click",()=>go(index));tabs.append(b);return b;}).filter(Boolean);
  const sheetHead=el("div",null,"config-sheet-head");sheetHead.append(handle,tabs);
  const hint=el("p",null,"config-hint");hint.setAttribute("role","status");
  const foot=el("div",null,"config-foot"),next=el("button",null,"config-next");next.type="button";foot.append(next);
  const locked=index=>index>0&&gate.disabled;

  // Volvo-style tiles and "Lägg till" pills mirror existing selects/checkboxes.
  const tileSets=[["location-store-mode",{radius:"Nära mig",municipality:"Hela kommunen",specific:"Välj själv"}],["location-radius"],["surplus-mode",{minimize:"Minsta överskott",allow_larger:"Större köp"}]].map(([id,labels])=>{
    const selectNode=$(id);if(!selectNode)return null;
    const row=el("div",null,"config-tiles");row.setAttribute("role","radiogroup");row.setAttribute("aria-label",selectNode.closest("label")?.firstChild?.textContent?.trim()||id);
    const buttons=[...selectNode.options].map(option=>{const b=el("button",labels?.[option.value]??option.text,"config-tile");b.type="button";b.setAttribute("role","radio");b.dataset.value=option.value;
      b.addEventListener("click",()=>{if(selectNode.value===option.value)return;selectNode.value=option.value;selectNode.dispatchEvent(new Event("change",{bubbles:true}));syncTiles();});row.append(b);return b;});
    return {selectNode,row,buttons};
  }).filter(Boolean);
  const pills=["enable-breakfast","enable-snack","organic-animals","planning-use-pantry"].map(id=>{const box=$(id);if(!box)return null;const pill=el("span",null,"config-pill");pill.setAttribute("aria-hidden","true");return {box,pill};}).filter(Boolean);
  function syncTiles(){
    for(const set of tileSets){for(const b of set.buttons)b.setAttribute("aria-checked",String(set.selectNode.value===b.dataset.value));set.row.hidden=!!set.selectNode.closest("[hidden]");}
    for(const {box,pill} of pills){pill.textContent=box.checked?"Tillagd ✓":"Lägg till";pill.classList.toggle("is-on",box.checked);}
  }

  function setExpanded(value){
    expanded=value;document.body.classList.toggle("config-expanded",expanded);
    handle.setAttribute("aria-expanded",String(expanded));handle.setAttribute("aria-label",expanded?"Visa mindre av valen":"Visa alla val");
    view.style.removeProperty("--config-drag");
  }

  function updateChrome(){
    tabButtons.forEach((b,i)=>{if(i===active)b.setAttribute("aria-current","step");else b.removeAttribute("aria-current");b.classList.toggle("is-locked",locked(i));});
    const postcode=$('customer-postcode')?.value.trim();
    topArea.textContent=gate.disabled?"Ange postnummer":`Nära ${postcode}`;
    done.disabled=gate.disabled;
    if(active===summaryIndex)next.textContent="‹ Tillbaka till valen";
    else if(active===0&&gate.disabled)next.textContent="Fortsätt till måltider";
    else if(active===summaryIndex-1)next.textContent="Klar – granska planen";
    else next.textContent=`Nästa: ${steps[active+1].title}`;
  }

  function render(){
    const visible=new Set(steps[active].nodes().filter(Boolean));
    steps.forEach(step=>step.nodes().forEach(n=>n&&n.classList.toggle("config-off",!visible.has(n))));
    hero.innerHTML=art[steps[active].art];
    view.classList.toggle("config-summary",active===summaryIndex);
    syncTiles();updateChrome();
  }

  function go(index){
    if(index<0||index>=steps.length)return;
    if(locked(index)){hint.textContent="Ange postnummer och välj butiker först.";index=0;}else hint.textContent="";
    active=index;render();view.scrollTop=0;
    tabButtons[Math.min(index,tabButtons.length-1)]?.scrollIntoView({block:"nearest",inline:"center",behavior:"instant"});
  }

  next.addEventListener("click",()=>{
    if(active===summaryIndex){go(summaryIndex-1);return;}
    if(active===0&&gate.disabled){
      const confirm=$('confirm-location');
      if(confirm&&!confirm.closest("[hidden]")&&!confirm.disabled){awaitingLocation=true;confirm.click();}
      else{hint.textContent="Skriv ditt postnummer och tryck på Hitta butiker.";setExpanded(true);$('customer-postcode')?.focus();}
      return;
    }
    go(active+1);
  });
  done.addEventListener("click",()=>{go(summaryIndex);setExpanded(true);});
  close.addEventListener("click",()=>document.querySelector('.personal-nav [data-open="plan"]')?.click());

  // Tap the handle to toggle; drag it to pull the sheet up or down.
  let drag=null;
  handle.addEventListener("pointerdown",event=>{drag={y:event.clientY,start:view.getBoundingClientRect().top,moved:false};handle.setPointerCapture(event.pointerId);});
  handle.addEventListener("pointermove",event=>{if(!drag)return;const dy=event.clientY-drag.y;if(Math.abs(dy)>6)drag.moved=true;if(drag.moved){view.style.setProperty("--config-drag",`${Math.max(0,drag.start+dy)}px`);document.body.classList.add("config-dragging");}});
  const endDrag=event=>{if(!drag)return;const dy=event.clientY-drag.y,moved=drag.moved;drag=null;document.body.classList.remove("config-dragging");setExpanded(moved?dy<0||(Math.abs(dy)<40&&expanded):!expanded);};
  handle.addEventListener("pointerup",endDrag);handle.addEventListener("pointercancel",endDrag);
  view.addEventListener("scroll",()=>{if(on&&!expanded&&view.scrollTop>12)setExpanded(true);},{passive:true});
  view.addEventListener("focusin",event=>{if(on&&!expanded&&event.target.matches("input:not([type=checkbox]),textarea,select"))setExpanded(true);});

  // shopping-location.js opens the gate on confirm; continue to meals then.
  $('confirm-location')?.addEventListener("click",()=>{awaitingLocation=true;});
  new MutationObserver(()=>{if(!on)return;if(awaitingLocation&&!gate.disabled){awaitingLocation=false;go(1);}else if(locked(active))go(0);else{syncTiles();updateChrome();}}).observe(gate,{attributes:true,attributeFilter:["disabled"]});
  form.addEventListener("input",()=>on&&syncTiles());form.addEventListener("change",()=>on&&(syncTiles(),updateChrome()));

  function enter(){
    if(on)return;on=true;extraWasOpen=extra?.open??false;if(extra)extra.open=true;
    document.body.classList.add("config-mode");document.body.prepend(top,hero);
    view.prepend(sheetHead,hint);view.append(foot);
    for(const set of tileSets)set.selectNode.closest("label").after(set.row);
    for(const {box,pill} of pills)box.after(pill);
    setExpanded(window.innerHeight<600);
    // A confirmed location (e.g. restored) starts at the meals, like a resumed build.
    go(active===0&&!gate.disabled?1:active);
  }
  function exit(){
    if(!on)return;on=false;if(extra)extra.open=extraWasOpen;
    document.body.classList.remove("config-mode","config-expanded","config-dragging");view.classList.remove("config-summary");
    for(const n of [top,hero,sheetHead,hint,foot,...tileSets.map(s=>s.row),...pills.map(p=>p.pill)])n.remove();
    document.querySelectorAll(".config-off").forEach(n=>n.classList.remove("config-off"));
  }
  const sync=()=>{if(mobile.matches&&!view.hidden)enter();else exit();};
  mobile.addEventListener("change",sync);
  new MutationObserver(sync).observe(view,{attributes:true,attributeFilter:["hidden"]});
  sync();
})();

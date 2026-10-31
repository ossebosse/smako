/* Progress panel for creating a plan. It takes the place of the create button
   (inline on desktop, as a bottom card on mobile) and shows the server's
   reported stage, measured counts and elapsed time, with a drawn animation and
   a cancel button. Percentages appear only for counts the server measured;
   the stage dots are steps, not an estimate of remaining time. personal.js
   owns the request; this file only renders what it is told. */
(() => {
  "use strict";
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};
  const mobile=window.matchMedia("(max-width: 849px)");
  // Stages in the order the planner reports them (complete-recipes.js has the long texts).
  const STEPS=["queued","library_preparation","product_facts","candidate_qualification","week_search","final_audit","saving"];
  const TITLES={starting:"Skickar dina val till köket",queued:"Ställer oss i kön",library_preparation:"Bläddrar i receptboken",
    product_facts:"Kollar hyllor och priser",candidate_qualification:"Provsmakar recepten",week_search:"Pusslar ihop veckan",
    final_audit:"Dubbelkollar inköpslistan",saving:"Packar kassen",cancelling:"Avbryter…",reconnecting:"Tappade kontakten – återansluter",
    working:"Köket arbetar med din plan"};
  const UNITS={recipes:"recept prövade",publications:"steg klara"};
  const art=`<svg viewBox="0 0 120 96" aria-hidden="true" focusable="false" xmlns="http://www.w3.org/2000/svg">
    <g class="pp-items">
      <g class="pp-item pp-item-1"><path d="M54 4l6 20 6-20z" fill="#f2a65a" stroke="#c46b2a" stroke-width="2" stroke-linejoin="round"/><path d="M57 4c0-5 3-6 3-6s3 1 3 6" fill="none" stroke="#4f7a45" stroke-width="2" stroke-linecap="round"/></g>
      <g class="pp-item pp-item-2"><circle cx="60" cy="14" r="8" fill="#e35d4a" stroke="#a83a2b" stroke-width="2"/><path d="M60 6c0-3 2-5 4-5" fill="none" stroke="#4f7a45" stroke-width="2" stroke-linecap="round"/></g>
      <g class="pp-item pp-item-3"><path d="M50 18c4-12 16-14 20-12-2 10-12 16-20 12z" fill="#9cc086" stroke="#4f7a45" stroke-width="2" stroke-linejoin="round"/><path d="M52 17c5-4 10-7 15-9" fill="none" stroke="#4f7a45" stroke-width="1.5" stroke-linecap="round"/></g>
    </g>
    <g class="pp-bag">
      <path class="pp-draw pp-handle" pathLength="1" d="M47 42c0-17 26-17 26 0" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>
      <path class="pp-draw pp-bag-front" pathLength="1" d="M30 40h60l-6 48H36z" fill="var(--pp-bg)" stroke="currentColor" stroke-width="3" stroke-linejoin="round"/>
      <path class="pp-smile" d="M51 62c5 5 13 5 18 0" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>
      <circle class="pp-eye" cx="50" cy="54" r="2.4" fill="currentColor"/><circle class="pp-eye" cx="70" cy="54" r="2.4" fill="currentColor"/>
    </g>
    <path class="pp-check" pathLength="1" d="M47 64l9 9 18-20" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
  </svg>`;

  const panel=el("section",null,"plan-progress");panel.setAttribute("aria-labelledby","plan-progress-title");
  const visual=el("div",null,"plan-progress-art");visual.innerHTML=art;
  const body=el("div",null,"plan-progress-body");
  const title=el("p",null,"plan-progress-title");title.id="plan-progress-title";
  const detail=el("p",null,"plan-progress-detail");detail.setAttribute("role","status");detail.setAttribute("aria-live","polite");
  const steps=el("ol",null,"plan-progress-steps");steps.setAttribute("aria-hidden","true");const dots=STEPS.map(()=>steps.appendChild(el("li")));
  const meter=el("div",null,"plan-progress-meter"),fill=el("span",null,"plan-progress-fill");meter.append(fill);
  const meta=el("p",null,"plan-progress-meta"),count=el("span",null,"plan-progress-count"),clock=el("span",null,"plan-progress-clock");meta.append(count,clock);
  const actions=el("div",null,"plan-progress-actions"),cancel=el("button","Avbryt","plan-progress-cancel"),close=el("button","Stäng","plan-progress-close");
  cancel.type=close.type="button";actions.append(cancel,close);
  body.append(title,detail,steps,meter,meta,actions);panel.append(visual,body);

  let state=null,timer=null,anchor=null,startedAt=0,onCancel=null,canCancel=()=>false,closeTimer=null;
  const elapsed=()=>{const s=Math.max(0,Math.round((Date.now()-startedAt)/1000));return `${Math.floor(s/60)}:${String(s%60).padStart(2,"0")}`;};
  function place(){
    if(!state)return;
    if(mobile.matches||!anchor||!anchor.isConnected||anchor.closest("[hidden]"))document.body.append(panel);else anchor.after(panel);
  }
  function setState(next){
    state=next;panel.dataset.state=next;document.body.classList.toggle("plan-progress-open",!!next);document.body.classList.toggle("plan-progress-busy",next==="running"||next==="done");
    cancel.hidden=next!=="running";close.hidden=next==="running"||next==="done";
  }
  function refreshCancel(){cancel.disabled=state!=="running"||panel.dataset.stage==="cancelling"||!canCancel();cancel.title=cancel.disabled&&state==="running"&&panel.dataset.stage!=="cancelling"?"Kan avbrytas när beräkningen har startat":"";}

  function start({anchor:target=null,since=null,cancellable=()=>false,cancelAction=null}={}){
    clearTimeout(closeTimer);
    if(state==="running"){refreshCancel();return api;}
    anchor=target;startedAt=since||Date.now();onCancel=cancelAction;canCancel=cancellable;
    setState("running");panel.dataset.stage="starting";
    title.textContent=TITLES.starting;detail.textContent="Alla måltider räknas mot samma korg. En stor plan kan ta flera minuter. Dina val och senaste plan finns kvar medan du väntar.";
    count.textContent="";clock.textContent=elapsed();fill.style.width="0%";meter.hidden=true;steps.hidden=false;
    dots.forEach(d=>d.className="");
    // Restart the drawing animation for each new plan.
    visual.innerHTML=art;
    place();refreshCancel();
    clearInterval(timer);timer=setInterval(()=>{clock.textContent=elapsed();},1000);
    return api;
  }
  function update(text,data){
    if(state!=="running")return;
    const stage=data?(data.stage||"working"):/Återansluter/.test(text||"")?"reconnecting":panel.dataset.stage;
    panel.dataset.stage=stage;title.textContent=TITLES[stage]||TITLES.working;
    // The measured count gets its own line under the bar.
    if(text)detail.textContent=data?.progress?text.replace(/ \d+ av \d+ [^.]+\.$/,""):text;
    const index=STEPS.indexOf(stage);
    if(index>=0)dots.forEach((d,i)=>{d.className=i<index?"is-done":i===index?"is-current":"";});
    const p=data?.progress;
    if(p&&Number.isSafeInteger(p.completed)&&Number.isSafeInteger(p.total)&&p.total>0&&p.completed>=0&&p.completed<=p.total&&UNITS[p.unit]){
      const percent=Math.round(100*p.completed/p.total);
      meter.hidden=false;fill.style.width=`${percent}%`;meter.setAttribute("aria-hidden","true");
      count.textContent=`${percent} % · ${p.completed} av ${p.total} ${UNITS[p.unit]}`;
    }else if(data){meter.hidden=true;count.textContent="";}
    refreshCancel();
  }
  // Resolves after the check has been drawn, so the result follows the animation.
  function finish(){
    if(state!=="running")return Promise.resolve();
    clearInterval(timer);setState("done");panel.dataset.stage="saving";dots.forEach(d=>d.className="is-done");
    title.textContent="Klart! Din plan är packad";detail.textContent="Öppnar planen och inköpslistan…";meter.hidden=true;count.textContent="";
    const wait=window.matchMedia("(prefers-reduced-motion: reduce)").matches?150:900;
    return new Promise(resolve=>setTimeout(()=>{hide();resolve();},wait));
  }
  function fail(message,{cancelled=false}={}){
    if(state!=="running")return;
    clearInterval(timer);setState(cancelled?"cancelled":"error");
    title.textContent=cancelled?"Beräkningen avbröts":"Planen kunde inte skapas";detail.textContent=message;meter.hidden=true;count.textContent="";
    if(cancelled)closeTimer=setTimeout(hide,4000);
    close.focus({preventScroll:true});
  }
  function hide(){clearTimeout(closeTimer);clearInterval(timer);setState(null);delete panel.dataset.stage;panel.remove();}
  // Called when the request ends without finish()/fail(), e.g. leaving the page.
  function settle(){if(state==="running")hide();}

  cancel.addEventListener("click",async()=>{
    if(cancel.disabled||!onCancel)return;
    panel.dataset.stage="cancelling";title.textContent=TITLES.cancelling;detail.textContent="Avbryter beräkningen efter pågående arbetssteg.";refreshCancel();
    try{await onCancel();}catch(error){panel.dataset.stage="working";title.textContent=TITLES.working;detail.textContent=error.message||"Beräkningen kunde inte avbrytas. Den fortsätter.";refreshCancel();}
  });
  close.addEventListener("click",hide);
  mobile.addEventListener("change",place);

  const api={start,update,finish,fail,settle,get active(){return state==="running";}};
  window.SmakoPlanProgress=api;
})();

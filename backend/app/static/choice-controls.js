/* Presentation controls for the existing personal request contract. No API calls. */
(() => {
  "use strict";
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};
  const controls=new Map();
  const emit=node=>node.dispatchEvent(new Event("input",{bubbles:true}));
  function editor(id,title,unit,onEdit){
    const wrap=el("span",null,"slider-value-editor"),node=el("input");
    node.type="text";node.inputMode="decimal";node.id=`${id}-value`;node.placeholder="Standard";
    node.setAttribute("aria-label",title);node.autocomplete="off";
    node.addEventListener("input",event=>{event.stopPropagation();onEdit(node.value.trim().replace(",","."));});
    node.addEventListener("keydown",event=>{if(event.key==="Enter")event.preventDefault();});
    wrap.append(node);if(unit)wrap.append(el("span",unit));return {wrap,node};
  }
  function slider(id,title,initial,{min=0,max=7,unit="",optional=false}={}){
    const compact=!unit,box=el("div",null,`choice-slider${compact?" choice-stepper":""}`);
    const heading=el("div",null,"choice-slider-heading"),label=el("label",title);label.htmlFor=`${id}-value`;
    const range=el("input");range.type="range";range.id=id;range.min=optional?-1:min;range.max=max;range.step="any";
    range.setAttribute("aria-label",title);
    if(compact){range.className="stepper-model";range.tabIndex=-1;range.setAttribute("aria-hidden","true");}
    let value=initial??null;
    const entry=editor(id,title,unit,text=>{
      const next=text===""?null:Number(text);
      const valid=(optional&&next===null)||(text!==""&&/^\d+(\.\d+)?$/.test(text)&&Number.isFinite(next)&&next>=min&&next<=max&&(unit==="kcal"||Number.isInteger(next)));
      entry.node.setCustomValidity(valid?"":`Ange ${unit==="kcal"?"ett tal":"ett heltal"} mellan ${min} och ${max}${optional?", eller lämna tomt för Standard":""}.`);
      error.textContent=entry.node.validationMessage;entry.node.setAttribute("aria-invalid",String(!valid));
      if(valid){value=next;range.value=value??-1;emit(range);}
    });
    const error=el("p",null,"choice-error");error.id=`${id}-error`;entry.node.setAttribute("aria-describedby",error.id);
    function refresh(){entry.node.value=value??"";entry.node.setCustomValidity("");entry.node.removeAttribute("aria-invalid");error.textContent="";range.value=value??-1;range.setAttribute("aria-valuetext",value===null?"Standard":`${value} ${unit}`);}
    if(compact){
      const stepper=el("div",null,"stepper");
      for(const [symbol,delta,verb] of [["−",-1,"Minska"],["+",1,"Öka"]]){
        const b=el("button",symbol,"stepper-button");b.type="button";b.setAttribute("aria-label",`${verb} ${title.toLowerCase()} · ${id.split("-")[0]}`);
        b.addEventListener("click",()=>{value=Math.min(max,Math.max(min,(value??0)+delta));refresh();emit(range);});
        if(delta<0)stepper.append(b,entry.wrap);else stepper.append(b);
      }
      heading.append(label,stepper);
    }else heading.append(label,entry.wrap);
    range.addEventListener("input",()=>{value=optional&&Number(range.value)<0?null:Number(range.value);refresh();});
    range.addEventListener("keydown",event=>{if(["ArrowLeft","ArrowDown","ArrowRight","ArrowUp"].includes(event.key)){event.preventDefault();range.value=Number(range.value)+(["ArrowRight","ArrowUp"].includes(event.key)?1:-1);emit(range);}});
    box.append(heading,range,error);
    if(!compact){const scale=el("div",null,"choice-slider-scale");scale.append(el("span",optional?"Standard":String(min)),el("span",`${max} ${unit}`));box.append(scale);}
    if(optional){const reset=el("button","Standard","choice-reset");reset.type="button";reset.addEventListener("click",()=>{value=null;refresh();emit(range);});box.append(reset);}
    controls.set(id,{set(v){value=v??(optional?null:min);refresh();},read(){return value;},maximum(v){max=v;range.max=v;refresh();}});
    refresh();return box;
  }
  function interval(type,key,title,scaleMax,contractMax=scaleMax){
    const box=el("fieldset",null,"choice-interval");box.append(el("legend",title));
    const values=[null,null],track=el("div",null,"interval-track"),output=el("div",null,"interval-value"),note=el("p",null,"small"),error=el("p",null,"choice-error");
    error.id=`${type}-${key}-error`;let ceiling=scaleMax;
    const ranges=["min","max"].map(end=>{const n=el("input");n.id=`${type}-${end}_${key}`;n.type="range";n.min=0;n.max=ceiling;n.step="any";n.setAttribute("aria-label",`${title} ${end==="min"?"Min":"Max"} (${type})`);track.append(n);return n;});
    const entries=ranges.map((n,i)=>{
      const entry=editor(n.id,`${title} ${i?"Max":"Min"}`,"g",text=>{
        const value=text===""?null:Number(text),valid=text===""||(/^\d+(\.\d+)?$/.test(text)&&Number.isFinite(value)&&value>=0&&value<=contractMax);
        entry.node.setCustomValidity(valid?"":`Ange 0–${contractMax} g eller lämna tomt för Standard.`);
        if(valid){values[i]=value;draw();}validate();
      });
      const label=el("label",i?"Max":"Min");label.htmlFor=entry.node.id;label.append(entry.wrap);entry.node.setAttribute("aria-describedby",error.id);output.append(label);return entry;
    });
    function validate(){
      const crossed=values[0]!==null&&values[1]!==null&&values[0]>values[1];
      // Keep syntactically invalid text visible; never convert it into a constraint.
      for(const entry of entries){if(entry.node.validationMessage==="Min får inte överstiga Max.")entry.node.setCustomValidity("");}
      if(crossed&&!entries[1].node.validationMessage)entries[1].node.setCustomValidity("Min får inte överstiga Max.");
      error.textContent=entries.map(e=>e.node.validationMessage).filter(Boolean).join(" ");
      entries.forEach(e=>e.node.setAttribute("aria-invalid",String(!e.node.checkValidity())));
    }
    function draw(){
      ceiling=Math.max(scaleMax,...values.filter(v=>v!==null));
      ranges.forEach((n,i)=>{n.max=ceiling;n.value=values[i]??(i?ceiling:0);n.setAttribute("aria-valuetext",values[i]===null?"Standard – ingen extra gräns":`${values[i]} g`);});
      track.style.setProperty("--start",`${(values[0]??0)/ceiling*100}%`);track.style.setProperty("--end",`${(values[1]??ceiling)/ceiling*100}%`);
      note.textContent=`Skala 0–${ceiling} g. Lämna tomt för Standard.${contractMax>scaleMax?` Du kan skriva upp till ${contractMax} g.`:""}`;
    }
    function refresh(){entries.forEach((e,i)=>{e.node.value=values[i]??"";e.node.setCustomValidity("");});draw();validate();}
    ranges.forEach((n,i)=>{
      n.addEventListener("input",()=>{const next=Number(n.value),other=values[1-i];values[i]=Math.min(contractMax,Math.max(0,other===null?next:i?Math.max(next,other):Math.min(next,other)));refresh();});
      n.addEventListener("keydown",event=>{if(["ArrowLeft","ArrowDown","ArrowRight","ArrowUp"].includes(event.key)){event.preventDefault();n.value=Number(n.value)+(["ArrowRight","ArrowUp"].includes(event.key)?1:-1);emit(n);}});
      controls.set(n.id,{set(v){values[i]=v??null;refresh();},read(){return values[i];}});
    });
    const reset=el("button","Återställ standard","choice-reset");reset.type="button";reset.addEventListener("click",()=>{values.fill(null);refresh();});
    box.append(output,track,note,error,reset);refresh();return box;
  }
  function dialog({id,title,content,actions,host,validate=()=>true,onApplied=()=>{}}){
    const d=el("dialog",null,"meal-dialog");d.id=id;d.setAttribute("aria-labelledby",`${id}-title`);
    const header=el("div",null,"meal-dialog-header"),h=el("h2",title);h.id=`${id}-title`;
    const x=el("button","×","dialog-x");x.type="button";x.setAttribute("aria-label","Stäng utan att spara");
    const body=el("div",null,"meal-dialog-body"),footer=el("div",null,"meal-dialog-footer");body.append(content);
    const cancel=el("button","Avbryt","secondary-button"),done=el("button","Klart","primary-button");cancel.type=done.type="button";
    header.append(h,x);footer.append(cancel,done);d.append(header,body,footer);host.append(d);
    const open=el("button",title.split(" · ")[1],"secondary-button");open.type="button";open.id=id.replace(/-dialog$/,"-open");open.setAttribute("aria-haspopup","dialog");open.setAttribute("aria-controls",id);open.append(el("span","Standard","meal-button-summary"));actions.append(open);
    let snapshot=[],committed=false;
    open.addEventListener("click",()=>{
      if(document.querySelector("dialog[open]"))return;
      snapshot=[...content.querySelectorAll("input,select")].filter(n=>controls.has(n.id)||n.tagName==="SELECT"||n.type==="checkbox").map(n=>[n,controls.has(n.id)?controls.get(n.id).read():n.type==="checkbox"?n.checked:n.value]);
      committed=false;d.showModal();document.documentElement.classList.add("choice-modal-open");
    });
    done.addEventListener("click",()=>{
      const fields=[...content.querySelectorAll("input,select")],invalid=fields.find(n=>!n.disabled&&!n.checkValidity());
      if(invalid){invalid.focus();invalid.reportValidity();return;}if(!validate())return;
      committed=true;d.close();onApplied();
    });
    [x,cancel].forEach(n=>n.addEventListener("click",()=>d.close()));
    d.addEventListener("keydown",event=>{
      if(event.key!=="Tab")return;
      const fields=[...d.querySelectorAll('button,input,select,textarea,a[href],[tabindex]')].filter(n=>!n.disabled&&n.tabIndex>=0&&n.getClientRects().length&&!n.closest('[hidden]')&&n.getAttribute('aria-hidden')!=="true");
      const first=fields[0],last=fields.at(-1);
      if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
      else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
    });
    d.addEventListener("click",event=>{if(event.target!==d)return;const r=d.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)d.close();});
    d.addEventListener("close",()=>{
      if(!committed){for(const [n,v] of snapshot){if(controls.has(n.id))controls.get(n.id).set(v);else if(n.type==="checkbox")n.checked=v;else n.value=v;}validate();}
      document.documentElement.classList.remove("choice-modal-open");open.focus({preventScroll:true});
    });
    return d;
  }
  window.SmakoChoiceUI={controls,slider,interval,dialog};
})();

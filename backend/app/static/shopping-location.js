/* Postcode-first personal choices over the existing shared price contexts. */
(() => {
  "use strict";
  const $=id=>document.getElementById(id);
  const storage=window.SmakoRecipes.storage,key="smako.personal.location";
  const number=value=>Number(value).toLocaleString("sv-SE",{maximumFractionDigits:1});
  window.SmakoLocation={create(){
    let location=null,selected=[],confirmed=false,epoch=0,restored=null;
    const previous=storage.get(key);
    if(previous?.postcode)$('customer-postcode').value=previous.postcode;
    const gate=$('planning-choices'),status=$('location-status'),selectionStatus=$('location-selection-status');
    const mode=$('location-store-mode'),radius=$('location-radius'),dialog=$('location-stores-dialog');
    const messages={unknown_postcode:"Postnumret finns inte i vårt geografiska underlag. Kontrollera siffrorna eller prova ett annat postnummer.",ambiguous_postcode:"Postnumret har flera geografiska lägen. Vi kan inte avgöra avståndet säkert med detta underlag.",unavailable:"Aktuella butikspriser saknas för området just nu. Försök igen senare.",outside_coverage:"Smako har ännu ingen kartlagd butik inom ungefär 10 km från detta postnummer."};
    function hideMeals(){confirmed=false;gate.hidden=true;gate.disabled=true;}
    function currentIds(){return new Set((location?.contexts||[]).map(row=>row.context_id));}
    function validSelection(){const current=currentIds();return selected.length>0&&selected.length<=1000&&selected.every(id=>current.has(id));}
    function persist(){if(location)storage.set(key,{postcode:location.postal_code,area:location.area_postal_code,mode:mode.value,radius:radius.value,ids:selected.slice()});}
    function updateSelection({automatic=true}={}){
      hideMeals();
      $('location-radius-label').hidden=mode.value!=="radius";
      if(automatic&&location){
        if(mode.value==="municipality")selected=location.municipality_available?location.contexts.map(row=>row.context_id):[];
        if(mode.value==="radius")selected=location.contexts.filter(row=>row.distance_km!=null&&row.distance_km<=Number(radius.value)).map(row=>row.context_id);
      }
      const unavailable=selected.filter(id=>!currentIds().has(id));
      const text=unavailable.length?"En tidigare vald butik saknas i aktuellt underlag. Öppna butiksvalet och granska dina val.":selected.length>1000?"Fler än 1 000 inköpsställen valda. Välj en mindre radie eller välj specifika butiker.":selected.length?`${selected.length} inköpsställen valda${mode.value==="radius"?` inom ungefär ${radius.value} km`:mode.value==="municipality"?` i ${location.municipality_name} kommun`:""}.`:"Inga butiker valda. Öka radien, välj kommunen eller bocka i specifika butiker.";
      selectionStatus.textContent=text;$('location-modal-status').textContent=text;
      // No empty selection can silently expand to every store in the area.
      $('confirm-location').disabled=!validSelection();persist();
    }
    function renderStores(){
      const list=$('location-store-list');list.replaceChildren();
      const rows=[...(location?.contexts||[])];
      for(const id of selected.filter(id=>!currentIds().has(id)))rows.push({context_id:id,display_name:"Tidigare vald butik saknas i aktuellt underlag",missing:true});
      for(const row of rows){
        const label=document.createElement("label");label.className="check-label";
        const box=document.createElement("input");box.type="checkbox";box.id=`context-${row.context_id}`;box.value=row.context_id;box.checked=selected.includes(row.context_id);
        const text=document.createElement("span");text.textContent=[row.display_name,row.address,row.price_scope_label||row.price_semantics,row.distance_km==null?"Avstånd okänt":`ca ${number(row.distance_km)} km${row.distance_basis==="pickup"?" till upphämtning":""}`,row.missing?row.context_id:null].filter(Boolean).join(" · ");
        box.addEventListener("change",()=>{selected=[...list.querySelectorAll("input:checked")].map(n=>n.value);mode.value="specific";updateSelection({automatic:false});});label.append(box,text);list.append(label);
      }
    }
    function openStores(){if(!location)return;mode.value="specific";updateSelection({automatic:false});renderStores();dialog.showModal();}
    async function lookup(){
      const postal=$('customer-postcode').value.replace(/\s/g,"");
      const requestEpoch=++epoch;hideMeals();location=null;$('location-store-settings').hidden=true;
      if(!/^\d{5}$/.test(postal)){status.textContent="Ange ett svenskt postnummer med fem siffror.";$('customer-postcode').focus();return;}
      status.textContent="Kontrollerar postnummer och kartlagda butiker…";
      const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),20000);
      try{
        const response=await fetch(`/api/shopping-location?postal_code=${encodeURIComponent(postal)}`,{cache:"no-store",headers:{Accept:"application/json"},signal:controller.signal});
        const data=await response.json();if(requestEpoch!==epoch)return;
        if(!response.ok)throw new Error(typeof data.detail==="string"?data.detail:"Platskontrollen kunde inte genomföras.");
        if(data.status!=="eligible"){status.textContent=messages[data.status]||"Platsen kunde inte kontrolleras.";return;}
        location=data;status.textContent=`${data.municipality_name} kommun · närmaste kartlagda butik cirka ${number(data.nearest_distance_km)} km bort. Visar kartlagda inköpsställen i ${data.area_name}.`;
        const area=$('postal-code');area.value=data.area_postal_code;area.dispatchEvent(new Event("change",{bubbles:true}));
        mode.querySelector('[value="municipality"]').disabled=!data.municipality_available;
        mode.value="radius";radius.value="3";selected=[];
        const saved=storage.get(key);
        if(saved?.postcode===postal&&saved.area===data.area_postal_code){mode.value=saved.mode;radius.value=saved.radius;selected=saved.ids||[];}
        if(restored&&restored.postal_code===data.area_postal_code&&restored.allowed_store_ids?.length){mode.value="specific";selected=restored.allowed_store_ids.slice();restored=null;}
        if(mode.value==="municipality"&&!data.municipality_available)mode.value="radius";
        $('location-store-settings').hidden=false;updateSelection({automatic:mode.value!=="specific"});
      }catch(error){if(requestEpoch===epoch)status.textContent=error.name==="AbortError"?"Platskontrollen tog för lång tid. Försök igen.":error.message;}
      finally{clearTimeout(timer);}
    }
    $('check-postcode').addEventListener("click",()=>void lookup());
    $('customer-postcode').addEventListener("keydown",event=>{if(event.key==="Enter"){event.preventDefault();void lookup();}});
    $('customer-postcode').addEventListener("input",()=>{++epoch;location=null;selected=[];hideMeals();$('postal-code').value="";$('location-store-settings').hidden=true;status.textContent="Kontrollera postnumret för att fortsätta.";});
    mode.addEventListener("change",()=>{updateSelection();if(mode.value==="specific")openStores();});
    radius.addEventListener("change",()=>updateSelection());
    $('choose-specific-stores').addEventListener("click",openStores);
    $('location-stores-done').addEventListener("click",()=>dialog.close());
    $('confirm-location').addEventListener("click",()=>{
      if(!location||!validSelection())return;
      confirmed=true;gate.hidden=false;gate.disabled=false;persist();
      $('dinner-count').focus({preventScroll:true});gate.scrollIntoView({behavior:"instant",block:"start"});
    });
    return {
      values(){if(!confirmed||!location||!validSelection())throw new Error("Kontrollera postnumret och välj butiker under Mina val före beräkning.");return {postal_code:location.area_postal_code,allowed_store_ids:selected.slice()};},
      restore(request){
        if(confirmed&&location?.area_postal_code===request.postal_code&&JSON.stringify(selected.slice().sort())===JSON.stringify((request.allowed_store_ids||[]).slice().sort()))return;
        restored=request;hideMeals();
      },
    };
  }};
})();

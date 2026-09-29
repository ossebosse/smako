"""Build audit tables only from retained evidence; no network or price writes."""
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
R=Path(__file__).parent

def read(n):return json.loads((R/n).read_bytes())
def dump(n,d):(R/n).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")
def local(v):return datetime.fromisoformat(v.replace("Z","+00:00")).astimezone(ZoneInfo("Europe/Stockholm")).strftime("%d/%m %H:%M:%S") if v else "ej hämtat"
def esc(v):return str(v).replace("|","/").replace("\n"," ")
def table(headers,rows):return "| "+" | ".join(headers)+" |\n| "+" | ".join(["---"]*len(headers))+" |\n"+"".join("| "+" | ".join(esc(v) for v in row)+" |\n" for row in rows)
OWN={(x["chain"],x["store_external_id"]):x for x in read("own-readonly.json")["own_active_summary"]}
PIPE=read("pipeline-readonly.json")
PU={(s["store"]["chain"],s["store"]["source_store_id"]):s for s in PIPE["stores"]}
comparisons={(x["chain"],x["store"],x["source_id"]):x for x in PIPE["sample_comparisons"]}
base={"willys":"OWN aktiverad onlinebutik; full källa finns för 2176/2354","hemkop":"OWN online 4224; 4123 gammal; övriga ej aktiva","coop":"OWN Online Syd 730400 separat; inget fysiskt baspris belagt","citygross":"Befintlig Loop54 onlineconnector, ej aktiv Lundkälla","lidl":"Ingen full butikskatalog; endast regionalt publiceringsflöde"}
offer={"willys":"potentialPromotions i katalog/detalj","hemkop":"potentialPromotions i katalog/detalj; separat campaigns-route dokumenterad","coop":"renderad offentlig butikssida; aria/text","citygross":"prices.promotions i Loop54","lidl":"q/api/search, region 1, ej verifierat per butik"}
source={"willys":"https://www.willys.se/butik","hemkop":"https://www.hemkop.se/butik-sok","coop":"https://www.coop.se/butiker-erbjudanden/","citygross":"https://www.citygross.se/butiker","lidl":"https://www.lidl.se/s/sv-SE/butiker/"}
rows=[];store_data=[];national=[]
for chain in base:
    audit=read(chain+"-audit-expanded.json" if chain in {"hemkop","willys"} else chain+"-audit.json")
    for row in audit["stores"]:
        st=row["store"];sid=st["external_id"];key=(chain,sid)
        if sid=="public-default-region":
            if not national:national.append(row)
            continue
        own=OWN.get(key);pu=PU.get(key);fields=st["source_fields"]
        url=("https://www.coop.se"+fields["store_page_path"] if chain=="coop" else fields.get("store_url") or fields.get("official_store_url") or fields.get("canonical_url") or (("https://www.citygross.se"+fields["store_page_url"]) if chain=="citygross" and fields.get("store_page_url") else source[chain]))
        parsed_file=row.get("parsed_file")
        if chain=="citygross" and row["offer_check"]=="live_bounded":parsed_file="citygross-3211-expanded-sample-parsed.json"
        parsed=read(parsed_file) if parsed_file else None
        count=len(parsed["products"]) if parsed else None
        offers_count=sum(len(p["offers"]) for p in parsed["products"]) if parsed else None
        detail=R/(chain+"-"+sid+"-details-parsed.json")
        if detail.exists():
            ds=json.loads(detail.read_bytes())["products"];details=len(ds);offers_count=(offers_count or 0)+sum(len(p["offers"]) for p in ds)
            observed=max(p["fetched_at"] for p in ds)
        else:details=0;observed=row.get("observed_at")
        rawfile=("citygross-3211-expanded-sample.json" if chain=="citygross" and parsed else row.get("raw_file"))
        if rawfile and not details:
            observed=max(d["fetched_at"] for d in read(rawfile)["documents"])
        if chain=="coop":channel="fysisk butik, erbjudanden";block="Datum/produktvariant saknas i sparade kort; ordinarie prisroll obelagd"
        elif chain=="lidl":channel="fysisk butik identifierad; regional prisrelation obelagd";block="Nationellt/regionalt flöde får inte tilldelas denna butik"
        else:channel="butikens onlinekontext" if st.get("online_shopping") else "fysisk butik; online ej belagd";block="Onlinepris är inte verifierat hyllpris"
        if sid=="4123" and chain=="hemkop":block+="; fullcrawlens kända paginationfel ej återförsökt; OWN från 8/9"
        if chain=="hemkop" and details:block+="; applied=true men offerStatus=Vilande behöver utredas"
        if chain=="citygross":block+="; en av fyra kampanjer har oklar förpackning 2DL/1L"
        current={"chain":chain,"requested_municipality":row["discovery_area"],"municipality_status":row["municipality"]["status"],"municipality_reason":row["municipality"]["reason"],"store":st,"official_source":url,"channel":channel,"base_source":base[chain],"offer_source":offer[chain],"last_offer_fetch":observed,"check":row["offer_check"],"parsed_catalog_rows":count,"detail_rows":details,"parsed_source_offers":offers_count,"checkout_qualified_count":None,"validation":"existing parser only; no snapshot/checkout acceptance","own_active_products":own["products"] if own else 0,"own_active_offers":own["offers"] if own else 0,"own_oldest_observation":own["oldest"] if own else None,"pu_products":pu["products"] if pu else 0,"pu_products_with_offers":pu["products_with_offers"] if pu else 0,"stored_matched_candidates":pu["matched_candidate_products"] if pu else 0,"current_recipe_purchase_acceptance":"not available from stale active universe; not revalidated","blockers":block,"image_only_gap":"Not measured: no inference that every missing offer exists only in images","runtime":"Windows Python 3.12 live; server price feed not rerun in this stage"}
        store_data.append(current)
        rows.append([row["discovery_area"]+"?",st["name"]+" · "+sid+(" (fysisk site "+str(fields["site_id"])+")" if chain=="citygross" else ""),st.get("address"),"okänd",f"[källa]({url}); {channel}",base[chain]+" / "+offer[chain],local(observed),f"{count}+{details} rader / {offers_count} avtal" if parsed else "ej prisprovat",f"{current['own_active_products']} / {current['own_active_offers']}",f"{current['pu_products']} / {current['pu_products_with_offers']}",str(current["stored_matched_candidates"])+" / ej aktuell acceptans",block])
dump("store-matrix.json",{"stores":store_data,"separate_regional_feed":national,"municipality_complete":False,"physical_candidates":len(store_data)})
intro="""# Kedje- och butiksvis kontroll

Kontroll 20 september 2026, Europe/Stockholm. Tider nedan är lokal tid. Nya nätkontroller kördes på Windows med befintliga connectors och vanliga publika sessioner. Serverns OWN och aktiva PriceUniverse lästes endast. Ingen import, promotion, aktivering, bildmodell eller prisuppdatering utfördes.

Kommun med **?** betyder upptäcktskandidat, inte verifierad kommuntillhörighet. De andra kedjornas adresskällor saknar explicit kommunfält; koordinatkontroll mot Lantmäteriet stoppades av HTTP 401. Butikerna ligger kvar. Full kommuninventering är därför inte verifierad. Hemköp Elinegård återfinns vid kompletterande offlineanalys av den färska nationella listan; adressorten Limhamn får inte försvinna genom Malmö-filtret. City Gross Stora Bernstorp är en Malmö-namnträff med adressort Arlöv, inte automatiskt en Malmökommunbutik.

OWN-kolumn: produkter / promotions i aktivt **källsnapshot**, inklusive sådana som är för gamla. PU-kolumn: produkter / produkter med avtal i det oförändrade aktiva universumet från 16/9. Källsnapshot och aktivt PU är olika steg. Receptkolumnen visar lagrade ingrediensmatchade kandidater, inte nya närings-/checkoutgodkännanden. Den aktiva basen är över 48 timmar gammal; ingen aktuell köpacceptans hävdas. Antal hämtade/parsade avtal är inte antal godkända köp.

Alla värden för icke provade butiker är uttryckligen okända där läsning behövs; `ej prisprovat` är inte ett tomt erbjudandeflöde. Noll i OWN/PU betyder ingen aktiv exakt butikskontext i den lästa databasen/manifestet. Regionala Coop- och Lidl-priser har inte kopierats till fysiska butiker.

"""
(R/"STORES.md").write_text(intro+table(["Sökt kommun","Butik / ID","Adress","Kommunstatus","Officiell källa / kanal","Bas / erbjudandekälla","Senaste erbjudandeprov","Parsade rader / avtal","OWN produkter / avtal","Aktivt PU produkter / med avtal","Receptkandidater / nu","Lucka"],rows)+"\nBas- och erbjudandekälla, observationsintervall, runtime och osäkerhet per butik finns även i store-matrix.json. Bildberoende differens har inte inventerats och anges aldrig som noll.\n",encoding="utf-8")
# ICA's query-result denominator remains distinct from municipal proof.
geo=[];geodata=[]
for code in ["1281","1280"]:
    r=read("verified-"+code+"/coverage.json");counts=r["area_counts"];loc=sum(s["locality"].casefold()==r["area"]["city"].casefold() for s in r["stores"])
    geo.append(f"## {r['area']['city']} · {code}\n\nAdressort {loc}; kommun inkluderad {counts.get('inside',0)}, exkluderad {counts.get('outside',0)}, okänd {counts.get('unknown',0)}. Söklistan {r['inventory']['discovered']}/{r['inventory']['source_declared']}; full kommuninventering **ej verifierad**.\n\n")
    gr=[]
    for s in r["stores"]:
        key=("ica",s["ica_account_id"]);own=OWN.get(key);pu=PU.get(key);ev=s["geographic_evidence"].get("evidence") or {}
        gr.append([s['name']+' · '+s['ica_account_id'],s['address']+', '+s['locality'],s['area_membership'],s['area_reason'],f"[butik]({s['official_store_url']})",local(s['discovered_at']),ev.get('municipality_name','saknas'),own['offers'] if own else 0,pu['products'] if pu else 0])
    geo.append(table(["Butik / ICA-ID","Adress / adressort","Kommunstatus","Motivering","Källa","Inventerad","Kommun i källadress","Aktivt OWN avtal","Aktivt PU produkter"],gr));geodata.append(r)
(R/"MUNICIPALITIES.md").write_text("# Kommunläge och adressort, separat\n\nSCB:s kodregister 2026: Lund 1281, Malmö 1280. Kommunbevis kommer från respektive officiell adresspost och sparas med butik, adress, fältväg, URL, hash och faktisk observationstid. Samma kod kör båda områdena. Postnummer, användarval och antal inköpsställen är inte kommungränser.\n\nFullstora ICA-adresskort kompletterar fyra Malmöbutiker i Limhamn, Oxie och Bunkeflostrand. Tio exakta Lund-ID/adressmatchningar får återanvända Lunds kommunbevis som **utanför Malmö**, med ursprunglig observationstid. 35 andra map-poster är fortfarande okända; även Toftanäs. En URL eller adressort ensam används inte som kommunbevis.\n\nSCB:s förenklade kartor används inte för positionstest eftersom myndigheten avråder från analysbruk. Lantmäteriets API-metadata är öppna (200), men kommungeometrin krävde behörighet (401, ett försök). För nästa geografiska steg behövs konfigurerad åtkomst till kommungeometrin eller annan verifierbar administrativ adresskälla. Ingen ny behörighet skapades.\n\n"+"\n".join(geo),encoding="utf-8")
# Actual advertised sample, explicitly retaining unresolved applicability.
examples=[]
for chain in ["willys","hemkop","coop","citygross","lidl"]:
    audited=[s for s in store_data if s['chain']==chain and s['check']=='live_bounded']
    if chain=='lidl':audited=[{'store':{'external_id':'public-default-region','name':'Lidl publicerad standardregion 1'},'official_source':'https://www.lidl.se/q/search'}]
    for ar in audited:
        sid=ar['store']['external_id'];stem=chain+'-'+sid
        file=stem+'-details-parsed.json' if chain in {'willys','hemkop'} else stem+('-expanded-sample-parsed.json' if chain=='citygross' else '-sample-parsed.json')
        products=read(file)['products'];eligible=[p for p in products if p['offers'] and any((not o['valid_from'] or o['valid_from']<='2026-09-20') and (not o['valid_to'] or o['valid_to']>='2026-09-20') for o in p['offers'])]
        if chain=='citygross':eligible=[p for p in eligible if p['name']!='Björnbär Hallon']
        if chain=='lidl':eligible=[p for p in eligible if p['name'] in ['Färska skinkgrytbitar','Stenugnspizza salami','Kex med choklad']]
        if chain=='coop':eligible=[p for p in eligible if p['name'] in ['Rågbitar/Chiabröd','Pan Pizza','Bacon']]
        for p in eligible[:3]:
            o=p['offers'][0];quantity=o.get('quantity') or 1
            price=(str(quantity)+' för ' if quantity>1 else '')+str(o['price']).replace('.',',')+' kr'+(' / kg' if p.get('sale_unit')=='kg' else '')
            condition=('Medlem' if o['member_only'] else 'Publikt')+'; '+('max '+str(o['max_quantity'])+(' gruppköp' if quantity>1 else ' st') if o['max_quantity'] else 'köpgräns ej angiven')+'; pant ej angiven'
            if chain=='willys':condition+='; välj och blanda endast uttryckligen listade produkt-ID:n'
            if chain=='hemkop':condition+='; källa applied=true / offerStatus=Vilande: tillämplighet behöver verifieras'
            period=(o['valid_from'] or 'start ej angiven')+' – '+(o['valid_to'] or 'slut ej bevarat')
            source_url=ar['official_source']
            if chain in {'willys','hemkop'}:
                source_url='https://www.'+chain+'.se/erbjudanden'
                ds=read(stem+'-details.json')['documents'];rawdoc=next(d for d in ds if d['kind']=='product_detail' and json.loads(d['payload']).get('code')==p['external_product_id']);rawurl=rawdoc['url']
            elif chain=='lidl':source_url='https://www.lidl.se'+p['source_fields']['canonical_path'];rawurl=source_url;condition+='; ej belagd giltighet för enskild Lund-/Malmöbutik'
            elif chain=='citygross':
                ds=read(stem+'-expanded-sample.json')['documents']; rr=next(v for v in json.loads(ds[0]['payload'])['items'] if v['id']==p['external_product_id']);source_url='https://www.citygross.se'+rr['url'];rawurl=source_url
            else:rawurl=source_url;period='Visad 20/9; annonsens egna datum ej bevarade. Vecka 38 och 39 finns på sidan, får inte ärvas utan koppling.'
            cp=comparisons.get((chain,sid,p['external_product_id']),{})
            ex={'chain':chain,'store_id':sid,'store_name':ar['store']['name'],'title':p['name'],'brand':p['brand'],'package':p['package_text'],'source_product_id':p['external_product_id'],'price':price,'conditions':condition,'validity':period,'observed_at':p['fetched_at'],'official_source':source_url,'exact_transport_url':rawurl,'own_active':bool(cp.get('own')),'active_pu_product':bool(cp.get('active_pu')),'current_checkout_accepted':False,'source_product':p}
            examples.append(ex)
dump('examples.json',examples)
text='# Verkligt erbjudandeurval och kvarvarande osäkerhet\n\n20 september 2026, Europe/Stockholm. Nya avgränsade anrop, inte historisk replay. Onlineexemplen kräver att rätt butik väljs på webbplatsen. Samma produkt-ID hämtades separat för respektive butik; priser kopierades inte mellan butiker. Råanropens URL och sparat butiksreadback finns i examples.json.\n\nPris och förpackning återges från källan. Saknad pant/köpgräns är **inte** ett godkännande av noll pant eller obegränsade köp. Hemköps statuskonflikt och Coops saknade annonsdatum gör att dessa inte kallas datumvaliderade köp, trots att de visas i det färska publika svaret. Lidl-exemplen gäller det publicerade regionflödet; ingen fysisk butik är verifierad.\n\n'
for chain,sid in dict.fromkeys((e['chain'],e['store_id']) for e in examples):
    es=[e for e in examples if e['chain']==chain and e['store_id']==sid]
    text+='## '+es[0]['store_name']+' · '+sid+'\n\n'+table(['Produkt / förpackning / ID','Köppris','Villkor','Giltighet','Kontrollerat','Officiell källa','OWN / aktivt PU'],[[e['title']+'; '+str(e['brand'])+'; '+str(e['package'])+'; '+str(e['source_product_id'] or 'saknat käll-ID'),e['price'],e['conditions'],e['validity'],local(e['observed_at']),f"[källa]({e['official_source']})",('ja' if e['own_active'] else 'nej')+' / '+('ja, äldre version' if e['active_pu_product'] else 'nej')] for e in es])+'\n'
text+='\nInga av dessa nya observationer importerades. Lagrad produkt i aktivt PU betyder inte samma prisobservation: PU är fortfarande från 16/9. pipeline-readonly.json innehåller exakta gamla/nya belopp, villkor och observationer för jämförelsen. Inte ett komplett sortiment eller en billigast-jämförelse.\n'
(R/'EXAMPLES.md').write_text(text,encoding='utf-8')
print('Physical candidate rows',len(store_data),'ICA discovery rows',sum(len(x['stores']) for x in geodata),'sample offers',len(examples))

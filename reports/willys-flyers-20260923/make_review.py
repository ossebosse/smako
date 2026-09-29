"""Complete manual text-position review; no image reads and no product-count limit."""
import hashlib,json,re
from pathlib import Path
import pymupdf
from grocery_data.app.domain import RawBatch
R=Path(__file__).parent
# index: price, package amount/unit, member, required packages, household groups,
# exact named products (one or more explicitly enumerated variants), brand, price x/y.
H={
3:(24.9,900,'g',True,1,3,['Pågenlimpan'],'Pågen',147,649),
4:(9.9,1,'st',False,1,3,['Gurka ej ekologisk'],'',477,626),
5:(24.9,900,'g',False,1,None,['Vetekaka 24-pack','Rågkaka 30-pack'],'Garant',359,328),
6:(35,400,'g',False,2,None,['Kycklinggrillkorv'],'Eldorado',550,700),
7:(44.9,600,'g',False,1,None,['Smör & raps Normalsaltat','Smör & raps Extrasaltat'],'Garant',401,100),
8:(40,100,'g',False,2,None,['Jamon Serrano skivad 11 månader'],'Garant',577,555),
10:(24.9,200,'g',True,1,3,['Brie'],'Garant',399,543),
11:(19.9,560,'g',True,1,3,['Grekiskt lantbröd'],'Dafgårds',498,309),
12:(35,480,'g',True,2,3,['Pannkakor'],'Garant',138,206),
13:(99.9,900,'g',True,1,3,['Kycklingbröstfilé Sverige'],'Kronfågel',180,471),
15:(12.9,400,'g',True,1,3,['Pizzadeg'],'Monte Castello',146,240),
16:(34.9,1500,'ml',False,1,None,['Glass Vanilj','Glass Kladdkaka'],'SIA Glass',146,396),
17:(29.9,800,'g',False,1,None,['Falukorv'],'Garant',180,679),
19:(25,390,'g',False,2,None,['Ekologiska passerade tomater','Ekologiska krossade tomater'],'Garant Eko',314,376),
23:(79,1,'st',False,3,None,['Knoppljung'],'',559,586),
27:(9.9,100,'g',False,1,None,['Vitlök i kapsel Spanien'],'',262,524),
28:(59.9,1,'st',False,1,None,['Ljungplantering 11 cm'],'',547,350),
30:(9.9,100,'g',False,1,5,['Svamp Enoki Kina'],'',117,367),
31:(9.9,25,'g',False,1,None,['Koriander','Mynta'],'',256,293),
33:(9.9,1,'st',False,1,3,['Gurka ej ekologisk'],'',359,562),
}
W={
3:(69.9,15,'st',True,1,3,['Glass Leo´s Djungelmix 15-pack'],'Triumf Glass',662,803),
5:(9.9,1,'st',False,1,3,['Gurka ej ekologisk'],'',415,808),
7:(99,400,'g',False,2,5,['Vildfångad pinklax 4-pack djupfryst'],'Royal Foods',281,860),
8:(25,400,'g',True,2,3,['Pizzadeg'],'Monte Castello',442,246),
9:(29.9,500,'g',False,1,None,['Riven pizzamix 25%'],'Frischgold',442,451),
10:(12.9,200,'g',False,1,None,['Pizzasallad'],'Garant',656,478),
11:(16.9,1500,'g',False,1,None,['Pizzamjöl'],'Kungsörnen',156,906),
13:(18,250,'g',False,2,None,['Pizzasås'],'Garant',661,610),
14:(39.9,200,'g',True,1,3,['Grana Padano 12 månader'],'Garant',669,192),
15:(40,230,'g',True,2,3,['Pinsa'],'Garant',58,463),
17:(35,125,'g',True,2,3,['Burrata'],'Garant',430,677),
19:(39.9,120,'g',False,1,None,['Tapas de España'],'Garant',352,900),
20:(29.9,170,'g',False,1,None,['Fuet'],'Garant',614,451),
22:(18,24,'g',False,2,None,['Cheese Snack Original','Cheese Snack Tryffel'],'Granarolo',338,146),
23:(29.9,115,'g',False,1,None,['Blåmögelost'],'Saint Agur',639,143),
24:(22.9,200,'g',False,1,None,['Brie'],'Garant',502,145),
25:(39.9,180,'g',False,1,None,['Cambozola'],'Wernersson Ost',54,143),
26:(59.9,500,'ml',True,1,5,['Ekologisk olivolja Italiensk Extra virgin'],'Garant Eko',85,422),
29:(40,100,'g',False,2,3,['Jamón Serrano 11 månader'],'Garant',485,850),
30:(24.9,900,'g',True,1,3,['Pågenlimpan'],'Pågen',267,164),
36:(24.9,350,'g',False,1,None,['Cognacsmedwurst Enrisrökt','Cognacsmedwurst Alspånsrökt'],'Garant',656,729),
37:(19.9,560,'g',True,1,3,['Grekiskt lantbröd'],'Dafgårds',314,850),
38:(22.9,900,'g',False,1,None,['Vetekaka 24-pack','Rågkaka 30-pack'],'Garant',97,905),
40:(41.9,600,'g',False,1,None,['Smör & raps Normalsaltat','Smör & raps Extrasaltat'],'Garant',596,862),
45:(39.5,400,'g',True,1,3,['Gyros Örter/Citron Sverige'],'Garant',431,893),
46:(49.9,420,'g',True,1,3,['Ribs Original Sverige'],'Texas Longhorn',166,858),
48:(99.9,900,'g',True,1,3,['Kycklingbröstfilé Sverige'],'Kronfågel',661,578),
49:(36.9,500,'g',True,1,3,['Fläskfärs Sverige 20%'],'Garant',427,592),
50:(19.9,1,'st',False,1,3,['Papaya Brasilien'],'',339,275),
52:(9.9,200,'g',False,1,3,['Ekologisk ingefära'],'',442,774),
53:(9.9,150,'g',False,1,5,['Svamp Shimej Kina'],'',224,457),
55:(9.9,100,'g',False,1,5,['Svamp Enoki Kina'],'',445,479),
56:(9.9,25,'g',False,1,None,['Koriander','Mynta'],'',208,866),
57:(9.9,1,'st',False,1,3,['Gurka ej ekologisk'],'',565,569),
58:(59.9,1,'st',False,1,None,['Ljungplantering 11 cm'],'',194,550),
62:(79,1,'st',False,3,None,['Knoppljung'],'',160,908),
65:(11.9,300,'ml',False,1,None,['Ekologisk gräddfil 12%'],'Garant Eko',473,129),
66:(23.9,500,'ml',False,1,None,['Crème fraiche 32%'],'Garant',644,417),
70:(28,250,'ml',False,2,None,['Kokosmjölk'],'Santa Maria',390,682),
72:(30,390,'g',True,3,5,['Ekologiska passerade tomater','Ekologiska krossade tomater'],'Garant Eko',202,704),
73:(12.9,300,'ml',False,1,None,['Laktosfri matgrädde 13%'],'Garant',105,880),
74:(35,400,'g',False,2,None,['Kycklinggrillkorv'],'Eldorado',335,104),
76:(39.9,500,'g',False,1,None,['Tärnat bacon'],'Prime Patrol',118,365),
77:(49.9,900,'g',False,1,None,['Varmkorv'],'Lithells',150,113),
78:(18.9,300,'ml',False,1,None,['Laktosfri vispgrädde 40%'],'Garant',320,883),
79:(49.9,400,'g',False,1,None,['Räkor med skal 90/120 djupfrysta'],'Royal Greenland',664,100),
82:(25.6,500,'ml',False,1,None,['Vispgrädde 36%'],'Arla Köket',609,241),
83:(29.9,800,'g',False,1,None,['Falukorv'],'Garant',424,695),
84:(21,750,'g',False,2,None,['Gammaldags idealmakaroner'],'Kungsörnen',433,440),
86:(38.9,450,'g',False,1,None,['Delikatessköttbullar'],'Garant',162,440),
87:(15.9,560,'g',False,1,None,['Ketchup'],'Garant',626,442),
88:(24.9,1000,'g',False,1,None,['Nordiska ärtor djupfrysta'],'Apetit',663,932),
90:(19.9,400,'g',False,1,None,['Jordgubbssylt Squeezy'],'Garant',371,234),
92:(27.9,720,'g',True,1,3,['Pannkakor 12-pack'],'Eldorado',149,227),
93:(14.9,90,'g',False,1,None,['Majskorvar Krispiga Glutenfria'],'Garant',640,524),
98:(49.8,500,'ml',False,1,None,['Munskölj'],'Flux',658,763),
99:(43.9,750,'ml',False,1,None,['Fläckborttagning'],'Vanish',100,772),
101:(49.9,400,'ml',False,1,None,['Micellar Water'],'Nivea',484,779),
105:(35,275,'g',False,2,None,['Salta jordnötter'],'Estrella',549,490),
108:(29.9,285,'g',False,1,None,['Cheez Doodles'],'OLW',577,253),
}
result=[]
for identity,specs in [('2863',H),('2352',W)]:
 pdf=(R/f'live-{identity}.pdf').read_bytes();doc=pymupdf.open(stream=pdf,filetype='pdf')
 ads=json.loads((R/f'ads-{identity}.json').read_bytes())
 # Three Black-face titles on the last Rosengård page are also advertisements.
 if identity=='2352':
  for b in doc[-1].get_text('blocks'):
   if b[4].startswith(('KOLSYRAT VATTEN','CHOKLADKAKA','ALKOHOLFRI ÖL')):
    ads.append({'page':12,'index':len(ads),'title':b[4].splitlines()[0].strip(),'block':b[5]})
 for ad in ads:
  blocks={b[5]:b for b in doc[ad['page']-1].get_text('blocks') if b[6]==0}
  block = next(b for b in blocks.values() if ad['title'].split()[0] in b[4] and (len(ad.get('bbox', [])) == 0 or b[0]-2 <= ad['bbox'][0] <= b[2]+2 and b[1]-2 <= ad['bbox'][1] <= b[3]+2));ad.update(text=block[4],bbox=list(block[:4]),text_sha256=hashlib.sha256(block[4].encode()).hexdigest())
  ad.pop('body',None)
  spec=specs.get(ad['index'])
  if spec:
   price,amount,unit,member,quantity,cap,names,brand,x,y=spec
   priceblock=min(blocks.values(),key=lambda b:abs(b[0]-x)+abs(b[1]-y))
   assert abs(priceblock[0]-x)+abs(priceblock[1]-y)<4,(identity,ad['index'])
   digits=str(round(price*100)); assert digits in re.sub(r'\s','',priceblock[4]),(identity,ad['index'],priceblock[4])
   ad.update(status='qualified',price=str(price),package_quantity=amount,package_unit=unit,member_only=member,
    required_packages=quantity,max_quantity=cap,names=names,brand=brand,
    price_bbox=list(priceblock[:4]),price_text=priceblock[4],valid_from='2026-09-21',
    valid_to='2026-09-23' if identity=='2352' and ad['index']==3 else '2026-09-27',deposit_status='not_applicable')
   if ad['index'] in ([33] if identity=='2863' else [57]): ad.update(status='duplicate',duplicate_of=4 if identity=='2863' else 5)
  else:
   text=ad['text'].lower()
   reason=('deposit_amount_and_variant_unverified' if '+pant' in text or ad['title']=='ALKOHOLFRI ÖL' else
    'variable_weight_no_fixed_purchase_package' if 'per kg' in text or 'ca ' in text or ad['title'] in ['ROYAL GALA, GRANNY SMITH','HEL SPETSKÅL','HEL BUTTERNUT PUMPA','PURJOLÖK'] else
    'net_and_drained_quantity_not_explicitly_labelled' if ad['index'] in ([32,80] if identity=='2352' else []) else
    'package_quantity_not_stated' if ad['title'] in ['SALLADSLÖK I KNIPPE','VITLÖK I KAPSEL'] else
    'unnamed_variants_or_package_range')
   ad.update(status='quarantine',reason=reason)
 listing=RawBatch.model_validate_json((R/f'live-{identity}.json').read_bytes()).documents[0].json_payload()
 result.append({'publication_url':listing['publication_url'],'viewer_text_sha256':[hashlib.sha256(t.encode()).hexdigest() for t in listing['pageTexts']], 'pdf_sha256':hashlib.sha256(pdf).hexdigest(),'review_method':'complete_document_text_positions_no_images',
  'pages':len(doc),'ads':ads,'valid_from':'2026-09-21','valid_to':'2026-09-27'})
 print(identity,len(ads),sum(a['status']=='qualified' for a in ads),sum(len(a['names']) for a in ads if a['status']=='qualified'))
path=Path('grocery_data/app/connectors/willys/fixtures/flyer_review_20260923.json');path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')

import os
from pathlib import Path

WORK = Path(os.environ.get("SMAKO_RECIPE_WORK", ".local/recipe-packs"))
import json

from builder import I, pack, recipe
from builder import keys as K

R=[]
def S(t,items,m,d): return (t,K(*items),m,d)
salt=lambda c,q=2: I("salt","as_sold",q,c,"flavour","Salt")
olja=lambda c,q=15: I("rapsolja","as_sold",q,c,"cooking","Rapsolja")
lok=lambda c,q=80: I("gul lök","raw_edible",q,c,"vegetable","Gul lök, rå")
vit=lambda c,q=6: I("vitlök","raw_edible",q,c,"flavour","Vitlök, rå")
ris=lambda c,q=140: I("ris","dry",q,c,"side","Långkornigt vitt ris, torrt",req=["pack:rice","white_rice"])
pasta=lambda c,q=160: I("pasta","dry",q,c,"side","Pasta, torr",req=["pack:pasta"])
yog=lambda c,q=80: I("yoghurt naturell","as_sold",q,c,"sauce","Grekisk yoghurt, naturell")
def kyck(c,q=300): return I("kyckling","raw_edible",q,c,"primary","Kycklinglårfilé, rå",req=["pack:chicken_thigh"])

# INDISKT 1
a=[kyck("c1"),lok("c1"),vit("c1"),I("ingefära","raw_edible",10,"c1","flavour","Ingefära, färsk"),
   I("gurkmeja","dry",1,"c1","flavour","Malen gurkmeja"),I("spiskummin","dry",1,"c1","flavour","Malen spiskummin"),
   I("malen koriander","dry",1,"c1","flavour","Malen koriander"),I("kokosmjölk","as_sold",200,"c1","sauce","Kokosmjölk",unit="ml"),
   I("tomatpuré","as_sold",20,"c1","sauce","Tomatpuré"),I("spenat","as_sold",100,"c1","vegetable","Fryst hackad spenat"),
   olja("c1",10),salt("c1")]
y=yog("c2",60); r=ris("c3")
R.append(recipe(base_id="smako-indian-chicken-korma-spinach", name="Kycklingkorma med kokos, spenat och ris", servings=2, meal_type="dinner",
  cuisine="indian", family="curry", primary="kyckling", method="pot", side="ris", flavor=["kokos","koriander","ingefära"],
  equipment=["Gryta","Kastrull"], vegetarian=False,
  components=[("c1","Korma",a),("c2","Topping",[y]),("c3","Ris",[r])],
  steps=[S("Koka riset enligt förpackningen.",[r],18,[]),
         S("Hacka lök, vitlök och ingefära. Skär kycklingen i bitar.",[a[0],a[1],a[2],a[3]],8,[]),
         S("Fräs lök, vitlök och ingefära i oljan 3 minuter. Rör ner gurkmeja, spiskummin, koriander och tomatpuré och fräs 1 minut.",[a[1],a[2],a[3],a[4],a[5],a[6],a[8],a[10]],4,["s2"]),
         S("Tillsätt kycklingen och bryn lätt. Häll i kokosmjölken och spenaten, salta och sjud 12 minuter tills kycklingen når minst 74 °C.",[a[0],a[7],a[9],a[11]],14,["s3"]),
         S("Servera kormat med ris och en klick yoghurt.",[r,y,a[0]],1,["s1","s4"])],
  active=25, total=35))

# INDISKT 2
b=[I("potatis","raw_edible",300,"c1","vegetable","Potatis, rå"),I("blomkål","as_sold",250,"c1","vegetable","Fryst blomkål",req=["frozen","pack:cauliflower","plain"]),
   I("kikärtor","cooked_drained",200,"c1","primary","Kikärtor, kokta och avrunna",req=["pack:chickpeas"]),lok("c1"),vit("c1"),
   I("ingefära","raw_edible",10,"c1","flavour","Ingefära, färsk"),I("gurkmeja","dry",1,"c1","flavour","Malen gurkmeja"),
   I("spiskummin","dry",1,"c1","flavour","Malen spiskummin"),I("krossade tomater","as_sold",200,"c1","sauce","Krossade tomater"),olja("c1"),salt("c1")]
rr=ris("c2"); ci=I("citronjuice","as_sold",10,"c2","flavour","Citronjuice"); pe=I("persilja","raw_edible",6,"c2","flavour","Persilja, färsk eller fryst")
R.append(recipe(base_id="smako-indian-aloo-gobi-chickpeas", name="Aloo gobi med kikärtor och citronris", servings=2, meal_type="dinner",
  cuisine="indian", family="curry", primary="kikärtor", method="pan", side="ris", flavor=["gurkmeja","spiskummin","ingefära"],
  equipment=["Stor stekpanna med lock","Kastrull"], vegetarian=True,
  components=[("c1","Aloo gobi",b),("c2","Citronris",[rr,ci,pe])],
  steps=[S("Koka riset enligt förpackningen.",[rr],18,[]),
         S("Skala och tärna potatisen. Hacka lök, vitlök och ingefära.",[b[0],b[3],b[4],b[5]],8,[]),
         S("Fräs lök, vitlök, ingefära, gurkmeja och spiskummin i oljan 2 minuter. Tillsätt potatisen och stek 5 minuter.",[b[0],b[3],b[4],b[5],b[6],b[7],b[9]],7,["s2"]),
         S("Tillsätt blomkål, kikärtor, krossade tomater, salt och 1 dl vatten. Sjud under lock cirka 15 minuter tills potatisen är mjuk.",[b[1],b[2],b[8],b[10]],15,["s3"]),
         S("Vänd riset med citronjuice och hackad persilja och servera med grytan.",[rr,ci,pe],2,["s1","s4"])],
  active=20, total=40))

# THAI 1
c=[kyck("c1"),I("jordnötssmör","as_sold",30,"c1","sauce","Jordnötssmör, naturellt"),I("kokosmjölk","as_sold",200,"c1","sauce","Kokosmjölk",unit="ml"),
   I("sojasås","as_sold",20,"c1","flavour","Japansk sojasås"),I("citronjuice","as_sold",10,"c1","flavour","Citronjuice"),vit("c1"),
   I("ingefära","raw_edible",10,"c1","flavour","Ingefära, färsk"),lok("c1",60),I("vitkål","raw_edible",200,"c1","vegetable","Vitkål, rå eller strimlad"),
   I("morot","raw_edible",100,"c1","vegetable","Morot, rå"),olja("c1",10),I("strösocker","dry",5,"c1","flavour","Strösocker")]
r2=ris("c2"); jn=I("jordnötter","as_sold",15,"c3","flavour","Rostade jordnötter")
R.append(recipe(base_id="smako-thai-peanut-chicken-cabbage", name="Jordnötsgryta med kyckling, vitkål och ris", servings=2, meal_type="dinner",
  cuisine="thai", family="gryta", primary="kyckling", method="pan", side="ris", flavor=["jordnöt","kokos","ingefära"],
  equipment=["Wokpanna eller stor stekpanna","Kastrull"], vegetarian=False,
  components=[("c1","Gryta",c),("c2","Ris",[r2]),("c3","Topping",[jn])],
  steps=[S("Koka riset enligt förpackningen.",[r2],18,[]),
         S("Strimla kål och morot, hacka lök, vitlök och ingefära och skär kycklingen i strimlor.",[c[0],c[5],c[6],c[7],c[8],c[9]],8,[]),
         S("Stek kycklingen i oljan tills den fått färg. Tillsätt lök, vitlök, ingefära, kål och morot och woka 4 minuter.",[c[0],c[10],c[5],c[6],c[7],c[8],c[9]],8,["s2"]),
         S("Rör ner jordnötssmör, kokosmjölk, sojasås och socker och sjud 6 minuter tills kycklingen når minst 74 °C. Smaka av med citronjuice.",[c[1],c[2],c[3],c[11],c[4]],6,["s3"]),
         S("Servera med ris och toppa med hackade jordnötter.",[r2,jn,c[0]],1,["s1","s4"])],
  active=25, total=32))

# THAI 2
d=[I("ris","dry",140,"c1","side","Långkornigt vitt ris, torrt",req=["pack:rice","white_rice"]),I("tofu","as_sold",250,"c1","primary","Tofu, naturell fast"),
   I("ärtor","as_sold",100,"c1","vegetable","Frysta gröna ärtor"),I("morot","raw_edible",100,"c1","vegetable","Morot, rå"),lok("c1",60),vit("c1"),
   I("ingefära","raw_edible",8,"c1","flavour","Ingefära, färsk"),I("sojasås","as_sold",25,"c1","flavour","Japansk sojasås"),olja("c1"),
   I("strösocker","dry",3,"c1","flavour","Strösocker"),I("vitkål","raw_edible",100,"c1","vegetable","Vitkål, rå eller strimlad"),
   I("sesamfrön","as_sold",8,"c1","flavour","Sesamfrön")]
R.append(recipe(base_id="smako-thai-tofu-fried-rice", name="Stekt ris med tofu, ärtor, kål och sesam", servings=2, meal_type="dinner",
  cuisine="thai", family="stekt ris", primary="tofu", method="pan", side="ris", flavor=["soja","ingefära","sesam"],
  equipment=["Kastrull","Wokpanna eller stor stekpanna"], vegetarian=True,
  components=[("c1","Stekt ris",d)],
  steps=[S("Koka riset enligt förpackningen och låt det ånga av och svalna en stund.",[d[0]],25,[]),
         S("Tärna tofun, riv moroten, strimla kålen och hacka lök, vitlök och ingefära.",[d[1],d[3],d[10],d[4],d[5],d[6]],8,[]),
         S("Stek tofun i hälften av oljan tills den är gyllene. Lägg upp.",[d[1],d[8]],7,["s2"]),
         S("Fräs lök, vitlök, ingefära, morot och kål i resten av oljan 3 minuter. Tillsätt ärtorna.",[d[4],d[5],d[6],d[3],d[10],d[2],d[8]],4,["s3"]),
         S("Vänd ner riset, tofun, sojasås och socker och stek på hög värme 3 minuter. Toppa med sesamfrön.",[d[0],d[1],d[7],d[9],d[11]],4,["s1","s4"])],
  active=25, total=40))

# MEXIKANSKT 1
e=[I("svarta bönor","cooked_drained",250,"c1","primary","Svarta bönor, kokta och avrunna",req=["pack:black_beans"]),I("krossade tomater","as_sold",400,"c1","sauce","Krossade tomater"),
   lok("c1"),vit("c1"),I("morot","raw_edible",200,"c1","vegetable","Morot, rå"),I("majs","as_sold",150,"c1","vegetable","Majs, fryst naturell",req=["frozen","plain"]),
   I("spiskummin","dry",2,"c1","flavour","Malen spiskummin"),I("paprikapulver","dry",2,"c1","flavour","Paprikapulver, milt"),
   I("rökt paprikapulver","dry",1,"c1","flavour","Rökt paprikapulver"),olja("c1",10),salt("c1")]
y2=yog("c2",80); r3=ris("c3",120)
R.append(recipe(base_id="smako-mexican-black-bean-carrot-chili", name="Chili sin carne med svarta bönor, morot och majs", servings=2, meal_type="dinner",
  cuisine="mexican", family="chili", primary="svarta bönor", method="pot", side="ris", flavor=["spiskummin","rökt paprika","tomat"],
  equipment=["Gryta","Kastrull"], vegetarian=True,
  components=[("c1","Chili",e),("c2","Topping",[y2]),("c3","Ris",[r3])],
  steps=[S("Koka riset enligt förpackningen.",[r3],18,[]),
         S("Hacka lök och vitlök och tärna moroten.",[e[2],e[3],e[4]],6,[]),
         S("Fräs lök, vitlök och morot i oljan 4 minuter. Rör ner spiskummin, paprikapulver och rökt paprikapulver.",[e[2],e[3],e[4],e[9],e[6],e[7],e[8]],5,["s2"]),
         S("Tillsätt krossade tomater, bönor, majs, salt och 1 dl vatten och sjud 15 minuter.",[e[1],e[0],e[5],e[10]],15,["s3"]),
         S("Servera chilin med ris och yoghurt.",[r3,y2,e[0]],1,["s1","s4"])],
  active=15, total=27))

# MEXIKANSKT 2
f=[kyck("c1"),I("spiskummin","dry",1,"c1","flavour","Malen spiskummin"),I("paprikapulver","dry",2,"c1","flavour","Paprikapulver, milt"),vit("c1",4),olja("c1",10),salt("c1",1)]
g=[I("svarta bönor","cooked_drained",200,"c2","primary","Svarta bönor, kokta och avrunna",req=["pack:black_beans"]),lok("c2",60),olja("c2",5),salt("c2",1)]
h=[I("vitkål","raw_edible",150,"c3","vegetable","Vitkål, rå eller strimlad"),I("citronjuice","as_sold",10,"c3","flavour","Citronjuice"),I("tomat","raw_edible",150,"c3","vegetable","Tomat, rå")]
t=I("tortillas","as_sold",160,"c4","side","Vetetortillor",req=["pack:tortilla"]); y3=yog("c4",80); o3=I("ost","as_sold",40,"c4","flavour","Riven lagrad ost")
R.append(recipe(base_id="smako-mexican-chicken-bean-tacos", name="Kycklingtacos med bönröra, kålsallad och tomat", servings=2, meal_type="dinner",
  cuisine="mexican", family="tacos", primary="kyckling", method="pan", side="tortilla", flavor=["spiskummin","paprika","citron"],
  equipment=["Stekpanna","Liten kastrull","Skål"], vegetarian=False,
  components=[("c1","Kyckling",f),("c2","Bönröra",g),("c3","Kålsallad",h),("c4","Servering",[t,y3,o3])],
  steps=[S("Strimla kålen fint och blanda med citronjuice. Tärna tomaten.",h,6,[]),
         S("Skär kycklingen i strimlor och vänd med spiskummin, paprikapulver, riven vitlök och salt. Stek i oljan 8–10 minuter tills den når minst 74 °C.",f,12,[]),
         S("Fräs hackad lök i oljan, tillsätt bönorna och salt och mosa grovt med lite vatten.",g,6,[]),
         S("Värm tortillorna och fyll med bönröra, kyckling, kålsallad, tomat, ost och yoghurt.",[t,y3,o3,f[0],g[0],h[0]],4,["s1","s2","s3"])],
  active=25, total=28))

# GREKISKT 1
k=[kyck("c1",250),I("ris","dry",80,"c1","side","Långkornigt vitt ris, torrt",req=["pack:rice","white_rice"]),I("morot","raw_edible",120,"c1","vegetable","Morot, rå"),
   lok("c1"),vit("c1",4),I("spenat","as_sold",80,"c1","vegetable","Fryst hackad spenat"),I("oregano","dry",1,"c1","flavour","Torkad oregano"),
   olja("c1",10),salt("c1",3),I("citronjuice","as_sold",20,"c1","flavour","Citronjuice")]
yk=yog("c2",80); di=I("dill","raw_edible",8,"c2","flavour","Dill, färsk eller fryst")
R.append(recipe(base_id="smako-greek-lemon-chicken-rice-soup", name="Grekisk citronsoppa med kyckling, ris, spenat och dill", servings=2, meal_type="dinner",
  cuisine="greek", family="soppa", primary="kyckling", method="pot", side="ris", flavor=["citron","dill","oregano"],
  equipment=["Kastrull","Skål"], vegetarian=False,
  components=[("c1","Soppa",k),("c2","Yoghurtkräm",[yk,di])],
  steps=[S("Hacka lök och vitlök, tärna moroten och skär kycklingen i bitar.",[k[0],k[2],k[3],k[4]],8,[]),
         S("Fräs lök, vitlök och morot i oljan 3 minuter. Tillsätt kyckling, ris, oregano, salt och 8 dl vatten och koka 15 minuter tills riset är mjukt och kycklingen når minst 74 °C.",[k[0],k[1],k[2],k[3],k[4],k[6],k[7],k[8]],18,["s1"]),
         S("Rör ner spenaten och värm 2 minuter. Smaka av med citronjuice.",[k[5],k[9]],3,["s2"]),
         S("Rör ihop yoghurt och hackad dill och servera på soppan.",[yk,di],2,["s3"])],
  active=15, total=31))

# GREKISKT 2
l=[I("linser","dry",150,"c1","primary","Röda linser, torra",req=["pack:red_lentils","red_split"]),I("krossade tomater","as_sold",400,"c1","sauce","Krossade tomater"),
   lok("c1"),vit("c1"),I("morot","raw_edible",100,"c1","vegetable","Morot, rå"),I("oregano","dry",1,"c1","flavour","Torkad oregano"),
   olja("c1",15),salt("c1"),I("citronjuice","as_sold",10,"c1","flavour","Citronjuice")]
fe=I("fetaost","as_sold",80,"c2","flavour","Fetaost, naturell"); pp=I("persilja","raw_edible",8,"c2","flavour","Persilja, färsk eller fryst"); br=I("bröd","as_sold",120,"c2","side","Matbröd")
R.append(recipe(base_id="smako-greek-lentil-tomato-stew-feta", name="Grekisk linsgryta med tomat, feta, persilja och bröd", servings=2, meal_type="dinner",
  cuisine="greek", family="gryta", primary="linser", method="pot", side="bröd", flavor=["oregano","tomat","citron"],
  equipment=["Gryta"], vegetarian=True,
  components=[("c1","Linsgryta",l),("c2","Servering",[fe,pp,br])],
  steps=[S("Hacka lök och vitlök och tärna moroten. Skölj linserna.",[l[0],l[2],l[3],l[4]],6,[]),
         S("Fräs lök, vitlök och morot i oljan 4 minuter med oregano.",[l[2],l[3],l[4],l[5],l[6]],4,["s1"]),
         S("Tillsätt linser, krossade tomater, salt och 5 dl vatten. Sjud 20 minuter tills linserna är mjuka. Smaka av med citronjuice.",[l[0],l[1],l[7],l[8]],20,["s2"]),
         S("Toppa med smulad feta och hackad persilja och servera med bröd.",[fe,pp,br],2,["s3"])],
  active=12, total=32))

# ITALIENSKT 1
m=[kyck("c1"),I("champinjoner","raw_edible",150,"c1","vegetable","Champinjoner, färska"),lok("c1"),vit("c1"),
   I("paprika","raw_edible",150,"c1","vegetable","Paprika, färsk",req=["pack:pepper"]),I("krossade tomater","as_sold",400,"c1","sauce","Krossade tomater"),
   I("tomatpuré","as_sold",20,"c1","sauce","Tomatpuré"),I("oregano","dry",1,"c1","flavour","Torkad oregano"),olja("c1"),salt("c1")]
p2=pasta("c2"); o2=I("ost","as_sold",30,"c3","flavour","Riven lagrad ost")
R.append(recipe(base_id="smako-italian-chicken-cacciatore", name="Kycklingcacciatore med champinjoner, paprika och pasta", servings=2, meal_type="dinner",
  cuisine="italian", family="gryta", primary="kyckling", method="pan", side="pasta", flavor=["tomat","oregano","svamp"],
  equipment=["Stor stekpanna med lock","Kastrull"], vegetarian=False,
  components=[("c1","Cacciatore",m),("c2","Pasta",[p2]),("c3","Topping",[o2])],
  steps=[S("Skär kycklingen i bitar, skiva champinjoner och paprika och hacka lök och vitlök.",[m[0],m[1],m[4],m[2],m[3]],8,[]),
         S("Bryn kycklingen i oljan. Tillsätt champinjoner, paprika, lök och vitlök och fräs 4 minuter.",[m[0],m[8],m[1],m[4],m[2],m[3]],9,["s1"]),
         S("Rör ner tomatpuré, krossade tomater, oregano och salt och sjud under lock 15 minuter tills kycklingen når minst 74 °C.",[m[6],m[5],m[7],m[9]],15,["s2"]),
         S("Koka pastan enligt förpackningen.",[p2],12,[]),
         S("Servera grytan med pasta och riven ost.",[p2,o2,m[0]],1,["s3","s4"])],
  active=20, total=34))

# ITALIENSKT 2
n=[I("kikärtor","cooked_drained",250,"c1","primary","Kikärtor, kokta och avrunna",req=["pack:chickpeas"]),pasta("c1",140),
   I("krossade tomater","as_sold",200,"c1","sauce","Krossade tomater"),lok("c1"),vit("c1"),I("morot","raw_edible",100,"c1","vegetable","Morot, rå"),
   I("oregano","dry",1,"c1","flavour","Torkad oregano"),olja("c1"),I("spenat","as_sold",80,"c1","vegetable","Fryst hackad spenat"),salt("c1",3),
   I("citronjuice","as_sold",5,"c1","flavour","Citronjuice")]
o4=I("ost","as_sold",40,"c2","flavour","Riven lagrad ost")
R.append(recipe(base_id="smako-italian-pasta-e-ceci", name="Pasta e ceci med tomat, morot, spenat och ost", servings=2, meal_type="dinner",
  cuisine="italian", family="soppa", primary="kikärtor", method="pot", side="pasta", flavor=["tomat","oregano","citron"],
  equipment=["Gryta","Stavmixer"], vegetarian=True,
  components=[("c1","Pasta e ceci",n),("c2","Topping",[o4])],
  steps=[S("Hacka lök och vitlök och tärna moroten.",[n[3],n[4],n[5]],6,[]),
         S("Fräs lök, vitlök, morot och oregano i oljan 4 minuter.",[n[3],n[4],n[5],n[6],n[7]],4,["s1"]),
         S("Tillsätt kikärtorna, krossade tomater, salt och 8 dl vatten. Mixa en tredjedel av grytan grovt för krämighet.",[n[0],n[2],n[9]],6,["s2"]),
         S("Koka pastan direkt i grytan cirka 12 minuter, rör ofta och späd med vatten vid behov. Rör ner spenaten de sista minuterna och smaka av med citronjuice.",[n[1],n[8],n[10]],13,["s3"]),
         S("Servera med riven ost.",[o4],1,["s4"])],
  active=18, total=30))

# SVENSKT 1
q=[I("lax","raw_edible",250,"c1","primary","Laxfilé, rå",req=["pack:salmon"]),I("potatis","raw_edible",300,"c1","vegetable","Potatis, rå"),
   I("morot","raw_edible",100,"c1","vegetable","Morot, rå"),lok("c1"),vit("c1",4),I("crème fraiche","as_sold",100,"c1","sauce","Crème fraiche"),
   I("mjölk","as_sold",200,"c1","sauce","Mjölk",unit="ml"),I("ärtor","as_sold",80,"c1","vegetable","Frysta gröna ärtor"),olja("c1",10),salt("c1",3),
   I("citronjuice","as_sold",10,"c1","flavour","Citronjuice")]
dd=I("dill","raw_edible",8,"c2","flavour","Dill, färsk eller fryst")
R.append(recipe(base_id="smako-swedish-salmon-potato-soup", name="Krämig laxsoppa med potatis, morot och dill", servings=2, meal_type="dinner",
  cuisine="swedish", family="soppa", primary="lax", method="pot", side="potatis", flavor=["dill","citron","grädde"],
  equipment=["Kastrull"], vegetarian=False, fish=True,
  components=[("c1","Soppa",q),("c2","Topping",[dd])],
  steps=[S("Skala och tärna potatis och morot, hacka lök och vitlök och skär laxen i bitar.",[q[0],q[1],q[2],q[3],q[4]],8,[]),
         S("Fräs lök och vitlök i oljan 2 minuter. Tillsätt potatis, morot, salt och 5 dl vatten och koka 12 minuter.",[q[3],q[4],q[8],q[1],q[2],q[9]],14,["s1"]),
         S("Rör ner mjölk och crème fraiche, lägg i laxen och ärtorna och sjud 5 minuter tills laxen precis är genomkokt, minst 63 °C. Smaka av med citronjuice.",[q[6],q[5],q[0],q[7],q[10]],6,["s2"]),
         S("Toppa med hackad dill.",[dd],1,["s3"])],
  active=15, total=29))

# SVENSKT 2
s=[I("nötfärs","raw_edible",400,"c1","primary","Nötfärs, rå"),I("ströbröd","dry",40,"c1","side","Ströbröd"),I("mjölk","as_sold",100,"c1","sauce","Mjölk",unit="ml"),
   lok("c1"),I("senap","as_sold",10,"c1","flavour","Senap"),I("sojasås","as_sold",10,"c1","flavour","Japansk sojasås"),salt("c1",3),
   I("svartpeppar","dry",0.5,"c1","flavour","Malen svartpeppar"),olja("c1",5)]
sa=[I("crème fraiche","as_sold",100,"c2","sauce","Crème fraiche")]
pt=I("potatis","raw_edible",500,"c3","side","Potatis, rå")
gs=[I("gurka","raw_edible",150,"c4","vegetable","Gurka, rå"),I("citronjuice","as_sold",10,"c4","flavour","Citronjuice"),I("dill","raw_edible",6,"c4","flavour","Dill, färsk eller fryst"),I("strösocker","dry",3,"c4","flavour","Strösocker")]
R.append(recipe(base_id="smako-swedish-meatloaf-cream-sauce", name="Köttfärslimpa med gräddsås, kokt potatis och pressgurka", servings=2, meal_type="dinner",
  cuisine="swedish", family="husman", primary="nötfärs", method="oven", side="potatis", flavor=["senap","grädde","dill"],
  equipment=["Ugn","Ugnsform","Kastrull","Skål"], vegetarian=False,
  components=[("c1","Limpa",s),("c2","Sås",sa),("c3","Potatis",[pt]),("c4","Pressgurka",gs)],
  steps=[S("Sätt ugnen på 200 °C. Blanda ströbröd och mjölk och låt svälla 5 minuter. Riv löken.",[s[1],s[2],s[3]],6,[]),
         S("Blanda färsen med ströbrödsblandning, lök, senap, sojasås, salt och peppar. Forma en limpa i en smord form.",[s[0],s[1],s[3],s[4],s[5],s[6],s[7],s[8]],5,["s1"]),
         S("Grädda limpan cirka 35 minuter tills den når minst 72 °C i mitten.",[s[0]],35,["s2"]),
         S("Koka skalad potatis i saltat vatten cirka 20 minuter.",[pt],22,[]),
         S("Skiva gurkan tunt och blanda med citronjuice, socker och hackad dill.",gs,5,[]),
         S("Häll av skyn från formen i en kastrull, vispa ner crème fraiche och 1 dl vatten och koka upp till en sås. Servera limpan skivad med sås, potatis och pressgurka.",[sa[0],s[0],pt],4,["s3","s4","s5"])],
  active=25, total=50))

json.dump(pack("smako-cuisine-dinners-20261017", R), (WORK / "dinners-20261017.json").open("w", encoding="utf-8"), ensure_ascii=False, indent=1)
for x in R:
    print(x["design"]["ingredient_count"], x["design"]["cuisines"][0], x["name"])

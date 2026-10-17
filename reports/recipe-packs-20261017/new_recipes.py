import os
from pathlib import Path

WORK = Path(os.environ.get("SMAKO_RECIPE_WORK", ".local/recipe-packs"))
import json

from builder import I, keys, pack, recipe

R = []
K = lambda *xs: keys(*xs)

# ---------- MIDDAGAR (2 portioner) ----------
fars=I("nötfärs","raw_edible",250,"c1","primary","Nötfärs, rå"); lok=I("gul lök","raw_edible",80,"c1","vegetable","Gul lök, rå")
vit=I("vitlök","raw_edible",6,"c1","flavour","Vitlök, rå"); mor=I("morot","raw_edible",100,"c1","vegetable","Morot, rå")
kro=I("krossade tomater","as_sold",400,"c1","sauce","Krossade tomater"); pur=I("tomatpuré","as_sold",20,"c1","sauce","Tomatpuré")
ore=I("oregano","dry",1,"c1","flavour","Torkad oregano"); olj=I("rapsolja","as_sold",10,"c1","cooking","Rapsolja")
sal=I("salt","as_sold",2,"c1","flavour","Salt"); pep=I("svartpeppar","dry",0.5,"c1","flavour","Malen svartpeppar")
pas=I("pasta","dry",160,"c2","side","Spaghetti eller annan lång pasta, torr",req=["pack:pasta"]); ost=I("ost","as_sold",40,"c3","flavour","Riven lagrad ost")
R.append(recipe(base_id="smako-italian-weekday-meat-sauce", name="Köttfärssås med morot, spaghetti och riven ost", servings=2,
  meal_type="dinner", cuisine="italian", family="köttfärssås", primary="nötfärs", method="pot", side="pasta",
  flavor=["tomat","oregano","morot"], equipment=["Kastrull","Stekpanna","Rivjärn"], vegetarian=False,
  components=[("c1","Köttfärssås",[fars,lok,vit,mor,kro,pur,ore,olj,sal,pep]),("c2","Pasta",[pas]),("c3","Topping",[ost])],
  steps=[("Hacka löken och vitlöken fint och riv moroten grovt.",K(lok,vit,mor),5,[]),
         ("Hetta upp oljan i en stekpanna och bryn färsen i två omgångar så den får färg. Smula sönder den under tiden.",K(fars,olj),8,["s1"]),
         ("Tillsätt lök, vitlök och morot och fräs 3 minuter. Rör ner tomatpuré och oregano.",K(lok,vit,mor,pur,ore),4,["s2"]),
         ("Häll i krossade tomater och 1 dl vatten, smaka av med salt och peppar och låt sjuda under lock cirka 20 minuter. Kontrollera att färsen är genomstekt.",K(kro,sal,pep),20,["s3"]),
         ("Koka pastan enligt förpackningen under tiden som såsen sjuder.",K(pas),12,["s1"]),
         ("Servera såsen över pastan och toppa med riven ost.",K(fars,kro,pas,ost),2,["s4","s5"])],
  active=25, total=40))

ff=I("fläskfärs","raw_edible",250,"c1","primary","Fläskfärs, rå",req=["pack:pork_mince"]); kal=I("vitkål","raw_edible",350,"c1","vegetable","Vitkål, rå eller strimlad")
lok2=I("gul lök","raw_edible",80,"c1","vegetable","Gul lök, rå"); soj=I("sojasås","as_sold",15,"c1","flavour","Japansk sojasås")
soc=I("strösocker","dry",5,"c1","flavour","Strösocker"); olj2=I("rapsolja","as_sold",15,"c1","cooking","Rapsolja")
sal2=I("salt","as_sold",2,"c1","flavour","Salt"); pep2=I("svartpeppar","dry",0.5,"c1","flavour","Malen svartpeppar")
pot=I("potatis","raw_edible",450,"c2","side","Potatis, rå"); cf=I("crème fraiche","as_sold",80,"c3","sauce","Crème fraiche")
sen=I("senap","as_sold",10,"c3","flavour","Senap"); per=I("persilja","raw_edible",8,"c3","flavour","Persilja, färsk eller fryst")
R.append(recipe(base_id="smako-swedish-cabbage-pudding-stew", name="Kålpuddinggryta med fläskfärs, kokt potatis och senapskräm", servings=2,
  meal_type="dinner", cuisine="swedish", family="kålpudding", primary="fläskfärs", method="pan", side="potatis",
  flavor=["kål","soja","senap"], equipment=["Stor stekpanna med lock","Kastrull","Skål"], vegetarian=False,
  components=[("c1","Gryta",[ff,kal,lok2,soj,soc,olj2,sal2,pep2]),("c2","Potatis",[pot]),("c3","Senapskräm",[cf,sen,per])],
  steps=[("Skala potatisen och koka den i lättsaltat vatten cirka 20 minuter tills den är mjuk.",K(pot),22,[]),
         ("Strimla kålen fint om den inte redan är strimlad och hacka löken.",K(kal,lok2),6,[]),
         ("Bryn färsen i hälften av oljan tills den fått färg och är genomstekt. Lägg upp.",K(ff,olj2),8,["s2"]),
         ("Fräs kål och lök i resten av oljan med sockret cirka 8 minuter tills kålen fått lite färg och mjuknat.",K(kal,lok2,soc,olj2),8,["s3"]),
         ("Blanda tillbaka färsen, tillsätt sojasås och 1 dl vatten och låt puttra under lock 5 minuter. Smaka av med salt och peppar.",K(ff,kal,soj,sal2,pep2),6,["s4"]),
         ("Rör ihop crème fraiche, senap och hackad persilja. Servera grytan med potatis och senapskräm.",K(cf,sen,per,pot,ff),3,["s1","s5"])],
  active=30, total=40))

fisk=I("fisk","raw_edible",300,"c1","primary","Torsk- eller sejfilé, rå",req=["pack:cod"]); spe=I("spenat","as_sold",150,"c1","vegetable","Fryst hackad spenat")
cf3=I("crème fraiche","as_sold",120,"c1","sauce","Crème fraiche"); sen3=I("senap","as_sold",10,"c1","flavour","Senap")
cit=I("citronjuice","as_sold",15,"c1","flavour","Citronjuice"); dil=I("dill","raw_edible",8,"c1","flavour","Dill, färsk eller fryst")
ost3=I("ost","as_sold",40,"c1","flavour","Riven lagrad ost")
lok3=I("gul lök","raw_edible",60,"c1","vegetable","Gul lök, rå"); vit3=I("vitlök","raw_edible",4,"c1","flavour","Vitlök, rå"); olj3=I("rapsolja","as_sold",5,"c1","cooking","Rapsolja"); sal3=I("salt","as_sold",2,"c1","flavour","Salt"); pep3=I("svartpeppar","dry",0.5,"c1","flavour","Malen svartpeppar")
pot3=I("potatis","raw_edible",500,"c2","side","Potatis, rå"); mj=I("mjölk","as_sold",100,"c2","side","Mjölk",unit="ml")
R.append(recipe(base_id="smako-swedish-fish-gratin-mash", name="Fiskgratäng med spenat, dill och potatismos", servings=2,
  meal_type="dinner", cuisine="swedish", family="fiskgratäng", primary="fisk", method="oven", side="potatismos",
  flavor=["dill","citron","senap"], equipment=["Ugn","Ugnsform","Kastrull","Potatisstöt"], vegetarian=False, fish=True,
  components=[("c1","Gratäng",[fisk,spe,cf3,sen3,cit,dil,ost3,lok3,vit3,olj3,sal3,pep3]),("c2","Potatismos",[pot3,mj])],
  steps=[("Sätt ugnen på 200 °C. Skala potatisen, dela den och koka i lättsaltat vatten cirka 20 minuter.",K(pot3),22,[]),
         ("Hacka lök och vitlök och fräs dem mjuka i oljan. Tina spenaten, krama ur vätskan och blanda med löken.",K(lok3,vit3,olj3,spe),8,[]),
         ("Blanda crème fraiche, senap, citronjuice, hackad dill, salt och peppar.",K(cf3,sen3,cit,dil,sal3,pep3),3,[]),
         ("Lägg fisken i en smord ugnsform, fördela spenaten över och bred på såsen. Strö över osten.",K(fisk,spe,cf3,ost3),5,["s2","s3"]),
         ("Gratinera mitt i ugnen cirka 20 minuter tills fisken flagnar och når minst 63 °C i mitten.",K(fisk,ost3),20,["s4"]),
         ("Häll av potatisen, värm mjölken och stöt ett slätt mos. Smaka av med salt. Servera med gratängen.",K(pot3,mj),5,["s1","s5"])],
  active=28, total=40))

lin=I("linser","dry",120,"c1","primary","Röda linser, torra"); mor4=I("morot","raw_edible",150,"c1","vegetable","Morot, rå")
pot4=I("potatis","raw_edible",200,"c1","vegetable","Potatis, rå"); lok4=I("gul lök","raw_edible",80,"c1","vegetable","Gul lök, rå")
vit4=I("vitlök","raw_edible",6,"c1","flavour","Vitlök, rå"); kro4=I("krossade tomater","as_sold",200,"c1","sauce","Krossade tomater")
spi4=I("spiskummin","dry",1,"c1","flavour","Malen spiskummin"); pap4=I("paprikapulver","dry",2,"c1","flavour","Paprikapulver, milt")
olj4=I("rapsolja","as_sold",10,"c1","cooking","Rapsolja"); sal4=I("salt","as_sold",3,"c1","flavour","Salt")
cit4=I("citronjuice","as_sold",10,"c1","flavour","Citronjuice"); yog4=I("yoghurt naturell","as_sold",100,"c2","sauce","Grekisk yoghurt, naturell")
per4=I("persilja","raw_edible",8,"c2","flavour","Persilja, färsk eller fryst")
R.append(recipe(base_id="smako-swedish-lentil-root-soup", name="Matig linssoppa med morot, potatis och örtyoghurt", servings=2,
  meal_type="dinner", cuisine="swedish", family="soppa", primary="linser", method="pot", side="potatis",
  flavor=["spiskummin","tomat","citron"], equipment=["Kastrull","Stavmixer","Skål"], vegetarian=True,
  components=[("c1","Soppa",[lin,mor4,pot4,lok4,vit4,kro4,spi4,pap4,olj4,sal4,cit4]),("c2","Örtyoghurt",[yog4,per4])],
  steps=[("Hacka lök och vitlök. Skala och tärna morot och potatis. Skölj linserna.",K(lin,mor4,pot4,lok4,vit4),8,[]),
         ("Fräs lök, vitlök, spiskummin och paprikapulver i oljan 2 minuter.",K(lok4,vit4,spi4,pap4,olj4),3,["s1"]),
         ("Tillsätt linser, morot, potatis, krossade tomater, salt och 7 dl vatten. Koka under lock cirka 20 minuter tills allt är mjukt.",K(lin,mor4,pot4,kro4,sal4),20,["s2"]),
         ("Mixa soppan grovt och smaka av med citronjuice.",K(cit4),3,["s3"]),
         ("Rör ihop yoghurt och hackad persilja och servera ovanpå soppan.",K(yog4,per4),2,["s4"])],
  active=15, total=36))

kyc=I("kyckling","raw_edible",300,"c1","primary","Kycklinglårfilé, rå",req=["pack:chicken_thigh"]); cha=I("champinjoner","raw_edible",200,"c1","vegetable","Champinjoner, färska")
lok5=I("gul lök","raw_edible",80,"c1","vegetable","Gul lök, rå"); vit5=I("vitlök","raw_edible",6,"c1","flavour","Vitlök, rå")
spe5=I("spenat","as_sold",100,"c1","vegetable","Fryst hackad spenat"); cf5=I("crème fraiche","as_sold",120,"c1","sauce","Crème fraiche")
pap5=I("paprikapulver","dry",2,"c1","flavour","Paprikapulver, milt"); soj5=I("sojasås","as_sold",10,"c1","flavour","Japansk sojasås")
olj5=I("rapsolja","as_sold",15,"c1","cooking","Rapsolja"); sal5=I("salt","as_sold",1,"c1","flavour","Salt"); pep5=I("svartpeppar","dry",0.5,"c1","flavour","Malen svartpeppar")
ris5=I("ris","dry",140,"c2","side","Långkornigt vitt ris, torrt",req=["pack:rice","white_rice"])
R.append(recipe(base_id="smako-swedish-chicken-mushroom-stew", name="Krämig kycklinggryta med champinjoner, spenat och ris", servings=2,
  meal_type="dinner", cuisine="swedish", family="gryta", primary="kyckling", method="pan", side="ris",
  flavor=["champinjon","paprika","grädde"], equipment=["Stor stekpanna","Kastrull"], vegetarian=False,
  components=[("c1","Gryta",[kyc,cha,lok5,vit5,spe5,cf5,pap5,soj5,olj5,sal5,pep5]),("c2","Ris",[ris5])],
  steps=[("Koka riset enligt förpackningen.",K(ris5),18,[]),
         ("Skiva champinjonerna, hacka lök och vitlök och skär kycklingen i bitar.",K(kyc,cha,lok5,vit5),8,[]),
         ("Stek kycklingen i hälften av oljan tills den fått färg runt om. Lägg upp.",K(kyc,olj5),6,["s2"]),
         ("Stek champinjoner, lök och vitlök i resten av oljan tills vätskan kokat in. Strö över paprikapulver.",K(cha,lok5,vit5,olj5,pap5),6,["s3"]),
         ("Tillsätt kycklingen, spenat, crème fraiche, sojasås och 1 dl vatten. Sjud 8 minuter tills kycklingen når minst 74 °C i tjockaste delen. Smaka av med salt och peppar.",K(kyc,spe5,cf5,soj5,sal5,pep5),8,["s4"]),
         ("Servera grytan med riset.",K(ris5,kyc),1,["s1","s5"])],
  active=25, total=32))

lax=I("lax","raw_edible",250,"c1","primary","Laxfilé, rå",req=["pack:salmon"]); spe6=I("spenat","as_sold",100,"c1","vegetable","Fryst hackad spenat")
cf6=I("crème fraiche","as_sold",100,"c1","sauce","Crème fraiche"); cit6=I("citronjuice","as_sold",15,"c1","flavour","Citronjuice")
dil6=I("dill","raw_edible",8,"c1","flavour","Dill, färsk eller fryst"); vit6=I("vitlök","raw_edible",6,"c1","flavour","Vitlök, rå")
lok6=I("gul lök","raw_edible",60,"c1","vegetable","Gul lök, rå"); olj6=I("rapsolja","as_sold",10,"c1","cooking","Rapsolja")
sal6=I("salt","as_sold",1,"c1","flavour","Salt"); pep6=I("svartpeppar","dry",0.5,"c1","flavour","Malen svartpeppar")
pas6=I("pasta","dry",160,"c2","side","Pasta, torr",req=["pack:pasta"]); ost6=I("ost","as_sold",30,"c3","flavour","Riven lagrad ost")
R.append(recipe(base_id="smako-swedish-salmon-spinach-pasta", name="Laxpasta med spenat, citron och dill", servings=2,
  meal_type="dinner", cuisine="swedish", family="pasta", primary="lax", method="pan", side="pasta",
  flavor=["dill","citron","spenat"], equipment=["Kastrull","Stekpanna med lock","Rivjärn"], vegetarian=False, fish=True,
  components=[("c1","Laxsås",[lax,spe6,cf6,cit6,dil6,vit6,lok6,olj6,sal6,pep6]),("c2","Pasta",[pas6]),("c3","Topping",[ost6])],
  steps=[("Koka pastan enligt förpackningen.",K(pas6),12,[]),
         ("Hacka lök, vitlök och dill. Skär laxen i bitar.",K(lax,lok6,vit6,dil6),5,[]),
         ("Fräs lök och vitlök i oljan 2 minuter. Tillsätt spenat och crème fraiche och låt sjuda tills spenaten tinat.",K(lok6,vit6,olj6,spe6,cf6),5,["s2"]),
         ("Lägg i laxbitarna och sjud under lock 5 minuter tills laxen precis är genomkokt, minst 63 °C. Smaka av med citronjuice, dill, salt och peppar.",K(lax,cit6,dil6,sal6,pep6),6,["s3"]),
         ("Vänd ner den avrunna pastan i såsen och toppa med riven ost.",K(pas6,lax,ost6),2,["s1","s4"])],
  active=20, total=22))

# ---------- FRUKOST (1 portion) ----------
tor=I("tortillas","as_sold",70,"c1","side","Vetetortilla",req=["pack:tortilla"]); sb=I("svarta bönor","cooked_drained",100,"c1","primary","Svarta bönor, kokta och avrunna",req=["pack:black_beans"])
spiB=I("spiskummin","dry",0.5,"c1","flavour","Malen spiskummin"); papB=I("paprikapulver","dry",0.5,"c1","flavour","Paprikapulver, milt")
oljB=I("rapsolja","as_sold",5,"c1","cooking","Rapsolja"); salB=I("salt","as_sold",0.5,"c1","flavour","Salt"); ostB=I("ost","as_sold",25,"c1","flavour","Riven lagrad ost")
tomB=I("tomat","raw_edible",80,"c2","vegetable","Tomat, rå"); rlB=I("rödlök","raw_edible",20,"c2","vegetable","Rödlök, rå")
citB=I("citronjuice","as_sold",5,"c2","flavour","Citronjuice"); yogB=I("yoghurt naturell","as_sold",40,"c3","sauce","Grekisk yoghurt, naturell")
R.append(recipe(base_id="smako-mexican-breakfast-bean-burrito", name="Frukostburrito med svarta bönor, ost och tomatsalsa", servings=1,
  meal_type="breakfast", cuisine="mexican", family="burrito", primary="svarta bönor", method="pan", side="tortilla",
  flavor=["spiskummin","tomat","citron"], equipment=["Stekpanna","Skål"], vegetarian=True,
  components=[("c1","Burrito",[tor,sb,spiB,papB,oljB,salB,ostB]),("c2","Salsa",[tomB,rlB,citB]),("c3","Topping",[yogB])],
  steps=[("Hacka tomat och rödlök fint och blanda med citronjuice.",K(tomB,rlB,citB),4,[]),
         ("Värm bönorna i oljan med spiskummin, paprikapulver och salt och mosa dem lätt.",K(sb,oljB,spiB,papB,salB),4,[]),
         ("Värm tortillan i torr panna, fyll med bönor, ost och salsa, rulla ihop och servera med yoghurt.",K(tor,sb,ostB,tomB,yogB),3,["s1","s2"])],
  active=11, total=11, level="simple"))

kroM=I("krossade tomater","as_sold",150,"c1","sauce","Krossade tomater"); kikM=I("kikärtor","cooked_drained",100,"c1","primary","Kikärtor, kokta och avrunna",req=["pack:chickpeas"])
lokM=I("gul lök","raw_edible",40,"c1","vegetable","Gul lök, rå"); vitM=I("vitlök","raw_edible",3,"c1","flavour","Vitlök, rå")
spiM=I("spiskummin","dry",0.5,"c1","flavour","Malen spiskummin"); papM=I("paprikapulver","dry",1,"c1","flavour","Paprikapulver, milt")
oljM=I("rapsolja","as_sold",5,"c1","cooking","Rapsolja"); salM=I("salt","as_sold",0.5,"c1","flavour","Salt")
speM=I("spenat","as_sold",40,"c1","vegetable","Fryst hackad spenat"); yogM=I("yoghurt naturell","as_sold",50,"c2","sauce","Grekisk yoghurt, naturell")
broM=I("bröd","as_sold",50,"c2","side","Matbröd")
R.append(recipe(base_id="smako-greek-breakfast-chickpea-tomato-pan", name="Varm frukostpanna med kikärtor, tomat, spenat och yoghurt", servings=1,
  meal_type="breakfast", cuisine="greek", family="frukostpanna", primary="kikärtor", method="pan", side="bröd",
  flavor=["tomat","spiskummin","paprika"], equipment=["Liten stekpanna"], vegetarian=True,
  components=[("c1","Panna",[kroM,kikM,lokM,vitM,spiM,papM,oljM,salM,speM]),("c2","Servering",[yogM,broM])],
  steps=[("Hacka löken och vitlöken. Fräs dem i oljan med spiskummin och paprikapulver 3 minuter.",K(lokM,vitM,oljM,spiM,papM),4,[]),
         ("Tillsätt krossade tomater, kikärtor, spenat och salt. Sjud 6 minuter tills det tjocknat.",K(kroM,kikM,speM,salM),6,["s1"]),
         ("Toppa med yoghurt och servera med brödet.",K(yogM,broM),1,["s2"])],
  active=11, total=11))

tof=I("tofu","as_sold",125,"c1","primary","Tofu, naturell fast"); gur=I("gurkmeja","dry",0.5,"c1","flavour","Malen gurkmeja")
speT=I("spenat","as_sold",50,"c1","vegetable","Fryst hackad spenat"); tomT=I("tomat","raw_edible",80,"c1","vegetable","Tomat, rå")
lokT=I("gul lök","raw_edible",30,"c1","vegetable","Gul lök, rå"); oljT=I("rapsolja","as_sold",5,"c1","cooking","Rapsolja")
salT=I("salt","as_sold",0.5,"c1","flavour","Salt"); pepT=I("svartpeppar","dry",0.2,"c1","flavour","Malen svartpeppar")
sojT=I("sojasås","as_sold",5,"c1","flavour","Japansk sojasås"); vitT=I("vitlök","raw_edible",3,"c1","flavour","Vitlök, rå"); papT=I("paprikapulver","dry",0.5,"c1","flavour","Paprikapulver, milt"); broT=I("bröd","as_sold",50,"c2","side","Matbröd")
R.append(recipe(base_id="smako-swedish-breakfast-tofu-scramble-greens", name="Tofuröra med spenat, tomat och rostat bröd", servings=1,
  meal_type="breakfast", cuisine="swedish", family="tofuröra", primary="tofu", method="pan", side="bröd",
  flavor=["gurkmeja","soja","tomat"], equipment=["Stekpanna","Brödrost eller ugn"], vegetarian=True,
  components=[("c1","Röra",[tof,gur,speT,tomT,lokT,vitT,papT,oljT,salT,pepT,sojT]),("c2","Bröd",[broT])],
  steps=[("Hacka löken och vitlöken och tärna tomaten. Smula tofun med en gaffel.",K(lokT,vitT,tomT,tof),3,[]),
         ("Fräs lök och vitlök i oljan 2 minuter. Tillsätt tofu, gurkmeja, paprikapulver och spenat och stek 4 minuter.",K(lokT,vitT,oljT,tof,gur,papT,speT),5,["s1"]),
         ("Vänd ner tomaten, smaka av med sojasås, salt och peppar.",K(tomT,sojT,salT,pepT),1,["s2"]),
         ("Rosta brödet och servera med röran.",K(broT),3,["s1"])],
  active=10, total=10, level="simple"))

hav=I("havregryn","dry",50,"c1","side","Havregryn"); mjo=I("mjölk","as_sold",120,"c1","side","Mjölk",unit="ml")
app=I("äpple","raw_edible",100,"c1","vegetable","Äpple, rått"); kan=I("kanel","dry",1,"c1","flavour","Malen kanel")
socH=I("strösocker","dry",5,"c1","flavour","Strösocker"); salH=I("salt","as_sold",0.3,"c1","flavour","Salt")
jns=I("jordnötssmör","as_sold",10,"c1","flavour","Jordnötssmör, naturellt"); oljH=I("rapsolja","as_sold",3,"c1","cooking","Rapsolja")
jnt=I("jordnötter","as_sold",10,"c2","flavour","Rostade jordnötter"); kva=I("kvarg","as_sold",100,"c2","primary","Kvarg, naturell")
R.append(recipe(base_id="smako-swedish-breakfast-baked-apple-oats", name="Ugnsbakad äppelhavre med kanel, jordnötter och kvarg", servings=1,
  meal_type="breakfast", cuisine="swedish", family="ugnsgröt", primary="havregryn", method="oven", side="kvarg",
  flavor=["kanel","äpple","jordnöt"], equipment=["Ugn","Liten ugnsform","Skål"], vegetarian=True,
  components=[("c1","Havre",[hav,mjo,app,kan,socH,salH,jns,oljH]),("c2","Topping",[jnt,kva])],
  steps=[("Sätt ugnen på 200 °C och pensla formen med oljan. Tärna äpplet.",K(oljH,app),4,[]),
         ("Blanda havregryn, mjölk, kanel, socker, salt och jordnötssmör. Vänd ner äpplet och häll i formen.",K(hav,mjo,kan,socH,salH,jns,app),3,["s1"]),
         ("Baka cirka 20 minuter tills ytan fått färg.",K(hav,app),20,["s2"]),
         ("Toppa med kvarg och hackade jordnötter.",K(kva,jnt),2,["s3"])],
  active=9, total=29))

# ---------- MELLANMÅL (1 portion) ----------
kikH=I("kikärtor","cooked_drained",100,"c1","primary","Kikärtor, kokta och avrunna",req=["pack:chickpeas"]); citH=I("citronjuice","as_sold",10,"c1","flavour","Citronjuice")
vitH=I("vitlök","raw_edible",2,"c1","flavour","Vitlök, rå"); spiH=I("spiskummin","dry",0.5,"c1","flavour","Malen spiskummin")
oljH2=I("rapsolja","as_sold",10,"c1","cooking","Rapsolja"); salH2=I("salt","as_sold",0.5,"c1","flavour","Salt")
papH=I("paprikapulver","dry",0.3,"c1","flavour","Paprikapulver, milt"); perH=I("persilja","raw_edible",3,"c1","flavour","Persilja, färsk eller fryst"); sesH=I("sesamfrön","as_sold",8,"c1","flavour","Sesamfrön")
morH=I("morot","raw_edible",80,"c2","vegetable","Morot, rå"); gurH=I("gurka","raw_edible",80,"c2","vegetable","Gurka, rå")
R.append(recipe(base_id="smako-greek-snack-hummus-crudites", name="Hemgjord hummus med morots- och gurkstavar", servings=1,
  meal_type="snack", cuisine="greek", family="dipp", primary="kikärtor", method="cold_assembly", side="grönsaker",
  flavor=["citron","spiskummin","vitlök"], equipment=["Stavmixer","Skål"], vegetarian=True,
  components=[("c1","Hummus",[kikH,citH,vitH,spiH,oljH2,salH2,papH,perH,sesH]),("c2","Grönsaksstavar",[morH,gurH])],
  steps=[("Rosta sesamfröna i torr panna tills de doftar. Mixa kikärtor, hälften av sesamfröna, citronjuice, vitlök, spiskummin, olja, salt och 2 msk vatten till en slät hummus.",K(kikH,sesH,citH,vitH,spiH,oljH2,salH2),6,[]),
         ("Strö över paprikapulver, hackad persilja och resten av sesamfröna.",K(papH,perH,sesH),1,["s1"]),
         ("Skär morot och gurka i stavar och servera med hummusen.",K(morH,gurH),3,[])],
  active=10, total=10, level="simple"))

kikR=I("kikärtor","cooked_drained",100,"c1","primary","Kikärtor, kokta och avrunna",req=["pack:chickpeas"]); oljR=I("rapsolja","as_sold",5,"c1","cooking","Rapsolja")
papR=I("paprikapulver","dry",1,"c1","flavour","Paprikapulver, milt"); spiR=I("spiskummin","dry",0.5,"c1","flavour","Malen spiskummin"); salR=I("salt","as_sold",0.5,"c1","flavour","Salt")
R.append(recipe(base_id="smako-indian-snack-roasted-spiced-chickpeas", name="Ugnsrostade kryddiga kikärtor", servings=1,
  meal_type="snack", cuisine="indian", family="rostade baljväxter", primary="kikärtor", method="oven", side="ingen",
  flavor=["spiskummin","paprika"], equipment=["Ugn","Plåt"], vegetarian=True,
  components=[("c1","Kikärtor",[kikR,oljR,papR,spiR,salR])],
  steps=[("Sätt ugnen på 220 °C. Torka kikärtorna torra med hushållspapper.",K(kikR),3,[]),
         ("Vänd kikärtorna i olja, paprikapulver, spiskummin och salt och rosta på plåt 25 minuter tills de är krispiga. Skaka plåten efter halva tiden.",K(kikR,oljR,papR,spiR,salR),25,["s1"])],
  active=5, total=28, waiting=0, level="simple"))

yogZ=I("yoghurt naturell","as_sold",100,"c1","primary","Grekisk yoghurt, naturell"); gurZ=I("gurka","raw_edible",80,"c1","vegetable","Gurka, rå")
vitZ=I("vitlök","raw_edible",2,"c1","flavour","Vitlök, rå"); dilZ=I("dill","raw_edible",2,"c1","flavour","Dill, färsk eller fryst")
citZ=I("citronjuice","as_sold",3,"c1","flavour","Citronjuice"); salZ=I("salt","as_sold",0.3,"c1","flavour","Salt")
broZ=I("bröd","as_sold",40,"c2","side","Matbröd"); oljZ=I("rapsolja","as_sold",3,"c2","cooking","Rapsolja")
R.append(recipe(base_id="smako-greek-snack-tzatziki-toast", name="Tzatziki med rostade brödbitar", servings=1,
  meal_type="snack", cuisine="greek", family="dipp", primary="yoghurt", method="pan", side="bröd",
  flavor=["gurka","dill","vitlök"], equipment=["Rivjärn","Skål","Stekpanna"], vegetarian=True,
  components=[("c1","Tzatziki",[yogZ,gurZ,vitZ,dilZ,citZ,salZ]),("c2","Brödbitar",[broZ,oljZ])],
  steps=[("Riv gurkan grovt, salta lätt och krama ur vätskan efter 2 minuter.",K(gurZ,salZ),4,[]),
         ("Blanda gurkan med yoghurt, riven vitlök, hackad dill och citronjuice.",K(yogZ,gurZ,vitZ,dilZ,citZ),2,["s1"]),
         ("Skär brödet i bitar och rosta dem i oljan i en panna tills de är krispiga. Servera med tzatzikin.",K(broZ,oljZ),4,[])],
  active=10, total=10, level="simple"))

json.dump(pack("smako-new-recipes-20261017", R), (WORK / "new-20261017.json").open("w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(R), "recept;", [(r["name"], len(r["ingredients"])) for r in R])

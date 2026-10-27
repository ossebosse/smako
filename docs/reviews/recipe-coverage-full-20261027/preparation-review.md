# Beredning: källor, mängdbalans och kvarvarande implementation

Detta är ett granskat konstruktionsunderlag, inte aktiverat beredningsstöd.
Ingen receptversion har skrivits om eller ersatts under denna etapp.
Källornas SHA, hämtningstid och lokala kopia sparas i `preparation-sources.json`.

## Hela ägg till gula och vita

[Kronäggs omvandlings- och näringsdata](https://www.kronagg.se/media/zkvbet4j/4-omvandlings-och-n%C3%A4ringsdata.pdf)
anger ungefär 30 % gula, 60 % vita och 10 % skal av ett hönsägg och separata
råa komponentvärden. PDF-sidan har lästs visuellt. Detta är en populations-
uppskattning, aldrig ett exakt utbyte för en enskild handlares förpackning.
Normaliserade värden och tillämpningsvillkor finns i `egg-separation-source.json`.

För redan kvalificerad rå ätbar heläggsmassa kan förhållandet 30:60 användas
som uppskattning. Om G och V är receptens använda gram gula respektive vita
blir separeringsinsatsen `max(G / (1/3), V / (2/3))`, plus separat efterfrågan
på helt ägg. Exempel: 30 g gula och 60 g vita delar 90 g ätbar heläggsinsats.
Med bara 30 g gula blir 60 g vita ett eget oanvänt utfall. Förpacknings-
överskott i hela ägg är ytterligare en rest. Skalmassa kommer från det
befintliga heläggsbeviset och får inte räknas av två gånger. De avrundade
exempelvikterna i källan är inte samma sak som exakt uppmätta proportioner.

Aktivering kräver ny spårbar receptversion med separering och kontrollvägning
före ingrediensens första användning. En tidsuppgift, exempelvis tre aktiva
minuter per referenssats, måste märkas som författaruppskattning och läggas i
befintlig steg-/beroendegraf. Det är inte en uppmätt tid i källan. Näringen
ska avse den använda råa komponenten, aldrig samma gram helt ägg. Ingen
tillagad vikt, retention eller hållbarhet härleds.

Den tekniska spärren är gemensam inköps- och skafferibokföring. Nuvarande
`PersonalPlanner._allocate`, grupperingen i `basket` och
`PersonalStore.inventory_action` förutsätter samma användbara mängd före och
efter köp. En ensidig resolverprojektion skulle antingen dubbelköpa ägg,
förbruka fel antal gram eller märka återstående vita som hela ägg. Därför
ingår ingen ofärdig runtimekoppling i leveransen.

## Torra baljväxter till kokta

[Saltå Kvarns mungbönsberedning](https://www.saltakvarn.se/recept/grundrecept/mungbonor/)
ger 8–24 timmars blötläggning, sköljning, nytt kokvatten och kokning tills
bönorna är mjuka, med kontroll efter tio minuter och femminutersförlängningar.
Källans cirka tredubblade volym är **inte** ett gramutbyte. Den räcker inte
för att omvandla receptets avrunna gram till inköpta torra gram, och den
fastställer inte näringsretention. Produktens egna tillagningsanvisningar
måste också bevaras. Den långa väntetiden får inte döljas i en kort middagstid.

Nästa nödvändiga bevis är ett tillämpligt torr-mass-/kokt-avrunnen-massutbyte,
avrinningens villkor och näringsgrund. Därefter behövs samma befintliga
inköps-/reservationsväg med separat förberedd mängd och vattenflöde. GoGreens
redan kokta gröna linser är däremot kvalificerade separat i denna etapp.

## Kaffepulver till färdigt kaffe

[NESCAFÉs tillagningsartikel](https://www.nescafe.com/id/id-id/budaya-kopi/gaya-hidup/meracik-kopi-kemasan)
anger för Classic två gram pulver till 150 ml vatten. Det är inte ett
uppmätt slutvolymutbyte och överförs inte till andra roster, koncentrat eller
svenska förpackningar utan granskad identitet. En framtida receptversion
kan specificera en dokumenterad dos och kontrollmätt slutvolym, men behöver
också rätt styrka, uppvärmnings-/avsvalningstid och pulverbaserad använd
näring. Vattenmassan är ingen kaffeprodukt och får inte bli köpt gramvara.

## Obligatoriska acceptansfall före aktivering

- Gula/vita i samma och olika måltider delar köp, med synliga båda utfall.
- Bara en komponent, helt ägg tillsammans med delar och paketavrundning
  ger sluten balans; inga negativa rester eller dubbelavdrag för skal.
- Verkligt uppmätt inköp och beredningsutfall, delvis förbrukning, omplanering,
  frigivning och kvarvarande skafferi behåller identitet och korrekta mängder.
- Ändrad källa, produkt, metod, form eller uppskattningspolicy invaliderar
  förberedd relation. Allergier, kost, ekokrav och näringskrav prövas som vanligt.
- Original-ID, ny innehållshash och versionskedja verifieras mot alla 2 200;
  ändrade tider deltar i användarens tidsgränser och korgarna får nya kvitton.

Arbetet ovan är tekniskt kvarvarande arbete. Det kräver inte ett ägarbeslut
om att sänka kvalitetskrav eller godta påhittade utbyten.

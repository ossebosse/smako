# Hindergranskning och receptimport 2026-11-01

Ägarens rättelse gäller: något separat 72/194-arkiv finns inte. Alla mottagna
recept finns i de fyra bevarade leveranserna, **165 grundrätter / 439 varianter**.
Nya ZIP med cirka 10–40 rätter kan tas emot utan att invänta ett större paket.

**41 hela grundrätter / 108 varianter är importerade** genom ordinarie
validering, diff och atomär publicering i det lokala biblioteket. Biblioteket
ökar från **934/2 462 till 975/2 570**. Detta är inte betaaktivering.
Alla nya versioner heter 1.0.1 och är innehållsgranskade, inte provlagade.
Originalfiler, ursprungliga ingrediensmängder och alla 3 517 tidigare utgivna
versioner är bevarade. De 2 200 ursprungsreferenserna har inte minskats.

## Register och produktstöd

142 ursprungliga namn/form-identiteter sorterades efter antal berörda
varianter och därefter antal där identiteten var det enda registerhindret.
Riktade sökningar gjordes i den befintliga referensens 89 458 produktposter;
sökord och antal träffar finns i [ingrediensliggaren](ingredient-blockers.json).
Träffar, kvalificerade produkter och kompletta korgar är skilda resultat.
En tom sökning bevisar inte att en vara saknas i handeln.

37 identiteter har nu granskade kopplingar, bland annat följande:

| Hinder | Berörda utkast före åtgärd | Åtgärd |
|---|---:|---|
| Olivolja | 106 | Ren olivolja med deklarerad ml-volym |
| Parmesan | 24 | Färdigriven Parmigiano Reggiano, utan antagen ostkant |
| Schalottenlök | 22 | Skalad ätlig mängd endast med tillåten uppskattning |
| Fläskkarré | 21 | Benfri hel karré; viktvarans osäkerhet bevaras |
| Fisksås | 20 | Exakt fermenterad fisksås, inga generiska såser till fisk |
| Lagerblad | 16 | Rätt produkt finns; borttagna blad är fortsatt ett processhinder |

Antalen överlappar. **Native-kompatibla utkast ökar från 98 till 189**;
registerblockerade minskar från 341 till 250. Detta är inte ett automatiskt
godkännande av alla 189. Den separata ingredienskontrollen löser 31 av de 37
nya identiteterna i exakt läge och alla 37 med tillåtna uppskattningar.

Varje koppling binds till butik, produkt/artikel/GTIN, exakt varunamn, märke,
förpackning, källkontext och granskad sammansättning. Ändrade fakta eller fel
produkter avvisas. Ingen närings-, allergen- eller ekologisk deklaration har
fabricerats. Några recept kräver fortfarande uppskattningar trots att nya
ingredienser har exakta förpackningar, eftersom andra ingredienser i rätten
är uppskattade.

Två mängdunderlag är uttryckliga:

- Schalottenlök: Matvaretabellens 72 procent ätlig del, alltså uppskattat
  180 g från en granskad 250 g-förpackning. Exakt läge får inte använda den.
- Zeta sardeller: tillverkarens deklarerade 43 g avrunnen fisk per 80 g
  förpackning. Det är inte en uppskattning från fiskprocenten i ingredienslistan.

Se [källor och exakta utdrag](quantity-sources.json). Utdragens hashvärden avser
de angivna textutdragen, inte HTML-filer. Nya synonymregler bevarar också
skillnaden mellan exempelvis evaporerad och vanlig mjölk samt mellan bruna,
svartögda och generiska bönor.

## Beredning och innehåll

[Receptgranskningen](recipe-review.json) redovisar originalfilens hash,
original-ID, nytt ID, innehållshash och varje avsiktlig ändring. Samtliga
ursprungliga livsmedelsmängder är jämförda i test. Exempel på åtgärder:

- Sardeller vägs avrunna; parmesan hanteras som den färdigrivna produkt som
  faktiskt är granskad. Sofrito använder uttryckligen färdigskivad lövbiff.
- Ma hor får upptining av fryst ananas och kokar in all upptiningssaft.
  Bourdeto får motsvarande fiskhantering. Fryst koriander genomhettas i
  marinad, fyllning eller bönkräm; kalla såser med basilika kräver färsk basilika.
- Wallenbergare och Biff Greta använder befintlig granskad äggseparering,
  vägd gula och separata rester. Uppskattat äggutbyte blir aldrig exakt.
- Frysta hallon kokas och kyls till uttrycklig kompott till mandelmusslor.
  Lingonen till Wallenbergare/äggakaka får uttrycklig kokning och avsvalning.
- Flygande Jacobs kyckling ugnsbakas i gratängformen med all sky kvar,
  i stället för att kokas i ett avkok som sedan kastas. Koktiden ändras samtidigt.
- Makaronstuvningen kräver gammaldags idealmakaroner. Assassina kräver
  spaghetti. Produktformen styrs utan att övriga identitets-/faktakontroller släpps.
  Första provet påvisade också ett verkligt sök-/matchningshinder för ordet
  `Idealmakaroner`. Det är nu kopplat till pasta med fortsatt kontroll av hela
  varunamnet. [Tillverkarens produktunderlag](https://www.kungsornen.se/produkter/gammaldags-idealmakaroner-750g/)
  anger makaronstuvning som användning; [källkvittot](macaroni-source.json)
  tillför inga nya priser eller näringsvärden.
- Granskade versioner serverar angivet steksmör, fett och salladsdressing;
  bortkastade andelar gissas inte. Aktiv hantering har skilts från passiv väntan
  där exempelvis ugnsförvärmning och nudelblötläggning tidigare blandades ihop.

Kulinarisk granskning jämför både ingredienser och arbetsmetod. Exempelvis
skiljs kolbulle från raggmunk, oskållad akki rotti från skållat risbröd,
conchas med kakdegsskal från sirapsindränkt baba och risfyllda köttbullar i
youvarlakia från kyckling med äggcitron. Nya ID:n eller likhetspoäng är inte
ensamma bevis för nyhet. [Nära träffar och beslut](culinary-comparison.json)
redovisas separat som granskningsunderlag.

## Verifiering och räckvidd

Kvalificeringen använder den oförändrade CI-referensen: Malmö-underlaget med
52 butikskontexter, prisklocka **2026-10-23 06:00:02.869273 UTC**, universumhash
`06cbf0b12e619f09dd3709b808916d1c74676859d246ad72f74d52d0e6d91857`
och faktahash `23c45ae2e4f27222833028277b3b9ca9426a232408baa4971c9e8114b766abca`.
Varje prov använder ordinarie planerare, högst två butiker, fyra portioner
middag eller en frukost/mellanmålsportion, tomt skafferi och ingen särskild
allergi-/närings-/ekologisk begränsning. Näringsuppskattningar tillåts.
Exakt respektive uppskattat läge avser inköpsberäkningen. Tidsgräns per
slutlig korg är 20 sekunder; en tidsgräns skulle räknas som okänd.

Det maskinläsbara [slutresultatet](summary.json) sammanfattar de fem
kvalificeringskvittona: **108/108 fullständiga korgar med tillåtna
uppskattningar, 67/108 i exakt läge**. Resterande 41 är uttryckligt
datablockerade i exakt läge. Inga korgprov nådde tidsgränsen.
Varje godkänd korg har passerat slutlig audit och
butiksgränsen. Resultaten beskriver detta frysta underlag, inte dagens beta,
alla användarval eller en uppmätt förändring av varm menyplaneringstid.
Det tidigare tidsprovet med 50 utkast kan inte återanvändas som mätning av 108.

De riktade regressionerna omfattar produktidentitet, fel sammansättning,
butik/förpackning, avrunnen kontra bruttovikt, uppskattningsspärrar,
kostpreferenser, kall hantering av rått kött, originalmängder, source-hashar,
manifestkedja, dubbla ID:n och oförändrad återimport. Ruff och compileall ingår.
Den samlade riktade körningen gav 646 godkända tester. Därefter kontrollerades
den slutliga makaronrättningen separat; kontrollkvitton finns i `.local/verification`.
Full CI och dess produkt-/recept-/korgöverblick ska vara grön före main-merge;
inga täckningsbaslinjer ändras för att få grönt.

[Manifestbeviset](library-transition.json) tillåter enbart tillagda,
disjunkta receptpaket och oförändrade gamla paket. Jämförelsen av de 2 200
ursprungsrecepten kan följa granskade manifeststeg till det större biblioteket;
okända manifest, ändrade ID:n eller ändrat gammalt innehåll godtas inte.

## Kvarvarande hinder och nästa leverans

[Variantkön](queue.json) redovisar alla 439 original-ID:n med aktuellt beslut.
De 331 som ännu inte importerats består av **250 med registerhinder, 39 med
kända insatser utan kvalificerad produkt och 42 med beredningshinder eller
blockerade syskon i familjen**. För varje kvarvarande
tekniskt giltig variant finns en konkret produktspärr, ett beredningshinder
eller blockerade syskon. Ett enskilt fungerande syskon räknas inte som en
godkänd hel receptfamilj.

De största olösta registerhindren är makrutlimeblad (19), grön chili och
räkpasta (18 vardera), curryblad (16), epazote och thaibasilika (10 vardera).
Thaibasilika finns exempelvis i kruka, men krukans bruttovikt är inte ätliga
blad. Mald ancho kan inte tyst ersätta hela chilifrukter som ska blötläggas.
Matlagningsvin, rå/torr/kokt vara, benbärande kött och avrunnet konserverat
innehåll kräver uttryckliga form- och mängdunderlag.

Frityrbad, avsilad vassle, borttagna skal/ben/blad och kasserad lag har inte
lösts genom påhittade konsumtionsandelar. Fortsätt med befintliga
beredningsvägar och verifierbara in-/utgångsmängder eller en sakgranskad
kulinarisk version. Tre Kosha mangsho-utkast har dessutom för hög aktiv tid;
aktivt arbete får inte märkas om till väntan enbart för att passera gränsen.

Kör kön efter varje bevarad leverans från projektroten:

```powershell
$env:PYTHONPATH='backend;.'
.venv/Scripts/python.exe -X utf8 scripts/recipe_layer/audit_expansion_queue.py --output .local/expansion-queue
```

Kommandot kontrollerar originalens manifest/hashar och dubbla ID:n, räknar om
registerhindren och lämnar ett separat native-paket. Det importerar eller
godkänner ingenting. Använd `--source` om en annan samling ska granskas.
`qualify_expansion.py --help` visar hur en uttryckligen vald pack provas mot
en hashkontrollerad fryst referens; `--input-only` gör ingen checkout.
`admit_expansion_20261101.py` återger endast de här uttryckligen granskade
familjerna. `--import` använder ordinarie import och verifierar återimport.
Utöka aldrig dess urval automatiskt från enbart en lyckad strukturkontroll.

Beställningsarbetsgången finns i [REQUESTING-RECIPES.md](../../recipes/REQUESTING-RECIPES.md).

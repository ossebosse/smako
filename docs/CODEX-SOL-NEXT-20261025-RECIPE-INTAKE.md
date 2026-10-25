# Sol: gör de 800 grundrätterna användbara i Smako

Ägaren har beställt att recepten läggs till och att du får nästa uppdrag.
Samlingen finns nu komplett på main som författarunderlag. Hämta aktuell
main i en ren arbetskopia. Följ AGENTS, DEVELOPMENT, produktmålet,
planeringsarkitekturen och HANDOFF. Inget meddelande till en annan chatt
eller någon produktionsaktivering följer automatiskt av denna beställning.

## Läs underlag och skilj mottaget från publicerat

- [Mottagningsrapport](reviews/recipe-intake-800-20261025.md) och dess JSON.
- [Samlingen och kontrollkommandot](../backend/app/data/recipes/incoming/authoring-800-20261025/README.md).
- `SOURCE-MANIFEST.json`, författarens registerförslag, leveransöversikt,
  dubblettgranskning och samtliga berörda författarpaket i samma katalog.
- [Befintlig författar-/importväg](recipes/AUTHORING.md).
- [Fortsatt V2-uppdrag](CODEX-SOL-NEXT-20261025-PREPARED-PLANNING.md).

Det finns 800 grundrättskandidater och 2 200 varianter, inte 2 200 nya
grundrätter. De är AI-författade och inte provlagade. Aktiva biblioteket har
262 recept. Native kontroll: 429 kompatibla, 1 763 ingrediensblockerade,
sex standardiseringsfel och två valideringsavslag. Befintliga alias minskar
författarens 198 råa identitetsförslag till 189 saknade kanoniska identiteter.
Kompatibel struktur är inte ett innehålls-, produkt- eller näringsgodkännande.

Prioritera nedanstående innehålls-/ingrediensarbete före stora nya skalprov.
Det ersätter inte V2-arkitekturen eller ger en ny extra benchmarkbudget.
Behåll ursprungsfilerna byteidentiska; lägg granskade ändringar, beslut,
källreferenser och tillhörande identiteter i en separat versionerad leverans.
Den befintliga intakekontrollen granskar avsiktligt originalet; gör en egen
vanlig author/validate-rapport för de korrigerade paketen.

## 1. Komplettera ingrediensvägen med spårbar täckning

Återkör `scripts/recipe_layer/audit_authoring_delivery.py` mot originalet;
exit 1 är väntad när rapporten innehåller blockerare. Använd
`ingredient_priorities`, inte bara alfabetisk ordning. Salladslök berör 139
varianter, mynta 131, purjolök och smör vardera 111. Effekterna överlappar:
antal faktiskt frigjorda recept får inte beräknas genom att summera dessa tal.

För varje saknad identitet, avgör med befintlig normaliserare, matchning,
råforms-/mängdkedja och godkänt produkt-/faktaunderlag:

1. Känd identitet med annat entydigt namn: använd dokumenterat korrekt alias.
   Färsk/torkad koriander, olika mjöl, smör/margarin och torra/kokta råvaror
   får inte slås ihop av namnlikhet. Granska också författarens föreslagna par;
   listan är inte ett godkännande att slå ihop exempelvis korngryn/pärlkorn.
2. Ny giltig identitet: registrera korrekt namn, form, enhet och verifierade
   produktkrav. Utöka befintlig författarväg för uttryckligt granskat nytt
   vokabulär om den bara kan härleda det från redan importerade recept.
   Lös bootstrap utan låtsasrecept eller tomma krav för att få importen grön.
3. Kontrollera riktig produktkoppling, förpackningsmängd, ätlig andel/
   avrunnen form och eventuella stödda tillagningsomvandlingar. Rå ätlig
   fruktvikt, hel frukt och konserverad frukt är inte samma köpmängd.
4. Ange vilka närings-, allergen-, eko- och animalieuppgifter som finns
   respektive saknas. Återanvänd behöriga befintliga fakta och tillåtna
   spårbara uppskattningar med korrekt status; skapa inga positiva intyg.
5. Saknas verkliga data eller rimlig butiksvara: behåll en exakt blockerare
   med recept-/produktidentitet och nästa komplettering. En godtycklig annan
   råvara får bara bli en uttryckligt författad och granskad receptvariant.

Priserna kan redan innehålla varan trots att den saknas i författarvokabulären.
Inventera därför redan behörigt underlag innan du beställer nya källor.
Ingen bred insamling eller nytt parallellt ingrediens-/prissystem ingår.
Axfoods tidigare principgodkännande gäller inom befintligt källscope.

## 2. Rätta innehåll och verkliga modellhinder

- Granska åtta kända native fel i maskinrapporten. Lång blötläggning,
  avrinning, jäsning och kylning ska ingå i rätt total-/väntetid. Utred en
  konsekvent modell för längre förberedelse genom API, UI och sparning där
  rimliga recept behöver det. Kapa inte tider eller ta bort beroenden för
  att komma under nuvarande 180 minuter. Ogranskade sådana fall får vänta.
- Kalla sluträtter med rå animalisk insats kan innehålla ett tillagningssteg.
  Granska verklig beredning och rätta metod/komponentkedja utan att byta rå
  insats till färdiglagad i metadata. Säkerhetskontrollen ska bestå.
- Kontrollera råvaror i instruktioner mot mängdbasis och produktkrav även
  när schema passerar. Varje variant ska ha fullständiga mängder och steg.
- Kontrollera dietklassificering mot utökat råvarusortiment: exempelvis lamm,
  skaldjur, gelatin och sammansatta produkter får inte bli vegetariska för
  att de saknas i en gammal namnlista. Skaldjur är inte automatiskt fisk.
  Kost, allergener och eko ska bedömas på varje variants faktiska produkter.
- Granska författarens namngivna likhetspar och jämför med befintliga
  grundrätter. Behåll gemensamt base_id för avsiktliga varianter. Redovisa
  om granskningen minskar antalet unika nya grundrätter; byt inte bara ID.
- Middag: enkel ungefär 5–7, vardag 8–11, utökad 12–15 ingredienser, med
  motiverade kulinariska undantag. Salt/peppar/vatten undantas i befintlig
  räknare. `variant_id` är inte `level`; simple/crafted är en egen dimension.
  Högre maxantal tillåter även enkel rätt; ett högre minantal kräver fler.
  Inga onödiga ingredienser eller utfyllnad för att nå en kvot.
- Innehållet har 294 avvikelser från variantintervallen och sju middagsbaser
  utan variant inom dagens standardfilter 10–15 enligt författarens rapport.
  Verifiera utfallet med Smakos räknare efter normalisering. Ändra inte
  användarens standardfilter tyst och kalla inte alla varianter sökbara.

## 3. Publicera granskade delmängder genom befintlig import

Leverera en första sammanhängande granskad delmängd och bygg sedan vidare
så långt faktiskt underlag räcker. Ta med alla måltidstyper och sex kök där
korrekt produktunderlag finns. Första delmängden ska pröva enkel/utökad
variant och gemensam grundrätt, inte bara välja varianter utan verklig skillnad.
Ägarens beställning medger vanlig integration i utvecklingsbiblioteket efter
granskning; be inte om ett nytt principgodkännande för varje ingrediens.

Använd `author -> validate -> diff -> import -> prepare` och befintliga
hashade manifest. Redovisa exakt accepterade ID:n och kvarstående avslag.
Behåll källoriginal och koppla granskade ändringar till dem. Nya granskade
filer ska inte påstå provlagning eller produktgodkännande som inte utförts.

De 160 små författarpaketen är en leveransindelning, inte 160 nödvändiga
runtimegenerationer. Samla granskade varianter i färre importpaket och
kontrollera både standardiserad och publicerad filstorlek mot **16 MiB**.
Aktuella + historiska generationer får vara högst **128**; dagens läge är
13 + 7. Ta inte bort historik/sparade referenser eller höj gränser på chans.
Kontrollera att import är idempotent och aldrig lämnar ett oläsbart manifest.

Förbered gemensam receptstruktur/portioner i befintliga artefakter; håll
produktscope, fakta och prisversioner exakta. Kör inte 2 200 individuella
veckoplaneringar som villkor för att kunna granska eller indexera samlingen.
Inventera produkt-/faktatäckning gemensamt och gör dyrare användarprov selektivt.

## 4. Avgränsad verifiering och fortsatt V2

Kör billiga strukturella kontroller över hela korrigerade samlingen samt
riktade tester för nya alias, råvaruformer, mängdomvandlingar, klassificering,
importstorlek/manifest och portionsskalning. Kontrollera att en veckoplan
inte kringgår `max_same_base_meals` genom simple/extended av samma rätt.
Ruff, compileall och relevant ordinarie CI ska passera före integration.

Fortsätt sedan det befintliga V2-uppdraget med de verkliga granskade recepten
som skalmaterial. Skilj mottagna, importerade, statiskt tillåtna,
produkt-/faktakvalificerade och faktiskt sökta kandidater. En rapport om
2 200 laddade utkast får inte beskrivas som 2 200 användbara kandidater.
Behåll jämförbar gammal 262-baslinje i separat fryst testläge.

Högst **120 minuters sammanlagd dyr kvalificering/prestandamätning för denna
fortsatta etapp tillsammans med V2-uppdraget**, inklusive förberedelse och
omtag. Befintlig förbrukad V2-budget räknas av; ingen ny budget genom ny fil.
Små riktade prov först; ingen gammal fullmatris eller nattlig fortsättning.
30–60 sekunders användarmål, korrekt checkout, två CPU/3 GiB och övriga
V2-gränser består. Giltig full lista/save/GET ska skiljas från dataavslag.

## Leverans

Integrera granskade små commits på main. Skriv
`docs/reviews/recipe-integration-800-20261025.md` med maskinunderlag och
uppdaterad HANDOFF. Redovisa faktiskt antal grundrätter/varianter per steg,
nya ingrediens-/produktkopplingar, kvarvarande luckor med prioritet, ändrade
innehållsbeslut, testresultat och verkliga tidsmätningar. Bekräfta vilka
recept som kan väljas lokalt. Bevara legacy-default, merge=False och separat
releaseförfarande för beta; granskad Git-import aktiverar ingen produktion.

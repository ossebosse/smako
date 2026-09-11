# Smako V2 – kvarvarande luckor, 2026-09-11

Leveransrapport. Startversion `personal-v2-20260910c`; slutversion
`personal-v2-gaps-20260911c`. [Aktuell R1–R9-matris](../docs/product/personal-planning-v2.md).
R1/R2/R4/R5/R9 har kvarvarande datakrav/operatörssteg; ingen blanketacceptans.

## Verifierat under implementation

- R6: fryst 2 l mjölk + 1 kg ris kostar 70 kr. Efter köp och ändring till
  1 l + 1,2 kg förblir köphistoriken 70 kr. 1 l mjölk blir disponibel;
  200 g nytt risbehov köper ett helt 500 g-paket för 15 kr. Lager ändras bara
  genom bekräftat köp/förbrukning. Delvis förbrukning, tomt tillfälle,
  återgång till tidigare receptinnehåll, stale revision och idempotens testas.
- R9: uttrycklig syntetisk grupp, tre varor för 75 kr; tröskel, medlemskap,
  giltighet, grupptak, konkurrens med grupp-/produktpris och återräknad audit.
  Källidentitet/produktlista krävs. Inga grupper härleds från produktnamn.
- R1/R4/R5: sparade råsvar innehåller användbara data som tidigare inte nådde
  personliga krav. Ny koppling läser endast godkända katalogfiler, verifierar
  filhash och exakt produkt/snapshot/butik. Ingen ny insamling eller priskälla.
  Näring markerad `PREPARED` får inte räknas som rå ingrediens. Ingen positiv
  allergifrihetskontroll eller tillagningsvikt uppfinns.
- OIDC: riktig Authlib mot offline-IdP testar PKCE S256, state, nonce,
  signerad ID-token, Secure/HttpOnly-cookie och lokal utloggning. Inte liveacceptans.

## OIDC – konkret operatörsåtgärd

Implementationen är generell OIDC via Authlib, inte leverantörsspecifik.
Alla tre OIDC-värden saknades vid produktionskontrollen 2026-09-11.
`PUBLIC_BASE_URL` matchar beta och befintlig `SECRET_KEY` är minst 32 tecken.
Inga hemliga värden har lästs ut eller dokumenterats.

Rekommenderat betaval: **Auth0 Regular Web Application** med leverantörens
värdbaserade inloggning. Det passar den befintliga serverklienten; operatören
måste godkänna leverantör, villkor och aktuell abonnemangsnivå innan registrering.
Ingen tjänst är skapad/beställd. Se [Auth0 applikationsinställningar](https://auth0.com/docs/get-started/applications/application-settings)
och [authorization code/OIDC](https://auth0.com/docs/api/authentication/authorization-code-flow/authorize-application).

1. Efter operatörens leverantörsval: skapa en Regular Web Application med
   Authorization Code, klientautentisering `client_secret_basic` och PKCE S256.
2. Allowed Callback URL: `https://beta.smako.nu/api/account/callback`.
   Applikationens origin/base URL: `https://beta.smako.nu`. Ingen wildcard.
   Scope är exakt `openid`; e-post behövs inte för ägarskap.
3. Sätt `SMAKO_OIDC_ISSUER_URL` (tenantens HTTPS-issuer), `SMAKO_OIDC_CLIENT_ID`
   och `SMAKO_OIDC_CLIENT_SECRET` privat i **`/opt/smako/production.env`**, 0600.
   `/opt/smako/compose` använder uttryckligen denna fil. Behåll stabil
   `SECRET_KEY`: ägaridentiteten är HMAC av verifierad issuer + subject.
4. Återskapa bara `app`/`smako-app-1` med `/opt/smako/compose up -d --no-deps
   --force-recreate app`, inom driftens gemensamma operationslås. Det färdiga
   låsta restart-kommandot är `python3 /opt/smako/evidence/personal_v2_gaps_activate.py restart personal-v2-gaps-20260911c`.
   Scheduler ska inte återskapas för kontokonfiguration.
5. Smakos utloggning är `POST /api/account/logout`, lokal session rensas.
   **Ingen RP-logout eller logout-callback-URI är implementerad.** Leverantörens
   SSO-session kan finnas kvar. Session: `smako_account`, signerad,
   HttpOnly, Secure, SameSite=Lax, sökväg `/`, max 86 400 s, inget Domain-attribut.
   State/nonce och verifierare hanteras av Authlib under inloggningen;
   endast ogenomskinlig kontoägare sparas efter callback, inga åtkomsttoken.

Liveacceptans efter konfiguration: skapa gästprofil/skafferi/plan; logga in och
bekräfta uttryckligen gästflytt; samma konto på andra enheten ska få samma data;
annat konto ska nekas; logga ut utan förlust; testa radering och återläsning av
äldre isolerad backup med aktuell raderingsledger; samma e-post med olika
issuer/subject får aldrig medföra sammanslagning. R2 förblir PARTIAL tills detta körts.

## Datakällor för kvarstående källluckor

| Behov / kandidat | Fält och identitetsnyckel | Specificitet / åtkomst | Tillräcklighet |
|---|---|---|---|
| Sparad Coop-/Axfood-katalog | Exakta produkt-ID:n + kontext + snapshot; deklaration, näringsgrund, uttrycklig ekologimärkning | Produktspecifik, redan insamlad under godkänd åtkomst | Positiv märkning/näring med rätt grund. Inte full allergenfrånvaro eller tillagningsutbyte. |
| Tillverkarens produktmetadata | Ingrediens-/allergendeklaration, certifieringsuppgift, näringsdeklaration; exakt GTIN + variant + versionsdatum | Produktspecifik. Åtkomst och återpublicering behöver kontrolleras per avtal | Kan stödja hårda krav bara när komplett, aktuell och spårbar; saknad uppgift är unknown. Ingen integration gjord. |
| GS1 Validoo/GDSN | Ingrediensförteckning, allergenuppgifter, eko och näringsämne med basmängd; GTIN och leverantör/version | Produktspecifik, Validoo Buyer kräver avtal/prenumeration. Ingen beställning | Potentiellt tillräckligt per faktiskt komplett fält och deklaration, inte automatisk säkerhetsgaranti. [Validoo Buyer](https://gs1.se/validoo-for-aterforsaljare/), [kvalitetskontroll](https://gs1.se/support/hur-kvalitetssakras-allt-jag-har-fyllt-i/) |
| Livsmedelsverkets livsmedelsdatabas | Makron/energi, generisk livsmedelsidentitet, rå/tillagad beredning och dokumenterade justeringsfaktorer | Generisk uppskattning, inte märkesprodukt. Käll- och versionsangivelse krävs; villkor/version kontrolleras före integration | Kan stödja uppskattningar. Får aldrig bevisa en märkesprodukts allergifrihet eller eko. [API](https://dataportal.livsmedelsverket.se/livsmedel/swagger/index.html), [beräkningsgrund](https://www.livsmedelsverket.se/livsmedel-och-innehall/naringsamne/livsmedelsdatabasen/omlivsmedelsdatabasen/), [användning](https://www.livsmedelsverket.se/livsmedel-och-innehall/naringsamne/livsmedelsdatabasen/sok-naringsinnehall/) |
| Manuellt verifierad receptmetadata | Receptinnehållets hash + ingrediensform/mängd + metod + mätt ätbar serverad vikt + portioner | Receptspecifik, dokumenterade egna mätningar eller tillåtet referensunderlag | Kan stödja portionsvikt och utbyte för just den revisionen; måste omprövas vid ändring. Inga värden har hittats på. |

## Kvantifierad täckning i godkänt underlag

Granskning 2026-09-11, oförändrat aktiverat Lund-underlag med 36 586 sökbara
produktrader, snapshot/version i [maskinläsbar täckning](personal-v2-gaps/source-coverage.json).
Täckningen avser produkt + priskontext, inte unika GTIN. Manifestets 2 093 gäller
ett annat plannerurval och används inte som nämnare här. Äldre Hemköp 4123 och
ICA OWN:s 229 erbjudanderader inventerades separat men ingår inte i aktivt
sökbart ICA/Primat-urval. Inga nya källanrop gjordes.

Råa deklarationer verifierades med sparad filhash och produktpekare. Den tidigare
normaliserade PriceUniverse-modellen hade inga allergen-, eko- eller näringsfält.
Källadaptern matar nu personliga kontroller utan att skriva till PriceUniverse.
Proveniens betyder spårbar produktkälla, inte komplett livsmedelsdeklaration.
Ett giltigt förpackningsmått bevisar inte rå ätbar vikt eller tillagningsutbyte.

### Alla sökbara produkter

| Fält | Coop | Hemköp | Willys | ICA/Primat |
|---|---:|---:|---:|---:|
| Produkter (nämnare) | 11429 | 5011 | 18261 | 1885 |
| Ingrediensdeklaration | 7991 (69.92 %) | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) |
| Strukturerade allergener | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) |
| Allergenfritext | 1648 (14.42 %) | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) |
| Spår/kan innehålla | 1648 (14.42 %) | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) |
| Specifikt fri-från-påstående | 0 (0.00 %) | 51 (1.02 %) | 1165 (6.38 %) | 0 (0.00 %) |
| Inget användbart allergenunderlag | 3438 (30.08 %) | 4960 (98.98 %) | 17096 (93.62 %) | 1885 (100.00 %) |
| Verifierat ekologisk | 645 (5.64 %) | 323 (6.45 %) | 1044 (5.72 %) | 0 (0.00 %) |
| Uttryckligt ej ekologisk | 0 (0.00 %) | 67 (1.34 %) | 274 (1.50 %) | 0 (0.00 %) |
| Eko okänd | 10784 (94.36 %) | 4621 (92.22 %) | 16943 (92.78 %) | 1885 (100.00 %) |
| Eko motstridig (ingår i okänd) | 0 (0.00 %) | 1 (0.02 %) | 2 (0.01 %) | 0 (0.00 %) |
| kcal | 6876 (60.16 %) | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) |
| Protein | 6737 (58.95 %) | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) |
| Kolhydrat | 6742 (58.99 %) | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) |
| Fett | 6747 (59.03 %) | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) |
| Verifierad näringsreferens g/ml | 6913 (60.49 %) | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) |
| Alla fyra näringsvärden med grund | 6725 (58.84 %) | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) |
| Giltigt förpackningsmått | 11176 (97.79 %) | 4766 (95.11 %) | 16792 (91.96 %) | 977 (51.83 %) |
| Källproveniens | 11429 (100.00 %) | 5011 (100.00 %) | 18261 (100.00 %) | 1885 (100.00 %) |
| Verifierad rå ätbar mängd | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) |
| Tillagad/serverad vikt | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) |
| Verifierat tillagningsutbyte | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) |
| Utbyte saknas | 11429 (100.00 %) | 5011 (100.00 %) | 18261 (100.00 %) | 1885 (100.00 %) |

### Produkter nåbara i befintlig receptpool

52 middagskandidater, 3 frukostar och 3 mellanmål; blandkost, fyra portioner, inga medlemskap. Unionen omfattar 449 produktrader i ordinarie kandidatsökning. Aktiva datakrav kan bredda produktsökningen.

| Fält | Coop | Hemköp | Willys | ICA/Primat |
|---|---:|---:|---:|---:|
| Produkter (nämnare) | 99 | 94 | 195 | 61 |
| Ingrediensdeklaration | 78 (78.79 %) | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) |
| Strukturerade allergener | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) |
| Allergenfritext | 2 (2.02 %) | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) |
| Spår/kan innehålla | 2 (2.02 %) | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) |
| Specifikt fri-från-påstående | 0 (0.00 %) | 0 (0.00 %) | 8 (4.10 %) | 0 (0.00 %) |
| Inget användbart allergenunderlag | 21 (21.21 %) | 94 (100.00 %) | 187 (95.90 %) | 61 (100.00 %) |
| Verifierat ekologisk | 14 (14.14 %) | 11 (11.70 %) | 20 (10.26 %) | 0 (0.00 %) |
| Uttryckligt ej ekologisk | 0 (0.00 %) | 3 (3.19 %) | 6 (3.08 %) | 0 (0.00 %) |
| Eko okänd | 85 (85.86 %) | 80 (85.11 %) | 169 (86.67 %) | 61 (100.00 %) |
| Eko motstridig (ingår i okänd) | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) |
| kcal | 74 (74.75 %) | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) |
| Protein | 73 (73.74 %) | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) |
| Kolhydrat | 73 (73.74 %) | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) |
| Fett | 73 (73.74 %) | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) |
| Verifierad näringsreferens g/ml | 74 (74.75 %) | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) |
| Alla fyra näringsvärden med grund | 73 (73.74 %) | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) |
| Giltigt förpackningsmått | 91 (91.92 %) | 78 (82.98 %) | 165 (84.62 %) | 52 (85.25 %) |
| Källproveniens | 99 (100.00 %) | 94 (100.00 %) | 195 (100.00 %) | 61 (100.00 %) |
| Verifierad rå ätbar mängd | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) |
| Tillagad/serverad vikt | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) |
| Verifierat tillagningsutbyte | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) | 0 (0.00 %) |
| Utbyte saknas | 99 (100.00 %) | 94 (100.00 %) | 195 (100.00 %) | 61 (100.00 %) |

Ingrediensfritext kan styrka en positiv konflikt, men här finns **noll kompletta
allergenfrånvarointyg** i alla kedjor. Axfoods enskilda gluten-/laktosmarkeringar
är inte ett fullständigt allergenregister. Frånvaro av en markering räknas aldrig
som fri från allergen. Allergenfritext/spår räknas här bara när deklarationen
uttryckligen innehåller motsvarande uppgift; fälten överlappar och ska inte summeras.

Coop: 7 168 näringsrubriker anger BY_MEASURE; 28 BY_SERVING, 2 BY_PACKAGE_OR_CONTAINER.
245 anger PREPARED. Rubrikantal är inte produktantal när flera rubriker finns.
Endast entydig g/ml-grund med rå/ej angiven tillagningsstatus och ett entydigt,
ändligt, icke-negativt värde per makro används. Tillagade värden används inte
som råvaruvärden. `<0,5`, saknade tal, flera motstridiga värden och okänd omräkning
är okända, inte noll. Inga faktorvärden eller vattenmängder har uppfunnits.

### Felklassning och åtgärd

| Fält/kedja | Klass före ändring | Åtgärd/kvarvarande hinder |
|---|---|---|
| Coop ingrediensdeklaration | MAPPING_MISSING + INTEGRATION_MISSING | `listOfIngredients` kopplas exakt och kan blockera positiva konflikter; inget frånvarointyg. Resterande tomma deklarationer SOURCE_MISSING i sparad källa. |
| Alla kedjors kompletta allergenregister | SOURCE_MISSING | Noll kompletta register; okänd allergi/produkt/sammansatt vara blockerar. ICA/Primat gäller kvarhållet godkänt underlag; det bevisar inte vad leverantörens andra API:er erbjuder. |
| Coop EU_ORGANIC_FARMING/KRAV_MARK, Axfood eu_ecological/krav | MAPPING_MISSING + INTEGRATION_MISSING | Positiv källmärkning förs in i kandidatval och slutlig kostnadsandel. Märkesnamn, bild och EU_ECO_LABEL används inte. |
| Axfood nonEkoProduct | MAPPING_MISSING, 3 CONFLICTING | Negativt statusfält bevaras; 1 Hemköp + 2 Willys motsägelsefulla rader blir unknown. Saknad positiv/negativ källa är SOURCE_MISSING. |
| Ekologiska animalier/sammansatta varors animaliska innehåll | SOURCE_MISSING | Ingen komplett produktklassning av animaliskt innehåll; särskilt krav på alla animalier kan inte verifieras. |
| Coop makron, enhet, basmängd, preparationState | MAPPING_MISSING + INTEGRATION_MISSING | Exakta produktdeklarationer per g/ml används, PREPARED hålls separat. Saknade/motstridiga värden förblir spärrande. |
| Hemköp/Willys/ICA-Primat makron | SOURCE_MISSING i godkänt sparat underlag | Axfoods `energyDeclaration` avser även lampors energiklass och mappas inte till kcal. Ingen liknande märkesprodukt används som proxy. |
| Alla kedjors rå ätbar vikt, tillagad vikt och utbyte | SOURCE_MISSING | Noll verifierade konverteringar. Receptens strukturerade mängder är inte ett bevis på tillagad ätbar vikt. |
| Produktionsdatabasens SQLAlchemy-URL | INTEGRATION_MISSING/adapterfel | URL-parser ersätter strängborttagning, inklusive drivrutin/query; default produktionskonfiguration testas. Ingen befintlig ICA/Primat-normalisering ändras. |

Inget fel i godkänd källinsamling eller ICA/Primat-normalisering har belagts;
därför har inget sådant system skrivits om. Fältspecifika begränsningar är
spärrar i kandidatval och slutvalidering, inte enbart inställningar eller eftertext.

## Kampanjgrupper

Befintlig BasketCalculator/BasketOptimizer använder uttryckliga gruppavtal med
kedja, exakt kontext, källproduktlista, grupp-ID, giltighetsfönster, medlemskap,
tröskel, fast total/rabatt och känt tak. Samma köpta paket får konsumeras av högst
ett konkurrerande gruppavtal. Resterande paket prissätts av den befintliga
produktprismotorn. Hela korgen optimeras tillsammans; skafferi och gamla köp
kvalificerar aldrig. Pris/audit återberäknas på servern och visar vilka rader och
paket som bidrar. Överdimensionerade kombinationer blockeras; ingen ungefärlig
kampanjkostnad markeras verifierad. Nya gruppfall deltar även i kandidatrankning
och ger en konservativ lägre gräns för kostnad vid urval.

Råinventeringen fann 2 288 erbjudanderader, varav 1 523 `realMixAndMatch=true`
och 2 222 med uttrycklig `productCodes`-lista. **Noll** uppfyller det fullständiga
kontraktet inklusive båda giltighetsgränserna. Befintlig normaliserad PriceUniverse
har därför inga godkända grupper. ENGINE SUPPORT är verifierat med uttryckliga
syntetiska avtal; liveanvändning är **LIVE_DATA_UNAVAILABLE**, inga kampanjer uppfunna.


## Kombinerad acceptans och bokföring

Frysta data, Chromium och WebKit: middag + frukost + mellanmål, generisk mjölkextra,
låst exakt icke-livsmedel, 300 ml befintligt skafferi, max två kontexter och
Coop-medlemskap. Första köpet **61 kr**, receptändring efter köp ger **31 kr** i
hela tilläggsförpackningar. Historiskt utlägg **92 kr**. Efter tilläggsköp och
omberäkning: **0 kr** återstår, **700 ml mjölk + 400 g ris** disponibelt. Första
köpets mängder och priser är oförändrade. Gruppkampanjer har separata tydligt
syntetiska kontrakt. [Fryst API/UI-evidens](personal-v2-gaps/browser/browser-results.json).

Faktisk HTTPS med dagens aktiverade priser och nya syntetiska gäster:
samma kombination kostar **41,35 kr + 35,67 kr = 77,02 kr** i verkliga hela
förpackningar. **Coop Online Syd + Willys Lund**, gemensamt max två kontexter.
Efter omberäkning återstår **0 kr**; **300 ml mjölk och 400 g ris** är disponibelt.
API/UI visar samma totalsummor. Medlemskap är uttryckligen valda i testprofilen;
ingen medlemskampanj används av just denna livekorg. Frysta fallet ovan provar
faktisk medlemseffekt. Inga butikskvitton eller riktiga inköp har skapats: detta
är syntetisk intern bokföring i separata gäster. Gästdata är bevarade.
[HTTPS-evidens och slutversion](personal-v2-gaps/https/results.json).

Bokföringsloggen är oföränderlig. Receptbyte/redigering/borttagning och återanvändning
av historiskt recept skapar nya revisioner och justerar reservationer utan att
lägga till, ta bort eller återbetala gamla köp. Delvis förbrukning avser en
uttryckligen bekräftad andel av kvarvarande reservationer. Tidigare förbrukning
följer måltidstillfälle + ingrediens/enhet/variant; utbytt ingrediens skapar ett
nytt behov. Dubbelbegäran återger samma revision. Samtidiga olika begäranden får
en vinnare och en 409-konflikt; förloraren ändrar inte lager eller historik.
Äldre booleska bokföringsmarkörer migreras från den oförändrade dåtida revisionen;
tidpunkt markeras okänd, inget datum eller lagertillskott hittas på.

Verkligt källtest över HTTPS: 100 g ris per portion ger **7,4 g protein och
351 kcal** från exakt Coop-produktdeklaration per 100 g. Hela förpackningen kostar
**22,67 kr**. En separat mjölkkorg klarar **100 % verifierad ekologisk kostnadsandel**
för **12,90 kr**. Ett hårt allergikrav utan komplett information ger DATA_BLOCKED.
Detta innebär partiell produktionsnytta, inte full allergi-/närings-/animaliskt
ekoacceptans. [Källkrav i verklig API-körning](personal-v2-gaps/live-facts.json).

## Tester, gränser och återupptagning

Samlad regression: 413 tester före den isolerade storleksgränsen, därefter
33 kalkylator-/audit-/grupptester inklusive den gränsen. Ytterligare 56
medlemspris-/scannerkontroller. Ruff, compileall med Python 3.12 och JavaScript-
syntaxkontroll passerar. Detaljer: [samlad JUnit](personal-v2-gaps/regression.xml),
[medlemskap/scanner](personal-v2-gaps/membership-scanner.xml),
[bokföring/OIDC/källdata/grupper](personal-v2-gaps/gap-focused-final.xml),
[slutlig kampanjgräns](personal-v2-gaps/group-bounds-final.xml).
Enda varningen är Authlibs aviserade `authlib.jose`-deprekering i offline-testet.

Chromium/WebKit: 18 tidigare mobilkontroller per motor plus bokförd kombinerad
revision, återladdning, sökning, isolering, stora texter och konkret DATA_BLOCKED-
åtgärd. WebKits full-page-skärmbild visar en offscreen skip-link som renderingsartefakt;
DOM-position/fokus och en faktisk viewportbild verifierar att den inte täcker
kontroller. Fysisk iPhone/Safari/kamera är fortfarande **UNVERIFIED**.

Balanserad och Varierad är fortsatt olika på samma frysta katalog: tre middagar
kostar Billigast 139,04 kr, Balanserad 163,92 kr och Varierad 167,90 kr. Minst två
middagar skiljer strukturellt mellan Balanserad och Varierad; variationens prispåslag
är inom befintlig gräns. [Lägesprov](personal-v2-gaps/modes.json).

Inga gamla prisgoldens ändrades. Den enda ändrade deploymentassertionen räknar
nu även appens **skrivskyddade** råkatalogvolym. Källinsamling, Willys-task/relay,
ICA/Primat-normalisering, ICA OWN-research, scheduler och Caddy är orörda.
Ingen ny extern tjänst eller betald AI är beställd.

Kampanjgrupper har explicita beräkningsgränser: högst 500 köpta paket, 100 000
allokeringssteg och 200 000 kandidatkombinationer. Överskridande ger DATA_BLOCKED,
inte ett obestyrkt pris. Kontosynk, full allergeninformation, animaliskt innehåll,
portionsutbyte och skafferiets näringsgrund återupptas enligt respektive R-rad.

## Deployment, backup och rollback

Källa `/opt/smako/releases/personal-v2-gaps-20260911c`, via `/opt/smako/current`.
Image `billigaste-veckomenyn:0.1.0-smako-personal-v2-gaps-20260911c`,
`sha256:c0eb914554b5f9bfa48058785123cec7a49f745803cb52be6ea658126f875d36`.
16 verifierade overlayfiler över tidigare release, följt av exakt URL-parserfix
och en isolerad kampanjgräns. Produktionskonfigurationen använder en SQLAlchemy-
URL vars databasdel måste parsas, inte tas fram med enkel prefixborttagning.
Källadaptern testades både med explicit sökväg och med verklig defaultkonfiguration;
34 701 befintliga källrader kopplas. [Defaultkonfiguration](personal-v2-gaps/facts-integration-default-config.json).

Backuper: `20260911T084740Z`, `20260911T090212Z`, `20260911T090702Z`.
Första återlästes till `/srv/smako/restore/personal-v2-gaps-20260911` och verifierades
med aktiva raderingsdirektiv, databas- och artifacthashar. Produktionsledgers
hade noll rader vid export; positiva raderingsfall med nya privata ledgerdata
provas därför separat i frysta restoretester. Ingen aktiv databas återställdes
eller användardata raderades. [Restore](personal-v2-gaps/restore.json).

Varje backup och aktivering använde befintligt gemensamt driftlås. En separat
container höll samma låsfil/inode under appens omstart, så refresh/retry/backup
inte överlappade aktiveringen. Endast appen återskapades. Alla äldre planrevisioners
fullständiga rad-hashar, scheduleridentitet och prismanifest kontrollerades.
[Slutlig deploymentkontroll](personal-v2-gaps/deployment.json).

**Rulla inte tillbaka direkt till den äldre C-imagen från 10 september.** Den
förstår inte alla nya revisionsfält. Förberedd rollback bygger på den imagen
med framåtkompatibla modeller och ett ärligt tillfälligt läsläge. Planer kan läsas,
men personal-/plan-/kontoskrivningar spärras; raderingens befintliga stöd finns kvar.
Den läste 82 backuprevisioner och två nya syntetiska revisioner med oförändrade
köp 70 + 15 kr utan databasskrivning. [Kompatibilitet](personal-v2-gaps/rollback-compatibility.json).

```sh
ssh smako 'python3 /opt/smako/evidence/personal_v2_gaps_activate.py rollback personal-v2-gaps-20260911c'
```

Rollback behåller alla databaser och ändrar endast appimage/symlink/version under
samma lås. Ingen historisk databasrestore krävs för appbytet. Hemliga env-backuper
stannar privat på servern, 0600. Vid riktig katastrofrestore krävs aktuell
raderingsledger enligt befintlig restore-rutin.


## Uppmätt ekonomisk och tidsmässig regression

Samma aktiverade katalog och samma gamla meny kostar **244,49 kr** före/efter.
Slutlig sekventiell före/efter-körning: kall **13,888 → 16,360 s (+17,8 %)**,
varm **0,785 → 0,780 s**. Detta är en uppmätt kall regression, inte en
prestandaförbättring eller ett SLA. En tidigare eftermätning var 16,664 s;
variation och nya gruppkontroller redovisas, ingen prestandaomskrivning gjordes.
Båda körningar gjorde noll livepris-anrop. [Före](personal-v2-gaps/benchmark-before.json),
[efter](personal-v2-gaps/benchmark-after.json). Kall plannerprestanda förblir uppskjuten.


Kampanjens fasta kostnad fördelas proportionellt mot de bidragande paketens
källstödda ordinarie kostnader, med deterministisk öresavrundning. UI anger att
radsumman är fördelad och visar samtliga bidragande varor. [UI-prov mot den verkliga
HTTPS-frontenden med syntetiskt motorresultat](personal-v2-gaps/group-ui/results.json).

Slutkontrollen 2026-09-11: **105 revisioner** i produktion. Alla 99 före sista
appbytet är oförändrade; tidigare aktiveringar bevarade alla 82 respektive 91
föregående revisioner. Endast syntetiska acceptansrevisioner har lagts till av
denna körning. Alla 15 ändrade appfiler matchar lokal verifierad källa.
[Hashjämförelse](personal-v2-gaps/source-match.json).

Skafferibegränsning som kvarstår från föregående release: exakt skafferiprodukt
behöver fortfarande finnas i godkänt katalogunderlag för automatisk tilldelning.
Okänd identitet eller oförenlig enhet ersätts inte genom namnlikhet.

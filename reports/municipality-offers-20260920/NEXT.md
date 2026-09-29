# Första nästa integrationssteg: Coops fysiska erbjudandetext

Föreslagen kedja är **Coop**, avgränsat till det befintliga fysiska offers_only-flödet. Online Syd 730400 lämnas separat och orört. Börja med Flöjtvägen och Bulltofta som verkliga regressioner; ingen hårdkodad butikslista som normal upptäckt.

Konkreta kodsteg, i ordning:

1. Utöka `connectors/coop/browser.py` inom befintlig sanering med per-annons synlig text, belagd aktuell/framtida period och de officiella variantlänkar/ID:n som kan följas via ”Se N varor”. Bind varje fält till samma kort, butik, URL, innehållshash och verklig observation. Behåll nätbudget och stoppregler. Perioderna får inte sammanblandas med reklambladsnavigationens vecka 38/39.
2. Rätta `CoopParser`: annonserat publikt styckpris ska bli köppris i SourceOffer med belagd period, inte obelagt ordinarie rest-/efterkampanjpris. Bevara variantundantag (exempel Yoggi: ej laktosfri), medlemskap, gruppköp, max ett gruppköp per hushåll och eventuell pant. Bevara läsbar prisuppgift även om köpidentiteten ännu saknas.
3. Återanvänd collector, OWN, befintliga prisavtal och provider. Generalisera endast den kedjelokala delen av det **uttryckliga** radgodkända kontraktet: ICA-specifika failureprefix/parserkrav får inte slopas globalt. Coop behöver en egen belagd allowlist för lokala fel, delad källvalidering och identitetsbevis. När relevant kontrakt saknas stannar raden i karantän. Ingen fristående prissättare eller parallell prisdatabas.
4. För kvalificerade rader vidare till samma PriceUniverse/matcher/näringsprövning/checkout/audit i isolering. Fysisk Coop får egen butiksgiltighet; 730400-priser kan inte lånas. Samma fysiska butik räknas en gång. Användarens max två inköpsställen ändras inte.

**Mätbar potential från provet:** 70 lästa butik-prisrader, varav 62 redan blir SourceOffer och 8 saknar korrekt erbjudanderoll. Det är taket för detta provs vidare kvalificering, inte ett löfte om 70 nya receptprodukter. Verifierat nya köpklara/importerade priser i denna etapp: **0**. Antal som klarar exakt variant, giltighet, förpackning och näring kan anges först efter nästa steg. Inget besparingspåstående.

Testbehov: verkliga sparade kort/period-/variantdata; laktosfri exkluderad; publikt vs medlem/personligt; gruppköp och restmängder utan påhittat ordinarie pris; maxgrupp över recept; pant okänd blockerar; vecka 38/39 och dagsvillkor; flyttad butik/ändrad källa; felaktigt generellt villkor stoppar alla berörda; oförändrad ICA-regression; separat verklig transportkontroll i avsedd servermiljö; identiska färska baser i jämförbar 15/20-körning innan nyttan hävdas.

Driftberoenden: befintlig Playwright Chromium i avsedd runtime, befintliga operationlås och nätbudgetar; verifierbar kommuninformation för automatisk kommunutvidgning. Inga nya modellberoenden. Windows-administratörssteget för den väntande ICA-releasen är ett **annat ärende** och ska inte få fler krav eller ändrad kod av detta förslag.

Separat observandum: Axfood-parsern tappar `offerStatus`, `applied` och variantlistor. Hemköps råkonflikt behöver en egen liten semantikregression innan dessa signaler kan användas för nya köpbeslut. Den ska inte lösas genom att anta att alla `potentialPromotions` är aktiva. Detta är inte en beställning på en parallell Hemköp-ombyggnad.

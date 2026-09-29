# Willys reklamblad via kommuninventeringen

Frivilligt `offers_only`-tillskott för officiellt inventerade, öppna Willys-butiker utan onlinekatalog. Befintlig Willys onlineinsamling förblir separat. Ingen produktionsaktivering ingår.

## Urval och prisbevis

`flyer_inventory` återanvänder Willys officiella register, kommunfunktionen och SCB-geometrin. Urvalet kräver verifierad kommuntillhörighet och butikens egen officiella `flyerURL`; kontrollfallen 2863, 2843, 2851, 2865, 2870, 2879 och 2352 är inte produktionslistan. Alla nationella registerrader, okänd kommuntillhörighet och misslyckade hämtningar finns kvar i inventering och status. Ingen användares butiksval, profil eller inköpsområde skrivs om.

Varje butiks aktuella publika iPaper-sida måste själv bekräfta utgåvan. Sidans dokumenttext och den offentliga PDF-nedladdningen binds till en granskad PDF-hash, publikationsidentitet, textblock och prisblock. Gemensam PDF hämtas en gång per klient först efter respektive butiks egen källkoppling. HTTP 401/403/429 stoppar återstående nätförsök i samma batch; orsaken förblir synlig. Ingen inloggning, bildtolkning eller betald tjänst används.

Detta är en utvidgning av befintlig Willys-connector och befintligt partiellt erbjudandekontrakt: `SourceOffer → collector → radvalidering → OWN → PriceUniverse`. Dokumentannonsens ID är ett separat opakt ID, aldrig påhittad GTIN eller online-SKU. Ordinarie köppris är okänt. Jämförpris, tidigare lägsta pris och uppgiven besparing används inte som ordinarie köppris. Butik, fysisk priskanal, namngiven variant, förpackning, datum, medlemsvillkor, flerköp och hushållsgräns följer med. Oklara pantbelopp, storlekar, varianter och viktköp stannar i karantän.

Den granskade veckan 21–27 september 2026 omfattar 34 textannonser i Hemma-utgåvan och 112 i Rosengårds utgåva. Samtliga är bedömda, inte bara presentationsexemplen. Befintlig fastförpackningsberäkning krävs; styckeannonser utan belagt ordinarie pris kan ännu inte köpas genom detta kontrakt. Flerköp kan verifieras för angivet antal av samma kvalificerade variant. Blandning av varianter får inte antas utan ett tillämpligt gruppkontrakt. Hushållsgränsen kan inte multipliceras genom flera recept eller butiker.

## Ordinarie drift

`WILLYS_FLYER_ENABLED=true` och `WILLYS_FLYER_MUNICIPALITY_CODE` väljer kommun i en **separat avsedd miljö**. `WILLYS_FLYER_ROOT` anger dess beständiga tillstånd; val och stad måste överensstämma. Detta dokument är inte en instruktion att aktivera produktion. Efter första sparade valet används beständig `config.json` även efter omstart. Ursprungliga officiella inventeringsbevis kan anges med `WILLYS_FLYER_INVENTORY` för verifierbar replay.

Adaptern körs inuti befintlig låst `daily-refresh` och befintlig behovsstyrd runner. Den använder befintlig kampanjplanering, 35-timmars återkontroll, 36/48-timmars färskhetsgränser, beständiga snapshotreferenser, publiceringskvitto efter faktisk reload, felbackoff och giltig LKG. Ingen separat scheduler eller daglig fullhämtning har tillkommit. Frivillig källas konfigurations-/hämtfel får inte stoppa fungerande bas. Utgångna kampanjer kan inte falla tillbaka på ett gissat ordinarie pris.

Ny PDF eller ändrad publicering kräver manuell dokumenttextgranskning och ett nytt versionsbundet register i `fixtures/flyer_review_20260923.json` eller dess efterföljare. Ogranskade annonser importeras inte. Samma granskade utgåvas hämtning, butikskoppling, validering, import och uppdatering är automatiska. Bildernas innehåll har inte analyserats; material utan verifierbar text förblir en täckningslucka.

## Verifiering och begränsningar

Källor, butikstabell, karantänorsaker, matcher/checkout/audit, faktaprövning, verklig nätinsamling och separat replay/felinjektion finns i `reports/willys-flyers-20260923/RELEASE.md` och tillhörande maskinläsbara resultat. Basens verkliga observationstider bevaras. Lunds äldre onlinebas kan ge degraderad driftstatus trots godkänd reklambladspublicering; den måste uppdateras genom sin redan befintliga godkända väg innan den förfaller.

Fullständigt Malmö-publiceringsprov med aktuell komplett bas kvarstår separat. Lidl-pilotens manuella kampanjkoppling och saknade historiska näringsfixture kvarstår uttryckligen; se `LIDL-AVGRANSNING.md`. ICA, Coop/X:-tra, City Gross, Willys online, Lidl och Primat har inte byggts om.

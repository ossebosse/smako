# Regel för veckans fördelning

Runtimeversion `authored-week-sources-v1` används i `recipe_week_variation.py` och ingår i planens cacheidentitet. Valet av matkök på en gammal begäran fortsätter bara att ange tillåtna inspirationer; det skapar inget nytt hårt krav. Tre explicita lägen finns: fritt, minst angivet antal olika kök och minst en middag från varje valt kök. För många obligatoriska kök i förhållande till antal middagar är ett valideringsfel före sökningen.

Ett middagsrecept räknas en gång oavsett portionsantal. Matkök tas från den granskade receptdesignen. En grundrätt identifieras med `base_id`; variationer av samma grundrätt ger inte ett nytt grundrecept. `base_id`, rättfamilj, tillagningssätt och huvudproteinkälla är separata dimensioner i resultatet.

Varje råvara som receptet märker som `primary` räknas som en verklig huvudproteinkälla. Designens `primary_ingredient` tas också med; upprepade etiketter inom samma middag avdubblas. En lins- och tofurätt räknas alltså en gång i *linser* och en gång i *tofu*, medan fyra portioner fortfarande är en middag. Tofu, linser, bönor, kikärtor, kyckling och namngivna fiskarter hålls åtskilda. Keso och ost är två källor när båda faktiskt anges som huvudingrediens. Okända primärnamn bevaras som egna kanoniserade etiketter; de slås inte tyst ihop med ”vegetariskt”.

Det frivilliga taket jämför antalet **middagar** per källa, också i blandrätter. Begränsningarna prövas som hårda veckovillkor ovanpå det ekonomiska mål användaren valt: Billigast, Balanserad eller Varierad. Sökningen använder säkra nödvändiga delvillkor och en slutkontroll. Ett resultat som inte uppfyller valet får inte märkas som giltigt. En utebliven träff inom begränsad sökning är inte ett bevis på att alla möjliga menyer är omöjliga.

Förslagsknappen ”Mer omväxling” sätter synligt minst tre matkök och högst två middagar per huvudproteinkälla när minst tre middagar och tre tillåtna kök finns. Den körs bara efter aktivt val, aldrig automatiskt för äldre Balanserad-begäranden.

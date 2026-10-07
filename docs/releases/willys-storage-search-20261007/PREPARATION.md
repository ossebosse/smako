# Förberedelse, invalidering och gemensamt inköp

Ny körning i den verifierade 54cb-imagen, jämförd med fd2 där tabellen anger
före/efter. Samma frysta priser och fakta. Inga nya verkliga produktfakta.
Fulla råresultat och hashreferenser finns i FOLLOWUP-EVIDENCE.json;
mätvärden och storlekar i PREPARATION.json.

## Ordinarie CLI-förberedelse

Hela aktuella biblioteket och dess historik, portionsskalor 1/2/4 samt
källprojektion för den faktiska prisartefakten. Ett par, inte tre upprepningar.
Tiden mäts runt CLI-anropet och inkluderar dess prisinläsning, fakta och
skrivning. Containerstart och de första Python-importerna ligger utanför.

| Läge | Före | Efter | CPU före/efter |
| --- | ---: | ---: | ---: |
| Tom förberedelsekatalog | 69,42 s | 64,11 s | 42,10 / 37,29 s |
| Identisk förberedelse igen i samma process | 22,52 s | 20,54 s | 22,51 / 20,54 s |

Varje sida lagrar samma 471 filer, 8 241 010 logiska byte, cirka 7,86 MiB.
Återanvändning tar alltså fortfarande tid för inläsning och kontroll; den
redovisas inte som gratis arbete. Förberedelsen ändrar inga insamlingsscheman.
Samtliga isolerade förberedelsekataloger i verifieringsvolymen upptar
221 169 304 logiska byte över 32 kataloger. Det är testernas separata kopior,
inte lagringskravet för en enda appgeneration. Filsystemets allokerade byte
och temporär topplagring är andra mått.

## Kontrollerade ändringar

- Identiskt underlag: återanvändning utan ny skrivning, korrekt korg.
- Ändrad näringsfakta: ny källprojektion och ändrat faktiskt näringsresultat.
  Den injicerade proteinökningen är ett testvärde, ingen ny källdeklaration.
- Alla kvargprodukter borttagna: korrekt stopp. En verklig tidigare produkt
  återförd: korrekt korg. Ett gammalt negativt resultat blockerar inte den.
- Prisändring: nytt sammanhängande prisunderlag och ny projektion används.
- Kampanjutgång: den verkliga kandidatens tre erbjudanden är borta dagen
  efter giltighetstidens slut. Datumet är kontrollerad fel-/gränsinjektion.
- En ny receptversion: 181 innehållsträffar och en ny innehållsartefakt.
  Beroendena anger `morot|raw_edible` och `kvarg|as_sold`.

Källändringarna bygger fortfarande ett helt sammanhängande produktindex:
6,59–7,24 s i de tre kontrollerade inventory-ändringarna, därefter
1,31–1,47 s för respektive riktade korgprov. Dessa intervall överlappar inte.
En registrerad cachemiss betyder här en projektion, inte att bara en produkt
har bearbetats. Receptförberedelserna återanvänds där beroendena är oförändrade.
Slutimagen och det riktiga innehållsmanifestet har inte ändrats av proven;
injektionerna sker i separata containerlager.

## Verkligt gemensamt förpackningsbehov

Två uttryckligt valda befintliga recept provades genom ordinarie veckokorg:

- Bön- och couscoussallad, middag för två: 150 g naturell yoghurt.
- Äppelhavre för förberedelse kvällen före, frukost för en: 150 g yoghurt.

Samma kvalificerade produkt från Coop Online Syd, online_fulfillment,
`89e16b84016d42a8b4159b59dc591df3`, täcker sammanlagt 300 g genom en
1 000-grams förpackning för 15,55 kr. Planerad rest är 700 g. Den blir inte
verkligt skafferi och dras inte av som framtida värde.
Hela provkorgen kostar 146,93 kr; audit PASS, köp VERIFIED_WITH_ESTIMATES
och båda måltidernas näring ESTIMATED enligt medgivandet. Det är en berikad
historisk replay. Provet visar samordning; någon separat besparing har inte
mätts med en kontrollerad ekonomisk jämförelse.

## Innehåll och gamla revisioner

Alla 24 pilotrecept och alla sex tillägg kvalificeras genom den vanliga
produkt-, mängd-, närings- och korgvägen. Villkoren är uppskattat köp,
uttryckligt näringsmedgivande, högst tre butiker och inget begärt proteinmål.
Det är inte ett godkännande av samtliga recept för 30 eller 40 g protein.
De fyra separata äldre 15/20-profilerna behåller däremot sina 40/30/20-krav.

Nio bevarade isolerade revisionsrader lästes oförändrade i den nya imagen,
inklusive två historiska rader med senare återkallat innehåll. Fingerprint
och materialisering finns i QUALIFICATION.json. Tidigare prov av 267 äldre
revisioner återanvänds för den oförändrade lagrings-/modellkoden och räknas
inte som nykörda. Nya revisioner och ägarisolering provas separat via HTTP,
webbläsare, faktisk appomstart och flagga av i samma image.

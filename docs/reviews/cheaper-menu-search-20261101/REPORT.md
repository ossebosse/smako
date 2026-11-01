# Billigare menyer: två sökförslag avvisade, 2026-11-01

**Inget av de två prövade sökförslagen införs.** De gav ingen verifierad
prisvinst i jämförelserna. Appkoden är återställd till main och betan ligger
kvar på `app-b7c8d0506e23-c18e4ba9`. Ordinarie 60-sekundersbudget består.
Detta visar inte att nuvarande menyer är globalt billigast.

[Slutlig budgetkontroll av sju middagar](BUDGET.md): även 60, 65 och 75 s
budget gav samma 321,98-kronorskorg. Fem ytterligare godkända anrop;
totalt 35 godkända och fyra blockerade försök. Ingen runtimeändring.

## Förslag och beslut

1. Samtidiga tvåreceptbyten: högst åtta prioriterade alternativ per plats,
   två begränsade förslagsköer och högst två nya checkouter per ankare.
   Riktade tester visar en verklig lucka för paketdelning/fördelningskrav:
   en kontrollerad korg kostar 30 kr, ett byte 35 kr och två byten 25 kr.
   Men det gav ingen lägre slutkostnad i de sex verkliga jämförelsefallen.
2. Prisordnad komplettering: pröva även en hel meny med billiga kvalificerade
   recept för varje ankare, utöver befintlig prioritering av gemensamma
   förpackningar. Ingen besparing i de sex fallen; heller ingen godkänd
   besparing i den senare utökade jämförelsen.

Exakta avvisade ändringar och deras riktade tester finns i
[parbytespatchen](paired-proposals.patch) och
[prisordningspatchen](price-led-completions.patch). De är arkivunderlag,
inte aktiv appkod eller en ny inställning. 81 riktade tester passerade för
parbytena, 15 för prisordningen; enhetstesterna ersätter inte prisjämförelsen.

## Matchad första jämförelse

Alla priser är faktisk gemensam kassakostnad. Samma Lundval, 17 kontexter,
2 portioner, 10–15 ingredienser, uppskattningar uttryckligen tillåtna,
balanserad variation, tomt skafferi och 1 liter mjölk som extra.
Alla 18 resultat passerade slutlig audit, sparning och ägd återläsning.

| Val | Nuvarande pris | Båda förslagens pris | Nuvarande tid | Parbyten | Prisordning |
| --- | ---: | ---: | ---: | ---: | ---: |
| En italiensk middag, en butik | 110,55 kr | 110,55 kr | 24,153 s | 24,279 s | 24,068 s |
| Tre middagar, en butik | 185,83 kr | 185,83 kr | 51,203 s | 51,386 s | 51,295 s |
| Tre middagar, upp till tre butiker | 182,39 kr | 182,39 kr | 52,035 s | 51,958 s | 51,985 s |
| Fem middagar, upp till tre butiker | 252,58 kr | 252,58 kr | 51,995 s | 51,969 s | 51,970 s |
| Tre italienska middagar | 253,85 kr | 253,85 kr | 27,839 s | 28,666 s | 30,330 s |
| Tre svenska middagar | 246,86 kr | 246,86 kr | 30,091 s | 32,048 s | 31,751 s |

## Utökad jämförelse och längre tid

I samma uppvärmda process växlades originalmetoden och den andra
försöksmetoden. Varje begäran fick nytt plantillstånd och en egen syntetisk
databas. Resultatens sparning och ägda återläsning verifierades före rensning.

- Sju middagar: försöket 328,98 kr / 49,073 s; nuvarande metod
  321,98 kr / 49,119 s. Detta godkänner inte ändringen. Körordningen är en
  begränsning: kvalificering tog 19,244 respektive 14,366 s och lämnade
  olika mycket söktid. Skillnaden är därför inget isolerat kausalbevis för
  att just algoritmändringen alltid höjer priset.
- Fem middagar för fyra, två vegetariska, två kyckling och en kött:
  båda 456,97 kr på cirka 49,10 s.
- Upprepade trebutiks- och svenska tremiddagsfall behöll 182,39 respektive
  246,86 kr. Den svenska försökskörningen var långsammare.
- Med **75 sekunders försöksbudget** kostade tre middagar fortfarande
  182,39 kr och fem 252,58 kr, för båda metoderna. Leverans cirka 64,0–64,1 s.
  Cirka 15 extra sekunder gav alltså ingen besparing i dessa fall.

Fyra försök med de äldre Malmöprofilerna A/B2 stoppades av befintlig
priskontextkontroll: `context:ica:89adf2bc4a5fc50b` och
`context:ica:f0d2c31124015463` saknades eller underkändes i det aktuella
underlaget. Samma avslag i båda metoderna. Butiker/krav togs inte bort för
att göra dem gröna. De räknas **inte** som lyckade menyer eller som
prisregressionskontroll mot de historiska frysta Malmöresultaten.

## Mätgränser och reproducerbarhet

[Maskinunderlaget](EVIDENCE.json) innehåller källhashar, råkvittohashar,
pris-/faktaversioner, tider, sökdiagnostik och minnestoppar. 30 godkända
menyer och fyra blockerade försök i denna rapport. Bas är main `5aa723b2dbda`,
aktiv appkod `b7c8d0506e23`, oförändrad image och kvarhållna prisunderlag.

Alla processer laddade aktiva Lund/Malmöunderlag och krävde uttryckligen
färdigt aktuellt receptbibliotek och båda faktaunderlagen **före** mätning.
2 462 varianter, 54 515 respektive 95 998 faktarader. Uppstart och gemensam
förberedelse finns separat i kvittona och ingår inte i varma anropstider.
Isolerade containrar med 4 GiB gräns, nät av och källdata skrivskyddade;
inga produktionsplaner, profiler eller insamlingsjobb ändrades.

Den första utforskande serien tog med admission/städning i väggtiden men
startade 60-sekundersdeadlinen inne i arbetstråden. Den senare serien
startade deadlinen **före admission**, som API:t. Därför är cirka 52 → 49 s
mellan dessa två protokoll ingen uppmätt optimeringsvinst. Jämför inom samma
protokoll. Den senare serien höll det befintliga gemensamma driftlåset;
första baslinjen kördes efter lugn driftkontroll, följande försök under lås.

Samma ordinarie krav, checkout och slut-audit gäller varje förslag.
Prisordning och paketlikhet är heuristik, inga giltighetsintyg eller
kostnadsgränser. Enstaka prov är inga p95-/samtidighets-/fullvalsgarantier.
Råunderlag och körhjälpare finns under `.local/cheaper-menus-20261101/`.
Referensdata och gamla mätningar är inte omskrivna.

För 75-s-försöken används separat uppmätt väggtid. Originalspårets
`first_valid_request_seconds` antar 60 s och är inte ett giltigt
anropsmått vid den utökade försöksbudgeten.

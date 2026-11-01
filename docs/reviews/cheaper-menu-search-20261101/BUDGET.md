# Sjudagarsmeny med 60, 65 och 75 sekunders budget

**Ingen besparing hittades.** Alla fem prov gav 321,98 kr. Nuvarande appkod,
60-sekundersbudget och beta behålls. Detta gäller den provade menyn, inte
ett bevis på globalt optimum.

| Prov | Budget | Verifierad/sparad/återläst meny | Pris |
| --- | ---: | ---: | ---: |
| seven-prime | 60 s | 49.088 s | 321,98 kr |
| seven-60-a | 60 s | 49.009 s | 321,98 kr |
| seven-65 | 65 s | 54.079 s | 321,98 kr |
| seven-75 | 75 s | 64.145 s | 321,98 kr |
| seven-60-b | 60 s | 49.084 s | 321,98 kr |

Samma syntetiska Lundbegäran i varje prov: sju middagar, två portioner,
17 valda kontexter, högst tre inköpsställen, fria matkök, 10–15 ingredienser,
balanserad variation, tomt skafferi och en liter mjölk som extra. Allt annat
än den yttre försöksdeadlinen var identiskt. Originalmetoden från den aktiva
imagen användes i samtliga fem prov; ingen försöksalgoritm var på.

Bibliotek och båda aktuella kommunernas faktaunderlag var uttryckligen
färdiguppvärmda före första anropet. Första anropet redovisas som prime.
Därefter jämfördes ordinarie och längre budgetar, med en ny kontroll på
60 sekunder sist. Alla anrop räknade admission/städning, beräkning,
audit, sparning och ägd återläsning inom mättiden och yttre deadline.
Ordinarie slutreserv på 12 sekunder förblev densamma. En budget på 75
sekunder är därför inte detsamma som 75 sekunders uppmätt leveranstid.

65 sekunders budget gav cirka fem sekunder längre väntan; 75 gav cirka
15 sekunder längre väntan. Båda gav noll kronor besparing. Ingen timeout,
sänkt källa-/pris-/näringskontroll eller lättnad av användarkrav räknas som
en förbättring. Alla fem slut-audits och ägda återläsningar passerade.

[Maskinunderlaget](BUDGET-EVIDENCE.json) binder samma pris-/faktaversion,
request-/körkodshashar, tider och minnestoppar. Proven kördes isolerat med
4 GiB minnesgräns, skrivskyddade källor, nät av och befintligt driftlås.
Det är uppvärmda upprepningar, inte belägg för alla nya val, p95 eller
godtycklig samtidighet. Inga användarprofiler eller produktionsplaner ändrades.

Tillsammans med [de tidigare försöken](REPORT.md) är detta 35 godkända,
sparade och ägt återlästa menyer samt fyra historiska Malmöförsök som
blockerades av oförändrade priskontextkrav. De blockerade räknas inte som
lyckade leveranser. Båda offentliga kommunberedskaperna var fortsatt HTTP
200 med samma app- och pris-ID efter undersökningen. Ingen aktivering.

Driftstatusens senaste omladdningsförsök kl. 08:17 UTC avstod med
`operation_lock_held` medan testet höll det gemensamma låset. Det är
redovisat i maskinunderlaget; ingen manuell insamling/omkörning startades
för att ändra status. Testets låshjälpare avslutades efter serien.

Spårfältet `first_valid_request_seconds` i originalmetoden antar 60 s
yttre budget. Det används inte som tidmått för 65/75-s-proven; tabellens
väggtid är oberoende mätt runt hela anropet.

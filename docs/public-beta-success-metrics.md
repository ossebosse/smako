# Mätbara mål för de första 5–20 betaanvändarna

Dessa är första-betans beslutspunkter, inte permanenta KPI:er.

## Tillförlitlighet

- Minst 95 % av `plan_requested` ska följas av `plan_succeeded`.
- En enskild request-cold ska fortsatt ha mål under 10 sekunder och warm under 1 sekund; kall burst-kötid redovisas separat.
- Produktionsproxyns begränsade burst-SLA är 60 sekunder. En färsk c5-mätning gav 5/5 lyckade, 0 fel, p95 39,44 sekunder, vågtid 39,87 sekunder, 99,6 % CPU och 825,7 MiB peak RSS.
- Admission är 1 aktiv planerare + högst 4 köade. Fresh c10 betyder högst 5 admitted och snabba 503 + `Retry-After` för resten, inte bevis på skalbarhet för tio samtidiga kalla planer.
- Warm/upprepad interaktion ska ha median under 1 sekund i backendbenchmark.
- Inga provideranrop ska ske under normal planering.

## Förståelse och nytta

- Minst 70 % av testarna svarar att de förstod kärnvärdet utan muntlig förklaring.
- Minst 50 % svarar att de skulle använda tjänsten igen.
- Minst 70 % uppfattar inköpslistans butiks-/onlinekontext och antal förpackningar som tydliga.

## Datakvalitet

- Samla konkreta, sanningsenliga pris- eller sortimentsavvikelser där testaren faktiskt ser ett fel.
- Följ rapporter per plan, men sätt inget mål som uppmuntrar påhittade rapporter.
- Följ separat fel pris, saknad butik, saknad kampanj och ej hittad produkt.

## Operativ uppföljning

- Kontrollera dagligen: plan success rate, median/p95, felkoder, PriceUniverse-ålder och senaste refresh.
- Granska communityrapporter och feedback utan att exponera avsändaridentitet.
- Pausa nya testinbjudningar om PriceUniverse är STALE, readiness är röd eller planfel överstiger 5 %. `degraded` betyder att en äldre priskontext har uteslutits medan återstående aktuella källor fortfarande kan användas; följ då täckningsvarningen och reparera den felande källan utan att dölja den genom högre åldersgräns.

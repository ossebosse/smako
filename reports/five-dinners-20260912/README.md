# Fem middagar – evidens 2026-09-12

Slutlig appkod: e626ac0. Release: personal-v2-five-dinners-20260912c.

Slutacceptans: verified-frozen.json, runtime.json (aktuell serverdata, nätverk av), https/ (Chromium + WebKit på driftsatt kod). B5 kostar 677,43 kr i alla tre miljöerna.

regression.xml + final-focused.xml innehåller 250 distinkta godkända testfall (249 respektive 89 körda, överlapp). source-hashes.json verifierar release och körande container; deployment.json kontrollerar historik/driftlås; rollback.json avser nätverkslöst läskompatibilitetsprov. benchmark.json gäller oförändrad äldre basmeny.

tomato-qualification.json dokumenterar produktformer och vanliga alternativ. slv-1337.json är nytt aktiverat källunderlag för stekt torsk. Övriga slv-/review-filer är offentlig källgranskning, inte aktiverade nya kopplingar. profiles.json visar kandidatstrukturer.

Ej slutacceptans: frozen.json är avvisad utforskande körning före korrigerad tomatform. local-browser/ är ersatta lokala prov före sista korrigeringen. runtime-first.json är ett ogiltigt prov med ofullständig testmiljö, inte ett driftresultat. Behållna för spårbarhet; använd de tre slutliga proven ovan.

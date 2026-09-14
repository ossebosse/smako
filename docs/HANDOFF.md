# Smako – 14 september 2026

Live: `price-recovery-lund-20260914a` (app och scheduler).
[Återställningsrapport](../reports/smako-lund-price-recovery-20260914.md).

- Planering 22350 återställd: alla sex Lund-kontexter färska, samma universum på disk/i process `927c331c…f34f9e2`, health/ready 200. Gränser 36/48 h oförändrade.
- Exakt kvalificerad basrequest: 15 tillfällen/20 portioner, 40/30/20, max två butiker. HTTPS mobilvy 201/40,781 s efter omstart, 560,33 kr VERIFIED; byte 200/7,092 s. Noll externa källanrop. Ingen ny treprovs-prestandaacceptans.
- Willys-transportens fel rättat via befintlig driftcontainer/UID. Båda kontexter importerade med äkta observationer. Verkliga Windows-tasken återtestad: resultat 0; schema 01:30 oförändrat.
- Primats historiska ValueError är fortfarande oförklarat. Två isolerade kompletta 49-anropskörningar passerade även parsning/export/validering/context activation. Godkänd färsk export användes. Ny steg-/stack-/orsaksdiagnostik bevarar nästa fel; ingen specifik historisk Primat-fix hävdas.
- Obligatoriska kontexter kontrolleras vid aktivering, planering och ready. Driftstatus varnar vid 36 h och visar rebuild-/aktiveringsfel. Separata Coop-erbjudanden, Karhögstorg och Lidl-fel kvar enligt rapport.
- 139 tester PASS, Ruff/compileall PASS. Backup `20260914T123547Z`; samma VPS, Caddy och miljöfilens rättigheter bevarade. Föregående app är läskompatibel rollback; föregående schedulerbild sparad.

---

# Smako – 13 september 2026

Live: https://beta.smako.nu/personal · `personal-v2-fast-403020-20260913c` · appkod `98381e5`.
[Prestandaacceptans och reproduktion](../reports/smako-fast-combined-403020-20260913.md).
[Föregående kombinerade funktionsacceptans](../reports/smako-combined-403020-20260913.md).

- **30-sekundersmålet PASS.** Fryst request-kall beräkning 357,670 s (före n=1) → median 26,480 s (efter n=3). Slutrelease genom HTTP: 27,047 / 27,462 / 28,007 s, median 27,462 s, tre nya gäster och ingen färdig resultatcache.
- Middag 5×2 ≥40 g, frukost 5×1 ≥30 g, mellanmål 5×1 ≥20 g per portion. Totalt 15 tillfällen, 20 portioner, Blandad/Balanserad, max två inköpsställen gemensamt. Spårbara uppskattningar uttryckligen på enligt denna milstolpe. Inga extra kcal-, fisk-, eko- eller skafferikrav.
- Samma frysta priser/fakta ger exakt samma meny, kostnad 574,92 kr, variation och kravkontroller. Kandidatpooler 95/5/5 råa och 10/2/2 kvalificerade, sökbredd/policy/prismotor oförändrade. Request-lokal exakt näringsmemoization, ren textcache och hashverifierad offentlig faktacache ersätter upprepade beräkningar. Admission omfattar faktisk arbetstråd även vid avbrott.
- Processkall ASGI till resultat 48,537 s; varm HTTP 27,124 s. Mobilformulär via HTTPS 28,760 s med laddad katalog; första efter omstart 33,224 s. Byte dag fyra 4,562 s, hel korg 584,92 kr och alla 40/30/20-krav kvar. Browserprov 390×844; fysisk telefon/mobilnät inte mätt.
- Två samtidiga isolerade planer 27,301/55,544 s; en aktiv/en i kö, sök/health <0,16 s, korrekt ägarisolering, inga kvarvarande arbetare. Dubbelklick gav en POST; navigation/timeout gav inga automatiska retries. Befintliga 600/540 s timeoutgränser oförändrade.
- 477 distinkta fokuserade regressioner passerade; 79 berörda upprepades efter sista adapterändringen. Ruff/compileall PASS. Separata A/B/C, uppskattningar på/av, ändrat protein/portioner/skafferi, paket/kampanj, färskhet, köp/revisioner och isolering kontrollerade. Strikt A/D fortsatt datablockerat; B/C fungerar utan uppskattningar.
- Backup `20260913T194832Z`; 164 äldre revisioner hashbevarade, nu 168. Health/ready 200; scheduler och prismanifest oförändrade. Läskompatibel rollback till `personal-v2-fast-403020-20260913a` verifierad utan databasrestore. Mellanbild b aktiverades aldrig.
- Kvar: gemensam näringsalternativ-/paketsökning (7 335 korgoptimeringar), första råfaktaladdning, befintligt begränsad sökning, strikt middagsunderlag och okänd slutvikt. Inga nya källanrop, observationstider, recept, OIDC-, Willys-task/relay-, server- eller tjänsteändringar.
- Tidigare [fiskfria acceptansen](../reports/smako-fishfree-five-dinners-20260913.md) är historik och får inte ersätta 40/30/20-profilen.

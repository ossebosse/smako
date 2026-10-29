# Coop-fält rättat och aktiverat 29 oktober 2026

Coops nya `environmentalCode="A"` är granskat och stöds i parser v7.
Fyra Lund- och sex Malmöbutiker har nu färska, kvalificerade och laddade
erbjudanden. Dashboarden visar lyckad insamling med noll misslyckade återförsök
för dessa butiker och totalt 2925 användbara kampanjpriser.

Kod `1d092bc85f9156e092ab928fba2a531ba7e04107`, main-merge `d15f5f4ab0494b46496339c4366a844b0fb0dc91`,
[PR 43](https://github.com/ossebosse/smako/pull/43),
[grön CI](https://github.com/ossebosse/smako/actions/runs/40825672342).
[Grön main-CI](https://github.com/ossebosse/smako/actions/runs/40826387252)
bekräftar den integrerade koden.
Båda processerna använder BUILD_ID `source-ops-1d092bc85f91` sedan
`2026-10-29T06:11:42.343421+00:00`. App-image `sha256:64dfe8c387fc7e27f32ea2d1af858a891e20095993454a07a4b6ee84f67c27b6`;
scheduler-image `sha256:6a11786a93f0f7b4b9028dc53234197231c1c1c3fe23c8a93eddd19086a23527`.

Fyra granskade runtimefiler patchades mot de faktiska basbilderna.
1002 övriga appfiler och
997 schedulerfiler verifierades oförändrade.
Versionslistan accepterar uttryckligen v7 samt tidigare granskade versioner;
okända versioner, fält, värden och typer är fortfarande blockerade.
Fältet bevaras som opak metadata och härleder inga ekologiska fakta eller
köpvillkor. Ingen fysisk Coop-butik tilldelas onlinebaspriser från 730400.

Backup `20261029T060304Z` validerades före bytet under det
gemensamma driftlåset. Tidigare planer, profiler och konton bevarades;
miljön ändrades endast i BUILD_ID. Datamounts och båda aktiva prismanifesten
bevarades under kodbytet. Vanlig lagringsretention är complete efteråt.
Endast den verifierat sysslolösa cronprocessen byttes; inga insamlingsjobb
avbröts. Den befintliga serverpolicyn måndag/torsdag 03:17 svensk tid består,
liksom tidigare ICA-, recept- och beräkningsarbete.

Färska offentliga svar hämtades med vanlig transport och kvalificering.
De sparade svaren omkvalificerades utan nät i slutkandidaten: identiska
kvalificeringsbeslut, oförändrade databaser och verkliga observationstider.
Slutkandidatens ordinarie OWN-/Coop-läsare accepterade alla tio butiker.
Efter aktiveringen användes befintliga kommunala referens-/urvalsfunktioner
under driftlåset. Normal managed refresh byggde, validerade, publicerade och
laddade båda prisunderlagen; ingen ytterligare extern prishämtning behövdes.
Malmös laddning bekräftades av ordinarie återförsök 06:47:11 UTC efter ett
fördröjt HTTP-kvitto. Den slutliga kontrollen verifierade både laddade manifest,
samtliga tio nya källsnapshots, oförändrade råhashar och observationstider.
Lunds refresh har status degraded/stale på grund av äldre bevarade baskällor;
de fyra reparerade butikernas nya kampanjer är laddade och användbara.

| Kommun | Butik | Aktiva kampanjpriser | Verklig observation UTC |
| --- | --- | ---: | --- |
| Lund | Coop Värpinge Lund (3659) | 278 | 2026-10-29T05:42:37.427839Z |
| Lund | Coop Veberöd (1158) | 315 | 2026-10-29T05:42:44.935849Z |
| Lund | Coop Klostergården (3820) | 278 | 2026-10-29T05:42:53.345792Z |
| Lund | Coop Mårtenstorget (3813) | 315 | 2026-10-29T05:43:01.210499Z |
| Malmö | Coop Värnhem (3823) | 295 | 2026-10-29T05:44:06.891419Z |
| Malmö | Coop Norra Parkgatan (3816) | 278 | 2026-10-29T05:44:14.558687Z |
| Malmö | Coop Kirseberg (3834) | 278 | 2026-10-29T05:44:22.145417Z |
| Malmö | Coop Bulltofta (3815) | 315 | 2026-10-29T05:44:29.861671Z |
| Malmö | Coop Oxie (3819) | 295 | 2026-10-29T05:44:38.154462Z |
| Malmö | Coop Limhamn (3830) | 278 | 2026-10-29T05:44:45.747690Z |

Laddade pris-ID:n:

- Lund: `price-universe:9e45dc8ffb89a769d2fe0ee8d13488aa692ff67448a50885503ad112f5c79205`
- Malmö: `price-universe:e8ed718b6d66124375aac4b7ec42b70ec6f80f7f32cca86f1f65a22b960d0289`

Readiness och autentiserad dashboard verifierades per kommun och butik.
Admin utan autentisering gav 401. Lokal verifiering: 46 tester med spärrat
externt nät och inga åtkomstöverträdelser, 36 ytterligare Coop-tester,
Ruff, compileall och exakt fil-/konfigurationsjämförelse av båda bilderna.
Receptförberedelsernas metodhash är oförändrad; inga receptfiler ändrades.

Separata källfel återstår för Malmö Central, Kornettsgatan, Djupadal,
X:-tra Nydala och Online Syds katalogkontrakt. Deras felhistorik och tidigare
godkända underlag har bevarats. Windowsreläets administratörskrävande
registreringsbyte omfattas inte av denna Coop-rättning.

Maskinläsbara kvitton finns i [EVIDENCE.json](EVIDENCE.json).

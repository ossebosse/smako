# Rättning efter arkitekturgranskningen, 2026-10-24

Fortsättning på [den oberoende granskningen](sol-architecture-review-20261024.md)
och [arkitekturbeslutet](../CODEX-SOL-ARCHITECTURE-20261023.md).
Runtimekod: `9162f0fe5800a5c6ce52ac18cbbefa1a044ecc94`, i
[PR #8](https://github.com/ossebosse/smako/pull/8).
Standarderna är fortsatt `legacy` och `library_merge_generations=False`.
V1 är opt-in. Ingen produktionsaktivering eller schemaändring ingår.

## Rättade granskningsfynd

**P1 – sparad menyhistorik:** båda cachevägarna tar nu hänsyn till nya
menyidentiteter i ägarens sparade planrevisioner. Förberedda vyer binds till
identiteterna, inte bara explicit `previous_menus`. Det sparade certifikatet
gör inte sin egen vy inaktuell. Samma meny kan sparas igen utan att orsaka
ny förberedelse.

Vid ändrad historik återanvänds publiceringarnas certifikat och kvalificering,
men de nya kandidaterna måste genomgå aktuell gemensam kassakontroll. Vinnaren
uppdateras efter kontrollen. Den tidigare giltiga vinnaren behålls om den nya
menyn är ogiltig. Publiceringarnas sökningar körs inte om för enbart nya
historikidentiteter. Ägarbindning, den beständiga raderingsepoken och befintliga
läsgränser bevaras; inga privata identiteter läggs i offentliga artefakter.

**P2 – Axfoods basrelease:** CLI kontrollerar att staging är ny före första
staging-skrivningen, läser den godkända katalogens bevis till minnet, kopierar
den validerade basens dokument och journaler och skriver därefter det nya
katalogbeviset. Befintlig orelaterad staging avvisas före bevis-skrivningen.
Återupptagning använder samma run-id utan att ange `--base-release` igen.

Permanenta regressioner täcker båda menycachevägarna med en giltig billigare
meny och en ny meny som underkänns i checkout, ägargränsen, oförändrade
identiteter, första Axfood-körning, godkänd katalog plus bas, avbrott och
återupptagning, bevarade LKG-tider och negativa svar samt befintlig staging.
Axfood-proven använder riktiga arkiv/publiceringar och isolerade DB-/lease-
och klientdubblar; de gör inga handlaranrop. Granskningens gamla bugprober
är historiskt underlag för den granskade revisionen, inte acceptansprov för
den rättade koden.

## Oberoende fullbibliotekskandidat

Den gamla per-paket-sökningen körs också en gång för varje saknad exakt
publicering/kontext. Samma kohortbyggare används i legacy och förberedelsen;
förbättringsspåret behåller sina tidigare fasta budgetar. Varje sökning har
egen seedbehållare. Endast färdiga kandidater förs vidare till befintlig audit
och jämförelse med referens och föregående giltiga vinnare.

Förberedelsens tid, utvärderingar och föreslagna kassasumma finns per
publicering i `legacy_full_library_preparation`. Kostnaden ingår även i hela
anropets tid. En förberedd menyträff kör inte om dessa sökningar. Riktade
kontraktsprov visar att en billigare giltig legacy-kandidat kan vinna, medan
en underkänd kandidat eller en sökmiss inte ersätter en giltig meny.
Detta ger inget bevis på global optimalitet.

## Verifiering

Samlad riktad offlinekörning: **126 PASS**. Ruff, compileall och diffkontroll
passerar. Full [PR-CI 40064498355](https://github.com/ossebosse/smako/actions/runs/40064498355)
på `9162f0f`: **3 106 PASS, 10 XFAIL, 53 SKIP**, inklusive Chromium/WebKit.
Antalen har räknats från CI:s progressrader eftersom dess dubbla quiet-flagga
utelämnar den vanliga slutraden. De 53 skippen har befintliga evidens-/miljöskäl.

```powershell
.venv/Scripts/python.exe scripts/verify_offline.py backend/tests/test_verified_menu_search.py backend/tests/test_owned_planner_artifacts.py backend/tests/test_library_publications.py backend/tests/test_library_search_cohorts.py backend/tests/test_incremental_library_search.py backend/tests/test_axfood_detail_archive.py backend/tests/test_axfood_product_details.py backend/tests/test_axfood_detail_cli.py grocery_data/tests/test_axfood_catalogue_queue.py -o addopts='' -q --tb=short
```

## Omprov av Malmö/fördelning, 5 000 recept

Mätningen använder exakt de frysta
priserna, fakta, requesten, klockan och biblioteket från
[det tidigare motexemplet](verified-reference-axfood-20261023/failed-gate.json),
men samma nya plannerkod i båda policyarmarna. Två CPU och 3 GiB inklusive
swapgräns, en isolerad nätspärrad worker och en ny syntetisk PlanStore används.
Ingen skrivbar produktionsdatabas monteras.

| Policy | Kassasumma, tre körningar | Anropstid, sekunder |
| --- | --- | --- |
| Legacy | 988,32 / 988,32 / 988,32 kr | 253,50 / 101,82 / 98,64 |
| V1 | 988,32 / 988,32 / 988,32 kr | 740,87 / 8,44 / 8,37 |

Alla sex menyer klarar audit och har samma semantiska hash, även mellan
policyarmarna. Det tidigare motexemplets +3,90 kr är därmed undanröjt i
denna cell. Första v1-anropet förbereder elva publiceringar; legacy-spåret
står för **215,41 s och 9 517 utvärderingar**, inkluderade i 740,87 s.
Förberedda träffar kör inte om detta arbete.

Det är en process med legacy först, v1 därefter och delad offentlig
förberedelse. Första v1-anropet är en privat certifikatmiss, inte en separat
kall process. Peak RSS är 2 918 297 600 byte efter legacy och 3 043 393 536
byte efter v1; värdena är processens kumulativa toppar. Cgroup-peak för
den samlade processen är **3 120 193 536 byte, cirka 2,906 GiB**. Ingen OOM,
exit 0. 3 GiB-taket höll i detta prov; målet 2,5 GiB nåddes inte.
Det bevisar inte minnesbehovet för en isolerad kall v1-process eller
fleranvändarkapacitet.

En **ny process med samma varma diskcache och beständiga certifikat** gav
988,32 kr och samma meny/hash i alla tre anrop: **32,01 / 8,13 / 8,17 s**.
Alla tre var förberedda menyträffar; elva publiceringars sökning behövde inte
återskapas när processens RAM försvann. Hela containerkörningen inklusive
uppstart och tre plananrop tog **98,60 s**. Dess cgroup-peak var 2 833 084 416
byte, cirka 2,639 GiB, utan OOM. Det är inte ett prov med kall OS-disk.

Samma kod, fakta, priser, request och klocka med 262-receptsbiblioteket gav
996,22 kr i alla tre anrop: **14,02 / 8,38 / 8,00 s**. Första anropet
återanvände 262-certifikatet från den beständiga kedjan men behövde skapa
sin kvalificeringsvy; de två senare var förberedda menyträffar.
5 000-anropens långsammaste upprepning i den nya processen delat med
262-anropens snabbaste upprepning är **1,0214**, under målet 1,25 i denna
profil. Detta är två upprepade mätningar per storlek, inte en full matris
eller ett generellt latenslöfte.

Samtliga **tolv planer** klarar audit. De tre isolerade containrarna avslutades
utan OOM och har tagits bort; underlagen är bevarade. Det versionsbundna
[maskinunderlaget](sol-architecture-fixes-20261024/replay-summary.json) innehåller
indata-/biblioteks-/metodhashar, tider, minne, menyhashar och containerutfall.
[Exakta kommandon](sol-architecture-fixes-20261024/commands.json) och
[5 000-wrapper](sol-architecture-fixes-20261024/wrapper_5000.py) respektive
[262-wrapper](sol-architecture-fixes-20261024/wrapper_262.py) anger monteringen
och den pinnade referensen. Käll-ZIP:ens SHA-256 är
`0cc7e09f0bc383cbde8335878af2721589ab93c0611295ed715c5e03590b4357`.
Fulla mätfiler och körloggar finns i `.local/review-fixes-20261024/evidence/`
och `/opt/smako/evidence/sol-architecture-fixes-20261024-9162f0f/`.

## Kvarstående leveransgrindar

Den kända prisluckan är rättad och återstart samt upprepade 262/5 000-anrop
är mätta för Malmö/fördelning. **Skalningsuppdraget är inte fullständigt
godkänt:** minnesmålet 2,5 GiB missas, hela 252-cellsmatrisen är inte omkörd,
övriga städer/profiler och isolerad kall v1-kontext/kall OS-disk återstår.
Tidigare matrisunderlag är bundet till sina tidigare kodversioner. Fortsätt
minnes-/kallstartsarbetet separat före ny full kvalificering; höj varken
standardläge eller samtidighet med hänvisning till detta avgränsade prov.

Axfoods tidigare partiella faktarelease och inaktiva reader-paket är separata
underlag. CLI-rättningen aktiverar inte ett nytt runtimevärde eller ett nytt
automatiskt insamlingsschema. Arkivets principgodkännande gäller fortsatt.

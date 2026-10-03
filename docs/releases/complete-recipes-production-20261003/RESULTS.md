# Nya receptlagret aktivt på beta.smako.nu

Aktiveringen och publika knapp-prov är slutförda. Slutkontroll: **2026-10-03T15:38:23.456862+00:00**.
Den vanliga betasidan använder runtime **17a9c1330dcc72ff9750a3fa680fa6982f7ed99b**,
BUILD_ID **complete-recipes-17a9c1330dcc** och **COMPLETE_RECIPES_ENABLED=true**.
Ingen Git-push, prisinsamling, schemaändring eller separat testadress användes.

## Här finns de nya valen

- På [beta.smako.nu](https://beta.smako.nu): öppna menyformuläret och välj
  **Receptstil → Välj receptläge → Genomarbetade middagar**.
- På [Personlig planering](https://beta.smako.nu/personal): öppna
  **Välj måltider och skapa plan** och välj samma receptläge.
- Under **Dina middagar** finns **Matkök och inspiration**, ingrediensintervall,
  högsta uppskattade tid, proteinmål, fiskval och tillåtna variationer.
- **Befintliga vardagsrecept** finns kvar. Billigast, Balanserad och Varierad
  behåller sin betydelse. Uppskattade köp och medgivande till uppskattad näring
  är separata val; detta kontrollerades även i de riktiga formulären.

## Aktivering och bevarat tillstånd

Före bytet körde produktion `74c9077001b3084317f36630fd38ce48e4663473`.
Dess 419 runtimefiler matchade release-manifestet; inga senare appfixar fanns
att förlora. Kandidatpaketets 651 manifestfiler verifierades lokalt och på
servern. Den installerade imagen verifierades med fullständigt ID och 644
paketbundna backend-/grocery-/deploy-filer utan källkodsmounts.

- Paket: `smako-server-17a9c1330dcc.zip`, 2 739 005 byte.
- Paket-SHA256: `d3327b9137d4310707118b5272bc826ed0403ebd6d0c0ab935bb1196efee060a`.
- Aktiv image: `sha256:99bf3bfcb4f395ec1a06df23649e0241903d52bb5bba40ca4336abbd2bbecc35`.
- Beständig override: `/opt/smako/overrides/complete-recipes-17a9c1330dcc.yaml`.
- Befintlig `/opt/smako/compose` behåller sina ursprungliga Compose-filer och
  lägger denna override sist. `current`-länken och tidigare basfiler är kvar.

Upplöst konfiguration jämfördes exakt: endast appens image, BUILD_ID och
COMPLETE_RECIPES_ENABLED skiljer sig. Appen återskapades med `--no-deps`,
`--no-build` och `--pull never`. Scheduler och proxy har oförändrade container-ID,
image-ID och starttider. Collector, migrate, backup-tjänst, Windows-relä,
prisinsamling, scheman, femkällorspolicy och kommunurval ändrades inte.

Gemensamt driftlås användes. Appens trådar/CPU kontrollerades som vilande före
backup och omedelbart före respektive återskapande; HTTP-telemetrin granskades.
Inga pågående testjobb avbröts. Ordinarie online-SQLite-backup, integritetskontroll,
aktiva prisartefakter och SHA-manifest sparades privat före båda stegen:

- Flagga av: `backups-off/20261003T150917Z`, manifest-SHA256
  `afabc94006460754a1df41268026c6661bd492b3bef665b653c7c11d178523e6`.
- Flagga på: `backups-on/20261003T152044Z`, manifest-SHA256
  `bba22b11b0bc799e9689782b319ce472223abe96859b68966dd34eadd9cad919`.

Backuproten är `/opt/smako/evidence/complete-recipes-20261003`, skyddad och
utanför Git. Ingen äldre databas återställdes över aktuell data.
Alla **195 ursprungliga revisioner** är oförändrade;
slutkontrollen omfattar **207 revisioner**, samtliga läsbara
genom befintlig PlanStore-materialisering. Ursprungliga personliga tillstånd
är bevarade. Äldre testägda publika/personliga planer lästes även via HTTPS med
samma ägare efter flaggbytet; både innehåll och sparade formulärval stämde.

## Verkliga knapp-prov på produktion

Med flaggan av passerade publikt äldre menyflöde (101,781 s) och personlig
15/20-planering (283,296 s, 401,35 kr). Den senare hade 15 måltider/20 portioner
och minsta orundade protein 41,55/35,5/22 g, vilket uppfyller 40/30/20-kraven.
Readiness, image-ID, gamla planer och ägarskydd kontrollerades före aktivering.

Efter aktivering användes vanliga formulär och menyknappar, utan mockade anrop:

| Knappflöde | Generering, s | Byte, s | Omräkning, s | Initialt inköp, kr | Resultat |
|---|---:|---:|---:|---:|---|
| chromium-mobile-public (complete) | 101.797 | 18.953 | 13.282 | 738.17 | PASS |
| webkit-mobile-public (complete) | 92.610 | 17.032 | 12.329 | 738.17 | PASS |
| webkit-desktop-personal (complete) | 92.797 | 18.11 | 13.281 | 738.17 | PASS |
| chromium-desktop-public (legacy) | 102.688 | – | – | 168.55 | PASS |

De tre kompletta fallen skapade fem middagar för två, grekiskt/mexikanskt,
10–15 ingredienser och högst två butiker, dessutom högst 40 minuter och minst
40 g protein. Uppskattade köp och näringsuppskattning valdes uttryckligen var
för sig. Genereringen återanslöts efter omladdning; dubbelklick skapade ett jobb.
Receptbyte valde en annan grundrätt och omräkning skapade en separat revision.
Revision 1–3 återlästes oförändrade. Komponenter, mängder, instruktioner,
inköpslista och kvalitetsmärkning kontrollerades i DOM och faktisk layout.
Inga JavaScript-/nätfel eller horisontella layoutöverskridanden observerades.
Annan ägares plan och jobb nekades. Mobilvyer är emulerade; ingen fysisk iPhone.

Det lokala testverktyget rättades för äldre svar med `personal=null` och för
ordningen att öppna nästlade formulärdetaljer. Dessa var verktygsfel, inte
appändringar; det äldre publika flödet kördes också igen efter aktiveringen.
WebKit/personligt fick en klick-timeout efter lyckat receptbyte. Samma ägare
öppnade sin sparade revision 2 igen och valde **Min plan**. Den vanliga synliga,
aktiverade omräkningsknappen fungerade utan force-klick eller DOM-ändring och
skapade revision 3; alla tre revisioner återlästes identiskt. Både första
verktygsutfallet och fortsättningen har bevarats, utan ändrad appruntime.
Ingen syntetisk receptåterkoppling skickades till produktion.

## Menyn som faktiskt skapades

Publika Chromium-provet gav **cirka 738.17 kr** i inköp,
med beräknad använd kostnad **444.93 kr**. Butiker:
Coop Online Syd, Hemköp Lund Brunnshög.

| Rätt | Ingredienser | Uppskattade minuter | Protein per portion, g |
|---|---:|---:|---:|
| Krämig majs- och bönsoppa med ostquesadilla och tomatsalsa – större huvudportion | 14 | 37 | 40.172 |
| Mustig linschili med vita bönor, ris och limeyoghurt – större huvudportion | 13 | 40 | 43.533 |
| Kycklingbowl med ris, majsröra, limeyoghurt och tomatsalsa | 14 | 40 | 52.455 |
| Citronkyckling med spenatris, feta och gurksallad | 12 | 40 | 55.489 |
| Spenatris med kikärtor, feta och citronyoghurt | 12 | 35 | 41.515 |

Protein visas här avrundat; godkännandet jämförde orundade värden. Näringen är
märkt `ESTIMATED`, köpstatus `VERIFIED_WITH_ESTIMATES`.
Det är lägsta hittade inköpskostnad inom valen, inget bevisat globalt optimum.
Ingen allergensäkerhet eller fysisk provlagning påstås. Fulla receptmängder,
instruktioner, produkter, paket, källreferenser, pant och rester finns i
[LIVE-MENU.json](LIVE-MENU.json). Planerade rester har inte bokförts som skafferi.

Aktuellt produktionsunderlag och verklig klocka användes. Köpdatum är
**2026-10-03**, universe `price-universe:a2eb6ab5ffec325392ad98c69e6483a3b901312359c5c659673ea7da5fadd0c6`. Inga frysta
testpriser, testdatabaser eller replayinställningar kopierades till produktion.
Färskhetsgränserna är fortfarande 36/48 timmar. Beloppen är observerade utfall,
inte krav hämtade från historiska testmenyer eller löften för framtida köp.

## Återgång och bevis

Vid ett senare fel: sätt endast `COMPLETE_RECIPES_ENABLED` till `"false"` i
samma beständiga override, verifiera upplöst konfiguration och återskapa enbart
appen i **samma nya image**, efter att pågående jobb slutförts. Bevara all aktuell
lagring och alla revisioner. Följ [receptlagrets aktiveringsanvisning](../complete-recipes-20261002/ACTIVATION.md).

Kandidatens dokumenterade källluckor och söktidsbegränsningar kvarstår; inga
kvalitetsskydd sänktes för aktiveringen. [Sanerade aktiveringsbevis](ACTIVATION-RESULT.json)
innehåller exakta identiteter, tidsvärden, hashbindningar och publika readinessdata.
Råa svar, ägaridentiteter, cookies, full konfiguration och databaser ligger privat
utanför Git. Ingen Git-push har gjorts.

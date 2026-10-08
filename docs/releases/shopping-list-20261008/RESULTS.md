# Fristående inköpslista – separat kandidat

Måltidskandidaten är aktiverad på beta enligt [aktiveringsrapporten](../meal-activation-20261008/ACTIVATED.md).
Den här funktionen är **inte aktiverad**. Runtime `38a85dafa18a1fbc63834649fb6af38990bf33ef`.

## Funktion

- En egen lista utan recept, eller extra varor i samma korg som måltiderna.
- Specifika produkter med varumärke och förpackning, utan priser i sökförslagen.
- 18 interna generiska förslag. Exempel: `kaffe 500g` och `spaghetti`.
  Kaffesort bekräftas; mängder tolkas utan någon generell ml/g-omräkning.
- Två till åtta uttryckliga alternativ per rad. Befintlig veckokorg prövar
  dem mot hela inköpet, butikstaket och köp-/produktvillkoren. Lägsta hittade
  kostnad inom valen; ingen bevisad global optimalitet.
- Ägarbunden lista och högst 50 vanliga val sparas i befintlig PlanStore.
  Borttagning, tom lista, mängdändring, omräkning och oföränderliga revisioner.

Verifierat gemensam produktidentitet dedupliceras. Identiska namn/förpackningar
utan belagd gemensam identitet visas som en grupp: välj en exakt butiksvara
eller godkänn gruppen som alternativ. Namnlikhet kopplar inte automatiskt priser.
Alla alternativ täcker samma uttryckliga behov. Produktens egna villkor och
allergener bevaras; tidigare generiska/exakta anrop behåller sin betydelse.

## Verifiering

130 riktade backendtester PASS mot den slutliga imagen: korg, audit, privata
revisioner, kontokoppling, jobb/status, incidentspårning och de nya funktionerna.
Ett tidigare variantfel reproducerades mot förekoden och passerar efter rättning.
Ett test bevisar helkorgsvalet: en lokalt dyrare alternativvara ger total 55 i
stället för 70 med butikstak ett. Det är ett kontrollerat test, inte dagens offert.

Webbläsarutfall och mättider finns i EVIDENCE.json. Riktiga knappar, dubbelstart,
serverlagring, andra ägares nekade GET, uttrycklig omräkning och faktisk isolerad
appomstart används. Chromium kombinerar en middag med samma extravaror och
återansluter efter omladdning. WebKit prövar tomt utkast och uttryckligt godkännande
av en grupp vars gemensamma produktidentitet inte kan beläggas.

Tester använder den ordinarie planeraren och historiskt berikad replay från
4 oktober, oförändrat underlag/fakta. Mjölk och spaghetti är verkliga produktval
i underlaget. Blöjalternativ är verifierade i ett avgränsat test; ingen aktuell
Libero/Pampers-offert påstås. Två CPU, 3 GiB, befintlig admission ett tungt jobb.
Mobil Chromium/WebKit är inte fysisk telefon. Ingen ny prisinsamling gjordes.

Tidiga harnessfel och strikta FAIL med avbrutna anrop bevaras under privat
`.local/shopping-list-20261008/`. En senare PASS ändrar inte dessa till PASS.
Slutprovet väntar in sökförslag innan nästa inmatning; det är inte ett fullständigt
prov av alla möjliga snabba inmatnings-/navigationsavbrott. En snäv testklassificering
för statusavbrott kräver exakt request, livscykel och återanslutet jobb; andra fel
får inte undantas. Separata positiva och negativa klassificeringsprov finns.

## Uppmätta körningar

Slutlig fristående lista: 5,000 s Chromium och 5,266 s WebKit till resultat.
Ny beräkning tog 2,34–2,95 s i de fem små listkörningarna; kö under 0,1 ms.
Kombinationen efter processomstart tog 87,172 s till resultat, varav 85,188 s
beräkning. Det är inte ett prov under 60 s eller en generell prestandagaranti.
Processens högsta uppmätta RSS var 1 451 968 KiB. Inga dubbla beräkningar:
sex avsiktliga jobb, exakt en tung beräkning per jobb i servermätningarna.
9 snäva positiva/negativa testharnessprov kontrollerar statusavbrottsklassificeringen.

## Konto och kvarstående gränser

Listan följer befintlig verifierad kontokoppling och privat radering. Detta är
backendtestat. Betan saknar konfigurerad OIDC-inloggning; liveproven använder
separata gästsessionsidentiteter. Riktig kontoaktivering är därför ett eget
konfigurationsbeslut, och funktionen lovar inte synkronisering mellan enheter
innan sådan inloggning är tillgänglig.

Ingen ny generell motor för blandade SKU-storlekar. Okända produktfakta stoppar
fortsatt berörda val. Inget av recepten, prisinsamlingen, reläet, schemana eller
36/48-timmarsgränserna ändras av detta paket.

# Exakta källbelägg och kvarstående luckor

## Coop fysisk Scan 65

Två avgränsade offentliga butikshämtningar via befintlig browsertransport,
10 oktober. Inga nya fullkataloghämtningar och ingen produktionspublicering.
Originalsvaren ligger gzip-komprimerade i
`grocery_data/tests/fixtures/comparability-20261010/`; dekomprimerad hash kontrolleras i regressionen.

| Butik | Endpoint | Råsvar fångat UTC | SHA-256 | Byte |
| --- | --- | --- | --- | ---: |
| Värpinge 3659 | `https://external.api.coop.se/dke/offers/sorting-groups/216526` | 2026-10-10 13:57:03.334132 | `33a0795a63aa012ec5aa443ef7c8ce2e7b82dc3ce78cd3c11efbb8a6bb7f9fc0` | 580 969 |
| Klostergården 3820 | `https://external.api.coop.se/dke/offers/sorting-groups/106435` | 2026-10-10 13:57:08.137992 | `3f109dcea2559f7b8fcc0ccbe9a0c4b8b54606b7347d16eb65d8b29793c4ab6c` | 583 105 |

Transportens omslutande RawFetch slutfördes 13:57:04.993395 respektive
13:57:09.771907 UTC. Det är skilda loggningspunkter, inte samma tidsstämpel.
Replay behåller dessa tider. Parserns `source_sha256` avser det omslutande
RawFetch-dokumentet; originalets responsehash ovan redovisas separat.

Förekod f00 stoppar Värpinge på `priceInformation.buyAmount`, `payAmount`,
`claim` och Klostergården på `row.weeklyTip`. De första tre tillhör
**Underkläder**, inte Scan. Autentiska värden: 3 (int), 2 (int),
`Billigaste på köpet` (str). `weeklyTip` är bool och styr veckotipsmarkering;
pris, butik, giltighet och kampanjvillkor måste fortfarande vara verifierade.
Fel typ, null där bool/int krävs och andra okända fält stoppas fortsatt.
Köp 3 betala för 2 kan inte värderas utan variantpriser: 40 sådana produktposter
per butik bevaras blockerade med `buy_x_pay_y_variant_prices_unverified`.
Betala-antalet blir aldrig priset 2 kr.

249/250 produkter parsas; 160 i vardera butik kvalificeras med befintligt
kontrakt. Scan-kampanj-ID: `4272-36550-1072136` / `1273-36550-1072136`.
Källans produkt-ID `2320321600009` behandlas som opakt ID, inte bevisad GTIN.
Medlem 65 kr/kg, cirka 1 kg, max 2 per hushåll, 5–11 oktober. Separata
butiker bevaras; deras liknande kampanjer gör dem inte till samma prisområde.

## Återanvänt mängd- och kampanjunderlag

Små autentiska utdrag med tidigare råfilreferens, hash och hämtningstid finns
som `product-*.json` i samma fixturekatalog. Ursprunglig full prisartefakt:
`price-universe:50c0bb0e83de94803b9eb6d06576cbe653e29a5f5d7a43abc5af9117c721cd5a`,
SHA-256 `a7255fb2ffeb810ff883c1247e1be65a59d5291ca2a858e6cbb059c6a3456f6f`.
Fakta ur sparade svar återtolkas; observationer föryngras inte.

## Konkreta nästa källärenden (inte lösta genom antaganden)

| Fall | Redan kontrollerat | Behövs för bredare användning |
| --- | --- | --- |
| Hemköp Krispsallat `100565103_ST` | Sparat produkt-JSON; styckpris 23,61, jämförpris 59,03/kg | Källbunden ätbar/nettomängd för exakt vara; inte division av avrundade priser. |
| Willys Shi-take `101326484_ST` | Sparat JSON; text `150` utan enhet, ingen medelvikt | Uttrycklig enhet och nettomängd för just varianten. |
| Coop aluminiumfolie GTIN7340011372356 | Källtext 10MTR och 10000 Millimeter | Generellt separat längdbehovskontrakt om användare ska optimera meter; hela paket fungerar nu. |
| ICA Chips/Sverige-/Fullkornspasta; Willys Crunchy | Sparade kampanjrader med flerpris och öppet variantval | Exakta ingående SKU:er, respektive nettomängd och deklaration för recept/näring. |
| Andra viktkampanjer med köpgräns | Samma inventering och strikta mängdkontrakt | Belagd gränsenhet och beställningssätt; nytt stödd kontrakt får inte gissas från rubrik. |
| Coop Underkläder köp 3 betala 2 | Fulla nya butikssvar, ovan | Kvalificerade deltagande varianter och individuella priser för billigast-gratis. |
| City Gross | Ingen aktuell kvalificerad kontext i artefakten | Verifierad butik-/kanalbunden källa via ordinarie godkänd väg före produktbedömning. |

Mängd-/köpbarhet är inte närings- eller allergengodkännande. Saknade
produktdeklarationer för recept förblir separata kvalificeringsstopp.

# Varför Scan-erbjudandet saknades

## Belagd kedja

Coop Värpinge Lund, fysisk butik `3659`, ledger `216526`, har i det sparade
råsvaret ett kort med **Sverige/Scan, Färsk fläskytterfilé, ca 1 kg,
65 kr/kg medlemspris, max 2 st/hushåll**. Kortet är `cards[2]`.
Detta kompletterar den tidigare utredningen som bara verifierade Online Syd.

- Snapshot `2e0697b37b32418db0ae439263bf77c6`, scope `lund`, avvisad.
- Rå-ID `8be3ac4751d44c5799afc2f87abe3b1c`.
- Verklig hämtning: **2026-10-09 13:30:40.294974 UTC**.
- Råfil: `coop/3659/2e0697b37b32418db0ae439263bf77c6/20261009T133040294974Z_0000_rendered_offers_page_b45bc9ba.json`.
- 12 670 byte, SHA-256 `b2a497fed951a9f7da34dc4ab14863e2772145ff80211f59705b996ca738252b`.
- Sida: https://www.coop.se/butiker-erbjudanden/coop/coop-varpinge-lund/
- Observerat strukturerat endpoint: `https://external.api.coop.se/dke/offers/sorting-groups/216526`, HTTP 200.

`structured_offers` innehåller `public_structured_schema_unrecognized` och
`new public offer fields require schema review: priceInformation.buyAmount,
priceInformation.claim, priceInformation.payAmount`.

`sanitized_response` i `grocery_data/app/connectors/coop/structured_offers.py`
avvisar fälten eftersom de inte ingår i `_PRICE_KEYS`. `capture_public_response`
sparar felkoden och fältnamnen men inte den avvisade strukturerade datan.
`parse_structured` återger därför schemafelet utan produktrader.
`CoopParser.parse_catalog` gör uttryckligen `continue` efter denna väg;
sidkortens 65 kr/kg används inte som reservpris. Snapshoten publicerades inte.
Den obligatoriska femkällorsreadinessen kan samtidigt vara grön: dessa fysiska
kampanjer är kompletterande och skilda från basen Coop Online Syd.

## Vad som inte är belagt

Det historiska arkivet innehåller inte de tre nya fältens värden, typer,
fullständiga JSON-index eller kampanjidentiteter. Felet är inte bevisat ligga
på just Scans strukturerade rad: ett annat erbjudande kan ha stoppat hela
svaret. Ingen schemaändring kan därmed motiveras genom att bara anta att
fälten är tomma eller oviktiga.

Två avgränsade försök att läsa det offentliga strukturerade endpointet direkt
gav lokalt certifikatfel respektive HTTP 404 med Windows betrodda TLS-väg.
Ingen TLS-kontroll kringgicks, inget nytt godkänt prisunderlag skapades.

Online Syd `730400`, `online_fulfillment`, är en annan priskontext.
Dess hashkontrollerade råsvar för Scan GTIN `2320321600009` anger **105 kr/kg**
och inga aktiva kampanj-ID:n (2026-10-09 13:33:04.893007 UTC,
`raw:bf48747abff546d2be6d2ef663d37e23#results.items[7]`).
65 kr/kg har därför inte kopplats till onlineprodukten genom namnmatchning.

## Reproduktion och nästa konkreta källåtgärd

`grocery_data/tests/test_coop_scan_missing_evidence.py` läser den exakta
hashkontrollerade offentliga råfilen i fixtures och reproducerar att inga
produkter kommer igenom, med samma tre fältnamn och felkod. Originaltid bevaras.
Detta är ett diagnosprov, inte en rättning av källparsern.

För en avgränsad källfix behövs det offentliga strukturerade svaret från den
normala butikssidans egen transport, med nya fälts värden/typer och belagda
identiteter, perioder, prisbasis och köpgränser. Därefter schema-/semantikprov,
vanlig kvalificering och separat källpaket. Ingen generell okänd-fält-acceptans
eller fallback från namnet ska införas. Medlemsprisändringen i denna kandidat
rättar inte den kvarstående fysiska källspärren.

## Komplettering: Coop Klostergården verifierad separat

Samma erbjudande finns också i bevarat råsvar från Coop Klostergården,
butik **3820**, ledger **106435**: Scan färsk fläskytterfilé, ca 1 kg,
**65 kr/kg medlemspris, max 2 st/hushåll**. Värpinge är inte ensam butik.

- Rå-ID `372c3d78e7b64b85a781a936fd04cb98`, samma avvisade fysiska snapshot.
- Hämtat 2026-10-09 13:30:27.305802 UTC; 12 941 byte.
- SHA-256 `778fd5ca02bcd72688ef036536a2c8503115a0f701608d76d4906c75bb8829a1`,
  omkontrollerad mot originalfilen vid läsande serveråtkomst 10 oktober.
- Sida https://www.coop.se/butiker-erbjudanden/coop/coop-klostergarden/.
- Strukturerat endpoint `/dke/offers/sorting-groups/106435`, HTTP 200.
- Eget stopp: `public_structured_schema_unrecognized`, okänt fält **row.weeklyTip**.
  Det är inte samma observerade fältspärr som i Värpinges svar.

Kampanjen kan modelleras gemensamt med flera belagda butikskopplingar; varje
butiks kanal, period och köpgräns måste följa med. Ingen ny insamling eller
källfix utförd i denna komplettering. Övriga kedjors konkreta jämförelseexempel
och inventeringsantal finns i [COMPARABILITY.json](COMPARABILITY.json).
Lidl har 26 publicerade kampanjrader i detta underlag, ingen kvarstående
`not_compared` i kandidatens prisvisningsinventering; det bevisar inte komplett
sortiment eller att varje vara klarar receptens närings-/identitetskrav.
City Gross saknar rader i detta underlag; inga produktexempel kan styrkas där.

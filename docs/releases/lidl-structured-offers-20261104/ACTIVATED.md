# Lidl: nationella kampanjer från Lidls strukturerade erbjudanden (scheduler)

Aktiverad 2026-11-04 18:13 UTC. Ägarbeslut samma dag: lätta eller rätta
automatiskt och aktivera.

## Orsak

Endast 8 av 369 Lidl-kampanjrader per Lund-butik (0163, 0303) nådde priserna.
PDF-bindningen knöt 12 av 190 bildtexter; 119 föll på exakt sammansatt titel.

## Ändring

Kod `102e92b59547` (main). Två filer, bas byte-identisk med aktiv scheduler
`source-ops-db8710ad08fe`:

- `grocery_data/app/connectors/lidl/document_qualification.py`
  (`structured_offer_proof`, metod `lidl-structured-national-offer-v1`)
- `grocery_data/app/connectors/lidl/municipal_offers.py`

När bladet inte binder någon bildtext till varan kan Lidls egen nationella
erbjudanderad kvalificera den: ett livsmedel med komplett identitet och GTIN,
ett aktuellt icke-flerköpserbjudande för fast g/kg-förpackning (ml/l endast
icke-dryck), nationellt giltigt, inom bladets period, utan prislegend,
kupong, aktivering, sortval eller pant. Varor som bladet binder behåller
bladets bedömning. Övriga rad-, fönster- och providerkontroller oförändrade.

## Driftsättning och prov

- Paket sha256 `49cb3ffa30f7e84ef284d565f2094abc9f33dcaf139f9a9c0f0f8a6662b9a2df`,
  bygge utan nätverk `sha256:c64585702b95a35dfd7be5e61759e395198c0220a92a00b76d28dc8b0551d898`.
- Offlineprov i kandidaten mot arkiverad vecka 2026-11-02
  (`1281/attempts/20261102T035151-95cd14bc8c96`): 56 godkända rader per
  butik (tidigare 8), inga gemensamma blockeringar.
- 152 Lidl-tester gröna.
- Compose-config före/efter: endast image och BUILD_ID. Inget jobb pågick;
  appen orörd. Ingen databas ändrad.
- Nästa Lidl-hämtning 2026-11-05 02:17 UTC.

## Baspriser

Lidl.se publicerar inga ordinarie priser (sök-API:t returnerar bara
kampanjvaror med datum). Lidl förblir `offers_only`.

## Återställning

Compose utan `/opt/smako/overrides/source-ops-102e92b59547.json`
(bild `sha256:3337142a…`, BUILD_ID `source-ops-db8710ad08fe`).

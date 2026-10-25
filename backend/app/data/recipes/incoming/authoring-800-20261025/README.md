# Receptleverans: 800 grundrätter, 2 200 varianter

Ägaren lämnade denna AI-författade samling 2026-10-25 och beställde att den
läggs till i projektet samt färdigställs av Sol. Alla 160 författarpaket finns
i `paket/`, med originalens exakta byte. De innehåller 600 middagsgrundrätter
med tre varianter och 100 frukostar samt 100 mellanmål med två varianter.
Varianterna heter `simple`, `standard` och `extended`; grundrätts-ID återanvänds.

Detta är bevarat författarunderlag i Smako. Inga av dessa utkast är ännu
publicerade i runtimebibliotekets `library-manifest.json`. Innehållsgranskning,
ingredienskoppling, produkt-/faktakvalificering och vanlig import återstår.
Att en variant passerar strukturell kontroll är inte ett sådant godkännande.

## Filer och proveniens

- `SOURCE-MANIFEST.json`: originalbilagornas hash/storlek och varje bevarad
  fils hash/storlek. Bevara dessa original; gör granskade rättningar separat.
- `paket/*.json`: den enda receptvyn i denna katalog. Den är verifierad mot
  den samlade originalfilen som en multiset av receptobjekt, inklusive pilot 01.
- `smako-registerforslag.json`: författarens 198 råvaruidentiteter för granskning.
- `smako-leveransoversikt.json`: författarens fulla bokföring och granskningspunkter.
- `smako-dubblettgranskning.json`: pensionerade utkast och kvarvarande likhetspar.
- `smako-kontrollrapport.json`, `pilot-leveransoversikt.json`, `LAS-MIG.txt`:
  författarens egen kontroll och bakgrund. De är inte Smakos importkvitton.

ZIP, samlad receptfil och paketvisa översikter lagras inte en gång till som
duplicerat innehåll. ZIP/samlad fil har verifierats vid mottagningen och deras
hashar finns i källmanifestet. Alla 2 200 receptposter är bevarade.

## Reproducerbar kontroll

Kör från projektroten med Python 3.12:

```powershell
$env:PYTHONPATH='backend;.'
.venv/Scripts/python.exe -X utf8 scripts/recipe_layer/audit_authoring_delivery.py --output .local/recipes/intake-800-audit.json
```

Exitkod **1** betyder att den slutförda kontrollen rapporterar blockerare.
Läs rapporten; försök inte göra kontrollen grön genom att lägga påhittade
produktkrav på okända ingredienser. Kontrollen skriver endast sin rapport.
Den läser bibliotekets befintliga kanoniska namn och vokabulär och kör vanliga
`standardize`/`validate_pack_bytes` för de identiteter som redan stöds.

Första incheckade kontroll: **429** native-kompatibla varianter, **1 763**
blockerade av **189** okända kanoniska identiteter, **6** standardiseringsfel
och **2** valideringsavslag. Skillnaden mot författarens 198/1 778 beror på
Smakos befintliga namnnormalisering. Resterande fel kan framträda när fler
ingredienser kan standardiseras. Aktuellt runtimebibliotek har fortsatt 262 recept.

Se [kontrollrapporten](../../../../../../docs/reviews/recipe-intake-800-20261025.md)
och [Sols uppdrag](../../../../../../docs/CODEX-SOL-NEXT-20261025-RECIPE-INTAKE.md).

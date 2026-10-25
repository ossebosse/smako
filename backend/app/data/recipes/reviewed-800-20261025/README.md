# Granskade delmängder av 800-leveransen

De två första författardelmängderna omfattar 20 källkandidater och 45 fullständiga
varianter. Redaktionell samgruppering i `batch-03`/`batch-04` gör fyra av varianterna till
varianter av två befintliga grundrätter. Slutläget är 45 aktiva varianter, 18 nya
bas-ID:n och två befintliga baser med nya varianter. De fyra tidigare separata
ID:nas utgåvor är bevarade och återkallade. `batch-04` korrigerar även deras
diversitetsfamiljer i version 1.0.1; de fyra mellanversionerna är bevarade och
återkallade. Alla tre måltidstyper och sex kök
finns med. Recepten är AI-författade och inte provlagade.

`authoring.json` är korrigerat författarunderlag; `standardized.json` är dess
vanliga author-resultat. `REVIEW.json` binder varje beslut till källpaket,
radindex, originalets SHA-256 och korrigerad rad. Originalen är bytebevarade.
`baseline-262-manifest.json` binder det tidigare biblioteket till samma
oförändrade paketfiler i överordnad katalog, utan dubblerad receptdata.

Återskapa de redaktionella rättningarna med Python 3.12 och `PYTHONPATH=backend;.`:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/recipe_layer/build_reviewed_subset.py
.venv/Scripts/python.exe -X utf8 scripts/recipe_layer/build_reviewed_subset.py --batch 2
.venv/Scripts/python.exe -X utf8 scripts/recipe_layer/reconcile_reviewed_bases.py
```

Kör därefter vanlig author/validate/diff/import enligt
`docs/recipes/AUTHORING.md`. Efter import av `batch-04`, återkalla de exakt
angivna tidigare ID:na med vanlig `revoke` enligt `batch-03/REVIEW.json` och
`batch-04/REVIEW.json`, och
kör `prepare`. Runtimefilerna namnges och binds av importörens hash;
ingen handregistrering i Python används. `variant_id` skiljer varianter medan
gemensamt `base_id` bevarar veckans upprepningsgräns. Nivåfältet ändras inte för
att en variant heter simple eller extended.

Git-import gör recepten lokalt tillgängliga för uttryckligt tillåtna receptval.
Produktköp, källa, prisdatum, mängdgrund, näring, allergener och ekologiskt
kontrolleras fortfarande mot användarens faktiska produkter och krav. Ett
importerat recept är ingen universellt köpbar eller näringskvalificerad meny.
Se `docs/reviews/recipe-integration-800-20261025.md` för exakta utfall och ID:n.

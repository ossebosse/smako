# Granskade delmängder av 800-leveransen

Första delmängden: 16 grundrätter, 37 fullständiga varianter. Andra delmängden
under `batch-02`: fyra ytterligare grundrätter, åtta varianter. Alla tre
måltidstyper och sex kök finns med. Recepten är AI-författade och inte provlagade.

`authoring.json` är korrigerat författarunderlag; `standardized.json` är dess
vanliga author-resultat. `REVIEW.json` binder varje beslut till källpaket,
radindex, originalets SHA-256 och korrigerad rad. Originalen är bytebevarade.
`baseline-262-manifest.json` binder det tidigare biblioteket till samma
oförändrade paketfiler i överordnad katalog, utan dubblerad receptdata.

Återskapa de redaktionella rättningarna med Python 3.12 och `PYTHONPATH=backend;.`:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/recipe_layer/build_reviewed_subset.py
.venv/Scripts/python.exe -X utf8 scripts/recipe_layer/build_reviewed_subset.py --batch 2
```

Kör därefter vanlig author/validate/diff/import/prepare enligt
`docs/recipes/AUTHORING.md`. Runtimefilerna namnges och binds av importörens hash;
ingen handregistrering i Python används. `variant_id` skiljer varianter medan
gemensamt `base_id` bevarar veckans upprepningsgräns. Nivåfältet ändras inte för
att en variant heter simple eller extended.

Git-import gör recepten lokalt tillgängliga för uttryckligt tillåtna receptval.
Produktköp, källa, prisdatum, mängdgrund, näring, allergener och ekologiskt
kontrolleras fortfarande mot användarens faktiska produkter och krav. Ett
importerat recept är ingen universellt köpbar eller näringskvalificerad meny.
Se `docs/reviews/recipe-integration-800-20261025.md` för exakta utfall och ID:n.

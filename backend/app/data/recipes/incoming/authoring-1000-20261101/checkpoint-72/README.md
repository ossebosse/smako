# Receptcheckpoint: 72 grundrätter / 199 varianter

**Komplett receptleverans mottagen 2026-11-01; granskade utkast, inte importerade.**
ZIP-filen kompletterar den tidigare [rapportmottagningen](../checkpoint-72-reports/README.md).
De fyra tidigare rapporterna och samtliga sex pakethashar stämmer byte för byte.
Detta är samma checkpoint inom beställningen av 1 000 grundrätter, inte en ny
leverans som ska adderas en gång till.

| Kontroll | Resultat |
| --- | ---: |
| Receptpaket | 6 |
| Grundrätter | 72 |
| Varianter med fullständiga mängder/steg | 199 |
| Middag / frukost / mellanmål, grundrätter | 55 / 3 / 14 |
| Varianter som passerar Smakos `standardize` + `validate_pack_bytes` | 50 |
| Varianter stoppade av saknade ingrediensidentiteter | 149 |
| Nya namn/form-identiteter som behöver sakgranskning | 63 |
| Importerade / betaaktiverade från denna checkpoint | 0 / 0 |

50 är tekniskt kompatibla variantposter, inte godkända eller köpbara recept.
49 ligger i två kompletta paket med 20 grundrätter; den femtionde är
`pizzoccheri:simple`, vars övriga varianter har registerhinder. Ingen familj
har delimporterats. Biblioteket innehåller fortsatt 934 grundrätter och
2 462 aktuella varianter; de ursprungliga 2 200 importreferenserna består.

## Bevarat underlag

`source/paket/001–006` innehåller originalrecepten. `source/` innehåller också
kandidatregister, ingrediensförslag, källförteckning, checkpoint,
förslag till befintliga recept samt det strukturella leveransschemat.
[SOURCE-MANIFEST.json](source/SOURCE-MANIFEST.json) binder de 12 filerna med
storlek/SHA-256 och redovisar samtliga 42 filer i ZIP-filen.

De fyra redan bevarade rapporterna ligger kvar i föregående mottagning.
Stora härledda SQLite-/NPZ-/TSV-filer, dubbletter av referensunderlaget,
författarens skript och mellanrapporter ligger lokalt i den ursprungliga
ZIP-filen/uppackningen. De behövs inte för Smakos ordinarie validering.
Inga medföljande program har körts. Originalutkasten har inte ändrats.

## Resultat och nästa arbete

Läs [granskningen](../../../../../../../docs/reviews/recipe-checkpoint-72-20261101/REPORT.md),
[native-resultatet](../../../../../../../docs/reviews/recipe-checkpoint-72-20261101/NATIVE-AUDIT.json)
och [valideringskvittot](../../../../../../../docs/reviews/recipe-checkpoint-72-20261101/VALIDATION.json).
De skiljer strukturgodkännande från innehållsgranskning och köpbarhet.
Konkreta hinder gäller bland annat identitetsnormalisering, frysta insatser,
frityrolja och råvarornas form. Det finns också en
[förberedd återkoppling till Chat](../../../../../../../docs/recipes/requests/20261101/ATGARDER-CHECKPOINT-72-TILL-CHAT.txt),
som inte har skickats.

Fortsätt beställningen från paket **007**, med **928 grundrätter / 2 551
varianter** kvar räknat mot mottagna utkast. Dessa resttal betyder inte att
de första 72 är slutligt godkända som tillräckligt olika nya grundrätter.
Jämför fortsättningen med både aktuellt bibliotek och denna checkpoint.
Bevara kandidatbesluten: 72 författade, 7 öppna gränsfall och 5 avvisade.

Kör om den ordinarie mottagningskontrollen från projektroten:

```powershell
$env:PYTHONPATH='backend;.'
.venv/Scripts/python.exe -X utf8 scripts/recipe_layer/audit_authoring_delivery.py --input backend/app/data/recipes/incoming/authoring-1000-20261101/checkpoint-72/source --output .local/checkpoint-72-audit.json
```

Exitkod 1 betyder här att granskningen slutfördes med dokumenterade hinder.
Ingen import eller aktivering ingår i kommandot. Läs normaliseringsfynden i
granskningen även om antalet kanoniska okända nycklar är 62: alla 63
ursprungliga namn/form-förslag behöver fortsatt sakgranskas.

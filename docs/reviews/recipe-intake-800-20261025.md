# Mottagning av 800 grundrätter, 2026-10-25

Ägarens leverans är nu bevarad i
[`backend/app/data/recipes/incoming/authoring-800-20261025`](../../backend/app/data/recipes/incoming/authoring-800-20261025/README.md).
Alla 160 författarpaket är byteidentiska med ZIP-medlemmarna. Recepten är
också exakt samma multiset som i den samlade originalbilagan. Originalbilagor
och 166 bevarade källfiler binds av `SOURCE-MANIFEST.json` med SHA-256/storlek.
De bevarade källfilerna omfattar 29 392 586 byte, före mottagningsdokumentation.

## Antal och format

- 800 skilda grundrätts-ID:n, 2 200 unika ID/version/variant-kombinationer.
- 600 middagsgrundrätter med tre varianter; 100 frukostar och 100 mellanmål
  med två varianter. Inga grundrätts-ID-krockar med befintliga 262 recept.
- Middagar: grekiskt 103, italienskt 102, mexikanskt 76, indiskt 101,
  thailändskt 95, svenskt 123. Författarens önskade exakta köks-/proteinkvoter
  är alltså inte helt uppfyllda. ID:n bevisar inte kulinarisk unikhet.

## Oberoende kontroll med Smakos befintliga kod

Maskinunderlag: [recipe-intake-800-20261025.json](recipe-intake-800-20261025.json).
Kört med Python 3.12 och main `fcd4bf1` före denna mottagningsändring:

| Utfall | Varianter |
| --- | ---: |
| Befintlig standardisering och native strukturell validering passerar | 429 |
| Blockerad av ännu okänd kanonisk ingrediensidentitet | 1 763 |
| Standardisering misslyckas | 6 |
| Native validering avvisar | 2 |
| Totalt | 2 200 |

Vokabulären har 86 kända identiteter. Befintlig namnnormalisering gör att
189 kanoniska identiteter återstår, jämfört med författarens råa 198 förslag
och 1 778 berörda varianter. Ingen ny identitet, enhetsomvandling eller
produktkoppling har godkänts av denna kontroll.

Sex kända standardiseringsfel gäller `estimated_minutes` över modellens
nuvarande 180-minuterstak: tre linspannkaksvarianter (308/315/317 min),
en klibbigt-ris-/äggvariant (299 min), en paprikadipp-/risvariant (320 min)
och en avrunnen yoghurt-/risvariant (770 min). Tiderna inkluderar lång
förberedelse; att kapa eller ta bort den tiden är ingen giltig rättning.

Två enkla varianter, kall kyckling-/senapsröra och nudelsallad med lax,
anger en kall metod samtidigt som insatsformen är rå animalisk råvara.
Granska textens verkliga tillagningskedja och rätta rätt fält; ändra inte
råvaruform eller metod bara för att kringgå kontrollen. Exakta identiteter,
källpaket och fel finns i maskinrapporten.

De 1 763 blockerade varianternas övriga native kontroller är **inte körda**.
Fler fel kan därför framträda efter ingrediensarbetet. De 429 kompatibla
varianterna är inte innehålls-/köp-/näringsgodkända av strukturkontrollen.

## Import och nästa steg

Den samlade författarfilen är 18 940 892 byte, större än importörens 16 MiB.
Standardiserade/publicerade paket kan dessutom växa. Manifestet tillåter
högst 128 aktuella plus historiska paketgenerationer; dagens läge är 13 + 7.
Publicera därför inte varje författarpaket som en egen generation. Granskade
varianter behöver sammanföras i färre bounded paket med kontrollerad storlek
både före och efter vanlig import. Inga gränser höjs i mottagningen.

Aktivt manifest och befintligt bibliotek har bevarats. Leveransen är tillagd
som komplett underlag i projektet, ännu inte som valbara konsumentrecept.
Följ [Sols nya uppdrag](../CODEX-SOL-NEXT-20261025-RECIPE-INTAKE.md) för att
göra granskade delmängder användbara och förbereda verkliga skalprov.

## Verifiering av mottagningsändringen

57 riktade offlineprov för författarstandardisering, måltidsbibliotek och
befintligt innehållspaket passerar. Ruff och compileall passerar för det nya
kontrollverktyget. Kontrollverktyget verifierar samtliga bevarade källhashar
och att aktivt manifest är byteidentiskt före/efter. Inga prisinsamlingar,
planeringsbenchmarkar eller produktionsändringar har utförts i mottagningen.

# Grönsaksfond, en-proteinveckor och 90 nya middagar (2026-11-26)

Aktiverad 2026-11-26 12:08 UTC. App **app-72815cacaa24-bdd50ebd**
(`sha256:4bb19dc36a86…`), bas `app-3a58ee0fba39-5f00a1b9`. Scheduler orörd.
Backup före byte: `/srv/smako/backups/20261126T115811Z`.

Gren `feature/stock-and-varied-proteins`, releasegren
`release/varied-proteins-20261126` (`72815ca`, aktiv `3a58ee0` + `main..def6e2b`).

## Ändringar

- **Grönsaksfond** (`stock_concentrate.py`): flytande Touch of Taste-koncentrat
  godtas i alla butiker. Etiketten gäller 100 ml utspädd fond; koncentratets
  värde = deklarerad energi × 23,2 enligt tillverkarens dosering (1,5 msk till
  5 dl vätska), protein och fett ”under 0,5 g” räknas som 0. Tärningar, pulver,
  geléportioner och märken utan angiven dosering godtas inte. De 52 rätter som
  stoppades av grönsaksfond stoppas inte längre.
- **En-proteinveckor** (`same_protein_variety.py`): fem kycklingmiddagar gav
  ingen meny alls (tak två per huvudråvara). Taket följer nu en
  kycklingfördelning; veckor med tre eller fler av ett slag kräver olika
  rättfamiljer, högst två på samma kolhydrat eller tillagningssätt, två–tre
  metoder.
- **Näring:** ostronsås (USDA 174529), bröd utan tabell (Livsmedelsverkets
  brödsorter efter etikett), torkade nudlar/pasta med vatten i listan när egen
  tabell ≥ 300 kcal/100 g.
- **90 nya middagar** i sex nya `meal-pack-*`: 36 kyckling, 26 kött, 28 fisk och
  skaldjur. [Granskning](../../reviews/varied-proteins-20261126/REVIEW.md).

## Prov

- Nya prov: `test_stock_concentrate_20261126.py`, `test_same_protein_variety_20261126.py`,
  tillägg i `test_loose_food_reference_20261125.py`, `test_nutrition_reference.py`
  (170 referenser), `test_mint_leaf_preparation.py`. Relaterade prov för
  beredning, diet, kategorisökning och veckovariation går igenom.
- Serverkörning med livebilden och ändrade filer (en stad per container):
  5 × kyckling med 45 g protein 874,59 kr Lund / 773,78 kr Malmö (förut ingen
  meny); nya rätter som klarar en blandad vecka med 45 g: 69 Lund, 80 Malmö.
- Kandidatbild utan nätverk: 9 119 recept, 1 467 bas-ID (+90), `from app.main
  import app` ok.
- Efter aktivering: `/ready` Lund och Malmö ready med nytt BUILD_ID, inga fel
  i apploggen; Malmös prisunderlag `degraded` som före.

## Incident under arbetet

2026-11-26 09:30 UTC tog servern slut på minne när appen (8 GB) och ett
testcontainer-prov (4 GB) körde samtidigt; kärnan dödade appens process och
den startade om (cirka 4 minuter). Senare prov kördes en stad i taget med
3,5 GB och efter kontroll av ledigt minne.

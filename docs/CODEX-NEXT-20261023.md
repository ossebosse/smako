# Uppgift till Codex: granska integrationen och fortsätt skalningen (2026-10-23)

**Uppföljning:** granskningens resultat finns i
[slutrapporten](reviews/integration-scaling-20261023.md). Ägaren har därefter
godkänt Axfood-berikningen och beställt arkitektur med implementation hos Sol.
Fortsätt enligt [det nya arkitekturbeslutet](CODEX-SOL-ARCHITECTURE-20261023.md),
som ersätter öppna arkitektur-/ägarfrågor nedan. Denna ursprungliga
uppgiftsbeskrivning behålls som historik.

Utgå från aktuell `main`, läs `AGENTS.md`, `docs/HANDOFF.md`,
`docs/DEVELOPMENT.md` och underlaget
[`docs/reviews/recipe-scaling-20261023.md`](reviews/recipe-scaling-20261023.md)
samt [`docs/reviews/recipes-20261022.md`](reviews/recipes-20261022.md).
Arbeta i avgränsade grenar, små commits. **Ingen produktionsaktivering,
scheduleränding, live-insamling eller ändring av aktiva prismanifest ingår.**
Varje sådant steg kräver ägarens separata beslut.

## Vad som nu ligger på main (ej aktiverat)

| Del | Status | Var |
| --- | --- | --- |
| Utbackning `e6f7d32`/`ea847bb` | Verifierad: Lund all-macros 405 → 116 s, samma meny | `e190f3e` |
| 40 nya recept (Codex 20 + variety 20) | Kockgranskade, ej provlagade | `backend/app/data/recipes/` |
| Ägg: alla pack av hela skalägg | Ägarbeslut 2026-10-22 ersätter M/L-beslutet 2026-10-17 | `official_product_facts.is_plain_shell_egg` |
| Axfood-produktdetaljer som fakta | Kod klar, **av** i drift (`AXFOOD_PRODUCT_DETAIL_ROOT` ej satt) | `axfood_product_details.py`, `scripts/fetch_axfood_product_details.py` |
| Exakta prestandaförbättringar | Samma resultathash i alla uppmätta fall | se rapporten avsnitt 2 |
| Screening av substitutioner 10 % | **På** som standard; samma hash i alla uppmätta fall | `library_substitution_screen_margin` |
| Geometriska kohorter + prediktorordning | **Av** som standard | `library_merge_generations`, `library_substitution_slot_limit` |

Två beteendeändringar mot aktiv produktion som granskningen ska bekräfta:
1. Äggidentiteten och mängdbevisen (fler ägg, S/okänd storlek, mängd trots
   näringskonflikt, mängdbevis utan deklaration). `project_usable_quantity`
   blockerar inte längre mängd på konflikter som bara gäller näring; det
   gäller alla produkter, inte bara ägg.
2. Screeningen hoppar över substitutioner vars prediktion ligger mer än
   10 % över bästa vecka. Heuristik, mätt utan prisförändring.

## 1. Granska integrationen (först)

- Kör full CI (inkl. webbläsartester) på main och rapportera exakta PASS/XFAIL/SKIP.
  Lokal offline-svit vid integrationen: se HANDOFF.
- Verifiera de 40 recepten med serverns **riktiga** fakta (inte offlineexporten):
  kvalificering i Lund och Malmö, mängder, ordning, 63/72/74 °C, vatten i ml.
- Verifiera äggändringen mot serverns aktuella äggsortiment: varje godkänd
  produkt ska vara hela skalägg; ingen äggprodukt får godkännas
  (`backend/tests/test_egg_standard_weight.py`,
  `docs/reviews/recipes-20261022/egg_check.py`).
- Kontrollera att `_mass_blocking` (näringskonflikter blockerar inte mängd)
  inte släpper igenom en produkt där mängden faktiskt är osäker.
- Jämför den gamla och nya standardsökningen på serverns resurser för de sju
  profilerna i båda städerna (`backend/scripts/planner_acceptance_matrix.py
  --repeat 3`; `--screen-margin -1` ger förra sökningen). Ingen profil får bli
  dyrare; samma hash förväntas.

## 2. Sökningen som skalar (huvuduppgift)

Mål: tusentals recept utan att beräkningstiden växer nämnvärt, utan dyrare
menyer. Mätt lokalt (rapporten avsnitt 2): geometriska kohorter med
prediktorordning och K = 32 håller veckosökningen på 17–29 s från 262 till
5 000 recept och gav lika eller billigare menyer när biblioteket växte, men
Lund 1 000 blev 0,8 % dyrare än dagens per-paket-sökning.

Att göra:
- Kör `--merge-generations --substitution-pool 0 --slot-limit {16,32,48}` mot
  dagens standard för alla sju profiler, Lund och Malmö, vid 262, 1 000,
  2 000 och 5 000 recept, samt `--uncapped`-referens där det är praktiskt.
  Testbibliotek byggs med `docs/reviews/recipe-scaling-20261023/build_libraries.sh`
  (ordinarie `author --import`, isolerade worktrees, aldrig i main-checkouten).
- Förklara Lund 1 000 (+0,8 %) och rätta orsaken; sänk inte kvalitetskraven.
- Gör det nya läget till standard först när ingen profil blir dyrare än dagens
  sökning vid 262 recept och inget större bibliotek ger dyrare meny än ett
  mindre. Referenskontraktet är v5 och anger alla sökparametrar uttryckligen.
- Sökmissar i små pooler (vegan i Malmö med Axfood-fakta: 361,81 kr fast den
  tidigare menyn för 340,64 kr fortfarande är giltig): pröva uttömmande sökning
  när poolen är liten, eller att bästa giltiga kandidat behålls mellan kohorter.

## 3. Kvalificering, kallstart och minne

- Varm kvalificering växer linjärt (cirka 6 ms per recept, 27–37 s vid 5 000).
  Ett billigt rangmått (summa av radernas billigaste offert, median 92 % av
  enreceptpriset) placerade valda menyrecept högt i sin generation
  (`proxy_probe.py`). Pröva full kvalificering endast för de bästa per
  generation, måltidstyp och proteinkategori; validera mot hela poolen.
- Mät kallstart med varm förberedelsecache på disk (samma kodsignatur i båda
  processerna); den lokala mätningen blev ogiltig.
- Malmö når 3,4–3,8 GB peak RSS vid 5 000 recept, över serverns 3 GiB.

## 4. Axfood i drift (kräver ägarbeslut)

- Hämtningen är återupptagbar; 503 Hemköp-koder återstod lokalt. Bestäm
  lagringsplats (utanför Git), uppdateringsrytm (nya koder per katalog,
  befintliga takter: Willys 1/s, Hemköp 0,1/s) och proveniens/hashkontroll.
- Kör `backend/scripts/augment_review_facts.py` på serverns exporter och mät
  Lund och Malmö för alla profiler innan `AXFOOD_PRODUCT_DETAIL_ROOT` sätts i
  en granskad release.

## Leverans

Små granskbara commits, körkommandon, indatahashar och maskinläsbara
mätningar. Uppdatera `docs/HANDOFF.md` och rapportera beslut som kräver ägaren.

# Ägg, Axfood-fakta, utbackning och receptskalning (2026-10-22–23)

Ägarbeslut 2026-10-22: alla produkter som är hela ägg ska räknas i äggrecept;
`e6f7d32` backas ut ur main; de 40 recepten tas med; Axfood-hämtningen görs;
Smako ska klara tusentals recept utan att beräkningstiden växer nämnvärt.
**Ingen produktionsaktivering, scheduleränding eller serverkörning har gjorts.**
Allt nedan är mätt lokalt på frysta granskningsdata 2026-10-18 (Lund, Malmö,
klocka `2026-10-18T05:12:49.467392+00:00`, nät blockerat, estimerat läge).

Gren `content/recipes-20261021` (pushad). Main har endast utbackningen.

## 1. Utfört

| Område | Commit | Resultat |
| --- | --- | --- |
| Utbackning `e6f7d32` + `ea847bb` | main `e190f3e` (och `8748901`, `e8cc3c5` på grenen) | Lund all-macros 405 → 116 s vid samma meny ([underlag](recipes-20261022.md)). Aktiv produktion `c253cbd` hade den aldrig. |
| Ägg | `3fdf975` | En identitet, `is_plain_shell_egg`, för både receptmatchning och mängdbevis. Alla pack av hela skalägg; S = 42 g, okänd storlek = S, XL = L (undre gränser); näringskonflikter blockerar inte mängd; hylla utan deklaration får eget mängdbevis. Lund 102 och Malmö 192 godkända pack, alla med gram (förut 6 och 0). Inga äggprodukter godkänns. Ersätter ägarbeslutet 2026-10-17 om endast M/L. |
| Axfood-fakta | `f8c6a6c`, `363b8e2` | Se avsnitt 3. |
| Recepten | `6496586` (+ `73df6aa` m.fl.) | 40 recept publicerade på grenen efter kockgranskning; ej på main. |
| Exakta prestandaförbättringar | `db7eb68`, `856bdb5`, `387ab8e`, `d30f07f`, `d605d2e` | Identisk resultathash; se avsnitt 2. |
| Screening av substitutioner | `654dfc1` | Standard 10 %; samma hash i alla uppmätta fall. |
| Försöksinställningar (av som standard) | `32b7dcd`, ocommittad geometrisk kohort i denna commit | Prediktorordning, tak per plats, sammanslagna/geometriska kohorter. |

## 2. Skalning: vad som var dyrt och vad som är åtgärdat

Syntetiska testbibliotek via ordinarie `author --import` i isolerade
worktrees (`.local/scaling-20261022/lib-*`, ej incheckade), paket om 500:
1 000, 2 000 och 5 000 recept totalt (262 riktiga + 738/1 738/4 738).
Bärbar Ryzen 7 5700U, 13,8 GB; två processer samtidigt; tider är jämförbara
inom tabellerna, inte serverprestanda.

### Exakta förbättringar (samma hash, samma korgar)

1. Offertmängder och vinnarvektorer delas mellan inköpsrader `"namn [n]"`
   (paketberäkningar −36 %).
2. `BasketItem` byggs en gång per fryst offert.
3. Bibliotekspaket verifieras och parsas en gång per (fil, sha256) i stället
   för två gånger per planering.
4. Per-recept-hjälpare: `_mapping_value` var kvadratisk i poolen (97 miljoner
   `casefold` vid 5 000 recept), `recipe_id`, kulinariska profiler och
   trace-identiteter memoreras; receptcachen rymmer 16 384 i stället för 1 024.

Varm standardplanering, per paket (dagens sökning), samma meny före/efter:

| Recept | Lund före → efter | Malmö före → efter |
| ---: | --- | --- |
| 262 | 29,8 → 21,8 s | – |
| 1 000 | 50,4 → 38,9 s | 56,9 → 35,2 s |
| 2 000 | 74,8 → 55,0 s | 102,2 → 63,0 s |
| 5 000 | 143,9 → 100,4 s | 176,2 → 109,2 s |

### Sökningen: varför fler recept gav dyrare menyer

Substitutionen körs per publicerat paket, så arbetet växer med antalet paket,
och sökningen är inte monoton: Malmö fick 482,75 kr med 262/1 000 recept men
504,10/507,00 kr med 2 000/5 000; Lund 474,43 → 499,24 → 496,34 kr.

Mätt underlag för ny sökordning:
- 98 % av alla prissatta veckoförslag ligger över 20 % dyrare än bästa vecka.
- Prediktorn *vecka − enreceptpris(ut) + enreceptpris(in)* (från
  kvalificeringen, gratis) satte alla 22–23 förbättrande förslag inom +2,2–3,9 %
  av bästa vecka; 17 av 23 var bäst predikterade i sin plats.
- En säker undre kostnadsgräns finns inte: girig gruppering av rader till
  gemensamma förpackningar gör korgkostnaden icke-monoton.
- Att bara slå ihop alla nya paket med tak 160 gav dyrare meny (Lund 1 000:
  541 mot 474 kr). Utan prediktorordning är det oanvändbart.

Försök (varm tid; pris i kr; `geo` = geometriska kohorter där varje kohort
minst dubblar de kvalificerade alternativen, alla nyare recept med,
prediktorordning, högst 32 prissatta förslag per plats och svep):

| Stad | Recept | Per paket (dagens) | Två kohorter K32 | Geo K32 | Geo veckosökning |
| --- | ---: | --- | --- | --- | ---: |
| Lund | 262 | 486,85 | 486,85, 22,9 s | 486,85, 22,7 s | 16,9 s |
| Lund | 1 000 | 474,43, 38,9 s | 474,07, 28,3 s | **478,35**, 30,9 s | 19,8 s |
| Lund | 2 000 | 499,24, 55,0 s | 474,07, 40,4 s | ej mätt | – |
| Lund | 5 000 | 496,34, 100,4 s | 479,43, 57,7 s | 475,85, (ogiltig tid¹) | 25,4 s² |
| Malmö | 262 | 482,75 | 482,75, 32,4 s | 482,75, 32,8 s | 25,2 s |
| Malmö | 1 000 | 482,75, 35,2 s | 482,75, 49,2 s | ej mätt | – |
| Malmö | 2 000 | 504,10, 63,0 s | 508,00, 49,7 s | 481,57, 49,6 s | 26,0 s |
| Malmö | 5 000 | 507,00, 109,2 s | 508,00, 62,6 s | **470,62**, 63,8 s | 28,6 s |

¹ Datorn gick i viloläge under körningen; värdet ~16 000 s är ogiltigt.
² Kall körning. Övriga tider är varma.

Geo-sökningen håller veckosökningen på 17–29 s från 262 till 5 000 recept
och var i dessa data monoton i biblioteksstorlek (Lund 486,85 → 478,35 →
475,85; Malmö 482,75 → 481,57 → 470,62). Undantag: Lund 1 000 är 0,8 % dyrare
än dagens per-paket-sökning. Den är därför **inte** standard än.

### Kvar efter sökningen: kvalificering och minne

- Varm kvalificering 27–37 s vid 5 000 recept (en enreceptskorg per recept,
  cirka 6 ms vardera) och linjärt växande. Ett billigt rangmått (summa av
  radernas billigaste offert, median 92 % av enreceptpriset) placerade valda
  menyrecept högt i sin generation och kan användas för att kvalificera fullt
  endast de bästa per generation och kategori. Inte implementerat.
- Kall kvalificering 470–530 s vid 5 000 recept med tom förberedelsecache på
  disk. Mätningen "ny process, varm diskcache" blev ogiltig (koden ändrades
  mellan körningarna, så cachens metodsignatur missade 10 359 gånger) och
  ska göras om.
- Malmö når 3,4–3,8 GB peak RSS vid 5 000 recept, över serverns 3 GiB-gräns.

## 3. Axfood-produktdetaljer (Willys/Hemköp)

- Hämtning: `scripts/fetch_axfood_product_details.py`, befintliga klienter och
  takter (Willys 1/s, Hemköp 0,1/s), återupptagbar, inga cookies/huvuden
  sparade. Willys klar: 11 754 koder, 10 766 dokument, 988 utgångna. Hemköp
  (koder som saknas hos Willys + 100 stickprov): 2 105 av 2 513 klara,
  503 kvar när hämtningen stoppades 2026-10-23 på ägarens begäran; kör samma
  kommando igen för att fortsätta. Data i `.local/axfood-details-20261022/`
  (ej incheckat, publika produktdata).
- Delad artikelkod verifierad: i 81 jämförbara stickprov var EAN, namn,
  ingredienser och näringsdeklaration identiska hos Willys och Hemköp; bara
  sajtetiketter skilde (används inte).
- Projicering: ingredienser 85,5 %, näring 63 % av Willys-dokumenten. Precision
  `CA` behandlas som deklarerat värde (ägarbeslut), tröskelvärden blir
  `nutrition_limits`, per-100-huvudet väljs bredvid portionshuvuden, kJ/kcal
  kontrolleras med Coops integritetsgräns.
- Frysta Malmö-data berikade (`backend/scripts/augment_review_facts.py`,
  ny mapp `data/malmo-axfood-partial`): Willys ingredienser 0 → 82 %, näring
  0 → 62 %; Hemköp 0 → 78/64 %.

| Malmö, 262 recept | Kvalificerade före → efter | Pris före → efter |
| --- | --- | --- |
| standard | 133 → 135 | 482,75 → 482,75 |
| protein40 | 19 → 70 | 915,84 → **741,17** |
| all-macros | 19 → 64 | 915,84 → **739,67** |
| vegan | 14 → 19 | 340,64 → 361,81 ³ |
| frukost/mellanmål | 8 → 8 | 60,16 → 66,20 ⁴ |

³ Sökmiss: den gamla menyn är fortfarande giltig och kostar 340,64 kr med de
nya fakta. Samma icke-monotonitet som vid bibliotekstillväxt.
⁴ Korrekt: med deklarerad näring kostar den gamla menyn 70,20 kr.

**Inte i produktion.** `load_retained_facts` använder dokumenten endast om
`AXFOOD_PRODUCT_DETAIL_ROOT` pekar på en katalog; det är inte satt. Lund är
inte berikat/mätt (Coop Online täcker där redan).

## 4. Återstår

1. **Sökningen som standard**: kör geo K32 (och K48) för alla sju profiler i
   båda städerna vid 262/1 000/2 000/5 000 recept, inklusive negativa fall och
   `--uncapped`-referens; välj standard först när ingen profil blir dyrare än
   dagens sökning vid 262 recept. Lund 1 000 (+0,8 %) ska förklaras.
2. **Vegan-missen och liknande**: små pooler (≤ ~30 recept per plats) kan sökas
   uttömmande; annars behålla bästa giltiga kandidat mellan kohorter.
3. **Kvalificering**: begränsa full kvalificering per generation och kategori
   med rangmåttet; mät om kall start med varm diskcache.
4. **Minne** vid 5 000 recept i Malmö.
5. **Axfood i drift**: hämta resterande 503 Hemköp-koder, bestäm lagringsplats
   och uppdateringsrytm (nya koder per katalog, respektfull takt), sätt
   `AXFOOD_PRODUCT_DETAIL_ROOT` i en granskad release. Kräver separat beslut.
6. **Integrera grenen i main** (40 recept, ägg, Axfood-kod, exakta
   förbättringar) efter full CI; aktivering är ett separat beslut.

## Reproduktion

Skript i [recipe-scaling-20261023/](recipe-scaling-20261023/) (sökvägar för
denna arbetsstation): `build_libraries.sh` bygger testbiblioteken,
`run_grid.sh`/`run_scale.sh` kör matrisen, `summ.py` sammanfattar,
`gap_probe.py`/`predictor_probe.py`/`proxy_probe.py` mäter sökningen,
`qualify_probe.py`/`diff_probe.py` Axfood-effekten. Råvärden:
[measurements.jsonl](recipe-scaling-20261023/measurements.jsonl) (115 körningar;
`valid_timing` false för vilolägesvärdena). Frysta indata finns i
`Downloads\smako-allt-till-claude-20261018.zip`.

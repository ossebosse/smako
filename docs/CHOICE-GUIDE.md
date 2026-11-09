# Frågor: guiden som fyller i Mina val

Den fjärde mobilvisningen av Mina val (`choice-guide.js`, kopplad i
`configurator.js`). Väljs i mobilmenyn under "Visning av Mina val" → Frågor.
Ägaren godkände förslaget 2026-11-09.

## Flöde

1. **Butiker**: det befintliga platssteget (postnummer, butiker).
2. Åtta frågor, en per steg, med stora knappar.
3. **Din plan i korthet**: svaren med Ändra per rad, Skapa plan och
   länken **Anpassa i detalj**, som öppnar hela formuläret med svaren ifyllda.

Guiden har inga egna inställningar. Varje svar läses från och skrivs till
de befintliga kontrollerna i formuläret, så begäran till servern är exakt
densamma som från formuläret. Ett värde som inte motsvarar något svar (t.ex.
4 middagar eller en egen fördelning) visas som "Eget val" tills användaren
väljer ett alternativ.

## Frågor och vilka inställningar de sätter

| Fråga | Svar | Inställning |
|---|---|---|
| Hur många brukar äta? | 1–4, 5 eller fler (5–8) | Portioner per rätt för alla måltider |
| Vad vill du planera? | Middagar 3/5/7; Lägg till frukost/mellanmål med 3/5/7 | Antal middagar, Lägg till frukost/mellanmål, antal måltider |
| Hur äter du? | Allt / Mest vegetariskt / Pescetariskt / Vegetariskt / Veganskt | Kostval för alla måltider; fördelningen nollställs |
| Inte äter / allergi | Nio vanliga allergener + fritext via Tolka | Undvik med Allergi markerat |
| Vad tycker du om? | Sex matkök, åtta råvaror | Matkök och Gillar |
| Laga mat en vanlig dag | Snabbt och enkelt / Vardagsmat / Gärna lite mer | Aktiv tid och Ingredienser |
| Omväxling | Gärna samma favoriter / Lagom / Så varierat som möjligt | Omväxling Lite / Lagom / Mer |
| Viktigt för dig (flerval) | Mycket protein / Lättare mat / Stora portioner / Ekologiskt kött, ägg och mejeri / Inget särskilt | Näringsvärden, Portionsvikt, Kräv ekologiskt för animaliska produkter |

Frågas inte (behåller standard): tillåtna anpassningar, skafferi, överskott,
väntetid, total tid, samma grundrätt, detaljerad proteinfördelning, antal
butiker att handla i och medlemskap.

## Siffror bakom svaren (beslut 2026-11-09)

| Svar | Värde |
|---|---|
| Snabbt och enkelt | Högst 30 min aktiv tid, högst 8 ingredienser (alla måltider) |
| Vardagsmat | Högst 45 min, högst 12 ingredienser |
| Gärna lite mer | Ingen gräns |
| Mest vegetariskt | Minst hälften (avrundat uppåt) av varje måltidstyps rätter vegetariska; övriga väljer Smako fritt |
| Mycket protein | Minst 30 g per middagsportion och 20 g per frukost (Smakos standard för middag: 18 g) |
| Lättare mat | Högst 600 kcal per middag, 450 per frukost, 250 per mellanmål (standard för middag: 900) |
| Stora portioner | Minst 450 g tillagad vikt per middagsportion |

Värdena är satta efter Smakos standardgränser, inte uppmätta mot
receptbiblioteket. Om något svar ofta stoppar planer ska siffran justeras
här och i `choice-guide.js` samtidigt.

## Avgränsningar

- Bara mobil (under 850 px), som de andra visningarna. Datorn har hela formuläret.
- Kostvalet gäller alla måltider. Ett eget kostval för frukost eller
  mellanmål finns kvar under Anpassa i detalj.
- När antalet måltider ändras behåller "Mest vegetariskt" hälften av det nya antalet.
- Guiden är inte förvald; Bild är fortfarande standardvisningen.

Test: `test_question_guide_fills_in_mina_val_and_creates_the_plan` i
`backend/tests/test_personal_choices_browser.py`.

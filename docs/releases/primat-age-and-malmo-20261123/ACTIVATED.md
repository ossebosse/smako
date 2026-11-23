# Primat: prisåldern gäller även Primat-butiker; Mobilia och Maxi Malmö in

Aktiverad 2026-11-23 kväll (scheduler 16:3x–16:56 UTC). Ägarens "Fix the
open issues" och "Yes, merge and activate" samma kväll.

## Orsaker

- `/ready` visade `degraded`: Lunds Primat-cache bar 38 varor från ICA
  Malmborgs Clemenstorget observerade 2026-09-23. Butiken har inte längre
  full katalog hos Primat (`offers_only`), misslyckades varje natt i
  revalidering och dess LKG slogs in igen: `_merge_context_lkg` räknade
  åldern men jämförde den aldrig med gränsen, och prisbygget (`_fresh`)
  kontrollerade bara framtida tider.
- Mobilia (1004037) och Maxi ICA Stormarknad Malmö (1004492) har full
  katalog hos Primat men var felkopplade (unresolved/probable) och Primat
  löser alla Malmö-postnummer till centrum (21120), som inte returnerar dem.

## Ändring (main `17302fa`)

- `6b3da9e`: LKG äldre än gränsen lämnas ute (`lkg_expired`); en
  Primat-kontext vars senaste verifiering är äldre än gränsen är inte
  priskvalificerad och prisbygget hoppar över dess cacherader i stället för
  att fallera; nattens Primat-steg gör upp till 3 extra uppslag nära
  registrets koordinater för verifierade butiker som postnummeruppslaget
  missar; butiksupptäckt och kontextprov tar valfri stad och koordinater.
- `15b0727`: butikskoppling (`map-primat-stores`) klarar en del av staden åt
  gången (påstående föll för verifierad butik utanför uppslaget) och behåller
  rökprovsbevisad korgkoppling och prislinje för oförändrad butik.
- `17302fa`: kontextprovet läser registret med `mode=ro` (inte
  `immutable=1`, som missade nyss skrivna rader i WAL).

## Driftsättning

Scheduler `source-ops-17302fa4f4ff` (`sha256:f959328e3215…`) via
`source-ops-6b3da9ef18bb` och `source-ops-15b072778bad`; varje steg med
`build_source_patch.py --primat-refresh`, verifierade runtimefiler, bygge
utan nätverk, compose-diff endast image/BUILD_ID, inget jobb igång vid byte.

## Registerändring (Malmö)

Före-läge sparat: `reports/operations/primat-malmo-identity-before-20261123.json`
(20 mappningar, 11 länkar; korg: Västra Hamnen, Caroli).

1. Upptäckt nära Mobilia (55.5795, 13.0010; 1 gratis uppslag): 21 kontexter.
2. `map-primat-stores --city Malmö` (torrkörning, sedan skrivning): Mobilia och
   Maxi Malmö `verified exact_id`; Västra Hamnen och Caroli behöll
   korgkoppling och prislinje.
3. Kontextprov (1 uppslag + 1 sökning): Mobilia 46, Maxi Malmö 54 prissatta
   rader; `verify-primat-context-smoke`: 2 aktiverade, 0 avvisade.

## Kvar

Primat-kvoten var slut för dygnet. Schemalagd körning 2026-11-24 01:10:
Primat-uppdatering Lund + Malmö (Malmö: 4 ICA-butiker via ett extra
koordinatuppslag; Lund: Clemenstorget `lkg_expired`) och omräkning av
prisunderlagen. Tills dess behåller Malmö sitt tidigare prisunderlag (ett
ombygge kräver att cachen har de två nya butikerna).

Kända testfel som fanns före dessa ändringar (även på `a632476`):
`grocery_data/tests/test_ica_flyer_pipeline.py`,
`test_ica_quality_real_sources.py`, `test_ica_real_flyer_comparison.py`.

## Återställning

Scheduler: compose utan `source-ops-17302fa4f4ff.json`,
`source-ops-15b072778bad.json` och `source-ops-6b3da9ef18bb.json`.
Register: återställ raderna i före-filen.

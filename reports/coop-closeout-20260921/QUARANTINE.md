# Karantän: 379 unika butik–variantposter

Underlag: föregående Exakta bortfall, slutacceptans och sparade verkliga källsvar från 21/9 kl. 09:44 Stockholm. Ingen ny hämtning.

## Livsmedel / övrigt / okänt per butik

| Butik | Klass | Varianter | Erbjudandegrupper |
|---|---|---:|---:|
| 3839 | livsmedel | 78 | 10 |
| 3839 | övrigt | 13 | 1 |
| 3839 | okänt | 0 | 0 |
| 3815 | livsmedel | 185 | 31 |
| 3815 | övrigt | 103 | 9 |
| 3815 | okänt | 0 | 0 |

Livsmedel inkluderar drycker och godsaker; det betyder inte recept-/näringsgodkänt. Övrigt omfattar uttryckliga hushållsvaror, hygien och lampor. Klassningen är en rapportgranskning av källtitel och variantlista, inte en ny produktionsregel. Okända titlar skulle hamna i okänt. Alla radbevis och klassningar finns i `quarantine-grouped.json`.

## En huvudorsak per variant – inga dubbla totalsummor

Prioritet: procentpris → isPil → pant → variantgruppköp → ungefärlig mängd → obelagd förpackning → styckstöd → övrigt köpavtal. Detta är endast presentationsordning. Att lösa huvudorsaken löser inte automatiskt överlappande hinder.

| Butik | Klass | Huvudorsak | Varianter | Berörda grupper |
|---|---|---|---:|---:|
| 3815 | livsmedel | Ungefärlig förpackning | 3 | 3 |
| 3815 | livsmedel | Obelagd pant | 30 | 3 |
| 3815 | livsmedel | Fast köp-/förpackningsmängd obelagd | 6 | 4 |
| 3815 | livsmedel | Blandat variantgruppköp utan stödd restprismodell | 137 | 17 |
| 3815 | livsmedel | Oklar isPil-markering | 9 | 4 |
| 3815 | övrigt | Blandat variantgruppköp utan stödd restprismodell | 24 | 3 |
| 3815 | övrigt | Styckkontrakt saknar köpstöd | 1 | 1 |
| 3815 | övrigt | Procentpris utan köpprisgrund | 74 | 1 |
| 3815 | övrigt | Oklar isPil-markering | 4 | 4 |
| 3839 | livsmedel | Ungefärlig förpackning | 1 | 1 |
| 3839 | livsmedel | Obelagd pant | 36 | 2 |
| 3839 | livsmedel | Fast köp-/förpackningsmängd obelagd | 6 | 4 |
| 3839 | livsmedel | Blandat variantgruppköp utan stödd restprismodell | 35 | 3 |
| 3839 | övrigt | Blandat variantgruppköp utan stödd restprismodell | 13 | 1 |

Variantkolumnen summerar exakt till 379. Gruppantal får inte summeras mellan huvudorsaker: olika varianter i samma grupp kan ha olika huvudorsak. Gruppnyckeln är fysisk butik + source group-ID; liknande annonser i olika butiker slås inte ihop.

## Alla felorsaker – överlappande, varje variant högst en gång per orsak

| Butik | Felorsak | Unika varianter | Grupper |
|---|---|---:|---:|
| 3815 | `approximate_package` | 3 | 3 |
| 3815 | `bounded_checkout_contract_unverified` | 74 | 1 |
| 3815 | `deposit_amount_unverified` | 30 | 3 |
| 3815 | `fixed_purchase_package_unverified` | 9 | 7 |
| 3815 | `mixed_variant_group_checkout_unsupported_without_ordinary_price` | 191 | 23 |
| 3815 | `piece_purchase_contract_not_supported` | 62 | 6 |
| 3815 | `purchase_price_role_unverified` | 74 | 1 |
| 3815 | `source_is_pil_requires_review` | 13 | 8 |
| 3839 | `approximate_package` | 1 | 1 |
| 3839 | `deposit_amount_unverified` | 36 | 2 |
| 3839 | `fixed_purchase_package_unverified` | 7 | 5 |
| 3839 | `mixed_variant_group_checkout_unsupported_without_ordinary_price` | 84 | 6 |

Den äldre rapporten räknade felkodsförekomster, även när samma felkod fanns två gånger på samma variant. Denna tabell deduplicerar även dessa upprepningar. Alla ömsesidigt uteslutande kombinationer finns i JSON (`disjoint_reason_combinations`); deras variantantal summerar också till 379.

Stora grupper är inte lika många oberoende fel: Bulltoftas 74 procentposter är EN LED-annons. Blandade gruppköp behöver stöd för gemensam varukorg mellan belagda varianter, inte en text- eller prisjustering. Pant och isPil kräver ytterligare verifierat underlag. Inget av detta släpps genom denna avslutning. Mjölet ingår redan i de 112 radgodkända, inte i karantänens 379.

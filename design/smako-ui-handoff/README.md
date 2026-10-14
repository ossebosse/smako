# Smako · UI-överlämning till Codex
**Alternativ 3 · Version 1.0 · 2026-10-14**

## Börja här
Detta paket innehåller den godkända designbilden, en körbar frontendprototyp, designtokens, funktionsspecifikation, integrationsunderlag och tester. Uppdraget är att sätta denna design på **befintligt Smako**, inte att bygga en ny fristående produkt.

Packa upp mappen `smako-ui-handoff` under `D:\Projects\Smako\design\`, om det fortfarande är den aktiva arbetskopian. Starta Codex i projektroten och ge den innehållet i `START_HERE_CODEX.md`. Alla sökvägar i instruktionen är relativa till projektroten. Flytta inte projektet, byt inte stack och skriv inte över befintlig `AGENTS.md`.

## Prova gränssnittet
Öppna `smako-ui-preview.html` i en vanlig webbläsare. Den är fristående och innehåller alla stilar och all JavaScript. Alternativt öppna `prototype/index.html` tillsammans med filerna i samma mapp. Ingen installation, inloggning eller internetanslutning behövs för prototypen.

En lokal server är ett alternativ när miljön blockerar lokala HTML-filer:
```shell
python -m http.server 8765 --bind 127.0.0.1 --directory prototype
```
Öppna därefter `http://127.0.0.1:8765`.

Testa postnumret 222 25 och tryck Hitta butiker. Öppna Extraval och aktivera frukost och/eller mellanmål. De får egna kort direkt under middag. Prova alla tre dialoger på varje måltid. Tryck till sist Skapa plan och inköpslista för att inspektera prototypens UI-testdata.

**Inga verkliga priser hämtas, ingen plan optimeras och inga inställningar sparas permanent.** Butiker, avstånd, standardvärden och UI-nycklar i prototypen är exempel. Postnumret utgör inte en riktig geografisk kontroll. En omladdning nollställer demot. HTML-filen är en designreferens, inte en färdig integration.

## Paketets innehåll
| Fil/mapp | Användning |
|---|---|
| `START_HERE_CODEX.md` | Uppdraget att ge Codex. |
| `UI_SPEC.md` | Layout, komponenter, dialoger, tillstånd och avvikelser mellan bild och implementation. |
| `FUNCTIONAL_PARITY.md` | Bevarandekrav för befintliga funktioner, inklusive det som inte visas i skissen. |
| `API_MAPPING.md` | Underlag som Codex fyller i efter läsning av verklig kod. Inga påhittade endpoints. |
| `ACCEPTANCE.md` | Acceptanstester för den slutliga integrationen. |
| `contracts/ui-contract.ts` | Teknikoberoende, föreslagen semantisk UI-modell; INTE ett backendkontrakt. |
| `prototype/` | HTML, CSS och JavaScript; vanlig frontendkod utan ramverksberoende. |
| `references/approved/` | Godkänd design och utsnitt för respektive vy. |
| `references/current/` | Användarens skärmbilder av befintlig funktionalitet. |
| `tests/test_prototype.py` | Körbara tester av just referensprototypen. |
| `verification/` | Körningsrapport och skärmbilder av referensprototypen. |

## Vad som är känt och vad som inte är känt
Designvalet, måltidsbeteendet och de uppladdade skärmbilderna är underlaget. Det faktiska Smako-repot har **inte** lästs i denna leverans. Frontendramverk, aktuella DTO:er, endpointnamn, autentisering och fullständiga enum-/standardvärden är därför inte verifierade här. Codex ska kartlägga dessa i aktuell kod innan integrationen, inte be användaren skriva om allt manuellt.

Källordning vid konflikt:
1. Användarens uttryckliga krav och befintligt verifierat backendbeteende styr funktionaliteten.
2. `FUNCTIONAL_PARITY.md`, `UI_SPEC.md` och fylld `API_MAPPING.md` preciserar integrationen.
3. Godkänd designbild styr den visuella riktningen.
4. Prototypen visar en möjlig implementation, men ersätter inte befintliga affärsregler.

## Avgränsning
Byt inte insamlare, scheduler, prisunderlag, optimerare, server eller driftsättning. Ingen push eller deployment ingår. Inga nya externa tjänster, typsnittsfiler, konton, analytics eller geografileverantörer behövs för denna referens.

Prototypens handritade SVG-ikoner är kod i paketet. Inga fontfiler medföljer. Återanvänd befintliga godkända bilder/logotyper i Smako vid integration; designbildens logotyper är inte rena produktionsresurser.

## Verifiering
Se `verification/TEST_REPORT.md` för faktiskt körda kontroller och deras begränsningar. Ett passerat prototyptest är **inte** bevis för att Smakos backendintegration fungerar.

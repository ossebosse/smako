# Test- och leveransrapport
**2026-10-14 · Avser ENDAST den fristående referensprototypen.**

## Faktiskt utfört
| Kontroll | Resultat |
|---|---|
| JavaScript-syntax: `node --check prototype/app.js` | Godkänd, exit code 0 |
| UI-modell: `tsc --noEmit --strict contracts/ui-contract.ts` | Godkänd, exit code 0 |
| `python -m unittest discover -s tests -v` | **18 av 18 testfall godkända** |
| Ohanterade JavaScript-fel i testfallen | Inga observerade |
| Nätverksförfrågningar från den inlinade prototypen under testfallen | Inga observerade |
| Screenshot-körning av mobil- och desktopvyer | Utförd utan observerade JavaScript-fel |
| Visuell granskning | Mobil huvudvy/näringsdialog/fördelning och desktop huvudvy granskade; övriga screenshots medföljer |

Körlogg: `test-log.txt`. Separata loggar: `syntax-log.txt` och `typecheck-log.txt`.

## Testmiljö
- Linux, Python 3.13.5.
- Node 22.16.0.
- Playwright 1.57.0.
- Chromium 144.0.7559.96, headless.
- Källfilerna inlinades i ett HTML-dokument via `page.set_content`. Detta undviker testmiljöns policy som blockerar `file://`; det är samma markup, CSS och JavaScript som i levererad standalone-fil.
- Mobil/dator testades med ändrade viewportstorlekar, inte med fysisk iPhone eller riktig mobil Safari.

## Täckning
De 18 testfallen omfattar bland annat frukost/mellanmål oberoende av/på och utkastbevarande, individuella måltidsinställningar, alla nio kombinationer av måltid och dialogtyp, explicit 0 jämfört med tomt/standard, korrekt numerisk min/max-position, verklig musdragning och tangentbordsändring av slider, validering, lokal återställning och avbrytning, kostfördelningens summering, konflikter efter minskat måltidsantal, demo-butiksurval kontra max butiksbesök, föråldrat söksvar, granskning av preferenser, escapad användartext, ekologisk andel och noll middagar med aktiv frukost.

Layoutkontrollerna omfattar **320, 375, 390, 430, 768 och 1440 px** bredd. Ingen horisontell dokumentöverströmning observerades i kontrollerade tillstånd. Samtliga tre dialogtyper kontrollerades för intern horisontell överströmning vid dessa bredder. En näringsdialog kontrollerades även vid **390 × 568 px**, med rullbart innehåll och åtkomlig sidfot.

Fokus med Tab och Escape kontrollerades för samtliga nio måltid/dialog-kombinationer. Detta är inte en fullständig skärmläsar-, kontrast- eller WCAG-granskning.

## Skärmbilder
- `mobile-initial.png`: mobil, huvudflöde med exempelbutiker.
- `mobile-three-meals.png`: Middag, Frukost och Mellanmål samtidigt.
- `mobile-extras.png`: extraval inklusive smak, receptstil, ekologiskt och överskott.
- `mobile-nutrition.png`: Frukost med illustrativa egna protein-/kolhydratintervall.
- `mobile-weight.png`: Middag med illustrativt eget viktintervall.
- `mobile-distribution.png`: 3 vegetariska + 2 kyckling = 5 av 5, 0 kvar.
- `desktop-initial.png`: tvåkolumnslayout med sammanfattning.
- `desktop-three-meals.png`: desktop med alla måltider aktiva.

Värdena på bilderna är testdata, inte rekommenderade näringsmål eller verifierad geografisk information.

## Inte verifierat i denna leverans
Smakos verkliga repo, faktiskt frontendramverk, API-kontrakt, fullständiga fältlistor, servervalidering, autentisering, persistens, geografi, prisunderlag, optimering, riktiga plan-/inköpslistsvar, iOS Safari med mjukvarutangentbord, VoiceOver/skärmläsare och faktisk produktion har **inte** verifierats här.

Dessa delar ska Codex verifiera vid integration enligt `API_MAPPING.md` och `ACCEPTANCE.md`. Ingen integration, push eller deployment har utförts.

## Kör om prototyptesterna
För prototypen behövs ingen installation. För just testerna behövs Python, Playwright och en tillgänglig Chromium-installation. Testmiljöns version är angiven i `tests/requirements-tests.txt`; använd projektets befintliga testmiljö när den är lämpligare.

Från paketets rot:
```shell
python -m unittest discover -s tests -v
node --check prototype/app.js
tsc --noEmit --strict contracts/ui-contract.ts
```
Browserbinären söks bland installerade Chromium/Chrome eller Playwrights vanliga browserinstallation. Miljövariabeln `CHROMIUM_EXECUTABLE` kan ange annan installerad binär. Tester installerar eller hämtar inte browsern automatiskt.

Bygg om den fristående HTML-filen efter ändringar:
```shell
python tests/build_preview.py
```
Den byggningen använder bara Python-standardbiblioteket.

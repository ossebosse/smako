# Smakokonto och gästläge

Medlemskapet är ett registrerat Smakokonto, utan betalflöde. Det är separat
från butikernas lojalitetsprogram och påverkar inte prisunderlag eller prisregler.

- Gäster får skapa högst **3 recept per meny**, sammanräknat över middag,
  frukost och mellanmål, och högst **2 portioner per recept**.
- Konton får använda planerarens befintliga maxgränser: upp till sju tillfällen
  per måltidstyp och åtta portioner i konsumentgränssnittet.
- Gränsen är per meny, inte en livstidskvot. Receptbyten inom gränsen är tillåtna.
- Kontroller sker i API:t före planering/köning och vid ändringar i sparade planer.
  Butiksmedlemskap, formulärfält eller egna recept kringgår inte kontokravet.
- Varulistor utan recept fungerar även för gäster.

## Kontoflöde

Öppna `/personal#account`. Registrera e-postadress och ett lösenord med 12–128
tecken. Registrering loggar in direkt och visar en återställningskod en gång.
Spara koden i en lösenordshanterare. E-post skickas inte och adressen är inte
verifierad. Återställning kräver adressen och koden, utfärdar en ny kod och
återkallar samtliga befintliga lokala kontosessioner.

Skafferiet sparas automatiskt för den inloggade kontoinnehavaren. Gästdata är
separata tills användaren väljer **Spara mitt gästskafferi … på kontot**. Då
flyttas skafferi, profil och gästplaner atomärt med revisionskontroll. Ett konto
som redan har privata data skrivs inte över; gästskafferiet finns kvar separat.
Utloggning återgår till gästsessionen och rensar privata webbläsarutkast.

Befintlig OIDC-inloggning finns kvar som alternativ när dess miljövariabler är
konfigurerade. Konton länkas aldrig automatiskt enbart utifrån e-postadress.
Lokala konton och OIDC-identiteter har skilda ägaridentiteter.

## Lagring och driftsättning

Den befintliga `PLAN_STORE_PATH`-databasen utökas vid `PlanStore`-initiering
med `member_accounts`, `member_sessions` och `member_auth_attempts`. Inga
befintliga plan- eller skafferirader skrivs om vid initieringen. Samma privata
databas och backup ska bestå över omstarter och uppdateringar.

Lösenord lagras som saltade scrypt-hashar (N=32768, r=8, p=3). Sessionsnycklar
och återställningskoder lagras bara som hashvärden. Sessioner gäller högst
30 dagar, med HttpOnly/SameSite=Lax och Secure på HTTPS. Utloggning återkallar
nyckeln i databasen. Inloggning kontrollerar också lösenordsversionen atomärt
vid sessionsskapande så att en samtidig återställning inte kan kringgå spärren.
Försök begränsas i databasen per normaliserad inloggningsadress och nätadress;
räknarna gäller även mellan processer/omstarter och löper ut efter 15 minuter.

Använd befintlig HTTPS-konfiguration och `PUBLIC_BASE_URL` i drift. Lokalt
fungerar `scripts/dev.py` utan extern inloggningstjänst eller nya beroenden.
**Detta är en schemautökning:** gör separat granskad release med databasbackup
enligt `BETA.md`; behandla den inte som en enbart statisk apppatch. Arbetet
aktiverar inte betan eller ändrar driftsinställningar.

Integritetssidans befintliga radering omfattar den inloggade ägarens skafferi
och planer. Inloggningskontot behålls; separat kontoradering är inte implementerad.

## Verifiering

`backend/tests/test_smako_membership.py` provar riktiga lokala konton,
sessionsflöden, skafferi mellan klienter, dataseparation, revisionskonflikter,
återställning/utgång/utloggning, samtidighetsfallet vid återställning, begränsning
av inloggningsförsök samt gäst- och medlemsgränser på båda planerings-API:erna.
Browserproven kör registrering, skafferiöverföring och återinloggning i Chromium
på datorbredd och WebKit på mobilbredd mot en isolerad lokal testserver.
De använder inga privata användardata eller externa pristjänster.

Äldre numeriska planeringstester som kräver fem middagar/fyra portioner har
en uttrycklig fixture för autentiserad medlem. Separata gäst-, ägarskaps- och
kontotester använder inte denna fixture. Befintliga kända XFAIL är oförändrade.

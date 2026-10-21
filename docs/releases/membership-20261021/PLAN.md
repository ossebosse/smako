# Separat releaseplan: medlemskap och additivt kontoschema

Användaren begärde att uppdatera betan 2026-10-21. Kandidatens kod är
`c253cbd9ef93` (medlemskap `4474e06` och rättad PWA-cacheversion), ovanpå
aktiv `73306ac`. Detta är en granskad schemautökning,
inte en vanlig appändring utan databaspåverkan.

## Omfattning och migrering

Exakt tolv ändrade appfiler paketeras från Git. Beroenden, config.py,
grocery-kod, scheduler, proxy, volymer och driftmiljö behålls.
PlanStore lägger vid start till tre tabeller med `CREATE TABLE IF NOT EXISTS`:
`member_accounts`, `member_sessions`, `member_auth_attempts`, samt ett index.
Diffen i befintlig PlanStore är en import och ett executescript-anrop.
Ingen befintlig tabell, kolumn eller rad ändras av migreringen.

Före aktivering ska exakt Linuxkandidat verifieras med en separat databas:
skapa äldre schema med föregående runtime, lägg in syntetisk privat data,
kör kandidatens initiering två gånger, jämför gamla scheman och radhashar,
prova konto/session och öppna därefter databasen med föregående runtime igen.
Kandidatens kontoflöden och gästgränser provas utan produktionsvolymer.
Tidigare 314 fokuserade tester (3 befintliga XFAIL därutöver), Ruff,
compileall, JavaScript-syntax och desktop-/mobilprov återanvänds för oförändrad kod.

## Aktivering och återgång

Den befintliga releasehjälparens exakta filpaketering, imagebygge och
låsta backup-/appbytesmekanik återanvänds för denna separat granskade release.
Dess vanliga antagande om oförändrat schema ersätts här med ovanstående
explicit verifierade migrering och återgångsprov. Inga spärrar kring lease,
trafik, filhashar, retention, backup eller bevarande av tidigare data tas bort.

Före byte tas verifierad, konsistent backup av båda SQLite-databaserna i
ordinarie roterande backupkatalog under det gemensamma driftlåset.
Appbytet ändrar endast image och BUILD_ID. Efteråt krävs ready för Lund
och Malmö, oförändrade tidigare rader och prismanifest samt lyckad retention.
Publika prov använder enbart nya syntetiska konton/gästsessioner.

Vid fel återställs föregående appimage och compose-wrapper. Databasen
återställs inte: de nya oanvända tabellerna kan lämnas kvar och eventuell
ny medlemsdata bevaras för en korrigerad release. Medlemsfunktioner blir då
otillgängliga och gamla gästgränser återkommer. Återgångsprovet måste visa
att äldre runtime fortfarande kan öppna databasen och läsa tidigare skafferi.
Ingen automatisk nedmigrering eller tabellradering utförs.

Aktiveringens faktiska kvitton och efterkontroller journalförs i ACTIVATED.md.

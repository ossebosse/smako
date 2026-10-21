# Medlemskap aktiverat 2026-10-21

Appbyte klart **11:07:40 UTC / 13:07:40 Europe/Stockholm**.
Kod `c253cbd9ef93d82c3ff96d5470b6deae131ee82d`,
BUILD_ID `app-c253cbd9ef93-9940259d`, image
`sha256:dc23ba03be3ca2370d28d6230d392160a63fb278a56f5b0171ebe91947713072`.
Se [releaseplan](PLAN.md) och [kandidatverifiering](VERIFICATION.md).

## Bevarade data och runtime

Verifierad backup: `/srv/smako/backups/20261021T101710Z`.
Aktiveringskvittot bekräftar samtliga 310 tidigare planrevisioner och 119
privata tillståndsrader med oförändrade radhashar. Prismanifest och mounts
bevarades. Endast appen byttes och endast BUILD_ID ändrades i miljön.
Scheduler och proxy är oförändrade; alla tre containrar kör utan OOM och
utan omstarter efter start. Lund och Malmö är ready med kandidatens BUILD_ID.

Separat läsning efter aktivering verifierar oförändrade äldre tabelldefinitioner
och exakt tre nya tabeller: member_accounts, member_auth_attempts,
member_sessions. Ingen produktionsdatabas återställdes.

## Publika efterprov

Prov mot https://beta.smako.nu med nya syntetiska identiteter är godkända:

- Medlemssida och service worker med cacheversion v18 levereras korrekt.
- Båda planerings-API:erna avvisar gäster över 3 recept eller 2 portioner.
- Gäst i Lund: 3 recept, 2 portioner, färdig meny på 9,94 sekunder.
- Medlem i Malmö: 5 recept, 4 portioner, färdig meny på 17,39 sekunder.
- Båda menyerna har rätt antal olika rätter, högst två butiker, godkänd
  kassakontroll utan okända mängder eller underskott och identisk sparad återläsning.
- Registrering, säker sessionskaka, uttrycklig gästöverföring och skafferi
  från en andra inloggad klient fungerar.
- Återställningskod återkallar andra sessioner; ny inloggning bevarar skafferiet.
  Utloggning fungerar. Testkontots skafferi och planer raderades genom det
  publika integritetsflödet. Ett syntetiskt konto utan dessa data finns kvar;
  slumpmässiga inloggningsuppgifter sparades inte och ingen e-post skickades.

## Kvarvarande driftkontroll och fördröjning

**Appen är aktiverad och verifierad; releasekommandots efterretention pågår
vid journalföringen. Kommandots slutliga exitstatus är ännu inte verifierad.**
Underlag finns i `.local/membership-beta-20261021/`: activate.json,
active-verification.json och live-verification.json. Slutligt lagringskvitto
ska bli storage-after-activate.json. Kör inte samma aktivering igen.

Releaseflödet gör full retention före bygge, före aktivering, inuti backupen
och efter aktivering. De två avslutade fristående kontrollerna tog cirka
40 minuter var och frigjorde 0 byte. Backupsteget omfattade ytterligare
retention samt kopiering och integritetskontroll av en grocery-databas på
cirka 7,21 GB. Därutöver inväntades ett tidigare driftjobb före bygget.
Upprepningen förklarar väntetiden; exakt prestandaflaskhals i retentionen
är inte profilerad och ingen optimering eller säkerhetsgrind ändrades.

Föregående appimage för återgång är
`sha256:0ad2b6021e6a71b5a849edb42430d0a94c33ea152e58984353de8124182a0830`,
BUILD_ID `app-73306acc382d-0d139487`. Återgång får inte automatiskt återställa
databasen; ny medlemsdata måste bevaras enligt releaseplanen.

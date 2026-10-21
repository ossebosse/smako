# Verifierad medlemskapskandidat

Kod: `c253cbd9ef93d82c3ff96d5470b6deae131ee82d` på main.
BUILD_ID: `app-c253cbd9ef93-9940259d`.
Image: `sha256:dc23ba03be3ca2370d28d6230d392160a63fb278a56f5b0171ebe91947713072`.

Exakt tolv appfiler ändras från aktiv basbild
`sha256:0ad2b6021e6a71b5a849edb42430d0a94c33ea152e58984353de8124182a0830`.
Övriga 689 runtimefiler och bildens körkonfiguration är verifierade mot basen.
Den äldre admininställningen i basens config.py bevaras.

## Kod och användarflöden

[Full CI på kandidatens kod](https://github.com/ossebosse/smako/actions/runs/39568656554):
2 872 PASS, 10 befintliga XFAIL och 53 SKIP för saknat lokalt underlag.
Antalen är räknade från den fullständiga körningens pytest-resultatrader.
De fyra PWA-proven passerar även lokalt efter rättningen av cacheversionens namn.
Tidigare fokuserade medlemskaps-, planner- och browserprov beskrivs i
[MEMBERSHIP.md](../../MEMBERSHIP.md).

## Exakt Linuxbild och schema

Proven kördes med nätverk avstängt och separat syntetisk databas, utan
produktionsvolymer. Föregående runtime skapade databasen och sparade skafferi.
Kandidaten initierade databasen två gånger utan att ändra befintliga scheman
eller radhashar. Exakt de tre granskade kontotabellerna lades till.

Registrering med scrypt och beständig session fungerade. Därefter öppnades
den migrerade databasen med föregående runtime: samtliga rader bevarades vid
öppning, och läsning samt uppdatering av skafferi fungerade.

Kandidatens HTTP-prov verifierar registrering, Secure/HttpOnly/SameSite-kaka,
uttrycklig överföring av gästskafferi, åtkomst från en andra inloggad klient,
utloggning och API-gränserna 3 recept/2 portioner för gäster. Inloggad medlem
når planeringen med 5 recept/4 portioner; gästförsök över gränsen avvisas.
Själva menyberäkningen ersätts av en markör i detta isolerade HTTP-prov;
publik menyberäkning verifieras separat efter aktivering.

Läsning av betans verkliga schema före release visar endast
`consumer_plan_revisions` och `personal_private_state`, utan namnkollisioner.
Serverns backup- och retentionskod matchar granskad Git-kod efter
radslutsnormalisering. Backup och restore kopierar hela SQLite-filen, så de
nya tabellerna omfattas även om äldre semantiska delinventarier inte listar dem.
Ingen produktionsdatabas har återställts i dessa prov.

Detta är kandidatverifiering. Faktisk aktivering, backup och publika efterprov
journalförs separat i ACTIVATED.md. Privat underlag finns i
`.local/membership-beta-20261021/` och ingår inte i Git.

# Dashboard och drift 2026-10-28

Dashboardrättningen är aktiverad på https://beta.smako.nu/admin sedan
**2026-10-28 22:02:31 UTC**. Ladda om sidan för att hämta ny JavaScript.

## Aktiverad version och prov

- Kod `fac3a7e021a06038c76c2a281bc8c7623f026a34`, main-merge
  `c965426254bfab0e3ac1058216215534a588de7f` via [PR42](https://github.com/ossebosse/smako/pull/42).
- BUILD_ID `app-fac3a7e021a0-9fcadbe1`.
- Image `sha256:542132871f644fc1f1c186e5966e105ec4ea6cbb76249699b7493d5948ff47e3`,
  bas `sha256:d33eafe41e887d3b427ca2c85e0ef95309413b4de989a4eefb3ef170e55f16ac`.
- [Grön CI för PR](https://github.com/ossebosse/smako/actions/runs/40773482626)
  och [huvudgren](https://github.com/ossebosse/smako/actions/runs/40774758437).
- Exakt kandidat passerade vanlig uppstart och automatisk gemensam
  receptförberedelse, 189,66 s med 2 CPU/3 GiB och inget nätverk. Se
  [granskningen](REVIEW.md) och [EVIDENCE.json](EVIDENCE.json).

Fyra deklarerade appfiler ändrades. Övriga runtimefiler och konfiguration
verifierades oförändrade. Schedulern kör fortsatt
`beta-scheduler-2b65533af00d-contracts1`, image
`sha256:00d69bd1f4d5d4c6fa5a5fd6dc10d8eab9adef79654fb8669433a3112c37173d`.
Autentisering, produkt-/prisregler och användarval ändrades inte.

Befintligt driftlås skyddade verifierad backup `20261028T214850Z` och
appbyte. Alla tidigare plan-, profil- och kontorader finns kvar. Prismanifest,
mountar och övrig miljö bevarades; enbart BUILD_ID ändrades. Ordinarie
efterretention avslutades som complete. Rollback återställer kodbilden,
inte databaserna.

## Faktiskt verifierad dashboard

Slutkontroll **22:03:30 UTC** använde det autentiserade befintliga admin-API:t
och publika appen. Ingen behörighetsuppgift skrevs till kvittot.

| ICA-butik | Tillgängliga basposter |
| --- | ---: |
| Maxi Gunnesbo, Lund | 1 926 |
| Clemenstorget, Lund | 38 |
| Malmborgs Caroli, Malmö | 1 213 |
| Maxi Västra Hamnen, Malmö | 1 432 |

Clemenstorgets priser är kvalificerad äldre LKG från 23 september; dess
observationstid förnyades inte. Ett basantal innebär inte en heltäckande
ICA-katalog. De övriga ICA-kontexternas kampanjer redovisas separat.

Alla sju Willys-reklambladskontexter har nu visad lyckad körjournal från
27 oktober. Nästa hämtning visas som **29 oktober 03:17 svensk tid**.
Samma tid visas i gemensam serverstatus. Vid veckoschema projiceras sparade
äldre återförsökstider genom den aktiva tvånattspolicyn utan journaländring.

Offentligt hämtad JavaScript hade exakt kandidatens SHA-256. Admin-API utan
autentisering gav 401. Båda kommunernas publika readiness gav rätt BUILD_ID
och användbara obligatoriska kontexter med oförändrade pris-ID:n:

- Lund: `price-universe:0c617164ed822450e72b218929fe7c02f6647a2d07f08426c0ee89e0f9b590a2`.
- Malmö: `price-universe:b756752d4509a2c3597b676c7780e7a2c8a4fb0c2e7c332322d32a433cc5bee9`.

Inga nya externa prishämtningar eller publika menyberäkningar gjordes i denna
driftkontroll. Tidigare recept-/beräkningsarbete består; denna release gör
inget nytt påstående om kall menylatens eller full bibliotekstäckning.

## Återställd kvittens och kvarvarande källfel

Malmö-Willys fyra kataloger från 28 oktober var redan publicerade och laddade.
Den saknade beständiga Windowskvittensen återställdes **21:35:49 UTC** genom
ordinarie återleverans/import. Servern svarade `already_active` för exakt
samma artefakt och Malmöprisversion. `pending_delivery=false` verifierades.
Källtiderna behölls och en callback spärrade varje ny källinsamling i körningen.

Lund-Willys kataloger är från 27 oktober. Åldersvarningen består, liksom
användbara kvalificerade baspriser. Windowsuppgiften kör fortfarande paket
`2464596b6f07` med dagliga starttider; ny veckoregistrering kräver fortfarande
administratör. Det installerade nya paketet är inte bevis för aktiverat schema.
Det befintliga skriptet `.local/beta-all-20261028/activate_windows_admin.ps1`
är fortfarande den granskade administratörsåtgärden.

Coop-felen är **inte lösta av dashboardändringen**:

- Fyra Lund- och sex Malmöbutiker stoppas av det nya fältet
  `row.environmentalCode`; vardera har 14 efterföljande avvisade försök.
  Äldre, fortfarande giltiga kampanjer behålls.
- Malmö Central, Kornettsgatan och Djupadal har timeout vid hämtning av
  erbjudandesidan. X:-tra Nydala har ett separat återkommande källfel.
- Coop Online Syd `730400` använder 17 oktobers kvalificerade baspriser.
  Den avvisade kompletta källan har ändrat schema för kampanjers maxantal.

Nästa källreparation behöver granskning av de faktiska nya fälten och ett
versionsbundet paket med negativa pris-/identitetsprov. Ingen okänd miljö-
kod får användas för att påstå eko, och inget maxantal får antas obegränsat.
Gamla felkällor får inte omdateras för att göra driftstatus grön.

Skyddat råunderlag: `.local/ops-dashboard-20261028/`,
`.local/dashboard-app-v2-20261028/` och serverns
`/opt/smako/evidence/app-fac3a7e021a0-9fcadbe1/`.

# Driftåterställning 8 oktober – pågår

Windowsregistreringen är återläst: fe795e5b04f5, 625 paketfiler matchar.
Hela XML utom Actions matchar föregående definition. Konto ossia, S4U/Limited,
pinnad PowerShell och 01:30/09:30/17:30 är bevarade. Ingen omregistrering gjord.
Administratörens före/efter-XML är daterade 08:32:59 UTC.

Kontrollerad Scheduler-start 11:02:55 UTC: lagringsprovet passerar i session 0,
förälder och barn skapar temporärfiler direkt i kommunarbetsytans D:/tmp.
Inga prisanrop i detta prov. Riktig återleveranskörning startad 11:07:19 UTC.

Servern hade 0 byte ledigt; efter fem exakt arkiverade testkataloger och
61 identifierade byggcacheposter hade samma volym 14 007 619 584 byte ledigt.
Fyra arkiverade testdatabaser lämnades kvar. Inga produktionsdata, köer,
kvittorader, runtime-images eller användardatabaser raderades.
Arkivet och full återställningskopia finns kvar på skyddad D:-lagring.
Detaljer och faktisk uppmätt radering: CLEANUP.json.

Planlagring och grocery svarar åter ok; 216 befintliga revisioner och
61 privata tillståndsrader fingerprintade före menyproven. Betans dd12-image
och starttid är oförändrade. /ready är ännu 503 på gamla prisbaser.

Nattens bdc9 hämtade ett aktuellt paket 989f961ccfc64984a830de9584d437d5.
Morgonens transport misslyckades. Nuvarande fe-körning återlevererar paketet,
med autentiska observationer från 7 oktober 23:31 UTC. Inget nytt fullcrawl
utfört för Willys av oss. Import/publicering/slutkvitto återstår.

Ingen appaktivering, Git-push, ändrad källa, schema eller färskhetsgräns.

## Kapacitetsmarginal och bevisgränser

Före återleverans krävde det befintliga skyddet 7 521 539 842 byte plus
536 870 912 reserv; 14 007 607 296 byte fanns tillgängligt. Under ombyggnad
skapas ordinarie tillfällig källdatabas på 3 554 885 632 byte. Vid 11:22 UTC
fanns cirka 10,1 GB ledigt även med den kopian aktiv. Ingen aktiv tempfil raderad.
Byggcacheverktyget rapporterade 7,481 GB; uppmätt ytterligare frigörelse var
cirka 5,27 GB. Skillnaden behandlas inte som ytterligare säkert återvunnet utrymme.

Långsiktig retention är fortfarande ett separat beslut. Nuvarande skyddade
backups uppmättes tidigare till cirka 60,9 GB; ingen generell backupretention
eller automatisk rådataradering har införts. Aktuell arbetsmarginal ersätter
inte behovet av en framtida referensstyrd arkiveringspolicy.

D:-provet använder verklig S4U/session 0. Den nya körningen återlevererar ett
redan färdigt paket; inga nyinsamlade råsvar eller ny lokal insamlingsdatabas
påstås skapade av fe795 i detta återleveransprov. De återanvända råsvaren,
kandidatdatabasen och paketet ligger i den befintliga kommunarbetsytan på D:.
Det tidigare isolerade lagrings-/paketeringsbeviset gäller oförändrad kod.

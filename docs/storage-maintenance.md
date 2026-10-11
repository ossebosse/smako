# Lagring och säker arkivering

Inventeringen 2026-10-11 fann 403,1 GB använt och 12,3 GB ledigt på rotfilsystemet.
Serverdisken är 400 GiB; rotfilsystemets användbara storlek är 415,4 GB i decimala
enheter. Använd samma enhet när före/efter jämförs.

| Katalog | Allokerat före, GB | Innehåll |
| --- | ---: | --- |
| `/var/lib/containerd` | 161,4 | Containerbilder, lager och byggcache |
| `/var/tmp` | 116,7 | Historiska utvecklings-/testmiljöer, ofta med egna databaser |
| `/srv/smako/backups` | 65,0 | Dagliga och särskilda återställningspaket |
| `/srv/smako/data` | 33,6 | Databaser, råunderlag, prisuniversum, planer och rapporter |
| `/opt/smako/evidence` | 17,7 | Tidigare verifierings- och återställningsunderlag |

Detta är fysisk katalogstorlek. Dockers redovisning av bilder och byggcache
delar lager och får inte adderas som oberoende diskutrymme. `/tmp` är tmpfs;
dess användning är inte förklaringen till att rotfilsystemet fylldes.

## Arkiveringsverktyget

`scripts/archive_cold_test_tree.py` är en operatörsprimitiv för **en explicit
granskad** kall testkatalog direkt under `/var/tmp`. Den är inte en automatisk
städare. Anroparen måste först ta befintligt gemensamt produktionslås enligt
`RefreshRunLock`/`production_refresh_lock_path`. Avbryt eller vänta om upptaget;
stoppa inte pågående insamling. Kör inte samtidigt med en annan operatör.

Verktyget avvisar symlänkade rötter, ICA-namn, specialfiler, utökade attribut och
referenser från processer, samtliga Dockercontainrar (även stoppade) eller aktuell
servicekonfiguration. Operatören måste dessutom granska planerade releaser och
externa referenser; automatisk referenssökning ersätter inte den granskningen.

Alla filer hashas före arkivering. Ett privat gzip/tar-arkiv och inventarium
skrivs och fsyncas. Varje arkivmedlem verifieras inklusive filinnehåll, ägare,
behörigheter och symlänkar; hela ursprungsträdet måste fortfarande vara
oförändrat och oanvänt innan just den granskade roten tas bort. Fel behåller
originalet. Befintliga arkiv skrivs aldrig över. Misslyckade/avbrutna försök
kräver granskning före omkörning och kan lämna ett partiellt arkiv.

Linuxprov (sex isolerade fall, inga produktionsanrop):

```sh
python -m unittest discover -s scripts -p test_archive_cold_test_tree.py -v
```

Vid containerprov krävs minst 1 GiB ledigt i testets tmpfs eftersom
arkiveringsverktyget reserverar ytterligare 512 MiB i staging-kontrollen.

## Återställning av ett kallt testträd

Arkiv finns i `/srv/smako/cold-test-archives`, skyddade med katalogläge 0700 och
filläge 0600. Bevis och exakt urvalslista finns i
`/opt/smako/evidence/storage-reduction-20261011`. De är lokala återställningskopior,
inte en ersättning för extern backup.

1. Välj exakt arkiv från resultatlistan, kontrollera dess SHA-256 mot resultatet
   och kör `verify(archive, expected)` med tillhörande privata inventarium.
2. Ta driftlåset och kontrollera att den ursprungliga sökvägen är ledig samt att
   utrymme finns för inventariets expanderade filstorlek och driftmarginal.
3. Packa upp just det betrodda, verifierade arkivet med `tar -xpf <arkiv.tar.gz>
   -C /var/tmp` som administratör. GNU tar detekterar gzip vid läsning.
4. Verifiera återställda filhashar, symlänkar, ägare och behörigheter. Inode/ctime
   blir nya efter återställning och ska inte jämföras som identiska.

Återställning startar ingen container och ändrar ingen produktionskonfiguration.

## Begränsa fortsatt tillväxt

- Skapa inga nya fullständiga daterade projekt-/databaskopior på servern som
  standard. Använd det permanenta repot och avgränsade fixtures; arkivera granskade
  avslutade testmiljöer efter verifiering.
- Rensa endast oanvänd byggcache genom Dockers API i ett ledigt driftfönster.
  Radera aldrig containerd-lager direkt. Cache kan byggas om; bilder, containerdata
  och volymer har annan betydelse och får inte följa med i en generell prune.
- Behåll körande/stoppade containerreferenser, nuvarande release, återgångsversion
  och väntande ICA-arbete. Äldre bildhistorik kan granskas separat mot dessa
  referenser. Att Docker kallar något reclaimable är inte tillräckligt beslut.
- Backupkodens standard är 14 dagar, men rensning sker först efter en lyckad ny
  verifierad backup. Särskilda aktiveringspaket följer inte den dagliga rotationen.
  Kontrollera faktisk inställning och lyckad återställning innan retention ändras.
- Inför större kommunutrullning behövs retention för råunderlag, gamla
  prisartefakter och rapporter som respekterar aktiva/LKG-/plan-/auditreferenser,
  samt kommunövergripande verifierad backup. Kommunantal ensamt dimensionerar
  inte lagring; antal butiker, katalogstorlek och sparad historik avgör tillväxten.

Inga scheman, källkvalitetsgränser eller backupretention ändras av arkiveringen.

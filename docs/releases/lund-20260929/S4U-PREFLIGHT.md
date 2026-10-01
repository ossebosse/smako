# S4U: förkontroller 2026-10-01

**Historiskt förkontrollunderlag.** Operatören körde därefter uppgiften.
[S4U-LIVE.md](S4U-LIVE.md) redovisar PASS för exakt den avslutade körningen.
Nedanstående startkommando och tidsbegränsade kvitto är inte tillstånd
att köra uppgiften igen.

Operatören har registrerat testuppgiften. Den har **inte startats** av
Codex. Start kräver fortfarande separat uttryckligt godkännande för den
isolerade livekörningen. Detta är inte något av produktionsbesluten.

## Registrerad definition

Återläst `\Smako Lund bdc9 S4U isolated verification`:

- Program: `C:\Users\ossia\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe`.
- Argument: `-NoProfile -NonInteractive -File "D:\Projects\Smako\.local\drift-verification\s4u\run_s4u_probe.ps1"`.
- Arbetskatalog: `D:\smako-local-relay\releases\bdc9f7df4170`.
- Konto `ossia`, LogonType **S4U**, RunLevel **Limited**.
- **0 trigger-element** i registrerad XML. PowerShells `@($null).Count`
  kan ge 1 och har inte använts som bevis för en trigger.
- LastTaskResult `0x41303`, aldrig körd. Inget startanrop har gjorts.
- Observatörens SHA-256
  `66551d592c2a992adc09b74a5ca09b32c7a84cd3d8b5b84d55a850b4bae5316f`
  matchar operatörens registreringsunderlag. Den anropar oförändrat
  versionsbundet startskript med egen konfiguration och `s4u/state`.

Produktionsuppgiftens exporterade XML har fortsatt SHA-256
`c781d10ce504aa172d8006f365f7ad167ac2ca23688fcf629d1b0851c5ff6755`.
Ingen uppgift, trigger, principal, säkerhetspolicy eller schemainställning
har ändrats vid dessa förkontroller.

## Faktisk PowerShell och körpolicy

Den registrerade binären är signerad (`Valid`), version **7.6.5**,
SHA-256 `362a356ce7f0940ec74f73a8fc2c990a2cc24a38a11c90bbd8eca947110ad139`.
En ny process med exakt denna binär, `-NoProfile -NonInteractive` och
**utan Bypass**, visar:

| Värd | MachinePolicy / UserPolicy / Process / CurrentUser | LocalMachine / effektiv |
| --- | --- | --- |
| Uppgiftens PS7 | Samtliga Undefined | RemoteSigned |
| Windows PowerShell 5.1 | Samtliga Undefined | AllSigned |

PS7 läser sin befintliga `powershell.config.json`, där
`Microsoft.PowerShell:ExecutionPolicy=RemoteSigned`. Filens SHA-256 är
`98c0e5b6ee17eb8b8f4e4940c2b2528689cec8470db4bde427ad16d90d6a52d4`.
Den har inte ändrats. Den tidigare AllSigned-observationen är alltså riktig
för Windows PowerShell 5.1, men beskriver inte den registrerade PS7-värden.
Registreringsprocessens tillfälliga Bypass har inte använts som bevis.

Observatören, `start_packaged_relay.ps1` och dess dot-sourcade
`relay_process_lifetime.ps1` är osignerade men har endast `:$DATA`, ingen
`Zone.Identifier`. Det versionsbundna startskriptet kördes separat med
`-CheckInstall`, exakt PS7, utan policyöverstyrning: exit 0, **624 filhashar
verifierade**, rätt bdc9-commit/Python 3.12.10, **0 nätanrop**. Därmed är
startskriptets och hjälpskriptets laddning provad under aktuell policy.
Observatören och själva S4U-sessionen har inte körts. Förutsättningarna
överensstämmer med [Microsofts beskrivning av RemoteSigned](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies?view=powershell-7.6).
Ingen ändring av argument, signering eller permanent policy behövs på
grund av dessa mätningar. Kontrollera om policyn ändras före ett senare prov.

## Isolering och startgräns

Mottagare: `smako-lund-ops-s4u`, bild
`sha256:2f81344208e05cbc57d16fa74a73c97b26bc729859936ca5d96ab150579fe221`.
Dess enda datavolym är
`/var/tmp/smako-repo-release-20260929/ops-verification/s4u-data:/work`;
nätläge `none`, inga publicerade portar, ingen automatisk omstart.
Behovsstyrd källuppdatering görs i en separat engångscontainer med nät,
samma testdata och ordinarie operationslås. Mottagaren hålls stoppad medan
uppdateraren arbetar. Inga produktionsvolymer eller scheman används.

Förkontrollen 06:04 UTC fann Coop och Hemköp förfallna enligt 35-timmars
behovsstyrning, medan Willys inte var förfallen. Äldsta basobservation var
2026-09-29 11:53:03 UTC, drygt 42 timmar: AGING men ännu inte 48-timmarsstopp.
Uppdateringen använder den befintliga vägen med Coop Online Syd 730400,
Hemköps befintliga allowlist 4123/4224, och frivilliga källors vanliga
behovsurval. Ingen Willys-fullhämtning görs före det godkända liveprovet.

`s4u/state` innehåller bara verklig konfigurerad kommunbindning 1281, inget
kvitterat/replay-underlag som skulle låta liveprovet stanna vid `not_due`.
`receiver-ready.json` får skapas först efter färsk råfilskontroll, validerad
aktiv artefakt, fem giltiga obligatoriska baskontexter och kontroll av
**faktiskt laddat** manifest. Giltigheten begränsas till högst två timmar
och dessutom två timmars marginal till tidigaste basstopp. Ingen start
utlöses av denna fil.

Exakt kommando som användaren senare ska godkänna, efter godkänd kontroll:

```powershell
Start-ScheduledTask -TaskPath '\' -TaskName 'Smako Lund bdc9 S4U isolated verification'
```

## Slutlig förkontroll och tidsbegränsat kvitto

**Förkontroller klara; inget startgodkännande givet och ingen testuppgift körd.**
Mottagaren är startad isolerat och lämnas igång utan scheman, med samma
bild/enda testvolym/nätläge `none`/inga portar/omstart `no` som ovan.
Engångsuppdateraren har avslutats. [Maskinläsbart bevis](S4U-PREFLIGHT-EVIDENCE.json)
innehåller återläsning, faktiskt reload-resultat och slutlig serving-kontroll.

Behovsstyrd liveuppdatering avslutades 07:22 UTC med **exit 2 / degraded**:
Coop Online Syd 11 428, Hemköp 6 232 respektive 5 092 hämtade produkter,
alla tre `healthy` och inga insamlingsfel. Ordinarie lås och atomisk
publicering användes. Willys återanvändes med sina ursprungliga observationer;
befintlig artefakt fick `duplicate`, **0 nätanrop**, utan dubbelimport.
Efter uppdateringen visar behovskontrollen `work_due=false`, tom
`due_sources`, **0 externa prisanrop** i själva kontrollen.

`degraded` får inte döljas: den generiska Coop-offertkandidaten
`55e9c8ba…` promoterades inte (85,1 % produktfall). X:-tras separata
butiksbundna flöde 3658 gav en partiell kandidat med **11 kvalificerade
PU-rader och 39 i karantän**; snapshot-status `broken`/22 % parsing.
ICA hade 3 respektive 12 rapporterade radfel, den senare källan `degraded`.
Detta är frivilliga erbjudandetillskott, inte brister i de fem obligatoriska
onlinebaserna eller bevis för full erbjudandetäckning. Inga adaptrar,
kvalitetskrav, kommunbindningar eller källtider ändrades för detta prov.

Faktisk serving-reload gick från det tidigare **44 132**-manifestet
`624e4de9…` till följande nya **44 080**-manifest. Efter start av den separata
mottagarprocessen verifierades samma universe-ID, radantal och snapshot-ID:n
via ordinarie HTTP mot den aktiva, hashkontrollerade artefakten.

- Universe: `price-universe:a69651bdd5bae3326e23269cf86829d1569ea809061e6e0a02434a1a478a4fd8`.
- Manifest SHA-256: `821bb564c63ae1ddb2112c95d98d928882e09c67ccc79a50c806d83180def223`.
- Artefakt SHA-256: `b0bb2fd6f191b2362a7912d617a073f94ea3a265eabb679a509b756591d3ddd3`.
- **2 232 refererade OWN-råfiler, 0 saknade/hashfel**, kontroll 07:22:28 UTC.
- HTTP `/ready` 200 och faktiskt manifest verifierade **07:25:03 UTC**.
  Första omedelbara anslutningsförsöket under processens startup nekades;
  inget kvitto skapades förrän startup och samtliga kontroller passerat.

| Obligatorisk kontext (ID-suffix) | Äldsta verkliga observation UTC | Ålder vid kontroll | Status |
| --- | --- | --- | --- |
| Coop `23eaae11c9661e68` | 2026-10-01 06:09:21 | 1,262 h | FRESH |
| Hemköp `3288e04edd97e349` | 2026-10-01 06:55:05 | 0,500 h | FRESH |
| Hemköp `756955d0e6e05f23` | 2026-10-01 06:39:40 | 0,756 h | FRESH |
| Willys `383650ec6ff5a636` | 2026-09-30 09:13:41 | 22,190 h | FRESH |
| Willys `4a671428fc484e43` | 2026-09-30 09:35:23 | 21,828 h | FRESH |

Detta är ett **tredje manifest**, inte en omkörning av profilproven på
42 491 poster eller återgångsproven på 44 132 poster. Inga sådana prov
räknas om som nya resultat här.

Först efter kontrollerna skapades
`D:\Projects\Smako\.local\drift-verification\s4u\receiver-ready.json`,
SHA-256 `2f50da3cf88625e515842ef9e6a4cc6cd529fe89ad6e378e0ce689a0ac306b27`.
Gäller till **2026-10-01 09:25:03 UTC / 11:25:03 Europe/Stockholm**.
Efter denna tid måste mottagare, manifest, råfiler och åldrar kontrolleras
på nytt; ändra inte bara kvittots sluttid. Oförändrade 36/48-gränser gäller.

Slutåterläsning: testets LastTaskResult är fortfarande `0x41303`, testets
tillstånd innehåller endast `source-scope.json`, och produktionsuppgiftens
XML-hash är oförändrad. Varken uppgiftsargument eller säkerhetspolicy har
ändrats. Endast verifieringsverktyg/underlag ändrades i Git; bdc9-paketen
och driftkoden är oförändrade. Ruff och compileall för de två nya
Pythonverktygen passerar. De tidigare testsiffrorna är inte omkörda här.

**Nästa separata beslut är godkännande av exakt startkommando ovan för
den isolerade livekörningen.** S4U-hämtning, nät/nyckelåtkomst och obevakad
leverans är fortfarande EJ PRÖVADE. Releaseövergångens och den äldre bildens
läskompatibilitet är separata öppna driftspärrar: den samlade releasen är
fortfarande **INTE REDO** för produktionsaktiveringsbeslut.

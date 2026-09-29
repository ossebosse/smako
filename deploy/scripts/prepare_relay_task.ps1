[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Release,
    [Parameter(Mandatory=$true)][string]$Workspace,
    [Parameter(Mandatory=$true)][string]$Config,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [string]$TaskName = 'Smako Willys Local Relay'
)
$ErrorActionPreference = 'Stop'
$relayRoot = (Resolve-Path -LiteralPath $Release).Path
if (-not (Test-Path -LiteralPath (Join-Path $relayRoot 'RELEASE.json'))) { throw 'Pinned release required.' }
foreach ($relayValue in @($relayRoot, $Workspace, $Config)) {
    if ($relayValue.Contains('"')) { throw 'Quoted paths are unsupported.' }
}
if (Test-Path -LiteralPath $OutputDirectory) { throw 'Use a new private output directory.' }
New-Item -ItemType Directory -Path $OutputDirectory | Out-Null
$relayXml = Export-ScheduledTask -TaskName $TaskName
$relayXml | Set-Content -LiteralPath (Join-Path $OutputDirectory 'task-before.xml') -Encoding Unicode
[xml]$relayCandidate = $relayXml
$relayNs = New-Object Xml.XmlNamespaceManager($relayCandidate.NameTable)
$relayNs.AddNamespace('t', $relayCandidate.DocumentElement.NamespaceURI)
$relayActions = $relayCandidate.SelectNodes('//t:Actions/t:Exec', $relayNs)
if ($relayActions.Count -ne 1) { throw 'Review unexpected task action count.' }
$relayAction = $relayActions[0]
$relayAction.Arguments = '-NoProfile -NonInteractive -File "{0}" -Workspace "{1}" -Config "{2}"' -f (Join-Path $relayRoot 'deploy/scripts/start_packaged_relay.ps1'),$Workspace,$Config
$relayAction.WorkingDirectory = $relayRoot
$relayCandidate.Save((Join-Path ([IO.Path]::GetFullPath($OutputDirectory)) 'task-proposed.xml'))
Write-Output 'Prepared only. Program, principal, triggers, rights and all settings preserved. No task registration performed.'

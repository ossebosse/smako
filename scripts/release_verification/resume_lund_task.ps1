#requires -Version 7.0
[CmdletBinding()]
param([switch]$Enable)
$ErrorActionPreference = 'Stop'
$root = 'D:\Projects\Smako\.local\activation-live-20261001'
$evidence = Get-Content -LiteralPath "$root/production-acceptance-ready.json" -Raw | ConvertFrom-Json
if ($evidence.status -ne 'PASS' -or $evidence.server_runtime -ne '08c137475d9ca96a6ef7673245a639c8c5c9e922') { throw 'Production acceptance is not confirmed.' }
$age = [DateTimeOffset]::UtcNow - [DateTimeOffset]::Parse($evidence.checked_utc)
if ($age.TotalMinutes -lt 0 -or $age.TotalMinutes -gt 60) { throw 'Acceptance must be rechecked before enabling.' }
$service = New-Object -ComObject Schedule.Service
$service.Connect()
$folder = $service.GetFolder('\')
$task = $folder.GetTask('Smako Willys Local Relay')
function ProtectedXml([string]$text) {
    [xml]$doc = $text
    $ns = [Xml.XmlNamespaceManager]::new($doc.NameTable)
    $ns.AddNamespace('t', $doc.DocumentElement.NamespaceURI)
    $node = $doc.SelectSingleNode('//t:Settings/t:Enabled', $ns)
    if ($node) { $null = $node.ParentNode.RemoveChild($node) }
    $doc.DocumentElement.OuterXml
}
$expected = Get-Content -LiteralPath "$root/windows-paused.xml" -Raw
if ((ProtectedXml $task.Xml) -ne (ProtectedXml $expected)) { throw 'Task changed since approved paused readback; inspect first.' }
if ($task.State -eq 4 -or $task.GetInstances(0).Count -ne 0) { throw 'Unexpected running relay.' }
$acl = $task.GetSecurityDescriptor(4)
if (-not $Enable) { Write-Output 'Acceptance and paused task validated only.'; return }
# Change only Enabled; no registration, account, policy, action or trigger edits.
$task.Enabled = $true
$after = $folder.GetTask('Smako Willys Local Relay')
if (-not $after.Enabled -or (ProtectedXml $after.Xml) -ne (ProtectedXml $expected) -or $after.GetSecurityDescriptor(4) -ne $acl) { throw 'Unexpected enable readback; inspect immediately.' }
$after.Xml | Set-Content -LiteralPath "$root/windows-enabled.xml" -Encoding utf8
[ordered]@{checked_utc=[DateTimeOffset]::UtcNow.ToString('o');enabled=$after.Enabled;state=$after.State;next_run_local=$after.NextRunTime.ToString('o');task='Smako Willys Local Relay';protected_fields_unchanged=$true;acl_unchanged=$true} | ConvertTo-Json | Tee-Object -FilePath "$root/windows-enabled-evidence.json"

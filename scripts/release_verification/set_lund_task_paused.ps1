#requires -Version 7.0
[CmdletBinding()]
param([switch]$ApplyPaused)
$ErrorActionPreference = 'Stop'
$taskName = 'Smako Willys Local Relay'
$root = 'D:\Projects\Smako\.local\activation-approved-20261001'
New-Item -ItemType Directory -Force -Path $root | Out-Null
$service = New-Object -ComObject Schedule.Service
$service.Connect()
$folder = $service.GetFolder('\')
$task = $folder.GetTask($taskName)
$before = $task.Xml
$expectedXmlHash = 'd9b7266e5dc36956849171171b96db18242df6eb0e2c0ed2c3f73c3759c28e70'
$actualXmlHash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($before))).ToLowerInvariant()
if ($actualXmlHash -ne $expectedXmlHash) { throw 'Task differs from reviewed original. Inspect rather than overwrite later work.' }
$release = 'D:\smako-local-relay\releases\bdc9f7df4170'
$manifest = Get-Content -LiteralPath (Join-Path $release 'RELEASE.json') -Raw | ConvertFrom-Json
if ($manifest.commit -ne 'bdc9f7df417084641d0a712e3dad188dad1ad7d4') { throw 'Wrong relay release.' }
foreach ($file in $manifest.files.PSObject.Properties) {
    if ((Get-FileHash -LiteralPath (Join-Path $release $file.Name)).Hash -ne $file.Value) { throw "Package mismatch: $($file.Name)" }
}
[xml]$xml = $before
$ns = [Xml.XmlNamespaceManager]::new($xml.NameTable)
$ns.AddNamespace('t', $xml.DocumentElement.NamespaceURI)
function Node([string]$path) { $xml.SelectSingleNode($path, $ns) }
function ProtectedXml([string]$text) {
    [xml]$document = $text
    $namespaces = [Xml.XmlNamespaceManager]::new($document.NameTable)
    $namespaces.AddNamespace('t', $document.DocumentElement.NamespaceURI)
    foreach ($path in @('//t:Triggers', '//t:Settings/t:Enabled', '//t:Actions/t:Exec/t:Arguments', '//t:Actions/t:Exec/t:WorkingDirectory')) {
        $node = $document.SelectSingleNode($path, $namespaces)
        if ($node) { $null = $node.ParentNode.RemoveChild($node) }
    }
    $document.DocumentElement.OuterXml
}
if ((Get-TimeZone).Id -ne 'W. Europe Standard Time') { throw 'Unexpected local timezone.' }
if ((Node '//t:LogonType').InnerText -ne 'S4U') { throw 'Unexpected LogonType.' }
$runLevel = Node '//t:RunLevel'
if ($runLevel -and $runLevel.InnerText -ne 'LeastPrivilege') { throw 'Unexpected RunLevel.' }
foreach ($entry in @{'ExecutionTimeLimit'='PT3H';'MultipleInstancesPolicy'='IgnoreNew';'StartWhenAvailable'='true';'WakeToRun'='true'}.GetEnumerator()) {
    if ((Node ('//t:Settings/t:' + $entry.Key)).InnerText -ne $entry.Value) { throw "Unexpected $($entry.Key)." }
}
if ($task.State -eq 4 -or $task.GetInstances(0).Count -ne 0) { throw 'Wait for the existing task to finish.' }
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
if ((Node '//t:Principal/t:UserId').InnerText -ne $identity.User.Value) { throw 'Caller must be the existing ossia account, including when elevated.' }
$triggers = Node '//t:Triggers'
if ($triggers.ChildNodes.Count -ne 1) { throw 'Expected original single trigger; inspect before resuming a partial activation.' }
$originalTrigger = $triggers.FirstChild.CloneNode($true)
$triggers.RemoveAll()
# Floating local clock boundaries preserve these Stockholm wall-clock times
# across DST. Tomorrow prevents catch-up of newly added past triggers today.
foreach ($hour in @(1, 9, 17)) {
    $trigger = $originalTrigger.CloneNode($true)
    $trigger.SelectSingleNode('t:StartBoundary', $ns).InnerText = (Get-Date).Date.AddDays(1).AddHours($hour).AddMinutes(30).ToString('yyyy-MM-ddTHH:mm:ss')
    $null = $triggers.AppendChild($trigger)
}
$settings = Node '//t:Settings'
$enabled = Node '//t:Settings/t:Enabled'
if (-not $enabled) {
    $enabled = $xml.CreateElement('Enabled', $xml.DocumentElement.NamespaceURI)
    $null = $settings.AppendChild($enabled)
}
$enabled.InnerText = 'false'
# The final approved action is staged while DISABLED. Its private production
# configuration is checked during the coordinated cutover before any start.
(Node '//t:Actions/t:Exec/t:Arguments').InnerText = '-NoProfile -NonInteractive -File "D:\smako-local-relay\releases\bdc9f7df4170\deploy\scripts\start_packaged_relay.ps1" -Workspace "D:\smako-local-relay\scopes\municipality-1281" -Config "D:\smako-local-relay\config\relay.json"'
(Node '//t:Actions/t:Exec/t:WorkingDirectory').InnerText = $release
$proposed = $xml.OuterXml
if ((ProtectedXml $before) -ne (ProtectedXml $proposed)) { throw 'Unexpected change outside approved fields.' }
$before | Set-Content -LiteralPath "$root/schedule-original.xml" -Encoding utf8
$proposed | Set-Content -LiteralPath "$root/schedule-paused-proposed.xml" -Encoding utf8
$null = $folder.RegisterTask($taskName, $proposed, 1, 'ossia', $null, 2, $null) # TASK_VALIDATE_ONLY
if (-not $ApplyPaused) {
    Write-Output 'XML/package validated only. ApplyPaused stages approved Arguments/WorkingDirectory and local 01:30/09:30/17:30; leaves existing task DISABLED; never starts it.'
    return
}
$beforeDacl = $task.GetSecurityDescriptor(4)
try {
    # TASK_UPDATE | TASK_DONT_ADD_PRINCIPAL_ACE. Same account, S4U and XML RunLevel.
    $null = $folder.RegisterTask($taskName, $proposed, 20, 'ossia', $null, 2, $null)
} catch {
    $unchanged = $folder.GetTask($taskName).Xml -eq $before
    [ordered]@{utc=[DateTime]::UtcNow.ToString('o');operation='RegisterTask TASK_UPDATE|TASK_DONT_ADD_PRINCIPAL_ACE';task=$taskName;caller=$identity.Name;elevated=([Security.Principal.WindowsPrincipal]::new($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator);hresult=('0x{0:X8}' -f ($_.Exception.HResult -band 0xffffffffL));message=$_.Exception.Message;task_unchanged=$unchanged} |
        ConvertTo-Json | Set-Content -LiteralPath "$root/schedule-update-error.json" -Encoding utf8
    throw
}
$after = $folder.GetTask($taskName)
if ($after.Enabled) { throw 'Expected task to remain paused.' }
if ($after.GetSecurityDescriptor(4) -ne $beforeDacl) { throw 'Unexpected task ACL change.' }
$after.Xml | Set-Content -LiteralPath "$root/schedule-paused-registered.xml" -Encoding utf8
if ((ProtectedXml $before) -ne (ProtectedXml $after.Xml)) { throw 'Readback changed a protected field; keep paused and inspect.' }
[xml]$readback = $after.Xml
$times = @($readback.SelectNodes('//t:CalendarTrigger/t:StartBoundary', $ns) | ForEach-Object { $_.InnerText.Split('T')[1] })
if (($times -join ',') -ne '01:30:00,09:30:00,17:30:00') { throw 'Wrong trigger readback; keep paused.' }
foreach ($path in @('//t:Actions/t:Exec/t:Arguments', '//t:Actions/t:Exec/t:WorkingDirectory')) {
    if ($readback.SelectSingleNode($path, $ns).InnerText -ne $xml.SelectSingleNode($path, $ns).InnerText) { throw 'Wrong action readback; keep paused.' }
}
foreach ($trigger in $readback.SelectNodes('//t:CalendarTrigger', $ns)) {
    if ($trigger.SelectSingleNode('t:ScheduleByDay/t:DaysInterval', $ns).InnerText -ne '1' -or $trigger.SelectSingleNode('t:Repetition', $ns)) { throw 'Unexpected repetition; keep paused.' }
}
Write-Output 'Existing task staged for bdc9 and local 01:30/09:30/17:30, PAUSED. Principal, pinned PowerShell, policy and other settings preserved. Do not enable/start before coordinated cutover verification.'

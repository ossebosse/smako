[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ReleaseRoot,
    [Parameter(Mandatory=$true)][string]$Workspace,
    [Parameter(Mandatory=$true)][string]$Config,
    [Parameter(Mandatory=$true)][string]$EvidenceDirectory,
    [string]$TaskName = 'Smako Willys Local Relay'
)
$ErrorActionPreference = 'Stop'
$release = (Resolve-Path -LiteralPath $ReleaseRoot).Path
$scopeRoot = (Resolve-Path -LiteralPath $Workspace).Path
$transport = (Resolve-Path -LiteralPath $Config).Path
foreach ($path in @($release, $scopeRoot, $transport)) {
    if ($path.Contains('"')) { throw 'Paths must not contain quote characters.' }
}
if ([IO.Path]::GetFileName($scopeRoot) -match '^municipality-') {
    throw 'Workspace must be the parent of the existing municipality directories.'
}
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
if ($task.State -ne 'Ready') { throw 'Existing task must be idle before changing its action.' }
if (@($task.Actions).Count -ne 1) { throw 'Expected one existing task action.' }
& (Join-Path $release 'deploy/scripts/start_packaged_relay.ps1') -Workspace $scopeRoot -Config $transport -Municipalities -CheckInstall
if ($LASTEXITCODE -ne 0) { throw 'Installed release integrity check failed.' }
$before = [xml](Export-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath)
New-Item -ItemType Directory -Path $EvidenceDirectory -ErrorAction Stop | Out-Null
$evidence = (Resolve-Path -LiteralPath $EvidenceDirectory).Path
$before.Save((Join-Path $evidence 'task-before.xml'))
$arguments = '-NoProfile -NonInteractive -File "' + (Join-Path $release 'deploy/scripts/start_packaged_relay.ps1') + '" -Workspace "' + $scopeRoot + '" -Config "' + $transport + '" -Municipalities'
$action = New-ScheduledTaskAction -Execute $task.Actions.Execute -Argument $arguments -WorkingDirectory $release
Set-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath -Action $action -ErrorAction Stop | Out-Null
$after = [xml](Export-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath)
foreach ($part in @('Principals', 'Triggers', 'Settings')) {
    if ($before.Task.$part.OuterXml -ne $after.Task.$part.OuterXml) { throw "Unexpected task change: $part" }
}
$after.Save((Join-Path $evidence 'task-after.xml'))
$updated = Get-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath
if ($updated.Actions.Arguments -ne $arguments) { throw 'Task action was not applied.' }
[ordered]@{status='activated';municipalities=$true;workspace=$scopeRoot;account_and_schedule_preserved=$true;state=[string]$updated.State} | ConvertTo-Json -Compress

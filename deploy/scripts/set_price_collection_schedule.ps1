[CmdletBinding()]
param(
    [string]$TaskName = 'Smako Willys Local Relay',
    [Parameter(Mandatory=$true)][string]$Release,
    [Parameter(Mandatory=$true)][string]$Evidence,
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'
if ([TimeZoneInfo]::Local.Id -ne 'W. Europe Standard Time') {
    throw 'The relay host must use Stockholm civil time before this schedule is applied.'
}
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
if ($task.State -eq 'Running') { throw 'The relay is running; let its current work finish.' }
$before = Export-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath
$releaseRoot = (Resolve-Path -LiteralPath $Release).Path
if (-not (Test-Path -LiteralPath (Join-Path $releaseRoot 'RELEASE.json'))) { throw 'Verified installed relay release required.' }
$arguments = $task.Actions.Arguments -replace '-File "[^"]+"', ('-File "' + (Join-Path $releaseRoot 'deploy/scripts/start_packaged_relay.ps1') + '"')
$arguments = $arguments -replace '\s+-CollectionCadence\s+\S+', ''
$arguments += ' -CollectionCadence mon_thu'
$action = New-ScheduledTaskAction -Execute $task.Actions.Execute -Argument $arguments -WorkingDirectory $releaseRoot
$trigger = New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek Monday,Thursday -At '03:17'
if ($Apply) {
    New-Item -ItemType Directory -Force -Path $Evidence | Out-Null
    $stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
    $before | Set-Content -LiteralPath (Join-Path $Evidence "relay-$stamp-before.xml") -Encoding utf8
    Set-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath -Trigger $trigger -Action $action -ErrorAction Stop | Out-Null
    $after = Export-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath
    $after | Set-Content -LiteralPath (Join-Path $Evidence "relay-$stamp-after.xml") -Encoding utf8
    $original = [xml]$before
    $updated = [xml]$after
    foreach ($section in @('Principals', 'Settings')) {
        if ($original.Task.$section.OuterXml -ne $updated.Task.$section.OuterXml) {
            throw "Unexpected change to $section; inspect the saved before/after evidence."
        }
    }
    if ($updated.Task.Actions.Exec.Arguments -ne $arguments -or
        $updated.Task.Actions.Exec.WorkingDirectory -ne $releaseRoot -or
        $updated.Task.Actions.Exec.Command -ne $original.Task.Actions.Exec.Command) {
        throw 'Registered action does not match the pinned relay and explicit collection cadence.'
    }
    $calendar = $updated.Task.Triggers.CalendarTrigger
    if ($calendar.ScheduleByWeek.WeeksInterval -ne '1' -or
        $calendar.ScheduleByWeek.DaysOfWeek.ChildNodes.Count -ne 2 -or
        $calendar.ScheduleByWeek.DaysOfWeek.ChildNodes.Name -notcontains 'Monday' -or
        $calendar.ScheduleByWeek.DaysOfWeek.ChildNodes.Name -notcontains 'Thursday' -or
        $calendar.Repetition -or [datetime]$calendar.StartBoundary -ne [datetime]$trigger.StartBoundary) {
        throw 'Registered trigger does not match Monday/Thursday 03:17.'
    }
}
[ordered]@{status=$(if ($Apply) {'applied'} else {'prepared'}); task=$TaskName;
    days=@('Monday','Thursday'); time='03:17'; timezone='Europe/Stockholm';
    next_run=$(if ($Apply) {(Get-ScheduledTaskInfo -TaskName $TaskName).NextRunTime.ToString('o')} else {$null})} | ConvertTo-Json -Compress

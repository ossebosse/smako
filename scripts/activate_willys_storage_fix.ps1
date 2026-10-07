[CmdletBinding()]
param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$evidence = 'D:\Projects\Smako\.local\drift-restoration-20261007'
$name = 'Smako Willys Local Relay'
$release = 'D:\smako-local-relay\releases\fe795e5b04f5'
$baseline = Join-Path $evidence 'task-before.xml'
$workspace = 'D:\smako-local-relay\scopes\municipality-1281'
function Assert-Hash([string]$Path, [string]$Expected) {
    if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash -ne $Expected) {
        throw "Hash mismatch: $Path"
    }
}
Assert-Hash $baseline '6ECE9417794DFC3A9DB3D605CE310B2EDC873EE56914757D26E340053055E515'
Assert-Hash (Join-Path $release 'RELEASE.json') 'A41E47E7F91EC1031E6E5965D20A34C3BB10B9AB314A0DA0B46F9D526848A8C2'
$manifest = Get-Content -LiteralPath (Join-Path $release 'RELEASE.json') -Raw | ConvertFrom-Json
if ($manifest.commit -ne 'fe795e5b04f5a5ff973b71bb9bcdd28ca8668ce2') { throw 'Unexpected release.' }
foreach ($file in $manifest.files.PSObject.Properties) {
    $path = [IO.Path]::GetFullPath((Join-Path $release $file.Name))
    if (-not $path.StartsWith($release + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid package path.' }
    Assert-Hash $path $file.Value
}
[xml]$expected = Get-Content -LiteralPath $baseline -Raw
[xml]$current = Export-ScheduledTask -TaskName $name
if ($current.OuterXml -ne $expected.OuterXml) { throw 'Task definition changed; inspect before registration.' }
$task = Get-ScheduledTask -TaskName $name
if ($task.State -ne 'Ready' -or -not $task.Settings.Enabled) { throw 'Task must be idle and enabled.' }
if ($task.Principal.UserId -ne 'ossia' -or $task.Principal.LogonType -ne 'S4U' -or $task.Principal.RunLevel -ne 'Limited') { throw 'Unexpected principal.' }
$executable = 'C:\Users\ossia\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe'
if ($task.Actions.Count -ne 1 -or $task.Actions[0].Execute -ne $executable) { throw 'Unexpected executable.' }
if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) { throw 'PowerShell missing.' }
$arguments = '-NoProfile -NonInteractive -File "D:\smako-local-relay\releases\fe795e5b04f5\deploy\scripts\start_packaged_relay.ps1" -Workspace "D:\smako-local-relay\scopes\municipality-1281" -Config "D:\smako-local-relay\config\relay.json"'
if (-not $Apply) { Write-Output 'VALIDATED: package and complete current task XML match; no task changes or start.'; return }
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$locks = [Collections.Generic.List[IO.FileStream]]::new()
$paused = $false
try {
    Disable-ScheduledTask -TaskName $name | Out-Null
    $paused = $true
    if ((Get-ScheduledTask -TaskName $name).State -eq 'Running') { throw 'Task started before pause; leave it running and retry after completion.' }
    foreach ($lockName in @('local-workflow.lock', 'local-collection.lock')) {
        $stream = [IO.File]::Open((Join-Path $workspace $lockName), [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::ReadWrite)
        try { $stream.Lock(0, 1); $locks.Add($stream) } catch { $stream.Dispose(); throw }
    }
    $current.Save((Join-Path $evidence "task-$stamp-before.xml"))
    $action = New-ScheduledTaskAction -Execute $executable -Argument $arguments -WorkingDirectory $release
    Set-ScheduledTask -TaskName $name -Action $action | Out-Null
} catch {
    $_ | Out-String | Set-Content -LiteralPath (Join-Path $evidence "registration-$stamp-error.txt")
    throw
} finally {
    foreach ($stream in $locks) { $stream.Unlock(0, 1); $stream.Dispose() }
    if ($paused) { Enable-ScheduledTask -TaskName $name | Out-Null }
    Export-ScheduledTask -TaskName $name | Set-Content -LiteralPath (Join-Path $evidence "task-$stamp-after.xml") -Encoding utf8
}
[xml]$after = Export-ScheduledTask -TaskName $name
$actual = Get-ScheduledTask -TaskName $name
if ($actual.Actions[0].Execute -ne $executable -or $actual.Actions[0].Arguments -ne $arguments -or $actual.Actions[0].WorkingDirectory -ne $release) { throw 'Registered action mismatch.' }
$expected.Task.RemoveChild($expected.Task.Actions) | Out-Null
$after.Task.RemoveChild($after.Task.Actions) | Out-Null
if ($expected.OuterXml -ne $after.OuterXml) { throw 'Unexpected non-action task difference.' }
Write-Output 'PASS: only action arguments and working directory changed; task enabled; no job started.'

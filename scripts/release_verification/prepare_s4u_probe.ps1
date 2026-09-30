#requires -Version 7.0
[CmdletBinding()]
param([switch]$Register)
$ErrorActionPreference = 'Stop'
$repo = 'D:\Projects\Smako'
$root = Join-Path $repo '.local\drift-verification\s4u'
$taskName = 'Smako Lund bdc9 S4U isolated verification'
$activeName = 'Smako Willys Local Relay'
$release = 'D:\smako-local-relay\releases\bdc9f7df4170'
$expectedCommit = 'bdc9f7df417084641d0a712e3dad188dad1ad7d4'
if (Get-ScheduledTask -TaskName $taskName -TaskPath '\' -ErrorAction SilentlyContinue) {
    throw 'Test task already exists. Inspect it; do not replace its running observer or definition.'
}
New-Item -ItemType Directory -Force $root, (Join-Path $root 'state') | Out-Null
$active = Get-ScheduledTask -TaskPath '\' -TaskName $activeName
if ($active.Principal.LogonType -ne 'S4U' -or $active.Principal.RunLevel -ne 'Limited') {
    throw 'Active principal differs from the reviewed S4U/Limited proposal.'
}
$manifest = Get-Content -LiteralPath (Join-Path $release 'RELEASE.json') -Raw | ConvertFrom-Json
if ($manifest.commit -ne $expectedCommit) { throw 'Unexpected installed release commit.' }
$xmlBefore = Export-ScheduledTask -TaskName $activeName -TaskPath '\'
$xmlBefore | Set-Content -LiteralPath (Join-Path $root 'active-before.xml') -Encoding utf8
$wrapper = Join-Path $root 'run_s4u_probe.ps1'
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'run_s4u_probe.ps1') -Destination $wrapper
$config = Join-Path $root 'relay.json'
@{schema='smako-relay-config-v1';ssh_host='smako';container='smako-lund-ops-s4u';inbox='/work/raw/source-inbox/willys'} |
    ConvertTo-Json | Set-Content -LiteralPath $config -Encoding utf8
@{schema='willys-municipal-relay-v1';municipality_code='1281'} | ConvertTo-Json |
    Set-Content -LiteralPath (Join-Path $root 'state\source-scope.json') -Encoding utf8
$action = New-ScheduledTaskAction -Execute $active.Actions[0].Execute -WorkingDirectory $release `
    -Argument ('-NoProfile -NonInteractive -File "{0}"' -f $wrapper)
$principal = New-ScheduledTaskPrincipal -UserId $active.Principal.UserId -LogonType S4U -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 3)
$task = New-ScheduledTask -Action $action -Principal $principal -Settings $settings `
    -Description 'Explicitly approved isolated live verification only; no trigger; never production inbox.'
$task | Export-Clixml -LiteralPath (Join-Path $root 'test-definition.clixml')
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$admin = ([Security.Principal.WindowsPrincipal]::new($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$scheduler = New-Object -ComObject Schedule.Service
$scheduler.Connect()
$folder = $scheduler.GetFolder('\')
[ordered]@{folder='\';folder_dacl=$folder.GetSecurityDescriptor(4);
    active_task_dacl=$folder.GetTask($activeName).GetSecurityDescriptor(4);
    operational_log_enabled=(Get-WinEvent -ListLog 'Microsoft-Windows-TaskScheduler/Operational').IsEnabled;
    active_last_result=(Get-ScheduledTaskInfo -TaskPath '\' -TaskName $activeName).LastTaskResult} |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $root 'scheduler-permissions.json') -Encoding utf8
[ordered]@{task=$taskName;folder='\';caller=$identity.Name;caller_sid=$identity.User.Value;
    elevated=$admin;run_as=$principal.UserId;logon_type='S4U';run_level='Limited';triggers=0;
    command=$action.Execute;arguments=$action.Arguments;working_directory=$release;
    wrapper_sha256=(Get-FileHash -LiteralPath $wrapper -Algorithm SHA256).Hash;
    active_xml_sha256=(Get-FileHash -LiteralPath (Join-Path $root 'active-before.xml')).Hash} |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $root 'registration-context.json') -Encoding utf8
if (-not $Register) {
    Write-Output "Prepared only: $root. No task registered or started."
    return
}
if (-not $admin) { throw 'Registration requires an elevated operator PowerShell. No elevation or policy change is attempted.' }
if (Get-ScheduledTask -TaskName $taskName -TaskPath '\' -ErrorAction SilentlyContinue) {
    throw 'Test task already exists; inspect it. This script never overwrites a task.'
}
try {
    # This is the sole scheduler mutation. No Force, trigger, RunLevel or account change.
    Register-ScheduledTask -TaskName $taskName -TaskPath '\' -InputObject $task -ErrorAction Stop | Out-Null
    Export-ScheduledTask -TaskName $taskName -TaskPath '\' |
        Set-Content -LiteralPath (Join-Path $root 'registered-test.xml') -Encoding utf8
} catch {
    $_ | Export-Clixml -LiteralPath (Join-Path $root 'registration-error.clixml')
    $_ | Format-List * -Force | Out-String |
        Set-Content -LiteralPath (Join-Path $root 'registration-error.txt') -Encoding utf8
    $errors = @()
    $exception = $_.Exception
    while ($null -ne $exception) {
        $errors += @{type=$exception.GetType().FullName;message=$exception.Message;
            hresult=('0x{0:X8}' -f ($exception.HResult -band 0xffffffffL))}
        $exception = $exception.InnerException
    }
    $errors | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $root 'registration-errors.json') -Encoding utf8
    throw
} finally {
    $xmlAfter = Export-ScheduledTask -TaskName $activeName -TaskPath '\'
    if ($xmlAfter -ne $xmlBefore) { throw 'Active task changed externally during the probe; investigate.' }
}
Write-Output 'Registered only. Do not start until the isolated receiver and live-test approval have been verified.'

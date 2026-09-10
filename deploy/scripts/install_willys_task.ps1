[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Repository,
    [Parameter(Mandatory=$true)][string]$Workspace,
    [Parameter(Mandatory=$true)][ValidatePattern('^\d{2}:\d{2}$')][string]$DailyAt
)
$ErrorActionPreference = 'Stop'
$relayRepository = (Resolve-Path -LiteralPath $Repository).Path
$relayScript = Join-Path $relayRepository 'deploy/scripts/collect_willys_local.ps1'
if (-not (Test-Path -LiteralPath $relayScript)) { throw 'Reviewed relay script missing.' }
if ((Get-TimeZone).Id -ne 'W. Europe Standard Time') { throw 'Verify Stockholm local time before installing.' }
New-Item -ItemType Directory -Force -Path $Workspace | Out-Null
$relayWorkspace = (Resolve-Path -LiteralPath $Workspace).Path
if ($relayRepository.Contains('"') -or $relayWorkspace.Contains('"')) { throw 'Unsupported quoted path.' }
$relayArguments = '-NoProfile -NonInteractive -File "{0}" -Repository "{1}" -Workspace "{2}"' -f $relayScript,$relayRepository,$relayWorkspace
$relayPowerShell = (Get-Command pwsh.exe -ErrorAction Stop).Source
$relayAction = New-ScheduledTaskAction -Execute $relayPowerShell -Argument $relayArguments -WorkingDirectory $relayRepository
$relayTrigger = New-ScheduledTaskTrigger -Daily -At ([datetime]::ParseExact($DailyAt,'HH:mm',[Globalization.CultureInfo]::InvariantCulture))
$relaySettings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -WakeToRun -ExecutionTimeLimit (New-TimeSpan -Hours 3) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$relayPrincipal = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName 'Smako Willys Local Relay' -Action $relayAction -Trigger $relayTrigger -Settings $relaySettings -Principal $relayPrincipal -Description 'Daily validated Willys OWN LOCAL_RELAY; existing user SSH smako; wake requested; no automatic crawl retry. Password-mode registration requires local operator dialog.' | Out-Null
Get-ScheduledTask -TaskName 'Smako Willys Local Relay'
Get-ScheduledTaskInfo -TaskName 'Smako Willys Local Relay'

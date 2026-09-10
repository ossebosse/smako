[CmdletBinding()]
param(
    [string]$Workspace = 'D:\smako-local-relay',
    [switch]$LocalOnly
)
$ErrorActionPreference = 'Stop'
$relayRepository = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$relayTask = Get-ScheduledTask -TaskName 'Smako Willys Local Relay'
$relayInfo = Get-ScheduledTaskInfo -TaskName $relayTask.TaskName
Push-Location $relayRepository
try {
    $env:PYTHON_DOTENV_DISABLED = 'true'
    $relayArgs = @('-3.12','-m','grocery_data.relay_status','--workspace',$Workspace)
    if ($LocalOnly) { $relayArgs += '--local-only' }
    $relayStatusText = & py @relayArgs
    if ($LASTEXITCODE -ne 0) { throw 'Relay status could not be read.' }
    $relayStatus = ($relayStatusText -join "`n") | ConvertFrom-Json
} finally { Pop-Location }
[ordered]@{
    Task = [ordered]@{
        Name = $relayTask.TaskName
        User = $relayTask.Principal.UserId
        LogonType = [string]$relayTask.Principal.LogonType
        RequiresLoggedInUser = ($relayTask.Principal.LogonType -eq 'Interactive')
        RunLevel = [string]$relayTask.Principal.RunLevel
        State = [string]$relayTask.State
        LastRun = $relayInfo.LastRunTime.ToString('o')
        LastResult = $relayInfo.LastTaskResult
        LastResultHex = ('0x{0:X8}' -f $relayInfo.LastTaskResult)
        NextRun = $relayInfo.NextRunTime.ToString('o')
        WakeToRun = $relayTask.Settings.WakeToRun
        StartWhenAvailable = $relayTask.Settings.StartWhenAvailable
        MultipleInstances = [string]$relayTask.Settings.MultipleInstances
        ExecutionTimeLimit = $relayTask.Settings.ExecutionTimeLimit
        DisallowStartIfOnBatteries = $relayTask.Settings.DisallowStartIfOnBatteries
        StopIfGoingOnBatteries = $relayTask.Settings.StopIfGoingOnBatteries
        RestartCount = $relayTask.Settings.RestartCount
        RestartInterval = $relayTask.Settings.RestartInterval
        Actions = @($relayTask.Actions | Select-Object Execute,Arguments,WorkingDirectory)
    }
    Relay = $relayStatus
} | ConvertTo-Json -Depth 8

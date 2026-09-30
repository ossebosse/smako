# Immutable copy staged by prepare_s4u_probe.ps1; Task Scheduler invokes this
# observer, which invokes the actual unmodified version-bound start script.
$ErrorActionPreference = 'Stop'
$root = 'D:\Projects\Smako\.local\drift-verification\s4u'
trap {
    $_ | Format-List * -Force | Out-String |
        Set-Content -LiteralPath (Join-Path $root 'observer-error.txt') -Encoding utf8
    exit 1
}
$release = 'D:\smako-local-relay\releases\bdc9f7df4170'
$config = Join-Path $root 'relay.json'
$transport = Get-Content -LiteralPath $config -Raw | ConvertFrom-Json
if ($transport.container -ne 'smako-lund-ops-s4u' -or $transport.inbox -ne '/work/raw/source-inbox/willys') {
    throw 'Only the isolated receiver is permitted.'
}
if (-not (Test-Path -LiteralPath (Join-Path $root 'receiver-ready.json'))) {
    throw 'Missing reviewed isolated receiver readiness evidence.'
}
$ready = Get-Content -LiteralPath (Join-Path $root 'receiver-ready.json') -Raw | ConvertFrom-Json
if ($ready.image -ne 'sha256:2f81344208e05cbc57d16fa74a73c97b26bc729859936ca5d96ab150579fe221' -or
    [DateTimeOffset]::Parse($ready.expires_utc) -le [DateTimeOffset]::UtcNow) {
    throw 'Isolated receiver readiness is stale or belongs to another image.'
}
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$context = [ordered]@{started_utc=$stamp;user=$identity.Name;sid=$identity.User.Value;
    session_id=(Get-Process -Id $PID).SessionId;interactive=[Environment]::UserInteractive;
    process_id=$PID;release=$release;config=$config;
    task_principal=(Get-ScheduledTask -TaskPath '\' -TaskName 'Smako Lund bdc9 S4U isolated verification').Principal}
$context | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $root "$stamp-context.json") -Encoding utf8
$program = (Get-Process -Id $PID).Path
& $program -NoProfile -NonInteractive -File (Join-Path $release 'deploy\scripts\start_packaged_relay.ps1') `
    -Workspace (Join-Path $root 'state') -Config $config *> (Join-Path $root "$stamp-process.log")
$result = $LASTEXITCODE
@{finished_utc=[DateTime]::UtcNow.ToString('o');exit_code=$result;session_id=(Get-Process -Id $PID).SessionId} |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $root "$stamp-result.json") -Encoding utf8
exit $result

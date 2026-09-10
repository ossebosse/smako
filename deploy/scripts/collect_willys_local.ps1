[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Repository,
    [Parameter(Mandatory=$true)][string]$Workspace
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'relay_process_lifetime.ps1')
$relayRepository = (Resolve-Path -LiteralPath $Repository).Path
if (-not (Test-Path -LiteralPath (Join-Path $relayRepository 'grocery_data/local_relay.py'))) {
    throw 'Repository does not contain the reviewed local relay command.'
}
Push-Location $relayRepository
try {
    $env:PYTHON_DOTENV_DISABLED = 'true'
    $relayProbeRequest = Join-Path $Workspace 'preflight.request'
    if (Test-Path -LiteralPath $relayProbeRequest) {
        # Explicit operator-requested one-shot probe; never a product collection.
        $relayConsumed = Join-Path $Workspace 'preflight.consumed'
        Move-Item -LiteralPath $relayProbeRequest -Destination $relayConsumed -Force
        & py -3.12 -m grocery_data.relay_preflight --workspace $Workspace --output (Join-Path $Workspace 'preflight-status.json')
    } else {
        & py -3.12 -m grocery_data.local_relay --workspace $Workspace
    }
    $relayExit = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $relayExit

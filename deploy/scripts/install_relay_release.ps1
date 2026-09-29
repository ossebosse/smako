[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Package,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$Sha256,
    [Parameter(Mandatory=$true)][string]$Destination,
    [Parameter(Mandatory=$true)][string]$Wheelhouse
)
$ErrorActionPreference = 'Stop'
if ((Get-FileHash -LiteralPath $Package -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Sha256) {
    throw 'Package hash mismatch.'
}
if (Test-Path -LiteralPath $Destination) { throw 'Release destination must be new; never overwrite an installation.' }
Expand-Archive -LiteralPath $Package -DestinationPath $Destination
$relayRoot = (Resolve-Path -LiteralPath $Destination).Path
& py -3.12 -m venv (Join-Path $relayRoot '.venv')
if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed.' }
$relayPython = Join-Path $relayRoot '.venv/Scripts/python.exe'
& $relayPython -m pip install --no-index --find-links $Wheelhouse -r (Join-Path $relayRoot 'deploy/requirements.txt') -c (Join-Path $relayRoot 'requirements-dev.lock')
if ($LASTEXITCODE -ne 0) { throw 'Locked dependency installation failed.' }
& $relayPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependency check failed.' }
& $relayPython -I -B (Join-Path $relayRoot 'scripts/run_packaged_relay.py') --check-install
if ($LASTEXITCODE -ne 0) { throw 'Release integrity/import check failed.' }
# Deliberately does not register, start, stop or change any Windows task.

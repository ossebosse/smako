[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Workspace,
    [Parameter(Mandatory=$true)][string]$Config,
    [switch]$CheckInstall
)
$ErrorActionPreference = 'Stop'
$relayRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$relayWorkspace = [IO.Path]::GetFullPath($Workspace)
$relayConfig = (Resolve-Path -LiteralPath $Config).Path
if ($relayWorkspace.StartsWith($relayRoot + '\', [StringComparison]::OrdinalIgnoreCase) -or
    $relayConfig.StartsWith($relayRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Configuration and state must be outside the immutable release.'
}
. (Join-Path $PSScriptRoot 'relay_process_lifetime.ps1')
$relayPython = Join-Path $relayRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $relayPython)) { throw 'Install the release environment first.' }
$env:PYTHON_DOTENV_DISABLED = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$relayArgs = @('-I', '-B', (Join-Path $relayRoot 'scripts/run_packaged_relay.py'))
if ($CheckInstall) { $relayArgs += '--check-install' }
else { $relayArgs += @('--workspace', $relayWorkspace, '--config', $relayConfig) }
& $relayPython @relayArgs
exit $LASTEXITCODE

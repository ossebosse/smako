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
# Set the child's temporary storage before Add-Type, Python or collector imports.
# Do not create a missing data root or silently fall back to the system volume.
if (-not (Test-Path -LiteralPath $relayWorkspace -PathType Container)) {
    throw 'Relay workspace is unavailable; no fallback storage is allowed.'
}
$relayTemp = Join-Path $relayWorkspace 'tmp'
$relayDirectory = Get-Item -LiteralPath $relayWorkspace
while ($null -ne $relayDirectory) {
    if ($relayDirectory.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw 'Relay data directories must not redirect storage through a reparse point.'
    }
    $relayDirectory = $relayDirectory.Parent
}
if ((Test-Path -LiteralPath $relayTemp) -and
    ((Get-Item -LiteralPath $relayTemp).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    throw 'Relay temporary directory must not redirect storage.'
}
New-Item -ItemType Directory -Force -Path $relayTemp | Out-Null
$env:TEMP = $relayTemp
$env:TMP = $relayTemp
$env:TMPDIR = $relayTemp
$env:SQLITE_TMPDIR = $relayTemp
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

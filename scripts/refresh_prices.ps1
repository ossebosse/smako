[CmdletBinding()]
param(
    [string[]]$Cities = @("Lund", "Malmö"),

    [string[]]$Chains = @(),

    [string]$ContextStoreId = "",

    [string[]]$PostalCodes = @(),

    [switch]$DryRun,

    [switch]$NoExternalRefresh,

    [ValidateSet("human", "json")]
    [string]$Format = "human"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))

function Expand-RefreshValues {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Values,

        [Parameter(Mandatory = $true)]
        [string]$ParameterName
    )

    $expanded = [System.Collections.Generic.List[string]]::new()
    foreach ($value in $Values) {
        foreach ($part in $value.Split(",", [System.StringSplitOptions]::RemoveEmptyEntries)) {
            $normalized = $part.Trim()
            if ([string]::IsNullOrWhiteSpace($normalized)) {
                continue
            }
            if (-not $expanded.Contains($normalized)) {
                $expanded.Add($normalized)
            }
        }
    }
    if ($expanded.Count -eq 0) {
        throw "$ParameterName must contain at least one non-empty value."
    }
    return $expanded.ToArray()
}

$normalizedCities = Expand-RefreshValues -Values $Cities -ParameterName "Cities"
$normalizedChains = @()
if ($Chains.Count -gt 0) {
    $normalizedChains = Expand-RefreshValues -Values $Chains -ParameterName "Chains"
}

$venvPython = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
$pythonCommand = $null
$pythonPrefix = @()
if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
    $pythonCommand = $venvPython
}
else {
    $pyLauncher = Get-Command "py" -ErrorAction SilentlyContinue
    if ($null -ne $pyLauncher) {
        $pythonCommand = $pyLauncher.Source
        $pythonPrefix = @("-3.12")
    }
    else {
        $python = Get-Command "python" -ErrorAction SilentlyContinue
        if ($null -eq $python) {
            throw "Python was not found. Install Python 3.12 or create .venv first."
        }
        $pythonCommand = $python.Source
    }
}

$cliArguments = @("-m", "grocery_data", "daily-refresh")
# Python otherwise inherits the legacy Windows console code page on some
# PowerShell installations, which corrupts city/context names such as Malmö
# and Hemköp in the operator report.  This affects only the child process.
$env:PYTHONUTF8 = "1"
foreach ($city in $normalizedCities) {
    $cliArguments += @("--city", $city)
}
foreach ($chain in $normalizedChains) {
    $cliArguments += @("--chain", $chain.ToLowerInvariant())
}
foreach ($postalCode in $PostalCodes) {
    if (-not [string]::IsNullOrWhiteSpace($postalCode)) {
        $cliArguments += @("--postal-code", $postalCode.Trim())
    }
}
if (-not [string]::IsNullOrWhiteSpace($ContextStoreId)) {
    $cliArguments += @("--context-store-id", $ContextStoreId.Trim())
}
if ($DryRun) {
    $cliArguments += "--dry-run"
}
if ($NoExternalRefresh) {
    $cliArguments += "--no-external-refresh"
}
$cliArguments += @("--format", $Format)

Write-Host ("PRICE REFRESH: {0}" -f ($normalizedCities -join ", "))
if ($DryRun) {
    Write-Host "MODE: DRY RUN (no collection, promotion or PriceUniverse activation)"
}
else {
    Write-Host "MODE: COLLECT, VALIDATE, PROMOTE, BUILD AND ATOMICALLY ACTIVATE"
}

Push-Location $repositoryRoot
try {
    & $pythonCommand @pythonPrefix @cliArguments
    $refreshExitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}

# Preserve the Python CLI contract: 0=complete, 1=fatal, 2=degraded with a
# usable active universe. Do not translate a degraded refresh into success.
exit $refreshExitCode

[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8010,

    [string]$EnvFile = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
if ([string]::IsNullOrWhiteSpace($EnvFile)) {
    $EnvFile = Join-Path $repositoryRoot ".env"
}
elseif (-not [System.IO.Path]::IsPathRooted($EnvFile)) {
    $EnvFile = [System.IO.Path]::GetFullPath((Join-Path $repositoryRoot $EnvFile))
}

function Get-FieldSetting {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $processValue = [Environment]::GetEnvironmentVariable($Name, "Process")
    if (-not [string]::IsNullOrWhiteSpace($processValue)) {
        return $processValue
    }
    if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
        return $null
    }

    foreach ($line in [System.IO.File]::ReadLines($EnvFile)) {
        if ($line -notmatch '^\s*(?:export\s+)?(?<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?<value>.*)\s*$') {
            continue
        }
        if ($Matches.name -ne $Name) {
            continue
        }

        $value = $Matches.value.Trim()
        if ($value.Length -ge 2) {
            $first = $value.Substring(0, 1)
            $last = $value.Substring($value.Length - 1, 1)
            if (($first -eq '"' -and $last -eq '"') -or ($first -eq "'" -and $last -eq "'")) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }
        return $value
    }
    return $null
}

function Assert-FieldConfiguration {
    $fieldMode = Get-FieldSetting -Name "FIELD_MODE_ENABLED"
    $enabledValues = @("1", "true", "yes", "on")
    if ([string]::IsNullOrWhiteSpace($fieldMode) -or
        $enabledValues -notcontains $fieldMode.Trim().ToLowerInvariant()) {
        throw "FIELD_MODE_ENABLED must be explicitly set to true before field access is started."
    }

    $accessToken = Get-FieldSetting -Name "PHYSICAL_CHECK_ACCESS_TOKEN"
    if ([string]::IsNullOrWhiteSpace($accessToken)) {
        throw "PHYSICAL_CHECK_ACCESS_TOKEN is missing. Configure a strong, temporary token in .env or the process environment."
    }
    if ([Text.Encoding]::UTF8.GetByteCount($accessToken) -lt 32) {
        throw "PHYSICAL_CHECK_ACCESS_TOKEN must contain at least 32 bytes. The value remains hidden."
    }

    $databaseUrl = Get-FieldSetting -Name "GROCERY_DATABASE_URL"
    if ([string]::IsNullOrWhiteSpace($databaseUrl)) {
        throw "GROCERY_DATABASE_URL must explicitly identify the current field database; refusing the legacy default database."
    }

    # Pass only the named field settings to the child process. The token stays
    # in process memory and is never placed in output or the command line.
    [Environment]::SetEnvironmentVariable("FIELD_MODE_ENABLED", $fieldMode, "Process")
    [Environment]::SetEnvironmentVariable(
        "PHYSICAL_CHECK_ACCESS_TOKEN",
        $accessToken,
        "Process"
    )
    [Environment]::SetEnvironmentVariable("GROCERY_DATABASE_URL", $databaseUrl, "Process")
    foreach ($optionalName in @(
        "FIELD_SESSION_TTL_SECONDS",
        "FIELD_LOGIN_ATTEMPTS_PER_MINUTE",
        "FIELD_WRITE_REQUESTS_PER_MINUTE",
        "FIELD_PUBLIC_ORIGIN",
        "FIELD_TRUSTED_PROXY_CIDRS"
    )) {
        $optionalValue = Get-FieldSetting -Name $optionalName
        if (-not [string]::IsNullOrWhiteSpace($optionalValue)) {
            [Environment]::SetEnvironmentVariable($optionalName, $optionalValue, "Process")
        }
    }
}

function Test-HttpSuccess {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Uri
    )

    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -Method Get -TimeoutSec 3
        return [int]$response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

Assert-FieldConfiguration

$fieldLoginUrl = "http://127.0.0.1:$Port/physical-check/login"
$normalHealthUrl = "http://127.0.0.1:$Port/health"
if ((Test-HttpSuccess -Uri $fieldLoginUrl) -or (Test-HttpSuccess -Uri $normalHealthUrl)) {
    throw "A Grocery Data server already answers on port $Port. Stop it and restart it with this script so the field-mode configuration is known."
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
            throw "Python was not found. Install Python 3.12 or create .venv before starting field mode."
        }
        $pythonCommand = $python.Source
    }
}

Push-Location $repositoryRoot
try {
    & $pythonCommand @pythonPrefix -c "import uvicorn, grocery_data" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "The selected Python runtime cannot import uvicorn and grocery_data. Install the project dependencies first."
    }

    Write-Host "Database schema: applying verified additive migrations"
    & $pythonCommand @pythonPrefix -m alembic -c grocery_data/alembic.ini upgrade head
    if ($LASTEXITCODE -ne 0) {
        throw "Database schema migration failed. The field server was not started; existing observations and prices were left untouched."
    }
    Write-Host "Database schema: current"

    Write-Host "FIELD MODE: ENABLED"
    Write-Host "Access token: configured (value hidden)"
    Write-Host "Field database: explicitly configured (value hidden)"
    Write-Host "Backend: starting on loopback only at http://127.0.0.1:$Port"
    Write-Host "Physical-check: protected"
    Write-Host "Admin/debug/raw/collector routes: not registered in field mode"
    Write-Host "Keep this terminal open. Run scripts/start_field_tunnel.ps1 in a second terminal."

    $uvicornArguments = @(
        "-m", "uvicorn",
        "grocery_data.app.main:app",
        "--host", "127.0.0.1",
        "--port", $Port.ToString(),
        "--no-proxy-headers"
    )
    if (Test-Path -LiteralPath $EnvFile -PathType Leaf) {
        $uvicornArguments += @("--env-file", $EnvFile)
    }

    # Foreground execution makes Ctrl+C stop the local service immediately and
    # keeps the server lifecycle visible to the operator.
    & $pythonCommand @pythonPrefix @uvicornArguments
    if ($LASTEXITCODE -ne 0) {
        throw "The Grocery Data field server exited with code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

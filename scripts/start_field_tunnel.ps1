[CmdletBinding()]
param(
    [string]$LocalUrl = "http://127.0.0.1:8010",

    [string]$EnvFile = "",

    [string]$CloudflaredPath = ""
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

$fieldMode = Get-FieldSetting -Name "FIELD_MODE_ENABLED"
$enabledValues = @("1", "true", "yes", "on")
if ([string]::IsNullOrWhiteSpace($fieldMode) -or
    $enabledValues -notcontains $fieldMode.Trim().ToLowerInvariant()) {
    throw "FIELD_MODE_ENABLED must be explicitly set to true before a public tunnel is opened."
}

$accessToken = Get-FieldSetting -Name "PHYSICAL_CHECK_ACCESS_TOKEN"
if ([string]::IsNullOrWhiteSpace($accessToken)) {
    throw "PHYSICAL_CHECK_ACCESS_TOKEN is missing. Refusing to expose an unprotected field endpoint."
}
if ([Text.Encoding]::UTF8.GetByteCount($accessToken) -lt 32) {
    throw "PHYSICAL_CHECK_ACCESS_TOKEN must contain at least 32 bytes. The value remains hidden."
}

$parsedLocalUrl = $null
if (-not [Uri]::TryCreate($LocalUrl, [UriKind]::Absolute, [ref]$parsedLocalUrl)) {
    throw "LocalUrl must be an absolute loopback HTTP URL."
}
if ($parsedLocalUrl.Scheme -ne "http" -or
    $parsedLocalUrl.Host -notin @("127.0.0.1", "localhost", "::1")) {
    throw "LocalUrl must use http and a loopback host; refusing to tunnel another origin."
}
if ($parsedLocalUrl.AbsolutePath -ne "/") {
    throw "LocalUrl must identify the service root without a path."
}

function Get-HttpStatusCode {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Uri
    )

    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -Method Get -TimeoutSec 5
        return [int]$response.StatusCode
    }
    catch {
        $responseProperty = $_.Exception.PSObject.Properties["Response"]
        if ($null -ne $responseProperty -and $null -ne $responseProperty.Value) {
            $statusProperty = $responseProperty.Value.PSObject.Properties["StatusCode"]
            if ($null -ne $statusProperty) {
                return [int]$statusProperty.Value
            }
        }
        return $null
    }
}

# Field mode deliberately does not expose the broad /health and admin routes.
# Its bounded liveness check is the login page plus proof that an API request
# without a signed field session is rejected.
$loginUrl = ([Uri]::new($parsedLocalUrl, "/physical-check/login")).AbsoluteUri
$protectedUrl = ([Uri]::new(
    $parsedLocalUrl,
    "/physical-check/stores?city=Lund"
)).AbsoluteUri
$loginStatus = Get-HttpStatusCode -Uri $loginUrl
$protectedStatus = Get-HttpStatusCode -Uri $protectedUrl
if ($loginStatus -ne 200) {
    throw "The local field login check failed at $loginUrl. Start scripts/start_field_server.ps1 first."
}
if ($protectedStatus -ne 401) {
    throw "The local field authentication boundary did not reject an anonymous API request; no tunnel was opened."
}

$cloudflaredExecutable = $null
if (-not [string]::IsNullOrWhiteSpace($CloudflaredPath)) {
    $candidate = $CloudflaredPath
    if (-not [System.IO.Path]::IsPathRooted($candidate)) {
        $candidate = [System.IO.Path]::GetFullPath((Join-Path $repositoryRoot $candidate))
    }
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
        throw "CloudflaredPath does not identify an existing executable."
    }
    $cloudflaredExecutable = $candidate
}
else {
    $cloudflared = Get-Command "cloudflared" -ErrorAction SilentlyContinue
    if ($null -ne $cloudflared) {
        $cloudflaredExecutable = $cloudflared.Source
    }
}
if ($null -eq $cloudflaredExecutable) {
    throw "cloudflared was not found. Install it with: winget install --id Cloudflare.cloudflared -e"
}

Write-Host "Local field liveness and authentication-boundary checks passed."
Write-Host "Field token is configured (value hidden) and is not a cloudflared command-line argument."
Write-Host "FIELD MODE: ENABLED"
Write-Host "Backend: OK"
Write-Host "Physical-check: protected"
Write-Host "Admin/debug/raw/collector routes: unavailable to field users"
Write-Host "Tunnel: starting; open the HTTPS URL printed below with /physical-check"
Write-Warning "This opens an ephemeral public trycloudflare.com URL for a limited PoC field session."
Write-Warning "The browser login submission traverses Cloudflare, which terminates tunnel HTTPS."
Write-Warning "Keep both terminals open, share neither the URL nor token, and stop the tunnel with Ctrl+C immediately after the visit."

# With no tunnel name or credentials this is Cloudflare's ephemeral quick-
# tunnel mode. cloudflared prints the temporary HTTPS URL to this terminal.
$inheritedAccessToken = [Environment]::GetEnvironmentVariable(
    "PHYSICAL_CHECK_ACCESS_TOKEN",
    "Process"
)
try {
    # cloudflared never needs the application login secret. Remove it from
    # the child environment even when the operator configured it in the
    # current PowerShell process, then restore the parent environment.
    [Environment]::SetEnvironmentVariable(
        "PHYSICAL_CHECK_ACCESS_TOKEN",
        $null,
        "Process"
    )
    & $cloudflaredExecutable tunnel --url $parsedLocalUrl.AbsoluteUri --no-autoupdate
    if ($LASTEXITCODE -ne 0) {
        throw "cloudflared exited with code $LASTEXITCODE."
    }
}
finally {
    [Environment]::SetEnvironmentVariable(
        "PHYSICAL_CHECK_ACCESS_TOKEN",
        $inheritedAccessToken,
        "Process"
    )
}

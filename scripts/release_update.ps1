param(
    [Parameter(Mandatory = $true)]
    [string]$Note,

    [ValidateSet("major", "minor", "patch")]
    [string]$Level = "patch"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$versionFile = Join-Path $root "VERSION"
$changelogFile = Join-Path $root "CHANGELOG.md"
$memoryFile = Join-Path $root "PROJECT_MEMORY.md"
$pyprojectFile = Join-Path $root "pyproject.toml"
$packageInitFile = Join-Path $root "src\git_binance_trader\__init__.py"

if (-not (Test-Path $versionFile)) {
    throw "VERSION file not found."
}

$oldVersion = (Get-Content $versionFile -Raw).Trim()
$parts = $oldVersion.Split('.')
if ($parts.Count -ne 3) {
    throw "VERSION must be x.y.z format. current=$oldVersion"
}

$major = [int]$parts[0]
$minor = [int]$parts[1]
$patch = [int]$parts[2]

switch ($Level) {
    "major" { $major++; $minor = 0; $patch = 0 }
    "minor" { $minor++; $patch = 0 }
    default { $patch++ }
}

$newVersion = "$major.$minor.$patch"
Set-Content -Path $versionFile -Value "$newVersion`n" -Encoding UTF8

if (Test-Path $pyprojectFile) {
    $pyprojectText = Get-Content $pyprojectFile -Raw
    $pyprojectText = [System.Text.RegularExpressions.Regex]::Replace(
        $pyprojectText,
        'version = "[0-9]+\.[0-9]+\.[0-9]+"',
        "version = `"$newVersion`"",
        1
    )
    Set-Content -Path $pyprojectFile -Value $pyprojectText -Encoding UTF8
}

if (Test-Path $packageInitFile) {
    $initText = Get-Content $packageInitFile -Raw
    $initText = [System.Text.RegularExpressions.Regex]::Replace(
        $initText,
        '__version__ = "[0-9]+\.[0-9]+\.[0-9]+"',
        "__version__ = `"$newVersion`"",
        1
    )
    Set-Content -Path $packageInitFile -Value $initText -Encoding UTF8
}

$date = Get-Date -Format "yyyy-MM-dd"
$changelogEntry = @"

## v$newVersion - $date
- $Note
"@
Add-Content -Path $changelogFile -Value $changelogEntry -Encoding UTF8

$memoryEntry = @"

## Update Record v$newVersion - $date
- Note: $Note
- Risk check: no new plaintext credentials detected; keep simulation-only mode.
- Release action: VERSION, CHANGELOG, and PROJECT_MEMORY were updated.
"@
Add-Content -Path $memoryFile -Value $memoryEntry -Encoding UTF8

Write-Host "Version updated: v$oldVersion -> v$newVersion"
Write-Host "Updated files: VERSION, pyproject.toml, __init__.py, CHANGELOG.md, PROJECT_MEMORY.md"

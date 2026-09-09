[CmdletBinding()]
param([switch]$SkipTests)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$forbidden = '(?i)\.(exe|msi|xlsx|csv|s2b|s2blyrics|s2bscript|s2bchart|acb|awb|png|jpe?g|webp|wav|mp3)$'

Push-Location $repoRoot
try {
    $files = @(git -c core.quotepath=false ls-files --cached --others --exclude-standard)
    if ($LASTEXITCODE -ne 0) { throw "Unable to enumerate repository files." }
    $bad = @($files | Where-Object { $_ -match $forbidden -or $_ -match '(?i)(^|/)master_data[^/]*\.(json|s2b)$' })
    if ($bad) { throw "Forbidden data or output files:`n$($bad -join "`n")" }
    if (-not $SkipTests) { & (Join-Path $PSScriptRoot 'test.ps1') }
    Write-Host "Masterdata repository verification passed."
}
finally {
    Pop-Location
}


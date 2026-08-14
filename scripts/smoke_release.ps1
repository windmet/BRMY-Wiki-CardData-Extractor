[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Executable,
    [string]$ReportPath
)

$ErrorActionPreference = "Stop"
$executablePath = (Resolve-Path -LiteralPath $Executable).Path
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("brmy-release-smoke-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    Push-Location $temporaryRoot
    try {
        $doctorText = (& $executablePath doctor --json 2>&1) -join "`n"
        if ($LASTEXITCODE -ne 0) {
            throw "EXE doctor failed with exit code $LASTEXITCODE`n$doctorText"
        }
        $doctor = $doctorText | ConvertFrom-Json
        if ($doctor.status -ne "PASS" -or -not $doctor.frozen) {
            throw "EXE doctor did not report a healthy frozen runtime.`n$doctorText"
        }

        $listText = (& $executablePath list 2>&1) -join "`n"
        if ($LASTEXITCODE -ne 0) {
            throw "EXE list failed with exit code $LASTEXITCODE`n$listText"
        }
        foreach ($marker in @("cards", "home_voices", "update cards")) {
            if ($listText -notmatch [regex]::Escape($marker)) {
                throw "EXE list output is missing '$marker'."
            }
        }

        $masterdataBytes = [Convert]::FromBase64String(
            "xxJjzgAAAAzAgaltc3Rfc21va2UAxxhjzgAAABHwApGCoklkAaROYW1lpVNtb2tl"
        )
        [System.IO.File]::WriteAllBytes(
            (Join-Path $temporaryRoot "master_data.s2b"),
            $masterdataBytes
        )
        $decryptText = (& $executablePath decrypt 2>&1) -join "`n"
        if ($LASTEXITCODE -ne 0) {
            throw "EXE decrypt smoke failed with exit code $LASTEXITCODE`n$decryptText"
        }
        $jsonPath = Join-Path $temporaryRoot "master_data.json"
        $cachePath = Join-Path $temporaryRoot ".bmc_toolkit\master_data_cache.json"
        if (-not (Test-Path -LiteralPath $jsonPath) -or -not (Test-Path -LiteralPath $cachePath)) {
            throw "EXE decrypt smoke did not create JSON and cache manifest."
        }
        $decoded = Get-Content -LiteralPath $jsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $cache = Get-Content -LiteralPath $cachePath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($decoded[0].mst_smoke -ne 0 -or $decoded[1][0].Id -ne 1) {
            throw "EXE decrypt smoke produced unexpected masterdata content."
        }
        if ($cache.output.table_count -ne 1 -or $cache.parser_version -ne 1) {
            throw "EXE decrypt smoke produced an invalid cache manifest."
        }

        $report = [ordered]@{
            schema_version = 1
            status = "PASS"
            executable = $executablePath
            doctor = $doctor
            list_markers = @("cards", "home_voices", "update cards")
            masterdata_decrypt = [ordered]@{
                status = "PASS"
                table_count = 1
                parser_version = 1
            }
        }
        if ($ReportPath) {
            $reportFile = [System.IO.Path]::GetFullPath($ReportPath)
            $reportDirectory = Split-Path -Parent $reportFile
            New-Item -ItemType Directory -Force -Path $reportDirectory | Out-Null
            [System.IO.File]::WriteAllText(
                $reportFile,
                (($report | ConvertTo-Json -Depth 8) + "`n"),
                [System.Text.UTF8Encoding]::new($false)
            )
        }
        Write-Host "Release EXE smoke test passed."
    }
    finally {
        Pop-Location
    }
}
finally {
    $resolvedTemporary = [System.IO.Path]::GetFullPath($temporaryRoot)
    $resolvedSystemTemp = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    if (-not $resolvedTemporary.StartsWith($resolvedSystemTemp, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove non-temporary smoke directory: $resolvedTemporary"
    }
    if (Test-Path -LiteralPath $resolvedTemporary) {
        Remove-Item -LiteralPath $resolvedTemporary -Recurse -Force
    }
}

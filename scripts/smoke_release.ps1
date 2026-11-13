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

        $guiText = (& $executablePath gui --self-test 2>&1) -join "`n"
        if ($LASTEXITCODE -ne 0) {
            throw "EXE GUI construction failed with exit code $LASTEXITCODE`n$guiText"
        }
        $gui = $guiText | ConvertFrom-Json
        if ($gui.status -ne "PASS" -or $gui.scope -ne "hidden-widget-construction") {
            throw "EXE GUI construction did not pass.`n$guiText"
        }

        $listText = (& $executablePath list 2>&1) -join "`n"
        if ($LASTEXITCODE -ne 0) {
            throw "EXE list failed with exit code $LASTEXITCODE`n$listText"
        }
        foreach ($marker in @("cards", "home_voices", "campaign_voices", "card_update")) {
            if ($listText -notmatch [regex]::Escape($marker)) {
                throw "EXE list output is missing '$marker'."
            }
        }

        $websiteHelp = (& $executablePath website check --help 2>&1) -join "`n"
        if ($LASTEXITCODE -ne 0 -or $websiteHelp -notmatch '--expected-manifest') {
            throw "EXE website modules or CLI options are missing.`n$websiteHelp"
        }
        $emptyCache = Join-Path $temporaryRoot 'empty-cache'
        $websiteOutput = Join-Path $temporaryRoot 'website-output'
        $websiteFailure = (& $executablePath website check --offline --cache $emptyCache --output $websiteOutput 2>&1) -join "`n"
        if ($LASTEXITCODE -eq 0 -or -not (Test-Path (Join-Path $websiteOutput 'website_failure.json'))) {
            throw "EXE offline missing-cache check did not fail explicitly.`n$websiteFailure"
        }

        $masterdataBytes = [Convert]::FromBase64String(
            "xxJjzgAAAAzAgaltc3Rfc21va2UAxxhjzgAAABHwApGCoklkAaROYW1lpVNtb2tl"
        )
        [System.IO.File]::WriteAllBytes(
            (Join-Path $temporaryRoot "master_data.s2b"),
            $masterdataBytes
        )
        # generate decodes master_data.s2b strictly before checking tables; the
        # one-table sample must decode and then be rejected for missing tables.
        $generateOutput = Join-Path $temporaryRoot "generate-output"
        $decryptText = (& $executablePath generate cards --masterdata (Join-Path $temporaryRoot "master_data.s2b") --output $generateOutput 2>&1) -join "`n"
        if ($LASTEXITCODE -eq 0 -or $decryptText -notmatch 'required table is missing') {
            throw "EXE generate did not reject the one-table masterdata explicitly.`n$decryptText"
        }
        $jsonPath = Join-Path $generateOutput ".bmc_toolkit\master_data.json"
        $cachePath = Join-Path $generateOutput ".bmc_toolkit\.bmc_toolkit\master_data_cache.json"
        if (-not (Test-Path -LiteralPath $jsonPath) -or -not (Test-Path -LiteralPath $cachePath)) {
            throw "EXE decrypt smoke did not create JSON and cache manifest.`n$decryptText"
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
            gui_construction = $gui
            list_markers = @("cards", "home_voices", "campaign_voices", "card_update")
            website_cli = 'PASS: help and offline missing-cache rejection'
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

# Callers read $LASTEXITCODE, which would otherwise still hold the expected
# non-zero exit of the masterdata rejection check above.
exit 0

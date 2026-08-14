[CmdletBinding()]
param(
    [string]$PythonExe,
    [switch]$InstallDependencies,
    [switch]$SkipSmoke
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$expectedPython = "3.12.9"
$expectedNuitka = "4.1.2"
$requirements = Join-Path $repoRoot "requirements\release-build.txt"
$distDirectory = Join-Path $repoRoot "dist"
$executable = Join-Path $distDirectory "bmc_toolkit.exe"

if (-not $PythonExe) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $PythonExe = (& py -3.12 -c "import sys; print(sys.executable)").Trim()
    }
    if (-not $PythonExe) {
        $PythonExe = (Get-Command python -ErrorAction Stop).Source
    }
}
$PythonExe = (Resolve-Path -LiteralPath $PythonExe).Path

$pythonVersion = (& $PythonExe -c "import platform; print(platform.python_version())").Trim()
if ($LASTEXITCODE -ne 0 -or $pythonVersion -ne $expectedPython) {
    throw "Release build requires CPython $expectedPython; found '$pythonVersion' at $PythonExe."
}

if ($InstallDependencies) {
    & $PythonExe -m pip install --disable-pip-version-check --upgrade `
        "pip==26.2.1" "setuptools==82.0.1" "wheel==0.48.0" "packaging==26.3"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install pinned release bootstrap dependencies."
    }
    & $PythonExe -m pip install --disable-pip-version-check --no-build-isolation -r $requirements
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install pinned release dependencies."
    }
}

$dependencyJson = (& $PythonExe -c @"
import importlib.metadata, json, pathlib, sys
requirements = {}
for raw in pathlib.Path(sys.argv[1]).read_text(encoding='utf-8').splitlines():
    line = raw.strip()
    if not line or line.startswith('#'):
        continue
    name, expected = line.split('==', 1)
    actual = importlib.metadata.version(name)
    if actual != expected:
        raise SystemExit(f'{name}: expected {expected}, found {actual}')
    requirements[name] = actual
print(json.dumps(requirements, sort_keys=True))
"@ $requirements).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Installed packages do not match requirements/release-build.txt."
}

$nuitkaOutput = (& $PythonExe -m nuitka --version 2>&1) -join "`n"
if ($LASTEXITCODE -ne 0) {
    throw "Nuitka is not installed for $PythonExe. Use -InstallDependencies."
}
$nuitkaVersion = ($nuitkaOutput -split "`r?`n")[0].Trim()
if ($nuitkaVersion -ne $expectedNuitka) {
    throw "Release build requires Nuitka $expectedNuitka; found '$nuitkaVersion'."
}

New-Item -ItemType Directory -Force -Path $distDirectory | Out-Null
Push-Location $repoRoot
try {
    & $PythonExe -m nuitka `
        --standalone `
        --onefile `
        --enable-plugin=tk-inter `
        --msvc=latest `
        --windows-console-mode=force `
        --assume-yes-for-downloads `
        --remove-output `
        --output-dir=$distDirectory `
        --output-filename=bmc_toolkit.exe `
        --company-name=BRMY-Wiki `
        --product-name=BRMY-Wiki-Toolkit `
        --file-description="Break My Case Wiki data toolkit" `
        --file-version=0.2.0.0 `
        --product-version=0.2.0.0 `
        toolkit\run.py
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $executable)) {
        throw "Nuitka release build failed."
    }
}
finally {
    Pop-Location
}

$smokeStatus = "SKIPPED"
if (-not $SkipSmoke) {
    & (Join-Path $PSScriptRoot "smoke_release.ps1") `
        -Executable $executable `
        -ReportPath (Join-Path $distDirectory "smoke_report.json")
    if ($LASTEXITCODE -ne 0) {
        throw "Release EXE smoke test failed."
    }
    $smokeStatus = "PASS"
}

$sha256 = (Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash.ToLowerInvariant()
[System.IO.File]::WriteAllText(
    (Join-Path $distDirectory "bmc_toolkit.exe.sha256"),
    "$sha256  bmc_toolkit.exe`n",
    [System.Text.UTF8Encoding]::new($false)
)

$gitCommit = (git -C $repoRoot rev-parse HEAD 2>$null)
$gitDirty = [bool](git -C $repoRoot status --porcelain --untracked-files=no)
$manifest = [ordered]@{
    schema_version = 1
    built_at_utc = [DateTime]::UtcNow.ToString("o")
    artifact = "bmc_toolkit.exe"
    artifact_size = (Get-Item -LiteralPath $executable).Length
    artifact_sha256 = $sha256
    git_commit = ($gitCommit | Select-Object -First 1)
    git_dirty = $gitDirty
    python_version = $pythonVersion
    python_executable = $PythonExe
    nuitka_version = $nuitkaVersion
    dependencies = ($dependencyJson | ConvertFrom-Json)
    smoke_status = $smokeStatus
}
[System.IO.File]::WriteAllText(
    (Join-Path $distDirectory "build_manifest.json"),
    (($manifest | ConvertTo-Json -Depth 6) + "`n"),
    [System.Text.UTF8Encoding]::new($false)
)

Write-Host "Release build passed: $executable"
Write-Host "SHA-256: $sha256"

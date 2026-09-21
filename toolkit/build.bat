@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

where powershell.exe >nul 2>&1
if errorlevel 1 (
    echo [ERROR] powershell.exe is required.
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%CD%\scripts\build_release.ps1" -InstallDependencies
if errorlevel 1 (
    echo [FAILED] Release build failed.
    exit /b 1
)

echo [SUCCESS] dist\bmc_toolkit.exe
exit /b 0

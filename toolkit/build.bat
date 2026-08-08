@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ========================================
echo   BMC Toolkit - Nuitka Build Script
echo ========================================
echo.

REM Verify Nuitka
python -m nuitka --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Nuitka not found. Installing...
    pip install nuitka
    python -m nuitka --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install Nuitka.
        pause
        exit /b 1
    )
)

echo [*] Building, please wait...
echo.

REM Try --onefile first (single .exe, larger but portable)
python -m nuitka ^
    --standalone ^
    --onefile ^
    --enable-plugin=tk-inter ^
    --output-dir=dist ^
    --output-filename=bmc_toolkit.exe ^
    --assume-yes-for-downloads ^
    run.py

if %errorlevel% equ 0 (
    echo.
    echo [SUCCESS] dist\bmc_toolkit.exe
    copy /Y "dist\bmc_toolkit.exe" "..\bmc_toolkit.exe" >nul
    if %errorlevel% equ 0 (
        echo [SUCCESS] ..\bmc_toolkit.exe
    )
    goto :done
)

echo.
echo [*] --onefile failed, trying --standalone (folder mode)...
echo.

python -m nuitka ^
    --standalone ^
    --enable-plugin=tk-inter ^
    --output-dir=dist ^
    --assume-yes-for-downloads ^
    run.py

if %errorlevel% equ 0 (
    echo.
    echo [SUCCESS] dist\run.dist\run.exe
) else (
    echo.
    echo [FAILED] Nuitka build failed. Check dependencies.
)

:done
pause

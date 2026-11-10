@echo off
echo ========================================================
echo Launching Model Y - AgroShield (Electron Desktop App)
echo Domain 01: Cost of living and everyday economics
echo ========================================================

set ELECTRON_PATH="d:\Beach resort Project\Mawella-Beach-Resort-POS\node_modules\electron\dist\electron.exe"

if exist %ELECTRON_PATH% (
    echo Using Electron from Beach Resort Project...
    %ELECTRON_PATH% "%~dp0."
) else (
    echo Electron binary not found, attempting system electron...
    electron "%~dp0."
)

pause

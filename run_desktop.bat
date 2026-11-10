@echo off
echo ========================================================
echo Launching Model Y - AgroShield (Electron Desktop App)
echo Domain 01: Cost of living and everyday economics
echo ========================================================

cd /d "%~dp0"
if not exist node_modules\electron (
    echo Installing Electron (first run only)...
    call npm install
)
call npx electron .

pause

@echo off
echo ========================================================
echo Launching Model Y - AgroShield Web App
echo Domain 01: Cost of living and everyday economics
echo ========================================================

start "" "http://localhost:3000"
d:\Conda\python.exe -m http.server 3000 --directory "%~dp0ui"

pause

@echo off
title NUMBER BOTMAN Runner
chcp 65001 >nul
color 0A
cd /d "%~dp0"

echo ===================================================
echo             NUMBER BOTMAN RUNNER
echo ===================================================
echo.
echo Terminating any duplicate bot instances...
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*bot.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1

echo Starting bot in foreground mode...
echo (Press Ctrl+C to stop)
echo.

:LOOP
python bot.py
echo.
echo [INFO] Bot process ended (exit code %ERRORLEVEL%).
echo Auto-restarting in 3 seconds... (Press Ctrl+C to stop)
timeout /t 3 /nobreak >nul
goto LOOP

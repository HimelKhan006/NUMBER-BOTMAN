@echo off
title NUMBER-BOTMAN - DIAGNOSTICS TEST
chcp 65001 >nul
cls
cd /d "%~dp0"
python bot.py --test
echo.
pause

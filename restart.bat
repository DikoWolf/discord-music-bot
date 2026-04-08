@echo off
:: Discord Music Bot Restart Script
:: Usage: restart.bat atau klik dua kali

echo ==========================================
echo    Discord Music Bot - Restart Script
echo ==========================================
echo.

:: Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python tidak dijumpai dalam PATH
    echo Pastikan Python telah dipasang.
    pause
    exit /b 1
)

echo Checking for running bot process...

:: Kill any existing python processes running bot.py (optional - remove if not needed)
taskkill /F /FI "WINDOWTITLE eq bot.py" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq *bot.py*" /T >nul 2>&1

echo.
echo Starting bot...
echo.

:: Run the bot
python bot.py

echo.
echo Bot telah ditamatkan.
pause

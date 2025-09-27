@echo off
REM Wildmeta Intelligence Suite - Bot Launcher
REM This script starts both the RSS and X bots in separate windows

echo ========================================
echo    Wildmeta Intelligence Suite
echo    Starting RSS and X Feed Bots...
echo ========================================
echo.

REM Check if .env file exists
if not exist ".env" (
    echo ERROR: .env file not found!
    echo Please create .env file with your configuration.
    echo Copy from config.template and add your tokens.
    pause
    exit /b 1
)

REM Activate virtual environment if it exists
if exist "..\venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call ..\venv\Scripts\activate.bat
)

REM Start RSS Macro/Crypto Bot
echo Starting RSS Macro/Crypto Bot...
start "Wildmeta RSS Bot" cmd /k "python rss_macro_crypto_bot.py"

REM Wait a moment before starting second bot
timeout /t 2 /nobreak >nul

REM Start X Feed Bot
echo Starting X Feed Bot...
start "Wildmeta X Bot" cmd /k "python wildmeta_x_feed_bot.py"

echo.
echo ========================================
echo    Both bots started successfully!
echo    Check the opened windows for logs.
echo ========================================
echo.
echo Press any key to close this window...
pause >nul

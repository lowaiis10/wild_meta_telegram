@echo off
REM Wildmeta Intelligence Suite - Bot Launcher
REM This script starts the unified bot manager

echo ========================================
echo    Wildmeta Intelligence Suite
echo    Unified Bot Manager
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

REM Display options
echo Select operation mode:
echo   1. Run both bots (RSS + X)
echo   2. Run RSS bot only
echo   3. Run X bot only
echo   4. Check bot status
echo   5. Exit
echo.
set /p choice="Enter your choice (1-5): "

if "%choice%"=="1" (
    echo Starting both bots...
    python wildmeta_bot_manager.py
) else if "%choice%"=="2" (
    echo Starting RSS bot only...
    python wildmeta_bot_manager.py --rss
) else if "%choice%"=="3" (
    echo Starting X bot only...
    python wildmeta_bot_manager.py --x
) else if "%choice%"=="4" (
    echo Checking bot status...
    python wildmeta_bot_manager.py --status
    echo.
    pause
) else if "%choice%"=="5" (
    echo Exiting...
    exit /b 0
) else (
    echo Invalid choice!
    pause
    exit /b 1
)

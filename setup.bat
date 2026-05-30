@echo off
REM ============================================================
REM  Air Ocean Lead Finder - one-time setup (Windows)
REM  Double-click this ONCE. Needs Python 3.10+ installed.
REM ============================================================
cd /d "%~dp0"

echo [1/3] Creating virtual environment...
python -m venv .venv
call .venv\Scripts\activate.bat

echo [2/3] Installing the app and dependencies (a few minutes)...
python -m pip install --upgrade pip
python -m pip install -e .

echo [3/3] Installing browser for Google Maps / Yellow Pages (Phase 2)...
python -m playwright install chromium

echo.
echo ============================================================
echo  Setup complete! Double-click  launcher.bat  to start.
echo ============================================================
pause

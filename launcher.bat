@echo off
REM Air Ocean Lead Finder - start the app (Windows). Double-click this.
cd /d "%~dp0"
call .venv\Scripts\activate.bat
set PYTHONPATH=src
streamlit run src\aol_leadfinder\ui\app.py

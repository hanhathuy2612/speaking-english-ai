@echo off
rem Start the app with the settings in .env (docs/dev-environment.md). Usage: run
cd /d "%~dp0backend" && "%~dp0.venv\Scripts\python.exe" -m app

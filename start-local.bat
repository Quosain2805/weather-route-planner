@echo off
REM Starts the whole app (API + built web app) at http://localhost:8020
REM Keep this window open while you use it. Press Ctrl+C to stop.
cd /d "%~dp0backend"
set DJANGO_DEBUG=1
start "" "http://localhost:8020"
".venv\Scripts\python.exe" manage.py runserver 8020 --noreload
pause

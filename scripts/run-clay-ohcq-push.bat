@echo off
cd /d "%~dp0\.."
".venv\Scripts\python.exe" scripts\clay_push_ohcq_leads.py %*
exit /b %ERRORLEVEL%

@echo off
cd /d "%~dp0\.."
".venv\Scripts\python.exe" scripts\ohcq_citation_tracker.py %*
exit /b %ERRORLEVEL%

@echo off
cd /d "%~dp0\.."
".venv\Scripts\python.exe" scripts\md_ohcq_leads_pipeline.py %*
exit /b %ERRORLEVEL%

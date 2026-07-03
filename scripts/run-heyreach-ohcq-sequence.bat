@echo off
cd /d "%~dp0\.."
".venv\Scripts\python.exe" scripts\heyreach_build_ohcq_sequence.py %*
exit /b %ERRORLEVEL%

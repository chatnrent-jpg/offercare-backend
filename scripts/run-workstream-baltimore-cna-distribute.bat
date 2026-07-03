@echo off
cd /d "%~dp0\.."
".venv\Scripts\python.exe" scripts\workstream_distribute_baltimore_cna.py %*
exit /b %ERRORLEVEL%

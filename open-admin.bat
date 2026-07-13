@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set "PYTHONPATH=%~dp0"

.venv\Scripts\python.exe -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/admin', timeout=4)" >nul 2>&1
if %errorlevel%==0 goto open_admin

echo VettedMe API is not running — starting it...
call "%~dp0start-all.bat"
exit /b 0

:open_admin
start "" "http://127.0.0.1:8000/admin"
exit /b 0

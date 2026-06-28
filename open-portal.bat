@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title VettedCare Clinician Portal
set "PYTHONPATH=%~dp0"
set "PY=%~dp0.venv\Scripts\python.exe"

if not exist "%PY%" (
  echo [ERROR] Python venv not found: %PY%
  pause
  exit /b 1
)

"%PY%" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/vettedcare', timeout=4)" >nul 2>&1
if !errorlevel! neq 0 (
  echo Starting API on http://127.0.0.1:8000 ...
  start "VettedCare API" cmd /k "title VettedCare API && cd /d %~dp0 && set PYTHONPATH=%~dp0 && %PY% -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
  echo Waiting for API...
  set "TRIES=0"
  :wait_loop
  timeout /t 2 /nobreak >nul
  "%PY%" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/vettedcare', timeout=4)" >nul 2>&1
  if !errorlevel!==0 goto api_ready
  set /a TRIES+=1
  if !TRIES! LSS 30 goto wait_loop
  echo [ERROR] API did not respond. Check the VettedCare API window for errors.
  pause
  exit /b 1
  :api_ready
)

echo.
echo   Clinician portal: http://127.0.0.1:8000/portal/
echo   Look for: Sign in / Apply tabs and "build portal-restore-v3" on the page.
echo   If old UI: Chrome F12 - Application - Clear site data for 127.0.0.1
echo   Do NOT open index.html from disk — use the URL above.
echo.
start "" "http://127.0.0.1:8000/portal/"
pause

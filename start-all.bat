@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title VettedCare.ai Launcher
set "PYTHONPATH=%~dp0"

echo.
echo VettedCare.ai — Credential Safety Platform
echo.

set "NEED_START=1"

netstat -ano | findstr /R "127.0.0.1:8000 .*LISTENING" >nul 2>&1
if %errorlevel%==0 (
  .venv\Scripts\python.exe -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/vettedcare', timeout=4)" >nul 2>&1
  if !errorlevel!==0 (
    echo [OK] API already running on http://127.0.0.1:8000
    set "NEED_START=0"
  ) else (
    echo [WARN] Port 8000 in use but API is stale — restarting...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R "127.0.0.1:8000 .*LISTENING"') do (
      taskkill /PID %%a /F >nul 2>&1
    )
    timeout /t 2 /nobreak >nul
  )
)

if "!NEED_START!"=="1" (
  echo Starting API on port 8000...
  start "VettedCare API" cmd /k "cd /d %~dp0 && set PYTHONPATH=%~dp0 && call .venv\Scripts\activate.bat && uvicorn app.main:app --host 127.0.0.1 --port 8000"
  echo Waiting for API...
  set "TRIES=0"
  :wait_loop
  timeout /t 2 /nobreak >nul
  .venv\Scripts\python.exe -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/vettedcare', timeout=4)" >nul 2>&1
  if !errorlevel!==0 goto api_ready
  set /a TRIES+=1
  if !TRIES! LSS 15 goto wait_loop
  echo [ERROR] API did not start. Check the VettedCare API window for errors.
  pause
  exit /b 1
  :api_ready
  echo [OK] API is up.
)

echo.
echo   Admin:  http://127.0.0.1:8000/admin
echo   Portal: http://127.0.0.1:8000/portal
echo   Health: http://127.0.0.1:8000/health/vettedcare
echo.
echo Opening admin in your browser...
start "" "http://127.0.0.1:8000/admin"
echo.
echo Leave the black "VettedCare API" window open while you work.
echo Press any key to close this launcher...
pause >nul

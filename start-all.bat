@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title VettedMe Launcher
set "PYTHONPATH=%~dp0"
set "PY=%~dp0.venv\Scripts\python.exe"

echo.
echo VettedMe - Credential Safety Platform
echo.

if not exist "%PY%" (
  echo [ERROR] Python venv not found:
  echo   %PY%
  pause
  exit /b 1
)

set "NEED_START=1"

"%PY%" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/vettedme', timeout=4)" >nul 2>&1
if !errorlevel!==0 (
  echo [OK] API already running on http://127.0.0.1:8000
  set "NEED_START=0"
) else (
  netstat -ano | findstr /R "127.0.0.1:8000 .*LISTENING" >nul 2>&1
  if !errorlevel!==0 (
    echo [WARN] Port 8000 in use but API not healthy - restarting...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R "127.0.0.1:8000 .*LISTENING"') do (
      taskkill /PID %%a /F >nul 2>&1
    )
    timeout /t 3 /nobreak >nul
  )
)

if "!NEED_START!"=="1" (
  echo Starting API in a new window - check your taskbar for "VettedMe API"
  start "VettedMe API" cmd /k "title VettedMe API && cd /d %~dp0 && set PYTHONPATH=%~dp0 && %PY% -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
  echo Waiting for API up to 90 seconds...
  set "TRIES=0"
  :wait_loop
  timeout /t 2 /nobreak >nul
  "%PY%" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/vettedme', timeout=4)" >nul 2>&1
  if !errorlevel!==0 goto api_ready
  set /a TRIES+=1
  if !TRIES! LSS 45 goto wait_loop
  echo [ERROR] API did not respond in time.
  echo Check the taskbar for a window named "VettedMe API" for error messages.
  pause
  exit /b 1
  :api_ready
  echo [OK] API is up.
)

echo.
echo   Admin:  http://127.0.0.1:8000/admin
echo   Health: http://127.0.0.1:8000/health/vettedme
echo.
echo Opening admin in your browser...
start "" "http://127.0.0.1:8000/admin"
echo.
echo Leave the "VettedMe API" window open while you work.
echo Press any key to close this launcher only...
pause >nul

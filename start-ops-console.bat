@echo off
setlocal
cd /d "%~dp0"
title VettedMe Ops Console
set "PYTHONPATH=%~dp0"
set "PY=%~dp0.venv\Scripts\python.exe"

echo.
echo VettedMe.ai - Maryland Ops Console
echo.

if not exist "%PY%" (
  echo [ERROR] Python venv not found:
  echo   %PY%
  pause
  exit /b 1
)

echo Starting Streamlit on http://127.0.0.1:8503
echo Leave this window open while you use the ops console.
echo.

start "" "http://127.0.0.1:8503"
"%PY%" -m streamlit run ui_dashboard/ops_console.py --server.port 8503 --server.address 127.0.0.1

@echo off
cd /d "%~dp0\.."
title VettedMe Pre-flight

echo.
echo VettedMe infrastructure pre-flight
echo.

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

"%PY%" scripts\vettedme_preflight.py
set "RC=%ERRORLEVEL%"

echo.
if %RC%==0 (
  echo Pre-flight passed.
) else (
  echo Pre-flight failed — fix items above, then restart VettedMe.ai
)
pause
exit /b %RC%

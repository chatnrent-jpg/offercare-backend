@echo off
cd /d "%~dp0\.."
title VettedCare Pre-flight

echo.
echo VettedCare infrastructure pre-flight
echo.

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

"%PY%" scripts\vettedcare_preflight.py
set "RC=%ERRORLEVEL%"

echo.
if %RC%==0 (
  echo Pre-flight passed.
) else (
  echo Pre-flight failed — fix items above, then restart VettedCare.ai
)
pause
exit /b %RC%

@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title VettedCare Full Platform Restore
echo.
echo ========================================
echo  VettedCare FULL PLATFORM RESTORE
echo ========================================
echo.
echo The Next.js page on :3000 is a thin stub.
echo The REAL product is this FastAPI backend:
echo   Admin:  http://127.0.0.1:8000/admin
echo   Portal: http://127.0.0.1:8000/portal/
echo   Ops:    http://127.0.0.1:8503
echo.

REM Ensure .env exists
if not exist ".env" (
  if exist ".env.example" (
    copy /Y ".env.example" ".env" >nul
    echo [OK] Created .env from .env.example
  ) else (
    echo [ERROR] No .env or .env.example found
    pause
    exit /b 1
  )
) else (
  echo [OK] .env present
)

REM Create venv if missing
if not exist ".venv\Scripts\python.exe" (
  echo.
  echo Creating Python virtual environment...
  python -m venv .venv
  if errorlevel 1 (
    echo [ERROR] python -m venv failed. Is Python installed?
    pause
    exit /b 1
  )
  echo [OK] venv created
) else (
  echo [OK] venv already exists
)

echo.
echo Installing Python dependencies (this can take a few minutes)...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\pip.exe" install -r requirements.txt
if errorlevel 1 (
  echo [WARN] Some packages may have failed. Trying requirements-core.txt...
  if exist requirements-core.txt (
    ".venv\Scripts\pip.exe" install -r requirements-core.txt
  )
)

echo.
echo Starting full VettedCare API...
call start-all.bat

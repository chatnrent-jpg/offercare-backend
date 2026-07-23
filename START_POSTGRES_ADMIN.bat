@echo off
:: Requests Administrator rights, then starts PostgreSQL 17
net session >nul 2>&1
if %errorlevel% neq 0 (
  echo Requesting Administrator permission...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

echo.
echo Starting PostgreSQL Server 17...
net start postgresql-x64-17
if %errorlevel% equ 0 (
  echo.
  echo SUCCESS: PostgreSQL is running.
) else (
  echo.
  echo FAILED: Could not start postgresql-x64-17
  echo Open services.msc as Admin and start it manually.
)
echo.
pause

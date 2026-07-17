@echo off
echo.
echo ========================================
echo   VettedPay Landing Page - Local Test
echo ========================================
echo.
echo Starting local server on http://localhost:8080
echo Press Ctrl+C to stop
echo.

cd frontend\public
python -m http.server 8080

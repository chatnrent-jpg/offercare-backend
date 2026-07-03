@echo off
cd /d "%~dp0\.."
echo.
echo === VettedCare backend tests ===
echo Repo: %CD%
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: .venv not found. Run from vettedcare-backend folder.
    pause
    exit /b 1
)

echo [1/2] Caregiver tests...
".venv\Scripts\python.exe" -m pytest tests\test_caregiver_api.py tests\test_caregiver_accounts.py -q
set CAREGIVER_EXIT=%ERRORLEVEL%
echo Caregiver exit code: %CAREGIVER_EXIT%
echo.

echo [2/2] Payroll tax intercept tests...
".venv\Scripts\python.exe" -m pytest tests\test_payroll_tax_intercept_bridge.py -q
set PAYROLL_EXIT=%ERRORLEVEL%
echo Payroll exit code: %PAYROLL_EXIT%
echo.

if %CAREGIVER_EXIT% NEQ 0 (
    echo FAILED: caregiver tests
    pause
    exit /b %CAREGIVER_EXIT%
)
if %PAYROLL_EXIT% NEQ 0 (
    echo FAILED: payroll tests
    pause
    exit /b %PAYROLL_EXIT%
)

echo ALL PASSED
pause
exit /b 0

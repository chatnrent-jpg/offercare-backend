@echo off
cd /d "%~dp0\.."
".venv\Scripts\python.exe" -m pytest tests\test_payroll_tax_intercept_bridge.py -q %*
exit /b %ERRORLEVEL%

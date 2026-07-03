@echo off
cd /d "%~dp0\.."
".venv\Scripts\python.exe" -m pytest tests\test_caregiver_api.py tests\test_caregiver_accounts.py -q %*
exit /b %ERRORLEVEL%

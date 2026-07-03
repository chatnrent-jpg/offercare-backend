@echo off
cd /d "%~dp0\.."
".venv\Scripts\python.exe" -m pytest tests\test_compliance_sentinel.py -q %*
exit /b %ERRORLEVEL%

@echo off
cd /d "%~dp0\.."
call .venv\Scripts\activate.bat
python scripts\verify_portal_live.py
exit /b %ERRORLEVEL%

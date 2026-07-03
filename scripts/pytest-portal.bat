@echo off
cd /d "%~dp0\.."
call .venv\Scripts\activate.bat
python -m pytest tests\test_step15_portal_open_shifts_resilience.py tests\test_step12_portal_unified_open_shifts.py tests\test_step13_lock_preview.py tests\test_step14_lockable_filter.py -q %*
exit /b %ERRORLEVEL%

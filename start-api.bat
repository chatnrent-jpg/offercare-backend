@echo off
cd /d "%~dp0"
echo Starting VettedCare.ai API on http://127.0.0.1:8000
echo Admin UI: http://127.0.0.1:8000/admin
echo Portal: http://127.0.0.1:8000/portal/
echo.
call .venv\Scripts\activate.bat
for /f %%i in ('python -c "from app.main import PORTAL_BUILD_ID; print(PORTAL_BUILD_ID)"') do set EXPECTED_BUILD=%%i
echo Expected X-Portal-Build: %EXPECTED_BUILD%
echo If browser shows an older build, close other API windows and restart this script.
echo.
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

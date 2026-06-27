@echo off
cd /d "%~dp0"
echo Starting VettedCare.ai API on http://127.0.0.1:8000
echo Admin UI: http://127.0.0.1:8000/admin
echo.
call .venv\Scripts\activate.bat
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

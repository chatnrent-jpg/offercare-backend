@echo off
setlocal
cd /d "%~dp0.."
set PYTHONPATH=%CD%
echo Starting Maryland Rollout Streamlit dashboard on http://127.0.0.1:8502
.\.venv\Scripts\streamlit.exe run streamlit_apps\md_maryland_rollout.py --server.port 8502 --server.headless true

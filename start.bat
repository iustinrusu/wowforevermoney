@echo off
rem Starts WoW Forever Money and opens it in your browser. Close this window to stop it.
cd /d "%~dp0"
set PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe
if not exist "%PY%" set PY=python
"%PY%" -m pip install --user --quiet -r requirements.txt
"%PY%" run.py %*
pause

@echo off
setlocal EnableExtensions
rem Starts WoW Forever Money and opens it in your browser. Close this window to stop it.
rem Any earlier copy (even a hidden one) is stopped automatically, so this always starts a fresh one.
rem No Python yet? It offers to install Python 3.13 for you with winget (Windows' own app installer).
cd /d "%~dp0"

call :find_python
if not defined PY call :install_python
if not defined PY goto :end

"%PY%" -m pip install --user --quiet -r requirements.txt
"%PY%" run.py %*
goto :end

rem ---- helpers -------------------------------------------------------------
:find_python
rem Python 3.13 or newer (what the app is tested with). The "python" in WindowsApps is only a
rem shortcut to the Microsoft Store, not a real Python, so it's skipped.
set "PY="
for %%V in (313 314 315) do if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
for %%V in (313 314 315) do if not defined PY if exist "%ProgramFiles%\Python%%V\python.exe" set "PY=%ProgramFiles%\Python%%V\python.exe"
if not defined PY for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable if sys.version_info >= (3, 13) else '')" 2^>nul') do set "PY=%%P"
if not defined PY for /f "delims=" %%P in ('where python 2^>nul ^| findstr /v /i "WindowsApps"') do if not defined PY "%%P" -c "import sys; raise SystemExit(sys.version_info < (3, 13))" 2>nul && set "PY=%%P"
goto :eof

:install_python
echo WoW Forever Money needs Python 3.13 or newer (free, from python.org), and it isn't installed.
where winget >nul 2>nul || goto :manual_python
set "YN="
set /p "YN=Install Python 3.13 now with winget? Type Y and press Enter: "
if /i not "%YN%"=="Y" goto :manual_python
winget install --id Python.Python.3.13 --exact
call :find_python
if defined PY goto :eof
echo.
echo Python was installed, but this window can't see it yet. Close it and double-click start.bat again.
goto :eof
:manual_python
echo.
echo Install Python 3.13 from https://www.python.org/downloads/ and tick "Add python.exe to PATH",
echo then double-click start.bat again.
goto :eof

:end
echo.
pause
endlocal

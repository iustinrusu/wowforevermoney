@echo off
setlocal EnableExtensions
rem Installs or updates the ForeverMoneyBridge addon in WoW: Forever. Doesn't need Python or the app.
rem Double-click it. If it can't find WoW, it asks for the folder. You can also drag your
rem "World of Warcraft" folder onto this file.
rem (start.bat also installs the addon every time the app starts, so this is only needed without the app.)

set "NAME=ForeverMoneyBridge"
set "SRC=%~dp0addon\%NAME%"
rem Keep paths out of ( ) blocks: the ")" in "Program Files (x86)" would end a block early.
if exist "%SRC%\%NAME%.toc" goto :have_source
echo Can't find the addon files next to this script:
echo   %SRC%
echo Unzip the whole WoW Forever Money folder first, then run this from inside it.
goto :end
:have_source

set "WOW="
if not "%~1"=="" call :try "%~1"
if not defined WOW call :from_tsm
if not defined WOW call :from_registry
if not defined WOW for %%D in (C D E F G H) do (
  if not defined WOW call :try "%%D:\Games\World of Warcraft"
  if not defined WOW call :try "%%D:\Program Files (x86)\World of Warcraft"
  if not defined WOW call :try "%%D:\Program Files\World of Warcraft"
  if not defined WOW call :try "%%D:\World of Warcraft"
  if not defined WOW call :try "%%D:\Blizzard\World of Warcraft"
)
if not defined WOW call :ask
if not defined WOW goto :end

set "DEST=%WOW%\_forever_\Interface\AddOns\%NAME%"
if not exist "%DEST%\" mkdir "%DEST%"
if exist "%DEST%\" goto :have_dest
echo Couldn't create %DEST%
echo Try running this file again with right-click, Run as administrator.
goto :end
:have_dest
rem Checks.lua is written by the app (the items to check in game): keep the existing one.
for %%F in ("%SRC%\*") do (
  if /i not "%%~nxF"=="Checks.lua" copy /y "%%~fF" "%DEST%\" >nul || goto :copy_failed
)
if not exist "%DEST%\Checks.lua" copy /y "%SRC%\Checks.lua" "%DEST%\" >nul || goto :copy_failed

set "VER="
for /f "tokens=2 delims=:" %%V in ('findstr /b /c:"## Version:" "%SRC%\%NAME%.toc"') do set "VER=%%V"
echo.
echo Installed %NAME%%VER% into:
echo   %DEST%
echo.
echo Next, in WoW: Forever:
echo   1. If the game is open and this is the first install, restart it (new addons only show up after a restart).
echo      For an update, typing /reload in game is enough.
echo   2. At the character screen click AddOns and tick %NAME%.
echo      If it says "out of date", tick "Load out of date AddOns".
echo   3. Log in and type /reload. The addon saves your data on /reload or logout.
goto :end

:copy_failed
echo.
echo Copying failed. Is the folder read-only? Try right-click on this file, Run as administrator.
goto :end

rem ---- helpers -------------------------------------------------------------
:try
rem %1 is the World of Warcraft folder, or its _forever_ folder
if exist "%~1\_forever_\" (
  set "WOW=%~f1"
  goto :eof
)
if /i "%~nx1"=="_forever_" if exist "%~1\" for %%P in ("%~1\..") do set "WOW=%%~fP"
goto :eof

:from_tsm
rem the TSM desktop app remembers where WoW is
set "CFG=%APPDATA%\tradeskillmaster\TSM.cfg"
if not exist "%CFG%" goto :eof
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "$m = [regex]::Match((Get-Content -Raw $env:CFG), '\x22wowPath\x22\s*:\s*\x22([^\x22]+)\x22'); if ($m.Success) { $m.Groups[1].Value.Replace('\\', '\') }"`) do call :try "%%P"
goto :eof

:from_registry
rem the Battle.net launcher records the install folder (usually ending in a game-version subfolder)
for %%K in ("HKLM\SOFTWARE\WOW6432Node\Blizzard Entertainment\World of Warcraft" "HKLM\SOFTWARE\Blizzard Entertainment\World of Warcraft") do (
  for /f "tokens=2,*" %%A in ('reg query %%K /v InstallPath 2^>nul ^| findstr /i "InstallPath"') do (
    if not defined WOW call :try "%%B"
    if not defined WOW for %%P in ("%%B\..") do call :try "%%~fP"
  )
)
goto :eof

:ask
echo Couldn't find WoW: Forever automatically.
echo Paste your "World of Warcraft" folder (the one that contains _forever_), then press Enter.
echo Example: C:\Program Files (x86)\World of Warcraft
set "ANSWER="
set /p "ANSWER=Folder: "
if not defined ANSWER (
  echo Nothing was installed.
  goto :eof
)
set "ANSWER=%ANSWER:"=%"
call :try "%ANSWER%"
if not defined WOW echo "%ANSWER%" has no _forever_ folder inside. Nothing was installed.
goto :eof

:end
echo.
pause
endlocal

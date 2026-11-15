@echo off
rem Update Gold Ever After to the latest version from GitHub (main), then restart it with start.bat.
rem Works in a folder made with "git clone". A ZIP download has no git history: download the ZIP again instead.
setlocal
cd /d "%~dp0"
title Gold Ever After - update

where git >nul 2>nul
if errorlevel 1 (
  echo Git is not installed, so this folder can't update itself.
  echo Either install Git for Windows ^(https://git-scm.com/download/win^) and clone the app again,
  echo or download the latest ZIP from https://github.com/iustinrusu/wowforevermoney and unzip it over this folder
  echo ^(your data folder, settings and price history are kept: they are not in the ZIP^).
  pause
  exit /b 1
)
if not exist ".git" (
  echo This folder came from a ZIP download, not "git clone", so it can't update itself.
  echo Download the latest ZIP from https://github.com/iustinrusu/wowforevermoney and unzip it over this folder
  echo ^(your data folder, settings and price history are kept: they are not in the ZIP^).
  pause
  exit /b 1
)

echo Getting the latest version...
git pull --ff-only origin main
if errorlevel 1 (
  echo.
  echo The update didn't go through. Usually that means files of the app were changed in this folder.
  echo Nothing was lost. To see what changed: git status
  pause
  exit /b 1
)
echo.
echo Up to date. If the app is running, close its window and start it again with start.bat.
pause

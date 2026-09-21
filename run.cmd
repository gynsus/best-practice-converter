@echo off
rem Launcher for Windows Task Scheduler.
rem Captures ALL output (including early fatals that happen before the
rem converter can create its own log) into launcher.log next to this file.
cd /d %~dp0
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

rem keep launcher.log small: rotate when over ~512 KB
for %%F in (launcher.log) do if %%~zF GTR 524288 move /y launcher.log launcher.old.log >nul

echo ===== start %date% %time% =====>> launcher.log
".venv\Scripts\python.exe" main.py >> launcher.log 2>&1
set EC=%errorlevel%
echo ===== exit code %EC% at %date% %time% =====>> launcher.log
exit /b %EC%

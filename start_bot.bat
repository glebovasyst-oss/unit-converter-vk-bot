@echo off
setlocal
cd /d "%~dp0"

rem UTF-8 in the console so Russian text and emoji are readable.
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "PYTHON=%~dp0venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo [ERROR] venv\Scripts\python.exe not found.
    echo Create it with: py -3 -m venv venv
    echo Then run: venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

rem Find the bot folder (the one containing main.py) without hardcoding
rem the Cyrillic folder name, so this .bat works in any codepage.
set "BOT_MAIN="
for /d %%D in (VK_*) do if exist "%%D\main.py" if exist "%%D\config.py" set "BOT_MAIN=%%D\main.py"

if not defined BOT_MAIN (
    echo [ERROR] main.py not found in a subfolder.
    pause
    exit /b 1
)

echo Starting VK bot: %BOT_MAIN%
echo Press Ctrl+C to stop.
echo.
"%PYTHON%" "%BOT_MAIN%"

echo.
echo Bot stopped.
pause

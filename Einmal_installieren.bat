@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 install_windows.py
) else (
    python install_windows.py
)
if errorlevel 1 (
    echo Installation fehlgeschlagen. Bitte Python 3.10+ installieren.
    pause
    exit /b 1
)
echo.
echo Fertig. Kuenftige Updates im Programm ueber den Tab Updates installieren.
pause

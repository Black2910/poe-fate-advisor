@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON=py -3"
) else (
    set "PYTHON=python"
)
if not exist ".venv\Scripts\python.exe" (
    echo [PoE Fate Advisor] Ersteinrichtung der Python-Umgebung...
    %PYTHON% -m venv .venv
    if errorlevel 1 goto :failed
)
if not exist ".venv\.dependencies-v13" (
    echo [PoE Fate Advisor] Installiere die notwendigen Bibliotheken...
    ".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
    if errorlevel 1 goto :failed
    echo ok>".venv\.dependencies-v13"
)
".venv\Scripts\python.exe" app.py
if errorlevel 1 goto :failed
exit /b 0
:failed
echo.
echo Start fehlgeschlagen. Bitte Python 3.10+ installieren und README.md lesen.
pause
exit /b 1

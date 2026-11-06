@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv (py -3 -m venv .venv || goto error)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt || goto error
if not exist model\best.pt echo UWAGA: skopiuj model best.pt do folderu model.
start "" http://127.0.0.1:5000
python app.py
pause
goto end
:error
echo Blad instalacji lub uruchamiania. Sprawdz komunikaty powyzej.
pause
:end

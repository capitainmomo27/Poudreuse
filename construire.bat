@echo off
REM Compile Poudreuse.exe sur votre propre PC Windows.
REM Prérequis : Python 3.11 ou plus récent (https://www.python.org, cochez « Add Python to PATH »).
cd /d "%~dp0"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --clean --onefile --windowed --name Poudreuse ^
  --icon poudreuse\ressources\poudreuse.ico ^
  --add-data "poudreuse\ressources;poudreuse\ressources" ^
  main.py
echo.
echo Termine ! Le programme est dans le dossier dist\Poudreuse.exe
pause

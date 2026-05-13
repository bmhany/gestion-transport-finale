@echo off
setlocal
title MyCous - Installation automatique

echo ==============================================
echo  MyCous - Installation automatique
echo ==============================================

cd /d "%~dp0.."

where py >nul 2>nul
if %errorlevel% neq 0 (
  where python >nul 2>nul
  if %errorlevel% neq 0 (
    echo [ERREUR] Python n'est pas installe.
    echo Installez Python 3.11+ puis relancez ce script.
    pause
    exit /b 1
  )
)

if not exist ".venv\Scripts\python.exe" (
  echo [INFO] Creation de l'environnement virtuel...
  py -3 -m venv .venv 2>nul
  if %errorlevel% neq 0 (
    python -m venv .venv
  )
)

echo [INFO] Mise a jour pip...
call .venv\Scripts\python.exe -m pip install --upgrade pip

echo [INFO] Installation des dependances...
call .venv\Scripts\python.exe -m pip install -r requirements.txt

echo [INFO] Application des migrations...
call .venv\Scripts\python.exe manage.py migrate

echo [INFO] Collecte des fichiers statiques...
call .venv\Scripts\python.exe manage.py collectstatic --noinput

echo.
echo [SUCCES] Installation terminee.
echo Lancez ensuite:
echo   - 2_Lancer_Local.bat (usage sur le meme PC)
echo   - 3_Lancer_Reseau_Wifi.bat (partage avec camarades)
echo.
pause

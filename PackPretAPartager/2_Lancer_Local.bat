@echo off
setlocal
title MyCous - Lancement local

cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
  echo [ERREUR] Environnement non installe.
  echo Lancez d'abord 1_Installer.bat
  pause
  exit /b 1
)

echo ==============================================
echo  MyCous lance en local
echo  URL: http://127.0.0.1:8000
echo ==============================================
call .venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000

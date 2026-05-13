@echo off
setlocal
title MyCous - Lancement reseau Wi-Fi

cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
  echo [ERREUR] Environnement non installe.
  echo Lancez d'abord 1_Installer.bat
  pause
  exit /b 1
)

set "LOCAL_IP="
for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 ^| Where-Object { $_.IPAddress -like '192.168.*' -or $_.IPAddress -like '10.*' -or $_.IPAddress -like '172.16.*' -or $_.IPAddress -like '172.17.*' -or $_.IPAddress -like '172.18.*' -or $_.IPAddress -like '172.19.*' -or $_.IPAddress -like '172.2?.*' -or $_.IPAddress -like '172.30.*' -or $_.IPAddress -like '172.31.*' } ^| Select-Object -ExpandProperty IPAddress -First 1)"`) do set "LOCAL_IP=%%i"

echo ==============================================
echo  MyCous partage sur le reseau local
if defined LOCAL_IP (
  echo  Lien a envoyer: http://%LOCAL_IP%:8000
) else (
  echo  Lien a envoyer: http://VOTRE_IP:8000
)
echo ==============================================
echo.
if defined LOCAL_IP (
  echo [INFO] Adresse detectee: %LOCAL_IP%
) else (
  echo [ATTENTION] Impossible de detecter automatiquement votre IP.
  echo [INFO] Relevez-la ici puis remplacez VOTRE_IP dans le lien:
  ipconfig | findstr /R "IPv4"
)
echo.
echo [INFO] Si le pare-feu demande une autorisation, cliquez Autoriser.
echo [INFO] Vos camarades n'ont rien a installer: un navigateur suffit.
echo.
call .venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000

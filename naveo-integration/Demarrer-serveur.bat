@echo off
chcp 65001 >nul
cd /d "%~dp0.."
echo Dossier projet: %CD%
echo Lancement de Django sur http://127.0.0.1:8000/
echo Interface Navéo : http://127.0.0.1:8000/naveo/
echo Fermez cette fenêtre pour arrêter le serveur.
python manage.py runserver
pause

@echo off
REM Met à jour les fichiers .po/.mo dans l'environnement virtuel

cd /d "%~dp0"

REM Active l'environnement virtuel
call venv\Scripts\activate.bat

REM Extrait les nouvelles chaînes traduisibles
python manage.py makemessages -l en -l fr --no-obsolete

REM Compile les .po en .mo
python manage.py compilemessages

pause

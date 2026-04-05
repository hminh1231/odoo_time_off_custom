@echo off
cd /d "%~dp0"
echo Chay Odoo — mo http://localhost:8069 sau khi thay log san sang
venv\Scripts\python.exe odoo-bin -c odoo.conf
pause

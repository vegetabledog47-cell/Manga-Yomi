@echo off
cd /d "%~dp0"
"%~dp0.venv\Scripts\python.exe" "%~dp0manga-yomi\scripts\yomi_pdf.py" %*
if errorlevel 1 pause

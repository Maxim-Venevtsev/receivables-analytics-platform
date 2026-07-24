@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\debt_management_BI\scripts\sync_local_dry_run.ps1"
exit /b %ERRORLEVEL%

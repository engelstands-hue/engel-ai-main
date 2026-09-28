@echo off
title Engel CT 246 Repair Terminal
cd /d "D:\b.WorkSpace\Engel App"
echo Engel CT 246 Repair Terminal
echo Type the Proxmox root password when SSH asks.
echo This window will stay open.
echo.
powershell.exe -NoExit -NoProfile -ExecutionPolicy Bypass -File "D:\b.WorkSpace\Engel App\scripts\Open-EngelCt246RepairTerminal.ps1"
echo.
echo PowerShell exited. Press any key to close this command window.
pause >nul

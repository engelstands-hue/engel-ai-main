@echo off
title Engel CT 246 Persistent Forward Installer
cd /d "D:\b.WorkSpace\Engel App"
echo Engel CT 246 Persistent Forward Installer
echo Type the Proxmox root password when SSH asks.
echo This creates a systemd service for 192.0.2.50:24622 -^> CT 246 SSH.
echo No storage, VM disk, LVM, or Vault changes are performed.
echo.
powershell.exe -NoExit -NoProfile -ExecutionPolicy Bypass -File "D:\b.WorkSpace\Engel App\scripts\Install-EngelCt246PersistentForward.ps1"
echo.
echo Installer window finished. Press any key to close.
pause >nul

@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if exist "D:\EngelControlRoom_build\dist\Start-Conical-ControlRoom.vbs" (
  wscript.exe "D:\EngelControlRoom_build\dist\Start-Conical-ControlRoom.vbs"
  exit /b 0
)
set "ENGEL_CR_DATA=D:\EngelControlRoom_build\dist\data"
set "ENGEL_PYW=%~dp0runtime\python310\pythonw.exe"
if not exist "%ENGEL_PYW%" set "ENGEL_PYW=%~dp0runtime\python310\python.exe"
start "" "%ENGEL_PYW%" "%~dp0run_engel_control_room.py"
exit /b 0

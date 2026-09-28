@echo off
setlocal

set "ENGEL_APP_ROOT=D:\b.WorkSpace\Engel App"
set "ENGEL_EXE=%ENGEL_APP_ROOT%\engel_main\app\src-tauri\target\debug\Engel.exe"
set "CEF_PATH=F:\ENGEL_APP_MEMORY\runtimes\tauri-cef\146.0.9\cef_windows_x86_64"
set "ENGEL_HOME=F:\ENGEL_APP_MEMORY\engel-home"
set "ENGEL_WORKSPACE=F:\ENGEL_APP_MEMORY\engel-home"
set "ENGEL_CEF_CACHE_PATH=F:\ENGEL_APP_MEMORY\engel-home\users\local\cef"
set "OPENHUMAN_CEF_CACHE_PATH=F:\ENGEL_APP_MEMORY\engel-home\users\local\cef"
set "ENGEL_RUNPOD_ROOT=F:\ENGEL_APP_MEMORY\runpod"
set "ENGEL_RUNPOD_API_KEY_FILE=F:\ENGEL_APP_MEMORY\secrets\runpod_api_key.txt"
set "HF_HOME=F:\ENGEL_APP_MEMORY\hf-home"
set "CARGO_HOME=F:\ENGEL_APP_MEMORY\cargo-home"
set "VITE_ENGEL_LOCAL_DESKTOP_BYPASS=true"
set "LOCALAPPDATA=F:\ENGEL_APP_MEMORY\local-appdata"
set "APPDATA=F:\ENGEL_APP_MEMORY\roaming-appdata"
set "TEMP=F:\ENGEL_APP_MEMORY\temp"
set "TMP=F:\ENGEL_APP_MEMORY\temp"
set "PATH=%CEF_PATH%;%PATH%"

for %%D in ("%ENGEL_HOME%" "%ENGEL_CEF_CACHE_PATH%" "%ENGEL_RUNPOD_ROOT%" "%HF_HOME%" "%CARGO_HOME%" "%LOCALAPPDATA%" "%APPDATA%" "%TEMP%") do (
  if not exist "%%~D" mkdir "%%~D"
)

if not exist "%ENGEL_EXE%" (
  echo Engel Rust UI executable was not found:
  echo %ENGEL_EXE%
  pause
  exit /b 1
)

if not exist "%CEF_PATH%\libcef.dll" (
  echo Engel CEF runtime was not found:
  echo %CEF_PATH%\libcef.dll
  pause
  exit /b 1
)

cd /d "%ENGEL_APP_ROOT%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$target='%ENGEL_EXE%'; Get-Process Engel -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $target } | Stop-Process -Force -ErrorAction SilentlyContinue"
start "Engel Rust UI" "%ENGEL_EXE%" %*
endlocal

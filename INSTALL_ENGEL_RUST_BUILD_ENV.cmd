@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ENGEL_RUST_BUILD_ENV.ps1" -Persist
echo.
echo Engel Rust build environment was written to the user environment.
echo Open a new PowerShell window for plain cargo commands to inherit it.

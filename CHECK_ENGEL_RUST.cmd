@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -Command "& '%~dp0ENGEL_RUST_BUILD_ENV.ps1'; cargo check -q --manifest-path '%~dp0engel_main\app\src-tauri\Cargo.toml'; exit $LASTEXITCODE"

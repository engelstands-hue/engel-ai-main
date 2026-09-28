$venvPip = "D:\b.WorkSpace\Engel App\runtime\training-convo-gpu\venv\Scripts\pip.exe"
Write-Output "Fixing numpy in venv..."
& $venvPip install "numpy<2" --force-reinstall 2>&1 | Select-Object -Last 5
Write-Output "Done. Now torch should load."
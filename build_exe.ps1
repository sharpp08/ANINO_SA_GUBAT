<#
.SYNOPSIS
    Builds ANINO SA GUBAT into a standalone Windows executable using PyInstaller.
#>

$ErrorActionPreference = "Stop"

Write-Output "=== BUILDING ANINO SA GUBAT ==="

# 1. Activate venv & check environment
if (!(Test-Path ".venv")) {
    Write-Error ".venv not found!"
    exit 1
}
. .venv\Scripts\Activate.ps1

python --version
pip list

# 2. Build via PyInstaller
Write-Output "Running PyInstaller..."
pyinstaller --noconfirm --clean --onefile --windowed --name ANINO_SA_GUBAT `
    --hidden-import cinematic --hidden-import lore --hidden-import audio_synth --hidden-import asset_generator `
    --hidden-import settings --hidden-import player --hidden-import map_system `
    --hidden-import enemies --hidden-import renderer --collect-all pygame main.py

# 3. Create release folder and copy exe
if (!(Test-Path "release")) {
    New-Item -ItemType Directory -Path "release" | Out-Null
}
Copy-Item "dist\ANINO_SA_GUBAT.exe" "release\ANINO_SA_GUBAT.exe" -Force
Copy-Item "dist\ANINO_SA_GUBAT.exe" "ANINO_SA_GUBAT.exe" -Force

# 4. Cleanup build and spec file
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "ANINO_SA_GUBAT.spec") { Remove-Item -Force "ANINO_SA_GUBAT.spec" }

$exeSize = (Get-Item "release\ANINO_SA_GUBAT.exe").Length / 1MB
Write-Output "=== BUILD SUCCESSFUL ==="
Write-Output "Executable Path: D:\PhyGame\ANINO_SA_GUBAT\release\ANINO_SA_GUBAT.exe"
Write-Output ("Executable Size: {0:N2} MB" -f $exeSize)

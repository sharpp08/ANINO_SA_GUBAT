$ErrorActionPreference = "Stop"
$godotRoot = $PSScriptRoot
$repoRoot = Split-Path $godotRoot -Parent
$sourceAssets = Join-Path $repoRoot "assets"
$targetAssets = Join-Path $godotRoot "assets"

if (-not (Test-Path $sourceAssets)) {
    throw "Original assets folder was not found: $sourceAssets"
}
New-Item -ItemType Directory -Force -Path $targetAssets | Out-Null
foreach ($folder in @("audio", "sprites")) {
    $source = Join-Path $sourceAssets $folder
    $target = Join-Path $targetAssets $folder
    if (Test-Path $source) {
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        & robocopy $source $target /E /COPY:DAT /DCOPY:DAT /R:2 /W:1 /XJ
        if ($LASTEXITCODE -ge 8) {
            throw "Asset copy failed for $folder (robocopy exit $LASTEXITCODE)"
        }
    }
}
Write-Host "Original audio and sprite assets copied into the Godot project." -ForegroundColor Green
Write-Host "Open godot/project.godot and let the editor finish importing resources."

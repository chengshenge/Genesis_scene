param(
    [string]$PythonExecutable = "",
    [string]$GenesisCommit = "8de7e456d10436f9fea908fafad59a01c58aea9c"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$GenesisRoot = Join-Path $RepoRoot ".external\Genesis"
$LuisaRoot = Join-Path $GenesisRoot "genesis\ext\LuisaRender"
$BuildRoot = Join-Path $LuisaRoot "build-win-cuda"

if (-not $PythonExecutable) {
    $PythonExecutable = (Resolve-Path (Join-Path $RepoRoot ".venv\Scripts\python.exe")).Path
}

if (-not (Test-Path (Join-Path $GenesisRoot ".git"))) {
    git clone --recursive https://github.com/Genesis-Embodied-AI/Genesis.git $GenesisRoot
}

git -C $GenesisRoot fetch --all --tags
git -C $GenesisRoot checkout $GenesisCommit
git -C $GenesisRoot submodule update --init --recursive

cmake -S $LuisaRoot -B $BuildRoot -G "Visual Studio 17 2022" -A x64 `
    -DLUISA_COMPUTE_ENABLE_CUDA=ON `
    -DPYTHON_EXECUTABLE="$PythonExecutable"
cmake --build $BuildRoot --config Release --parallel

$LuisaBin = Join-Path $BuildRoot "bin\Release"
$env:GENESIS_SOURCE_ROOT = $GenesisRoot
$env:LUISA_RENDER_BUILD_BIN = $LuisaBin

Write-Host "Genesis source: $GenesisRoot"
Write-Host "LuisaRender bin: $LuisaBin"
Write-Host "Run: python scripts/check_environment.py --strict-raytracer"

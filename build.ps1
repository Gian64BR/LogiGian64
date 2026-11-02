$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $env:PYINSTALLER_CONFIG_DIR = Join-Path $PSScriptRoot 'buildcache'
    python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
    python -m PyInstaller --noconfirm LogiGian64.spec
    if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
} finally {
    Pop-Location
}

param([int]$Port = 8765)
$ErrorActionPreference = "Stop"
$viewerRoot = $PSScriptRoot
$repoRoot = Split-Path $viewerRoot -Parent
$viewerPython = Join-Path $repoRoot ".venv/Scripts/python.exe"
if (-not (Test-Path -LiteralPath $viewerPython)) {
    Write-Host "Repository virtual environment not found. Using Python for recorded/local evidence; Azure Live requires requirements-cloud.txt."
    $viewerPython = (Get-Command python -ErrorAction Stop).Source
}
Write-Host "Viewer Python: $viewerPython"
& $viewerPython (Join-Path $viewerRoot "server.py") --port $Port
exit $LASTEXITCODE

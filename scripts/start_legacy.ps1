# Prefer this checkout's virtual environment.
$ErrorActionPreference = "Stop"
$taskRepo = Split-Path -Parent $PSScriptRoot
$taskPython = Join-Path $taskRepo ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $taskPython)) { $taskPython = "python" }
$env:PYTHONPATH = $taskRepo
Push-Location -LiteralPath $taskRepo
try { & $taskPython -m streamlit run legacy/app.py } finally { Pop-Location }

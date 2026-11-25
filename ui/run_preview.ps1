# P3 preview using official Streamlit theme flags; does not change shared configuration.
param([string]$Python = "python", [int]$Port = 18503)
$ErrorActionPreference = "Stop"
$taskRepo = Split-Path -Parent $PSScriptRoot
$taskVenv = Join-Path $taskRepo ".venv\Scripts\python.exe"
if ($Python -eq "python" -and (Test-Path -LiteralPath $taskVenv)) { $Python = $taskVenv }
Push-Location -LiteralPath $taskRepo
try {
    & $Python -m streamlit run app.py --server.address 127.0.0.1 --server.port $Port `
        --theme.base dark --theme.primaryColor '#00d9ef' --theme.backgroundColor '#071b2a' `
        --theme.secondaryBackgroundColor '#0d293d' --theme.textColor '#f0f6fc'
} finally { Pop-Location }

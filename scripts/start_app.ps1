# 启动 Streamlit 演示系统
$env:PYTHONPATH = Join-Path $PSScriptRoot "..\pylibs" | Resolve-Path
python -m streamlit run (Join-Path $PSScriptRoot "..\app.py")

# Start Pallet Pre-Flight locally (Windows PowerShell). Keep this window open while you use the app.
Set-Location $PSScriptRoot
if (-not (Test-Path .venv)) {
    python -m venv .venv
    .\.venv\Scripts\python -m pip install -r requirements-dev.txt
}
.\.venv\Scripts\streamlit run app.py --server.port 8501

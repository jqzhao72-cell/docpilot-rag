$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendPath = Join-Path $projectRoot "backend"
$frontendPath = Join-Path $projectRoot "frontend"
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Python virtual environment not found: $pythonPath"
}

Start-Process powershell -WorkingDirectory $backendPath -ArgumentList @(
    "-NoExit",
    "-Command",
    "& '$pythonPath' -m uvicorn app.main:app --reload"
)

Start-Process powershell -WorkingDirectory $frontendPath -ArgumentList @(
    "-NoExit",
    "-Command",
    "npm.cmd run dev"
)

Write-Host "DocPilot backend and frontend are starting."
Write-Host "Frontend: http://127.0.0.1:5173"
Write-Host "API docs: http://127.0.0.1:8000/docs"

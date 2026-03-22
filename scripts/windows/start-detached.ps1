$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$pythonw = Join-Path $root '.venv\Scripts\pythonw.exe'
$python = Join-Path $root '.venv\Scripts\python.exe'

if (-not (Test-Path $pythonw)) {
  if (-not (Test-Path $python)) {
    throw "No Python executable found in .venv"
  }
  $pythonw = $python
}

try {
  $health = Invoke-RestMethod -Uri 'http://127.0.0.1:5000/health' -TimeoutSec 2
  if ($health.status -eq 'ok') {
    Write-Host 'Service already running on port 5000.'
    exit 0
  }
} catch {
}

Start-Process -FilePath $pythonw -ArgumentList '-m','apps.api.run' -WorkingDirectory $root -WindowStyle Hidden | Out-Null
Start-Sleep -Seconds 2

try {
  $health = Invoke-RestMethod -Uri 'http://127.0.0.1:5000/health' -TimeoutSec 5
  if ($health.status -eq 'ok') {
    Write-Host 'Service started detached and healthy.'
    exit 0
  }
} catch {
}

throw 'Service launch attempted but health check failed.'

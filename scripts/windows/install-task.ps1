$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $root '.venv\Scripts\python.exe'

if (-not (Test-Path $python)) {
  throw "Python executable not found at $python. Create venv first."
}

$action = New-ScheduledTaskAction -Execute $python -Argument '-m apps.api.run' -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)

try {
  Register-ScheduledTask -TaskName 'LocalTTSService' -Action $action -Trigger $trigger -Settings $settings -Description 'Local TTS API service' -Force | Out-Null
  Start-ScheduledTask -TaskName 'LocalTTSService'
  Write-Host 'Installed and started scheduled task via Register-ScheduledTask: LocalTTSService'
  exit 0
} catch {
  Write-Host 'Register-ScheduledTask failed, falling back to schtasks user-scope install...'
}

$taskCommand = '"' + $python + '" -m apps.api.run'
schtasks.exe /Create /TN LocalTTSService /SC ONLOGON /TR $taskCommand /F | Out-Null
schtasks.exe /Run /TN LocalTTSService | Out-Null
Write-Host 'Installed and started scheduled task via schtasks: LocalTTSService'

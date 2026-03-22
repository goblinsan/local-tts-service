$task = Get-ScheduledTask -TaskName 'LocalTTSService' -ErrorAction SilentlyContinue
if (-not $task) {
  Write-Host 'LocalTTSService task is not installed.'
  exit 1
}
Stop-ScheduledTask -TaskName 'LocalTTSService'
Write-Host 'Stopped LocalTTSService'

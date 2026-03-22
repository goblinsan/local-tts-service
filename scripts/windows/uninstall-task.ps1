$task = Get-ScheduledTask -TaskName 'LocalTTSService' -ErrorAction SilentlyContinue
if (-not $task) {
  Write-Host 'LocalTTSService task is not installed.'
  exit 0
}
try {
  Stop-ScheduledTask -TaskName 'LocalTTSService' -ErrorAction SilentlyContinue
} catch {
}
Unregister-ScheduledTask -TaskName 'LocalTTSService' -Confirm:$false
Write-Host 'Uninstalled LocalTTSService'

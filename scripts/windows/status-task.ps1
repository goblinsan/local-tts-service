try {
  $task = Get-ScheduledTask -TaskName 'LocalTTSService' -ErrorAction Stop
  $info = Get-ScheduledTaskInfo -TaskName 'LocalTTSService'
  $obj = [PSCustomObject]@{
    TaskName = $task.TaskName
    State = $task.State
    LastRunTime = $info.LastRunTime
    LastTaskResult = $info.LastTaskResult
    NextRunTime = $info.NextRunTime
  }
  $obj | Format-List
  exit 0
} catch {
}

$query = schtasks.exe /Query /TN LocalTTSService /FO LIST 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host 'LocalTTSService task is not installed.'
  exit 1
}

$query | Out-Host

$startupDir = [Environment]::GetFolderPath('Startup')
$launcherPath = Join-Path $startupDir 'local-tts-service.cmd'

if (Test-Path $launcherPath) {
  Remove-Item $launcherPath -Force
  Write-Host "Removed startup launcher: $launcherPath"
} else {
  Write-Host 'Startup launcher not present.'
}

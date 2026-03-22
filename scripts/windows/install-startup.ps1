$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$startupDir = [Environment]::GetFolderPath('Startup')
$launcherPath = Join-Path $startupDir 'local-tts-service.cmd'
$scriptPath = Join-Path $root 'scripts\windows\start-detached.ps1'

$cmd = @"
@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$scriptPath"
"@

Set-Content -Path $launcherPath -Value $cmd -Encoding Ascii
Write-Host "Installed startup launcher: $launcherPath"

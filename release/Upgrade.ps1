[CmdletBinding()]
param([string]$GamePath, [string]$BackupId)
$ErrorActionPreference = 'Stop'
if (-not $GamePath) { $GamePath = Read-Host 'Witcher 3 game root (contains bin/x64_dx12)' }
& "$PSScriptRoot/Manage.ps1" -Action 'Upgrade' -GamePath $GamePath -BackupId $BackupId

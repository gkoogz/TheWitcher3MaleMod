[CmdletBinding()]
param(
    [ValidateSet('Install','Upgrade','Uninstall','Rollback')][string]$Action = 'Install',
    [Parameter(Mandatory=$true)][string]$GamePath,
    [string]$BackupId
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2
function Hash([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-','').ToLowerInvariant() }
    finally { $sha.Dispose(); $stream.Dispose() }
}
function ReadJson([string]$Path) { Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json }
function Child([string]$Root, [string]$Relative) {
    if ([string]::IsNullOrWhiteSpace($Relative) -or $Relative -match '(^|[/\\])\.\.?([/\\]|$)' -or $Relative -match '[:*?]' -or [IO.Path]::IsPathRooted($Relative)) { throw "Unsafe relative path: $Relative" }
    $base = [IO.Path]::GetFullPath($Root).TrimEnd('\','/')
    $candidate = [IO.Path]::GetFullPath([IO.Path]::Combine($base, $Relative.Replace('/','\')))
    if (-not $candidate.StartsWith($base + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Path escapes managed root' }
    # Reject junctions/symlinks on every existing ancestor, including the root.
    $cursor = $candidate
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            $item = Get-Item -LiteralPath $cursor -Force
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Reparse point is not supported: $cursor" }
        }
        $parent = [IO.Directory]::GetParent($cursor)
        if (-not $parent) { break }
        $cursor = $parent.FullName
    }
    $candidate
}
function WriteJson([string]$Path, $Value) {
    $pending = $Path + '.pending'
    $Value | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $pending -Encoding UTF8
    Move-Item -LiteralPath $pending -Destination $Path -Force
}
function CopyVerified([string]$Source, [string]$Target, [string]$Expected) {
    if (-not (Test-Path -LiteralPath $Source -PathType Leaf) -or (Hash $Source) -ne $Expected) { throw "Source hash mismatch: $Source" }
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($Target)) | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Target -Force
    if ((Hash $Target) -ne $Expected) { throw "Copied hash mismatch: $Target" }
}
function CheckRows([string]$Root, $Rows) {
    $seen = @{}
    foreach ($row in @($Rows)) {
        if ($seen.ContainsKey($row.path) -or $row.sha256 -notmatch '^[0-9a-f]{64}$') { throw 'Invalid or duplicate manifest row' }
        $seen[$row.path] = $true
        $target = Child $Root $row.path
        if (-not (Test-Path -LiteralPath $target -PathType Leaf) -or (Hash $target) -ne $row.sha256) { throw "Managed file changed or missing; preserve it: $($row.path)" }
    }
}
$game = [IO.Path]::GetFullPath($GamePath).TrimEnd('\','/')
$exe = Child $game 'bin/x64_dx12/witcher3.exe'
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw 'Choose the Witcher 3 game root containing bin/x64_dx12/witcher3.exe' }
if (Get-Process -Name witcher3 -ErrorAction SilentlyContinue) { throw 'Close Witcher 3 before changing its files' }
$package = $PSScriptRoot
$manifest = ReadJson (Child $package 'manifest.json')
if ($manifest.schema -ne 1) { throw 'Unsupported package schema' }
CheckRows (Child $package 'payload') $manifest.files
CheckRows $package $manifest.packageFiles
$allowed = @{}
foreach ($row in @($manifest.files)) { $allowed[$row.path] = $true }
function CheckManagedPaths($Rows) {
    foreach ($row in @($Rows)) { if (-not $allowed.ContainsKey($row.path)) { throw "Unmanaged receipt path: $($row.path)" } }
}
$state = Child $game '.malemod-installation'
$currentPath = Child $state 'current.json'
$previous = $null
if (Test-Path -LiteralPath $currentPath -PathType Leaf) {
    $previous = ReadJson $currentPath
    if ($previous.schema -ne 1 -or $previous.game -ne $game) { throw 'Installation receipt belongs to another game or schema' }
    CheckManagedPaths $previous.files
    CheckRows $game $previous.files
} else {
    $existing = @($manifest.files | Where-Object { Test-Path -LiteralPath (Child $game $_.path) })
    if ($existing.Count) {
        foreach ($supported in @($manifest.supportedManualInstalls)) {
            if (@($supported.files).Count -ne $existing.Count) { continue }
            $match = $true
            foreach ($row in @($supported.files)) { $target = Child $game $row.path; if (-not (Test-Path -LiteralPath $target -PathType Leaf) -or (Hash $target) -ne $row.sha256) { $match = $false; break } }
            if ($match) { $previous = [pscustomobject]@{schema=1;game=$game;version=$supported.version;files=@($supported.files);backup=$null}; break }
        }
        if (-not $previous) { throw 'Unknown existing proxy/mod files: installation refused without overwriting them' }
    }
}
foreach ($row in @($manifest.files)) {
    $target = Child $game $row.path
    $longest = Child $state ('backups/' + ('0' * 32) + '/files/' + $row.path)
    if ($target.Length -ge 248 -or $longest.Length -ge 248) { throw 'Game path is too long for Windows PowerShell; use a shorter game root' }
}
$old = @{}
if ($previous) { foreach ($row in @($previous.files)) { $old[$row.path] = $row } }
$next = $null
$sourceRoot = Child $package 'payload'
switch ($Action) {
    'Upgrade' { if (-not $previous) { throw 'No supported existing installation to upgrade' } }
    'Uninstall' { if (-not $previous) { throw 'No managed installation to uninstall' } }
    'Rollback' {
        if (-not $BackupId) { if ($previous -and $previous.backup) { $BackupId = $previous.backup } else { throw 'Pass -BackupId from a prior operation' } }
        if ($BackupId -notmatch '^[0-9a-f]{32}$') { throw 'Invalid backup ID' }
        $sourceRoot = Child $state ('backups/' + $BackupId + '/files')
        $snapshot = ReadJson (Child $state ('backups/' + $BackupId + '/snapshot.json'))
        if ($snapshot.schema -ne 1 -or $snapshot.game -ne $game) { throw 'Backup belongs to another game or schema' }
        $next = $snapshot.previous
        if ($next) { CheckManagedPaths $next.files; CheckRows $sourceRoot $next.files }
    }
}
if ($Action -eq 'Install' -or $Action -eq 'Upgrade') {
    $next = [pscustomobject]@{schema=1;game=$game;version=$manifest.version;files=@($manifest.files);backup=$null}
}
$new = @{}
if ($next) { foreach ($row in @($next.files)) {
    if ($new.ContainsKey($row.path)) { throw 'Duplicate restore path' }
    $target = Child $game $row.path
    if ((Test-Path -LiteralPath $target) -and -not $old.ContainsKey($row.path)) { throw "Unmanaged restore target: $($row.path)" }
    $new[$row.path] = $row
} }
# The payload is verified before mutation. Backups are complete before writes.
[IO.Directory]::CreateDirectory($state) | Out-Null
$lockPath = Child $state 'operation.lock'
$operationLock = [IO.File]::Open($lockPath, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
# Recheck after taking the lock; another installer may have finished since validation.
try {
if ($previous) { CheckRows $game $previous.files }
$id = [Guid]::NewGuid().ToString('N')
$backup = Child $state ('backups/' + $id)
[IO.Directory]::CreateDirectory($backup) | Out-Null
foreach ($row in $old.Values) { CopyVerified (Child $game $row.path) (Child $backup ('files/' + $row.path)) $row.sha256 }
$savedReceipt = Test-Path -LiteralPath $currentPath -PathType Leaf
if ($savedReceipt) { Copy-Item -LiteralPath $currentPath -Destination (Child $backup 'current-before.json') }
WriteJson (Child $backup 'snapshot.json') ([pscustomobject]@{schema=1;game=$game;previous=$previous;action=$Action})
$changed = [Collections.Generic.List[string]]::new()
try {
    foreach ($row in $new.Values) { $changed.Add($row.path); CopyVerified (Child $sourceRoot $row.path) (Child $game $row.path) $row.sha256 }
    foreach ($relative in $old.Keys) { if (-not $new.ContainsKey($relative)) { $changed.Add($relative); Remove-Item -LiteralPath (Child $game $relative) } }
    if ($next) { $next.backup = $id; WriteJson $currentPath $next }
    elseif (Test-Path -LiteralPath $currentPath) { Remove-Item -LiteralPath $currentPath }
} catch {
    $failure = $_
    foreach ($relative in $changed) {
        $target = Child $game $relative
        if ($old.ContainsKey($relative)) { CopyVerified (Child $backup ('files/' + $relative)) $target $old[$relative].sha256 }
        elseif (Test-Path -LiteralPath $target -PathType Leaf) { Remove-Item -LiteralPath $target }
    }
    if ($savedReceipt) { Copy-Item -LiteralPath (Child $backup 'current-before.json') -Destination $currentPath -Force }
    elseif (Test-Path -LiteralPath $currentPath) { Remove-Item -LiteralPath $currentPath }
    throw $failure
}
Write-Output "$Action complete. Preferences and game settings preserved. Rollback ID: $id"
} finally { $operationLock.Dispose() }

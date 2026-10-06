param(
    [Parameter(Mandatory=$true)][string]$Package,
    [Parameter(Mandatory=$true)][string]$Acceptance,
    [switch]$Preview,
    [string]$Python = 'python'
)
$ErrorActionPreference='Stop'
$adapterRoot=Split-Path -Parent $PSScriptRoot
$pythonExe=(& $Python -c 'import sys; print(sys.executable)').Trim()
if ($LASTEXITCODE -ne 0) {throw 'A Python 3.10 or newer interpreter is required'}
$pythonWindowless=Join-Path (Split-Path -Parent $pythonExe) 'pythonw.exe'
$packagePath=(Resolve-Path -LiteralPath $Package).Path
$acceptancePath=(Resolve-Path -LiteralPath $Acceptance).Path
$launcherPath=Join-Path $PSScriptRoot 'play_iteration_platform.py'
$launchFlags=@()
if ($Preview) {$launchFlags+= '--preview'}
& $pythonExe $launcherPath --package $packagePath --acceptance $acceptancePath --check @launchFlags
if ($LASTEXITCODE -ne 0) {throw 'Sandbox launch preflight failed'}
if (!(Test-Path -LiteralPath $pythonWindowless)) {throw 'Windowless Python is missing'}
$desktopPath=[Environment]::GetFolderPath('Desktop')
$shortcutPath=Join-Path $desktopPath 'Witcher 3 Grey Sandbox.lnk'
$shellObject=New-Object -ComObject WScript.Shell
$link=$shellObject.CreateShortcut($shortcutPath)
$link.TargetPath=$pythonWindowless
$link.WorkingDirectory=$adapterRoot
$link.Arguments='"'+$launcherPath+'" --package "'+$packagePath+'" --acceptance "'+$acceptancePath+'"'
if ($Preview) {$link.Arguments+=' --preview'}
$link.Description='Grey in-engine Geralt studio. Uses existing mod; preserves saves and removes temporary studio files on exit.'
if ($Preview) {$link.Description='Playable grey Geralt studio preview. Known native motion floor artifact; stock world remains loaded. Saves and existing mod preserved.'}
$gameExecutable=(& $pythonExe -c "import sys; sys.path.insert(0,sys.argv[1]); from mod import settings; print(settings()['game']/'bin/x64_dx12/witcher3.exe')" (Join-Path $adapterRoot 'tools')).Trim()
if ($LASTEXITCODE -ne 0) {throw 'Configured game path could not be resolved'}
$link.IconLocation=$gameExecutable+',0'
$link.Save()
$readback=$shellObject.CreateShortcut($shortcutPath)
if ($readback.TargetPath -ne $pythonWindowless -or $readback.Arguments -ne $link.Arguments) {throw 'Shortcut readback differs'}
Write-Output $shortcutPath

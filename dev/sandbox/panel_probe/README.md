# Owned panel SDK fixture

This fixture runs the adapter's actual GDI overlay and navigation code in the
existing noninteractive launcher. It is a window/input/paint diagnostic, not
Witcher gameplay, anatomy acceptance or a replacement runtime installation.
No game, ordinary save, settings or audio files are opened. The source belongs
in Git; this directory is excluded from release/source archives.

Build with x64 Windows SDK and an explicitly identified clean Base header
checkout containing the shared menu theme. The header revision is recorded for
this diagnostic; it does not change the adapter's installed dependency pin.

```powershell
cmake -S dev/sandbox/panel_probe -B build/panel-probe -A x64 `
  -DMALEMOD_BASE_PATH=D:/Dev/MaleModBase `
  -DMALEMOD_BASE_REVISION=<exact-clean-commit>
cmake --build build/panel-probe --config Release
$probeRoot = (Resolve-Path build/panel-probe).Path
$probeToken = [Guid]::NewGuid().ToString('N')
$probeOutput = Join-Path $probeRoot "panel-probe-$probeToken"
New-Item -ItemType Directory -Path $probeOutput | Out-Null
$env:MALEMOD_PANEL_PROBE='1'
$env:MALEMOD_PANEL_PROBE_TOKEN=$probeToken
$env:MALEMOD_PANEL_PROBE_DIR=$probeOutput
try {
  & "$probeRoot/Release/launch_sealed.exe" `
    "$probeRoot/Release/overlay_panel_probe_test.exe" 1280 720
} finally {
  Remove-Item Env:MALEMOD_PANEL_PROBE,Env:MALEMOD_PANEL_PROBE_TOKEN,Env:MALEMOD_PANEL_PROBE_DIR
}
```

Repeat in a fresh token/output directory at 2560x1440. The launcher records the
exact PID/creation time, noninteractive station, audio cleanup and child exit.
Require the child's PASS and exitCode 0; launcher exit 0 alone is insufficient.
The fixture creates its own parent HWND, adjusts the real panel's controls,
captures WM_PRINTCLIENT output and closes its overlay thread/parent gracefully.

The real adapter transport requires the default-off CMake option
MALEMOD_ENABLE_OWNED_PANEL_PROBE, explicit environment opt-in/token/output path,
verified sealed station identity and an authorized same-process game parent.
Each command must match process ID, creation time, token and increasing revision.
No engine input is posted. A private probe session never polls host physical
keys, including after its evidence transport is disabled. Normal builds compile
the production stub without the development transport. The rich implementation
lives only in this excluded directory.

Before a Witcher native test, build from a clean committed source and tested
Base pin, stage only the owned clone, retain the previous accepted DLL/rollback,
and record package/runtime identities. Use the adapter's normal sealed session
cleanup. SDK fixture success does not certify game visibility, engine input
isolation, focus behavior, body attachment, garments, LODs or campaign transitions.

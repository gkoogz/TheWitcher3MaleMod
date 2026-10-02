# Live motion checks

## Current fixed-default phase

Sliders, tuning menus and owned hotkeys are removed. Never use or rebind F12.
The user approved .26 geometry but rejected sideways/wavy motion and low heft.
The .27 candidate corrects pelvis-relative dynamics while retaining that shape.
Compare steady straight travel, starts/stops, direction reversals and turns;
look for unnecessary lateral offset or waves, natural lag that settles, and
thigh clearance. Include idle and uneven frame pacing in this comparison.
The current default candidate uses Wolverine state 2/all-50 geometry and its
12-node mechanical guide at the measured character scale. Restart the game,
load the usual save and compare the relaxed size and shape while idle. Then
walk, run and turn; check the collar, thigh clearance, lobe movement and frame
pacing. Save/reload and outfit transitions remain separate checks. The first
physics attempt was reported moving in game but did not match these defaults.
Native build proof does not confirm the new visual match. Consult HANDOFF.md
and local/installation.json for the exact installed candidate and rollback.

## Historical slider test (superseded)

Checkpoint: September 30, 2026. Version `0.4.4-native-sliders-test`, installed
from `publish/20260930-183505-9d2838`. Inspect `local/installation.json` before changing files.
This is not a completed 1.0 or Wolverine runtime parity.

0.4.2 restored the shape per user feedback. 0.4.3 produced toasts but no visible
menu. 0.4.4 removes that debug HUD and uses the native pause-menu Scaleform slider
controls. The cooked mesh, dynamic rig, entity and caches remain unchanged.

## User test

1. Restart Witcher 3, load a save and equip/remove trousers if needed.
2. Press **F6**, then select **MaleMod - motion controls** in the native menu.
3. Check the **Gravity**, **Momentum retention**, and **Simulation speed** sliders.
   Use the game's normal mouse/controller controls. Historical arrow/F8 tuning
   handlers are no longer used. There should be no recurring MaleMod toast.
4. Change a value slightly, press **Escape** to return to gameplay, and observe
   the motion. This native menu pauses gameplay; it is not an unpaused overlay.
5. Reopen the menu and reload a save to check persistence. Report menu rendering,
   actual tuning effects and shape stability separately; send errors/screenshots.

Safe authored reference values: gravity 0.15, momentum retention 0.65, speed 0.30.
Ranges remain 0-2, 0-1 and 0.05-2 respectively; they are native backend values.
No live size slider or anatomy deformation bridge is implemented by this UI.
The full shared control catalog, corner overlay, calibrated contacts and measured
performance remain unfinished. Animation sequences, fluid and audio are deferred.

## Build and deployment

From this repository with the exact Base pin and local native prerequisites:

```powershell
python tools/build_native_converter.py
python tools/probe_runtime.py
python tools/build_motion_release.py
python tools/verify_motion_package.py
python tools/deploy_motion.py install
```

For this script-only patch (serialized fields must remain unchanged):

```powershell
python tools/build_motion_script_patch.py --source publish/20260930-180412-505185 --version 0.4.4-native-sliders-test
python tools/verify_motion_package.py
python tools/deploy_motion.py install
```

The current verified cage can be reused without rerunning its authoring/import
steps. Changed Base/profile/source geometry requires rebuilding the cage. See
`WCC-SCRIPTED-COOK.md` for the custom-class build fix. Ordinary `tools/mod.py
build` intentionally remains the static 0.3 baseline; it does not build this test.

## Rollback

Close the game and run:

```powershell
python tools/deploy_motion.py revert
```

This archives the managed motion test, restores the previously receipt-verified
static build, and removes only this mod's input lines. The static backup is
`local/uninstalled/modMaleMod-1291bcd1ecb4`. Local receipts and input backups are
ignored and must not be committed. The installer refuses a running game or
conflicting hotkeys and does not overwrite unrelated input actions.

## Hub/spoke adoption

Base still owns the reference anatomy, donor fields, cage authoring and shared
18-control contract. This pass adds REDengine-specific compilation/cooking,
native resource checks, input/HUD and deployment only. No Base code was copied
into an independently maintained adapter. Wolverine can adopt Base's existing
motion-binding verification for future rig exports while retaining its current
solver. The WCC session workaround is specific to REDengine; other spokes need
their own native output and runtime checks.

Next: obtain the installed test's game observations, then implement independent
bone/graph or morph outputs for shared dimensions. Keep the waist fixed unless
both body resources are driven from the same Base boundary bindings. Do not
scale the whole lower-body component or claim a stored slider is deformation.

## Native calibration correction

The original 0.12 tip envelope exceeded several 0.0375–0.0662 native-unit
segments. The revised envelope is at most 0.015, each limit below half the
shortest shaft segment; stock body joints and the root remain pinned. Thirteen
links preserve adjacent and next-neighbor rest distances. Shake and wind are
explicitly zero. Gravity defaults to 0.15, velocity retention to 0.65, and speed
to 0.3. The native field named `dampening` multiplies velocity, so larger values
retain more motion. These are conservative authored engine settings, not a
validated anatomical material model or observed stability claim.

The pose envelope and links are validated against the measured native cage.
Mesh geometry, original body boundaries and skin weights were not changed by
this correction. A future native calibration must not silently change shared
Wolverine parameter meaning.

## Rest-frame and input repair, 0.4.2

The native solver aims each single-child joint along its positive X axis. The
old identity rest frames differed by approximately 88-92 degrees, so native
evaluation could rotate the skin before any secondary displacement. Joint
frames and inverse skin binds are now rebuilt together. Official FBX export
checks both LODs, named bones, weights, seams and the aligned axes. This is an
offline/native consistency check; stable gameplay still needs observation.

F6 registration now wraps `CPlayerInput.Initialize`, following the installed
stock input lifecycle and CDPR's [annotation documentation](https://cdprojektred.atlassian.net/wiki/spaces/W3REDkit/pages/36241598).
No stock player script is copied or replaced. Console entry points call normal
helper functions, since exec-only functions cannot be called from scripts.
If no controller is found, F6 displays a diagnostic rather than silently failing.

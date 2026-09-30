# Installed native motion test

Checkpoint: September 30, 2026. Version `0.4.2-rest-frame-input-test` is installed
locally from `publish/20260930-174655-f7a8ff`. This is not completed 1.0 or
Wolverine runtime parity. Check `local/installation.json` before changing files.

0.4.0 loaded and produced motion, but the user reported severe undulation
and an unresponsive F6 key. It is a failed gameplay test, not a working release.
0.4.1 also failed gameplay testing. 0.4.2 aligns native joint frames and skin
binds, and registers F6 at player-input initialization. The component remains
the tuning backend; missing controllers now produce a diagnostic dialog. `provenance/motion-release.json` tracks it.

## User test

1. Restart Witcher 3 and load a save. If script compilation fails, capture the
   error before doing anything else.
2. Equip and remove trousers to recreate the bare lower-body item.
3. Look for **MaleMod motion controls ready: F6**. Walk, turn, stop, and
   confirm secondary motion without body/seam distortion.
4. Press **F6**. Use **Up/Down** to select gravity, momentum retention or simulation speed;
   **Left/Right** to adjust. **F8** resets tuning and requests a native simulation
   reset. **F6** closes the panel and requests saving user settings.
5. Check equipping trousers, loading a save, and reopening the panel. Record
   HUD visibility, tuning effect and persistence separately.

The panel uses the stock `DebugTextModule` positioned in a corner, falling back
to native visual-debug bars if that module is unavailable or already occupied.
The component initializes on attachment, with a bounded five-second startup
retry. It stops ticking when the panel is closed; display refresh is capped
at 10 Hz while open. Numerical simulation uses the
native small rig, not a per-vertex script loop. Actual FPS remains unmeasured.

For an already enabled console, `MaleModPhysicsStatus()` reports the active
controller/constraint, and `MaleModMenu()` opens its panel. The installer does
not enable the console. These diagnostics do not establish motion by themselves.

## Verified versus pending

Verified: original two-LOD seam/weight/native import checks; script compilation;
custom-class native cook; the controller handle and component reference the
same constraint in the native dump; mesh skinning attachment; four cooked
resources/buffers survive native pack/unpack byte-for-byte; installed file hashes;
26 adapter tests; Base source/provenance verification.

Pending for 0.4.2: observed game startup/motion/HUD, tuning response, preference persistence,
contacts, equipment/load transitions and performance. Live size, the full 18
Wolverine controls, official settings-menu integration, animation sequences,
fluid and audio are not implemented in this package. The three controls are
REDengine parameters, not mapped substitutes for the shared Wolverine controls.

## Build and deployment

From this repository with the exact Base pin and local native prerequisites:

```powershell
python tools/build_native_converter.py
python tools/probe_runtime.py
python tools/build_motion_release.py
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

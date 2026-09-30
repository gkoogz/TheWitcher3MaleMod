# Native motion candidate: not installed

> Updated checkpoint: `LIVE-MOTION-TEST.md` and `WCC-SCRIPTED-COOK.md` supersede
> the custom-class cooking failure described below. The 0.4 motion/menu test is
> installed; native binding is verified and gameplay feedback remains pending.
> Earlier probe results below are historical, not the current installation.

Run `python tools/probe_runtime.py` after building the converter described in
`NATIVE-CONVERTER.md`. The probe creates a fresh ignored job, prepares a cage,
imports/exports the mesh through official REDkit, checks both LODs, compiles the
menu script and cooks the native resources. A separate custom-class cook checks
the unresolved binding. Its failure is recorded; it is not a successful runtime
gate and cannot enter the normal package. Results: `build/motion/latest.json`.

## Base / adapter boundary

Base owns `motion_binding.py`: source donor-field transfer, cage centres,
partitioning and seam fade. It preserves the source bank and support lineage.
This is a native-cage approximation, not parity with Wolverine's full solver.
The adapter owns Geralt calibration, FBX/native formats, observed bone mapping,
authored native joint names, dynamic-resource tuning and WitcherScript/HUD.

There are eight authored shaft joints and two lobe joints. `mm_shaft_00` is
pinned; the remaining joints are native dynamic candidates. Both LODs retain
their original 13 mesh influences plus those 10 new joints. The dynamic rig
preserves all 94 observed stock skeleton joints with zero motion distance.
Root seam aliases receive identical weights and the stock body is unchanged.

Geralt calibration compares all 13 native skin bind matrices. Native skeleton
translations multiply by 100 to match the raw FBX frame. Maximum measured
translation discrepancy is about 5.39e-5 FBX units. The stock foot rotation
differs by 1.407e-4 between the mesh bind and `man_base` rig; retain both originals.
New cluster inverse binds must match the authored world rest frames; cloning
the pelvis's inverse bind is invalid even when WCC repairs it on import.

## Verification and remaining work

- Native mesh round-trip: all 23 bones retained in both LODs; maximum position
  error 1.261e-5, bind error 1.526e-5, weight error 2.981e-8. Graft seam position
  and weight discrepancies are zero.
- Native resource cook: stock-class entity, dynamic rig and mesh succeed.
- Script compilation: the candidate F6 panel, arrow navigation and F8 reset
  compile. Only native gravity, damping and simulation-speed tuning are coded.
- Custom script-item cooking fails. The runtime handle has not been verified;
  the panel is not installed, and no hotkeys or user settings were changed.
- Live size, separate shaft/lobe tuning, contact calibration, preference saving,
  official settings menu, in-game HUD visibility, motion and FPS remain pending.

The panel uses no timer when closed; its candidate display refresh is 10 Hz.
Simulation is delegated to the native small rig, with no per-vertex script loop.
These are implementation choices, not measured in-game performance results.
Animations, fluids and audio remain deferred.

## Next checkpoint

Resolve native custom-class/handle serialization or establish another supported
constraint-access path. Do not weaken the native failure gate, silently bypass
the custom-class cook, or install an unverified entity over the working build.
Then wire the shared control contract to verified dimension/deformation outputs;
the three native tuning controls are not Wolverine's full 18-control system.
Finally package, deploy with rollback and record observed motion/menu results.

Wolverine backport: adopt Base's donor-field/cage verification for future native
rig exports while retaining its current full solver. No Wolverine files or game
installation were changed. Every future spoke can consume the same Base module
and must supply its own observed native mapping and verification.

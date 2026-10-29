# Wolverine-parity rebuild

The user requests the same anatomy and behavior as Wolverine, with only the
small pelvic fit changes Geralt requires. This replaces the entire v1 repair
direction. The grey test room is retained.

V2 is installed and accepted in the actual installed game (October 28). The
original Wolverine anatomy and numerical worker use the stock bare Geralt body
with a measured small pelvic fit. The original jockstrap, 21-row menu, sliders,
controls, teaching sequence, throb, fluids/deposits and private audio are present.
Only Naked and Jockstrap are exposed; Witcher outfit fitting remains later work.

The source skin blend, body/garment pose timing and stock LOD1 waist join passed
native front/side/oblique review. Production and LOD1 each passed 90 views; the
full feature run, six-case performance comparison, ordinary-save campaign
save/load, and actual installed grey-room movement/views all passed their gates.
The default grey-room launcher now uses this installed v2. F6 opens the menu;
arrows adjust controls, Shift accelerates adjustments, with source F8/F9/J and
mouse controls retained. See `../docs/HANDOFF.md` for exact evidence and rollback.

Physics services every visible SDK update. Fine surface refresh retains the
original Wolverine cadence (every update bare; alternate updates in jockstrap).
Absolute FPS equivalence across the two engines is not established. Geralt's
native idle motion is retained; Wolverine FaceFX/head overlays are not retargeted.

The running waistband correction remains installed and verified in the actual
game. The October 28 repair additionally matches skin reflectance/color to the
body, corrects thigh donor selection and removes pale front atlas-gap bands.
Original anatomy, numerical physics, garment geometry and controls remain exact.
Fresh production/LOD1 matrices, complete features, motion/GPU pose, performance,
campaign and actual installed-room checks passed. See
`docs/VISUAL-REPAIR-20261028.md` for exact evidence and rollback. Actual installed
walking/running/sprinting/turning/stopping views passed, followed by the normal
grey-room launch check. See `docs/RIGID-CARRIER-FRAME.md` for the measured cause.
The pre-fix version is preserved as GitHub release `v0.6.0` and as a complete
private 74-file local restore point; the release excludes private assets/audio.

## Accepted source integration

The installed source integrates the canonical anatomy/physics worker,
accepted Meridian jockstrap, complete gameplay menu, throb, 20-second teaching
sequence, source fluid/deposits, cue audio, and idle-chatter pool. Only Naked and
Jockstrap are exposed. Wolverine's other outfits remain excluded by request.

The native input fence covers the observed executable keyboard imports, including
J journal suppression while anatomy is visible. Fake-path and sealed-panel checks
pass; actual native F6/F8/F9/J, all 21 rows, Shift and journal-message isolation
also pass in the closed combined run. See `docs/INPUT-FENCE.md` and
`build/menu-port/input-fence-evidence.json`.

The menu now follows the original 21-row layout after removing Top, including
F6, arrows/Shift, J, F8 and F9. Animated readouts use effective source controls;
adjustment and persistence retain the stored baseline. Version 3 preferences save
throb and idle chatter and still read version 2 preferences.

The actual GDI panel passed owned noninteractive-window tests at 1280x720 and
2560x1440, including native paint captures and all listed shortcuts. Production
fluid draw tests passed WARP and AMD hardware, including separate clear/opaque
receiver triangles, all vertex streams, frame coherence and upload fences.
Retained clinical material carriers were officially unbundled and their actual
CR2W CRCs, graph/texture metadata, quantization and 22 GPU fingerprints checked.
These are adapter/window/GPU fixtures, not final Witcher gameplay acceptance.
Evidence: `build/menu-port/implementation-evidence.json`; carrier receipt:
`build/materials/clinical-adoption-01/clinical-carrier-binding.json`.

Idle chatter now observes Geralt's real native idle-bridge start; the official
native-aware script compiler passes. It retains the engine's idle eligibility,
30-second cooldown and native Geralt motion. Wolverine's 19 custom neck/head
quaternion overlays and UE3 FaceFX are not retargeted; this is an explicit engine
adaptation, not identical facial animation. Actual autonomous in-game playback passed the closed combined feature run.

Final runtime SHA-256:
`8eb7ea3638ef2a20503d52427783dcb1106edad6937e5dc7a754c2154ee40a66`.
Installed inventory contains 74 exact files; rollback preserves the previous
installation. Installation, native acceptance, and performance evidence remain
separate records rather than an assertion of identical engine frame rates.

## Inputs

`geralt-base.json` pins untouched native dry bare pelvis/legs, torso, hands, feet
and the bare legs entity. `build/geralt-base/manifest.json` records fresh official
exports, LODs, skin bones, topology and source/output hashes. FBX and material XML
stay local. No v1 generated anatomy is an input.

`wolverine.lock.json` pins canonical Wolverine source, its exact Base include
dependency and the new Base reference harness. The installed DLL hash is recorded
separately; the reference does not claim to reproduce that DLL. The harness
includes canonical source directly without copying/editing numerical expressions.
It seeds the authored source body tables without gameplay captures, host input,
graphics device or game launch. It uses x86 MSVC /O2 /fp:precise. This reference
executable is not the future Witcher runtime architecture.

`build/wolverine-reference/manifest.json` records reset controls in all three
mechanical states, both source body resources and complete anatomy/indices.
Offline CPU measurements are separate from native frame times.

## Required behavior

1. Keep Wolverine's coarse motion cage, final surface construction, morphology,
   state/control mapping, relaxed defaults, topology and prepared-shape reuse.
   Do not substitute v1 modular reconstruction.
2. Keep its solver, constants, constraints, fixed-step budget, collisions,
   independent suspended motion and contact/reaction paths. Geralt pose, thigh
   contacts and world units require observed calibrated adapter inputs.
3. Keep its smooth pelvic recruitment and body/anatomy coupling. Fit Geralt
   locally while preserving his outer skin and native torso/leg joins. Measure
   corrections; do not silently widen the pelvis or replace the blend law.
4. Service physics and current surface every visible active frame with the same
   fixed-step accumulation semantics. Frame service and solver substeps are
   separate counters. Lower-frequency publication, skipped surface evaluation,
   stale poses or interpolation do not establish parity.
5. Adopt the actual accepted canonical Meridian jockstrap: sewn-boundary fitted
   pouch, waistband, straps, source support/contact construction and complete
   underlying anatomy. Its current accepted source has clothDynamics=0. Do not
   silently substitute the unfinished persistent-cloth experiment or describe
   the accepted fitted construction as persistent simulation.
6. Keep transferable controls, clinical/ambient and fluid behavior in scope.
   Character assets and engine/graphics bindings remain adapter-specific. Older
   v1 feature deferrals do not authorize silently omitting v2 parity.

## Earlier native checkpoint (before full feature integration)

The following checkpoint is historical. Use the current source status above for
feature coverage; final combined native acceptance remains pending.

The actual 17,528-vertex / 35,000-triangle source anatomy is fitted at scale1 to
stock dry bare Geralt. Source geometry is unchanged; existing Geralt vertices
move at most3.60mm, and new seam samples at most3.97mm. Official import/cook and
round-trip topology/position checks pass for both LODs. Native appearance is
still a development candidate: the Geralt skin atlas is provisional, and full
attachment coverage has not passed.

The generated Base closure executes the exact canonical x86 numerical code in a
synchronous worker. The changing120-frame control/state/force/contact trace
matches direct canonical-source guide samples and final whole surfaces with
zero position difference. Every active native OnTick requests and completes one
physics and surface service; no lower-frequency publication or interpolation is
used. Native Geralt pose/contacts feed the pinned canonical motion filter.

The accepted4279-vertex/8368-triangle Meridian construction is live in the room.
Only its target body bindings and native material/render transport are adapted.
Geralt's coarser skin uses a smooth animated target frame for trim, with measured
shell clearance corrections up to5.93mm; source anatomy and solver are unchanged.
Current rest-only trim probes pass. Native animated fit remains under review.

No v2 runtime is installed. Native frame-cost parity against Wolverine is NOT
proved: observed callbacks remain about40ms, with roughly4ms spent converting
the complete source surface to Geralt. Do not call the exact source trace a
gameplay FPS comparison. Controls UI, clinical/fluid transport, clean standalone
v2 packaging and the full attachment/campaign gates remain unfinished. Private
room testing currently retains generic legacy bootstrap scripts.

Compare paired deterministic controls/motion/contact traces against canonical
output, including complete anatomy/body surface, topology/UVs, guide and lobe
motion, forces, reset, pause/resume and combined extremes. Then fit measured
Geralt contacts and validate both body resources and every supported LOD.

Use front/side/oblique native room views and matched naked/jockstrap movement
workloads in both games. Record frame service, simulation age, solver/surface/
cloth CPU distributions, fallback behavior and native frame times. Do not call
offline CPU timings equal gameplay performance or reduce features to hit a
number. Complete campaign transitions and cleanup before installation review.

## Recovery

Both repos retain `archive/witcher-v1-20261024`. Read a file with
`git show archive/witcher-v1-20261024:<path>` without changing active development.
Exact commits and source inventories are in `../provenance/v1-archive.json`.
Old private/generated files are frozen in Work/witcher; new output is in
Work/witcher-v2. No source ZIP or full-game backup was created.

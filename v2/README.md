# Wolverine-parity rebuild

The user requests the same anatomy and behavior as Wolverine, with only the
small pelvic fit changes Geralt requires. This replaces the entire v1 repair
direction. The grey test room is retained.

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
5. Adopt the accepted canonical jockstrap, including sewn-boundary pouch,
   waistband, straps, persistent garment state, contact/support, materials and
   complete underlying anatomy. Do not revive the rejected cloth experiments.
6. Keep transferable controls, clinical/ambient and fluid behavior in scope.
   Character assets and engine/graphics bindings remain adapter-specific. Older
   v1 feature deferrals do not authorize silently omitting v2 parity.

## Pending evidence

No v2 Geralt graft, native runtime, garment integration or installation exists
yet. Attachment and performance gates are not passed. Existing Base extraction
is not automatically equal to today's canonical Wolverine code; historical
x86/x64 numerical and transport limits must be resolved against this reference
without widening tolerances or changing behavior.

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

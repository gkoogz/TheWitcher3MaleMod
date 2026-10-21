# Rear-only attachment extension

The user requested moving the back of the scrotal attachment toward the pelvis
while keeping the front fixed. Geralt's authoring recipe now uses Base's existing
`rear_extended_stations` map with `rearExtension=0.25`. The map is monotone and
has a quintic transition to zero displacement across the rear half. Its distal
half stays exact. No new deformation law or numerical-worker revision is needed.

The measured proximal station changes from 3.25 to 3.00; the distal station stays
12.80. These are source coordinates, not centimeters. The existing pelvic ramp
ends at 2.9116673061, leaving 0.0883326939 clearance. This is intentionally a
bounded extension: a larger translation would enter the separate pelvic ramp.
All 191 sampled front attachment points are exact. The complete shaft and retained
sac arrays are byte-for-byte numerically equal to the prior authoring inputs.
The assembled original pelvic surface has zero displacement. The rebuilt neck
and pelvic ramp have no locally reversed faces; the visible union is closed.

The shared implementation remains pinned at
`1f0b93367018ff6c8b8db4642a28ea73eeee1e23`; the installed root-motion correction
and numerical worker remain unchanged. Other spokes can use the same shared
rear-extension parameter after measuring their own pelvic clearance and passing
their native attachment gates. This does not install or alter Wolverine.

## Reproduction and compact storage

All private input/output stays under `D:/MaleMod/Work`. Start with the maintained
wire6 source and original joined body in `Work/witcher/assets/source`. Apply every
parameter in `characters/geralt-modular-authoring.json`, including its explicit
root. Run Base's `build_modular_anatomy.py`, `assemble_modular_pelvis.py`,
`build_modular_runtime.py`, `build_modular_dynamic.py`, and
`build_modular_transfer.py`. Keep the complete shaft and visible union separate.

The prior cleanup removed disposable historical FBX, rig JSON and texture bake
jobs. Re-export the two licensed stock meshes with `mod.py export --stock`.
`prepare_modular_render.py --stock-rig` uses an official stock-rig JSON export
plus the character profile's recorded extension name order; it does not infer
transforms or bones. `--winding-reference` accepts the retained native manifest
only when both its native binary and carrier hashes verify. The original native
winding evidence hashes remain identified as historical measurements.

Rebuild material bindings with the same explicit `--stock-rig`. Recover the
existing color-matched base atlas from the installed BodyBoundary package using
official uncook/export. `prepare_neck_material.py --source-atlas` accepts those
two measured 8192x4096 exports, avoiding deleted historical skin-match jobs.
Then run `prepare_join_material.py` and `build_neck_material.py`. The neck chart
is rebaked for the new surface. Bakes preserve the decoded original body tile
and pixels outside their support; this is not a claim that texture recompression
preserves every original compressed byte.

Keep all five coupled geometry/binding/material resources together with the
native texture package. The runtime DLL is unchanged. A previously tested owned
preview may serve as rollback only if every managed file matches the current
accepted installation. This avoids another copied runtime bank; never delete
or refresh a preview serving as the active rollback.

## Evidence

Private current work: `D:/MaleMod/Work/witcher/rear-attachment`.
`geometry-audit.json` records the fixed front, preserved shaft/sac and clearance.
Twenty Python geometry/shading/transfer tests, eight shared C++ tests, and nine
adapter authoring/preview tests pass. Native and installed results are recorded
separately in the final acceptance and installation receipts. Source checks or
a successful native texture cook do not establish attachment acceptance.

# Runtime physics investigation

The user supplied a game screenshot on 2026-09-30 showing the fitted 0.3.0
attachment. This confirms appearance only. A still image does not verify
independent motion, live controls, body contact, moving seams or performance.
The installed package remains 0.3.0-anatomy-skin-test.

## Scope and ownership

Requested: secondary motion, a corner hotkey panel and all nine rest-shape,
eight physics sliders plus the mechanical-state selector from Wolverine.
Animation sequences, fluids and audio are explicitly deferred.
Base owns `malemod_base.controls`, the versioned `modules/live-controls.json`
catalog, preference validation and source mappings. This adapter owns native
deformation, the HUD/input lifecycle and native calibration. Do not describe a
menu, catalog or successful script compilation as physics-enabled gameplay.

## Verified native evidence

- Stock `CAnimatedComponent` exposes `SetBehaviorVariable` and
  `SetBehaviorVectorVariable`, but no direct script bone-matrix setter was
  found in the installed script declarations.
- `CMorphedMeshManagerComponent.SetMorphBlend` exists, but does not establish
  nine independent live morphs on the current fitted mesh.
- Native `CAnimDangleConstraint_Dyng` contains `dampening`, `gravity`, `speed`,
  `dyng`, collision and iteration properties. Its `CDyngResource` carries node
  names/parents, masses, stiffnesses, distances, transforms, links and collisions.
- Importing the component's `constraint` field as a WitcherScript object fails:
  native type is `ptr:IAnimDangleConstraint`, script type is a handle. The
  attempted `ptr:` script syntax is also rejected. Do not repeat either route.
- An authored item property holding a handle to the constraint **compiles**.
  `probes/dynamic_constraint.ws` records the accepted declaration; run
  `python tools/probe_physics.py` against the pinned Base. This has not yet been
  serialized into an item, connected to its native constraint or exercised in
  the game. It is isolated from `workspace/` and cannot enter a normal package.
- Native graph types include bone scale/rotate/translate and parent alignment.
  They are candidate output paths, not tested support. Geralt's scabbards use
  their own `CAnimatedComponent` attached to the torso; this does not prove an
  independently animated lower-body mesh will preserve the stock leg rig.

## Headless resource inspection

`python tools/inspect_native.py <absolute-native-file>` copies the input into a
unique ignored job and runs the official `dumpfile` command. This handles native
versions the community converter refuses. REDkit concatenates output prefix,
input path and `.xml`; the validated local output uses Windows' `\\?\` prefix.
Keep the normal SDK working directory: another cwd fails to find gameconf.cfg.
The command has been exercised on stock `player_base_m.w2ent` (version 164).
Raw XML includes byte arrays and is not automatically an editable resource.

Local research inputs remain under `build/research/` and `build/probe/`:
WolvenKit-7 release 7.2.0 can read the stock pendant dynamic resource (159), but
its graph enum support is incomplete. A local build of current source reads
the scabbard behavior graph; permitting version 164 allowed inspection of the
player entity. That local version-gate change is **not** a validated writer or
an endorsed compatibility patch. Do not ship a player entity rewritten through
it. The original SDK/depot files were not changed. See `provenance/runtime-probe.json`
for source/tool identities and exact native log hashes.

## Next gates

1. Serialize the item-to-constraint handle into an isolated native fixture;
   validate native load/cook and inspect the recovered object reference.
2. Bind a small motion cage using Base's source lineage. Preserve body and
   module edge donors, UV aliases and stock waist/ankle boundaries. A second
   animated component must still receive Geralt's moving leg/torso transforms.
3. Establish a real independent scale/pose output using authored bones/graphs
   or morph assets. Do not scale the entire lower-body component. Preserve the
   shared final collar law; defer expansion outside the verified envelope.
4. Connect only verified capabilities to a hotkey panel and native settings.
   Keep per-frame work on the small cage, cache bindings, bound substeps and
   suspend when unequipped. Do not add a per-vertex WitcherScript loop.
5. Verify native assets/package, then test movement, contacts, saves, equipment
   transitions and actual timing in game. None of these runtime gates is passed
   by the current compiler probe.

Wolverine adoption: the shared control IDs and preference validation can be
backported independently of its established full solver. Native REDengine
dangle behavior is not numerical parity with Wolverine's XPBD/contact solver.

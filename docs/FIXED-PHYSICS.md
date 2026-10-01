# Fixed rest and secondary motion

The October 1 scope reset removes all live Witcher size/physics sliders, size
pose tables, settings persistence and tuning menu/hotkeys. The clarified fixed
baseline is Wolverine's evaluated ResetStudyControls default: state 2 and all
seventeen UI values 50, after 120 source reference frames. The large posed
authoring mesh is replaced. The original measured source-to-character scale
1.0255218584141075 is preserved; the smaller source seam does not cause a new
uniform enlargement. This does not remove Base's portable preference
contract or change Wolverine. Historical slider probes are superseded.

`tools/player_stack.py --physics` generates a controller using
`tools/fixed_physics.py` and `probes/runtime/fixedPhysics.ws`. The numerical
functions are translated directly from the pinned Base headers by
`physics_codegen.py`. The adapter supplies observed rest frames, skin envelopes,
bone mapping, world sampling, fixed-step scheduling and native pose delivery.

- Existing stock 94-bone prefix is retained; ten authored joints are independent
  pelvis children with identical world bind frames. Full 104-bone LOD is retained.
- Scale graph variables are assigned `(1,1,1)` once. Per-frame translation and
  rotation go through the working additional player pose layer.
- Twelve shaft physics particles are independent of the eight shaft skin joints.
  Two proximal particles are kinematic, separated by one uniform source segment
  (0.0237551723861 native units). Ten distal particles use the source distance
  compliance, zero-curvature Kelvin-Voigt bend, proximal gradient and exported
  raphe multipliers. The old centroid cage locked a much longer initial span.
- C1 Hermite sampling transfers the guide to the rendering joints. Source lobe
  centers and axes replace inferred centroids. Source Y maps to native -X;
  the lobe skin donors follow that conversion, preserving source mechanical order.
- Two lobes use gravity, source tension-only suspension, transverse shear, hard
  reach limits and damped orientation following.
- Collisions use actual animated `r_thigh/r_shin/l_thigh/l_shin` endpoints,
  measured stock thigh envelopes, source default radii, tapered-ovoid support,
  lobe/lobe separation and
  symmetric rod/lobe reactions. Contact correction is excluded from recovery
  velocity; moving thigh surfaces supply relative normal/friction response.
- Physics uses 60 fixed steps/second, 24 coupled iterations, interpolated pose
  history, at most three steps per tick and resets on teleports or large hitches.
  Broad phase rejects separated resources before ovoid support queries.
- The controller owns only `MaleModAnatomyLayer`; detach removes that layer and
  stops ticking. No stock graph replacement, pose freezing or input binding.

This is a point-mass adaptation, not full source solver parity. Angular contact
effective mass, full Hermite reaction Jacobian, source surface deformation,
pressure and dynamic collar remain omitted. The root droop is initialized from
the evaluated full-floppy state; source gait/side filtering and live root spring
response are not reproduced. The static surface now comes from the evaluated
default, with a bounded local seam repair and unchanged stock outer boundaries.
The shared `secondary_test` exercises a 600-step moving guide and suspended
lobes, source support agreement, contacts, length conversion and rest bend.
Native compile/cook/unbundle and gameplay must be recorded separately.

## Reproduce locally

The ignored source fixtures and native inspections must exist and match hashes.
Refresh the shipped templates if the installed game's startup bundle changes:

```powershell
python ../MaleMod/tools/export_default_baseline.py ../MaleMod/build/<new-default-export>
# Set characters/geralt-attachment.json evaluatedBaseline to the new export.
python tools/mod.py attachment
python tools/build_default_cage.py
python tools/verify_default_guide.py <new-cage-directory>
python tools/probe_deformation_bridge.py --identity-root --attached-pose --cage <new-cage-directory>
python tools/player_stack.py <new-deformation-probe> --rest-joints --full-joint-lod --effective-templates --shipped-player <current-shipped-player-receipt> --physics
python tools/verify_motion_package.py --directory <package-directory>
python tools/deploy_motion.py install --directory <package-directory>
```

Omit `--physics` to build the same fixed rest without simulation. Installation
requires the game closed and exact packed-resource verification. It preserves
rollback and removes only owned MaleMod input bindings. Never press/rebind F12.
The optional existing debug console command `MaleModPhysicsStatus()` reports
startup, steps, contacts, maximum motion, resets and variable acceptance without
adding a hotkey or tuning interface. Counters prove execution, not visual quality.

Gameplay check: idle, walking, running, turns, crouch, outfit changes and save
reload. Check attachment tracking, bounded motion, thigh clearance, lobe/shaft
separation, stable settling and frame pacing. Record the observations and any
status counters in the handoff; do not mark them successful from a cooked build.

## Historical native checkpoint: 0.4.25

Current .26 install: `publish/20261001-194607-3fc4a2`, Base `5f0cd94`.
58 adapter and 56 Base Python tests passed; native round-trips, full scripted
cook and ten unpacked resources/buffers passed. See HANDOFF.md and
provenance/fixed-physics.json for exact default-source and cage receipts.
The user observed motion in .25 but rejected its default shape. The .26 visual
match and live performance are still pending. Its five installed hashes match.

Full authored cook: `publish/20261001-185819-2d6df9`. Final candidate with the
compiled detach/startup cancellation patch: `publish/20261001-185931-7366b3`.
The patch preserves all four native package files byte for byte; all controller
declarations and function signatures are unchanged. Native cook evidence is
inherited explicitly, and the final script is separately compiled. Base pin:
`a3a8dd80ed08a3415828f6c5809f4b50d8c68bb9`.

57 adapter tests and 55 Base Python tests passed. Base `secondary_test` passed
5,000 source support cases (maximum float difference 0.0000109387 source units),
zero-rest bend equivalence, suspension/reach, contact recovery, symmetric
reaction, length conversion and a 600-step moving guide fixture (maximum rod
length error 0.000055775 native units). Full provenance verification passed.
Gameplay, visual contact accuracy and live frame cost remain unobserved.

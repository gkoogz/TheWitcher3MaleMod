# Restored baseline and motion-axis investigation

The user rejected .29's protected head/lobe binding as a workaround. The game
is restored to .28; the protected binding is removed from active Base and
adapter source. The original evaluated rest geometry, unit scale, uniform
render stations and source coefficients remain. Wolverine is unchanged.

## What was measured

Run `python tools/audit_motion_axes.py` with the restored local fixtures. It
checks the five installed file hashes, traverses the official cooked graph,
loads the observed native rig and interprets the REDkit executable's local
TranslateBone and RotateBone SIMD blocks. It evaluates the actual controller
angle expressions, rather than replacing them with a desired rotation formula.
No running process is attached; no key is pressed or rebound.

| Layer | Result | Limit |
| --- | --- | --- |
| Cooked graph output | 60 distinct, connected XYZ translation/rotation channels | Does not measure the game's currently sampled stack |
| Native delivery on ten observed bind frames | Translation rank 3 and rotation rank 3 at every joint | REDkit executable replay, not live game executable output |
| Guide-to-bone translation under 3D bends | Maximum error below 2.03e-8 native units | Synthetic guide trajectories |
| Tangent-to-orientation reconstruction | Rank 2: both bending freedoms, no independent axial roll | Does not carry a material director or torsional state |
| Restored mesh under nonuniform bends | Head edge-length change up to 20.25% | Controlled bends, not measured gameplay strain |

The surface test covers both LODs, each with 5,447 head-region vertices and
16,242 usable head edges. Bends about pelvis X/Y/Z produce guide excursions
.08134/.05371/.10009 native units and head edge strains
.20250/.03087/.14473. All three directions produce motion. Accurate center
positions do not guarantee preserved dimensions of the surrounding surface.

The matrix-direction wrapper and shortest-quaternion function were also
inspected read-only using `tools/inspect_editor_function.py`. `VecTransformDir`
uses all three basis vectors; shortest rotation uses the XYZ dot and cross
products, and `AtanF(a,b)` calls `atan2f(a,b)`. The controller uses 3D
`VecNormalize`, not `VecNormalize2D`. Base relative-frame integration, bend and
contact kernels operate on three-component vectors. This audit does not
establish that the game's runtime animation stack cannot override a component.

## Interpretation

No missing delivered XYZ axis was found in the authored/cooked/native replay
path. Independent roll is absent from the controller's tangent-only model, but
the Wolverine reference also uses shortest tangent rotation. Adding arbitrary
roll does not follow from these results and is not an established repair.

Wolverine additionally calls `ConstructLogicalShaftSurface(true)` after
simulation. That stage transports stored radial cross-sections onto the live
guide, with further material/suspension/collar stages. Witcher's small native
cage instead blends independently moving joint transforms. The audit reproduces
surface strain even when every commanded axis and joint center is delivered
correctly. This establishes a surface-transport defect in the offline model;
it does not prove it is the only defect in the running game.

## Required next evidence before another installation

Obtain controlled running-game readback of added joint positions and basis
vectors relative to the same-frame pelvis. Exercise isolated signed translation
and rotation on X/Y/Z with physics temporarily suspended in a diagnostic build,
then restore the original variables and restart simulation. Verify the final
evaluated pose, not just SetBehaviorVariable acceptance. Use an explicit console
command/API, never F12 or another newly bound key. Any diagnostic controller with
new serialized fields/signatures requires a full native cook, not a script-only
patch. No such diagnostic build was installed during this rollback.

If live delivery agrees, the correction belongs in shared surface transport
and its native adapter, with complete cross-section/material verification under
nonuniform motion. Base's extracted full surface session has a documented
32-bit parity gate and an unresolved 64-bit gate; neither its existence nor a
native bone cage establishes a performant Witcher vertex-upload capability.
Keep those requirements explicit rather than reinstating the rejected lock.

Evidence: `provenance/motion-axis-audit.json` and the ignored audit output path
recorded there. Current installed status is in `provenance/fixed-physics.json`.

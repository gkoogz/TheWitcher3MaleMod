# Suspension material continuity follow-up

The user rejected the installed October 19 envelope repair's appearance:
a horizontal band remains above the lobes and a separate texture/shading region
remains at the shaft join. The earlier recorded attachment review does not
establish acceptance of those two defects. Keep that installation as the
reversible baseline while the replacement is tested.

The previous bake reconciled boundary rows but preserved separate material
fields on either side. Its audit also omitted actual half-precision UVs and
GPU texel-center filtering. A flat-material native diagnostic substantially
reduces the apparent bands without changing any geometry or numerical physics.
The reconstructed proximal shaft also occupies UV space overlapping the retained
sac: writing a common spatial field into that shared area repaints the wrong
surface. The adapter must give the proximal shaft an independent atlas region.

Base `join_material.py` supplies geodesic support with smooth protected-surface
limits, measured skin detail sampled in common rest coordinates, and a
texel-center triangle rasterizer. The Witcher adapter relocates proximal shaft
UVs into the unused half of the anatomy tile, bakes a common pigment/detail field across
sac/neck and a bounded shaft overlap, and fades back to original shaft material.
The incompatible normal-map layers are replaced locally by a common neutral
map; existing native source normals and dynamic wrinkle fields still supply
surface relief. No geometry, joint, mechanical owner or simulation code changes.
The original body texture tile stays byte-exact. Atlas gutters cover the real
filter footprint instead of being blocked by unused authoring ramp UVs.

31 Python material, geometry, shading, union and transfer tests pass.
Private evidence: `D:/MaleModBuilds/modular-anatomy-20261015/scrotal-seams-20261019`.
Material08 used a V translation and was rejected for root-ramp stripes.
Material09 uses an exactly representable U translation and copies the full
original half-tile, preserving the root-ramp V sampling and its filter support.
The material09 native capture removed the material bands but retained a faint
lower shading crease. The native renderer applied retained normal relief and
wrinkle detail after its join correction, invalidating that correction. The
final candidate performs the endpoint normal blend after both detail passes,
using the final endpoint normals. On the identical captured pose, lower first
strip normal-turn median/p95 falls from 1.70/7.19 degrees to approximately zero;
positions are exactly unchanged. This replay measurement is separate from
native visual inspection.

Candidate04 is installed after 252 captured native stages, of which245 were
usable visual views; seven wall-occluded frames (full688 and690-695) were
excluded and superseded by nine unobstructed distant views. The matrix covers
representative sizes, angles, mechanical states, Hang, motion, both native body
resources, supported LODs and a campaign scene. All68 captured-pose audits pass.
31 Python tests and eight shared C++ tests pass. Native build, installed startup,
walking observation and Steam grey-room preflight pass.53 managed files and31
files protected before installation verify; owned sessions are closed, saves
and scoped audio restored. The engine reordered input.settings without changing
bindings; the exact pre-install file was restored after semantic comparison.

One initial offline motion replay reported an invalid bone binding. The full
recheck and six additional runs of the same input passed, with byte-identical
geometry and native shading outputs. No cause was established; initial failure,
rechecks and limitation remain in replay-anomaly.json and the acceptance proof.
This is not claimed as a fixed runtime defect or discarded from the evidence.

The material repair leaves geometry, physical ownership and numerical simulation
unchanged. Only one of114 compiler inputs differs from the installed baseline:
`native/modular_dynamic_render.hpp`. Exact compiler inputs and authoring tools
are archived because the adapter includes pre-existing uncommitted code; this
is not a clean-checkout release. Fine skin folds remain; existing extreme distal
shape defects and numerical performance are outside this repair. Coverage is
representative, not every Cartesian control combination or world transition.

Exact installed identity and rollback:

- Base material-authoring pin: efb825580ffacf47fc3b66be505c7e54ddcdc228.
- DLL: e81ae761b6231ab391da2144a33e72fe092d7d828d85fd4453d7525363438611.
- Material bindings:72412e7e6d100d83852fd70a5f404c1760c86b8a8298ec2e8ba45b385ac80c5d.
- Texture package:TheWitcher3MaleMod/publish/20261019-092502-121059.
- Evidence:scrotal-seams-20261019/candidate-04 under the private evidence root.
- Rollback:TheWitcher3MaleMod/local/native-backup-modular-20261019-101835.

Other adapters adopt the Base functions through a pinned revision, measure
their own atlas occupancy and native UV precision, regenerate their licensed
maps and run their own attachment gates. No other spoke is modified here.

# Continuous suspension skin - October 19

The lower skin transition used the same tangent-length safeguard as the upper
mounted rim. A tight upper wrap reduced both handles to 0.25, producing a short
shoulder above the retained lobes. The two endpoint lengths now have independent
bounded searches, with a common length per ring and the same orientation gate.
The measured character selects lower 1.0 / upper 0.25, with zero reversed loft
faces. Minimum outward cosine improves from 0.06077 to 0.19691. Median turning
between the first four strips falls from 1.80 to 0.88 degrees in the authored
surface. These are local geometric checks, not a global intersection proof.

The generated material also switched from retained boundary detail to the
independent neck tile in only 2.5% of meridian length. That narrow normal/detail
transition exposed a cuff despite welded geometry. Both transitions now occupy 20% of measured length. Fine detail transitions
separately over 3%, preventing long pore streaks. Boundary samples, retained
UVs and texture pixels outside the generated chart remain unchanged.

The intent is a thinner-looking continuous outer skin envelope. This does not
claim a new tissue-thickness simulation. The retained rest assets, complete shaft, mount footprint, pelvis, UV lineage
and independent numerical motion are preserved. A bounded material-space
corrective recesses the projecting medial bridge and limits the raised web to
the upper connecting skin. Compact C2 falloffs preserve the lateral supports,
back and mounted rim; the existing area safeguard prevents relief-induced
triangle reversals. This changes display skin, not the numerical bodies.
Three of 114 native compiler inputs change: shared skin_relief.hpp,
surface_stitch.hpp and the adapter modular_dynamic_render.hpp. The numerical
worker is unchanged. Native gameplay omits legacy shaft normals with immutable
morphology; the old join correction therefore skipped the upper endpoint.
The replacement constrains both endpoints using the current native endpoint
when no transferred field exists. A quintic spherical blend also suppresses
the interior shading spike instead of merely correcting the boundary value.
The original captured last strip turned its normal by median 6.18 degrees
over median 0.0235 source units. A replay probe exports actual packed native
normals to verify the repair without changing the captured pose. The same-pose
median falls from 6.18 degrees to zero at packed normal precision; the 95th
percentile falls from 13.39 degrees to below 0.000002 degrees. All 12 Hang
poses have last-strip median below 0.1 degree and 95th below 0.25 degree.
The source diagnostic and exact cooked native captures remain separate proof.

Shared commits: a9ea9b0 (independent tangents), f501fb1 (lower material blend),
7207e62 (separate broad shading and fine detail), 4162c13 (medial bridge),
8840071 (mounted rim broad/fine blend), a0a1fbf (remove reused tile slope
bias and blend pigment across the complete neck), 629363c (shared endpoint
normal constraint).
27 Python tests and eight C++ tests pass. The synthetic tapered-sac
regression specifically requires a full lower tangent while the upper handle
is constrained below 0.5. The material regression prevents a narrow lower cuff.

Private evidence and regeneration scripts:
`D:/MaleModBuilds/modular-anatomy-20261015/scrotal-envelope-20261019`.
Candidates 01-06 are uninstalled diagnostics. Candidate 07 adds the live
endpoint normal constraint to candidate 05 material and medial skin repairs.
Boundary color, vertex normal, color/reflection attributes were checked to match
exactly; the remaining generated interior was transporting the source tile
mean slope and retaining a lower-pigment plateau. Tests now forbid both.
Candidate 07 passed the native attachment gate and is installed. The recorded
matrix contains 252 stages: 96 scale/state/angle/LOD, 36 Hang, 36 motion,
12 pause/resume, 24 skin, nine dedicated distant and 39 campaign stages.
Six wall-occluded distant views in the 96-stage run are excluded from visual
acceptance and superseded by the dedicated distant run. The other 246 views
were visually reviewed, together with 68 captured-pose geometry audits.
The audits retain the original pelvis, boundary count and zero reversed or
nonmanifold collar faces. Native front/side/oblique views show the upper shaded
cap removed, a softer lower shoulder and reduced projecting medial skin.
Motion and pause/resume observations confirm varying independent lobe and tip
positions. Installed startup and movement were subsequently observed in three
native screenshots. This installed check is a startup/movement check; the
pre-install close-up matrix supplies the surface review.

Installed DLL:
`b974338b3236289e1ddbbb965f3825eadab7e0c4cdc528949238c2fe1a485a05`.
Shared authoring/runtime surface pin: `629363c838685f5815cd47f3d3c599908419fef9`.
Witcher adoption commit: `d7b35bd`. Numerical worker pin remains
`431e626cae6fb6720b552f8b20206727fe809c80`.
Cooked material package: `TheWitcher3MaleMod/publish/20261019-021514-53caaa`.
Exact coupled file identities, source inputs, preview, closed session receipts
and capture hashes are bound by `candidate-07/delivery/modular-acceptance.json`.
All 114 compiler inputs and reproduction tools are archived there. Pre-existing
uncommitted adapter runtime files are archived rather than represented as a
clean-checkout release. Three compiler inputs changed; the numerical worker did
not. No performance or simulation-cadence improvement is claimed.

All 53 managed files and 31 protected files verify after installation. The game
reordered input.settings only; identical section/line multisets were verified
before restoring the exact original bytes. All owned sessions are closed,
normal saves/settings/audio restored, and Steam grey-room preflight passes.
Installed session: `sealed-session-20261019-031146`.
Exact prior-runtime rollback:
`TheWitcher3MaleMod/local/native-backup-modular-20261019-031102`.

Coverage is finite and representative, not every Cartesian control combination,
world transition or garment. Existing extreme distal/glans deformation remains;
regional source pigmentation remains intentionally distinct with gradual joins.
The material chart retains 96 float32-collapsed UV microtriangles spanning
3.06e-7 of chart area; the geometric faces remain valid. No release was published.

Other spokes adopt these Base authoring functions through pinned revisions,
regenerate their licensed geometry and measured material charts, and perform
their native attachment gates. No Wolverine runtime is changed by this work.

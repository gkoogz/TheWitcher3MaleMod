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
normals to verify the repair without changing the captured pose.

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
Native attachment acceptance and installation are pending. Retain the preceding
accepted runtime and its exact rollback until the full gate passes.

Other spokes adopt these Base authoring functions through pinned revisions,
regenerate their licensed geometry and measured material charts, and perform
their native attachment gates. No Wolverine runtime is changed by this work.

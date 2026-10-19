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
transition exposed a cuff despite welded geometry. The lower transition now
occupies 20% of measured length. Fine detail transitions separately over 3%, preventing long pore streaks.
The upper transition, boundary samples, retained
UVs and texture pixels outside the generated chart remain unchanged.

The intent is a thinner-looking continuous outer skin envelope. This does not
claim a new tissue-thickness simulation. The retained lobes, complete shaft,
mount footprint, pelvis, UV lineage and independent numerical motion are exact.
The native DLL and all 114 compiler inputs are unchanged from the preceding
accepted runtime; this update changes shared authoring geometry and material.

Shared commits: a9ea9b0 (independent tangents), f501fb1 (lower material blend),
7207e62 (separate broad shading and fine detail).
25 Python tests and eight existing C++ tests pass. The synthetic tapered-sac
regression specifically requires a full lower tangent while the upper handle
is constrained below 0.5. The material regression prevents a narrow lower cuff.

Private evidence and regeneration scripts:
`D:/MaleModBuilds/modular-anatomy-20261015/scrotal-envelope-20261019`.
Candidates 01 and 02 are diagnostic only; candidate 03 separates fine detail
from the broad material transition.
Native attachment acceptance and installation are pending. Retain the preceding
accepted runtime and its exact rollback until the full gate passes.

Other spokes adopt these Base authoring functions through pinned revisions,
regenerate their licensed geometry and measured material charts, and perform
their native attachment gates. No Wolverine runtime is changed by this work.

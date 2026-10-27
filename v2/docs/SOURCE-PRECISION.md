# Native float baseline precision

This is an authoring correction for the observed B04 float renderer. It does
not change source geometry, canonical deformation, physics, skinning or the
official cooked allocation. Native visual acceptance remains required.

The cooked uint16 positions inherited four zero-area and two reversed microscopic
canonical module faces in each LOD. The same corner defects exist in the earlier
B03 cook. All six are original module faces, rather than new seam or stock body
faces. Their classification and native corner coordinates are recorded in
`v2/build/materials/anatomy-01/microface-classification.json`.

`tools/bind_wolverine_v2.py` retains its exact B03 path. After writing a B04
binding it calls `tools/v2_source_precision.py`. The helper matches native source
rows against authoritative fitted module positions using original half-UVs and
oriented triangle topology. This resolves the ten close UV/position aliases in
each actual source section without changing the established dynamic donors.
Every original triangle must still exist with the same orientation. Only the
one identical Erect transport triangle per LOD may be additional.

Only the three baseline position floats of source interior rows are restored.
All stock body rows and every shared seam row remain byte-identical. All other
bytes, including normal, tangent, bones, weights, canonical donor IDs/weights and
headers, remain byte-identical. Restoration rejects corrections above 0.00003 m,
unresolved positional ambiguity, unexpected topology, changed streams or a B03
input. All checks complete before replacement of the generated binding.

The generated `source-precision.json` records raw/final binding, fitted input and
cooked mesh/buffer hashes, correspondence details and correction bounds. Its
hash and contents are included in the binding manifest. The actual approved
candidate restores 69,968 interior rows, protects 8,369 rows, and changes each
baseline by at most 0.0000159876054 m.

The offline study checks all 142,844 main-body triangles across both LODs and both
logical skin states. Static and actual CP400 canonical deformation each change
from four zero plus two reversed faces per source section to zero defects, with
no newly reversed or zero faces. Protected CP400 output rows are byte-identical.
Four existing donor differences remain, with maximum displacement discrepancy
about 0.00000403 m; donors are deliberately preserved and these do not invert a
triangle. This checks the actual SourceBinding CPU output before native skinning;
there is no captured 94-bone pose or GPU output in the study.

Reproduction and exact outputs are in
`v2/build/materials/anatomy-01/precision-study/`. A fresh complete binder run
reproduces the approved B04 candidate SHA-256
`7bce802fc350a55b840c530fdf83b939b622f27149aefc68cf0de27d112cea66`.
The same authoring run's B03 binding is byte-identical to its retained reference,
SHA-256 `b979e970a6973523bd453ea19da1702ee00070c572665d21cd1b626f01329bbb`.
Six focused guard tests plus four native binding reader tests pass. The study
did not replace the global runtime binding, stage a package or launch a game.

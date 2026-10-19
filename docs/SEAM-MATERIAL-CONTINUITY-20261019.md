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
UVs into the unused lower atlas, bakes a common pigment/detail field across
sac/neck and a bounded shaft overlap, and fades back to original shaft material.
The incompatible normal-map layers are replaced locally by a common neutral
map; existing native source normals and dynamic wrinkle fields still supply
surface relief. No geometry, joint, mechanical owner or simulation code changes.
The original body texture tile stays byte-exact. Atlas gutters cover the real
filter footprint instead of being blocked by unused authoring ramp UVs.

31 Python material, geometry, shading, union and transfer tests pass.
Private evidence: `D:/MaleModBuilds/modular-anatomy-20261015/scrotal-seams-20261019`.
Material08 is the first candidate with the proximal shaft UV relocation.
Native visual acceptance and installation remain pending.

Other adapters adopt the Base functions through a pinned revision, measure
their own atlas occupancy and native UV precision, regenerate their licensed
maps and run their own attachment gates. No other spoke is modified here.

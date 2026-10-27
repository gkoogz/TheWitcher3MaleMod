# Material-split weld frames

Coincident body/anatomy rows are not sufficient for smooth shading if the two
materials transport their lighting frames differently. In the actual B04 data,
the complete 52-byte records agree at the physical weld: position, bones,
weights, packed normal/tangent and source donors/weights are identical.

`SourceBinding` now gives those exact stock-row aliases the stock lighting path
before generating frame groups and row aliases. Distinct anatomy interiors keep
the canonical full-frame path. This changes no position, bone, weight, source
packet, UV, mesh, worker or solver. It introduces no distance-based matching or
new geometry rule.

The native normal bake must also use actual cooked UVs and actual runtime rest
frames. A geometric UV-derivative frame is not a substitute for those frames.
At an identical-record weld the correct stock-to-module rest-frame transfer is
identity. The earlier proxy-frame bake plus different dynamic frame paths
produced up to 66 degrees of mapped-normal disagreement despite a zero position
gap and matching albedo.

The actual-data before/after fixture in `build/materials/seam-weld-fixture`
evaluates 31 recorded source cases across all 78,337 rows. All 312 distinct
module weld aliases share stock frames byte-for-byte. Every position/bone byte
and every nonmatched row is unchanged. The corresponding stock-side UV aliases
cover 112 LOD0 and 92 LOD1 seam rows. These are CPU pre-skin proofs; native visual
acceptance remains a separate gate.

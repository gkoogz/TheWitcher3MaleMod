# Source-backed size repair

## 0.4.23: coherent frame transport

The user's 07:35 screenshot shows 0.4.22 is closer, but still has an uneven
shaft and a sharp distal transition. Loading and visible enlargement are observed;
exact UI values, gait parity and preference persistence are not established.

Inspection found that the installed mesh is a large source reference in a different
pose from the AuthoredShape UI-default cage. Independent section displacement
vectors between those frames, and separate section RMS scales, were unsuitable.

Base `3119d70` now measures source radius and axial span with the original-code
verified SourceRestFrame, applies their default-relative ratios in the calibrated
export axis, and gives all shaft joints one uniform radial scale. The existing
export curve is retained. Both crown joints implement one similarity transform
about the calibrated flex .76 anchor, including glans enlargement. Their weighted
blend cannot squash or kink the free crown. Independent lobe fits remain.

59 adapter tests now include identical native crown transforms for all 256 lattice
profiles and min/default/max glans. Three coherent transport tests, three source
rest-frame oracle tests and four authored-stage oracle tests pass. Default weighted
skin error is 4.44e-16 and all-max seam separation is zero in the offline check.
This remains dimension transport rather than the complete logical/prepared surface.
The source short-profile prior-length fallback uses measured neutral for the
offline lattice; gameplay-history parity remains omitted. Native and installation
evidence is recorded in provenance/size-controls.json and the current handoff.

## Historical 0.4.22 section fitting

The user reports that 0.4.21 maximum size controls look smooshed and distorted.
Treat it as a failed shape-quality test. Its scale-only graph applied a
nonuniform transform above a curved chain and used independent ratio products
instead of Wolverine's authored morph sections.

0.4.22 consumes Base `34ffd86` shape_transport.py. Source-backed section fits
include rotation, positive RMS dimensions and centroid offsets for overall,
width, length and scrotum. The four-dimensional lattice includes source branch
knots, defaults and extremes. Glans enlargement uses the source .76 crown-base
anchor; the folded vertex attachment remains an approximation.

Only the ten authored joints become direct children of observed pelvis index 9.
Their rest world frames are preserved (max error 6.11e-16); the 94 stock bones,
native mesh palette/inverse binds and shipped-template loading repair remain.
The attached rest-mask graph delivers ten scale vectors and 60 scalar translation
and rotation channels. Native localSpace rotation left-multiplies the current
quaternion; XYZ delivery uses parent-space extrinsic XYZ angles. Read-only native
evidence is in build/probe/disassembly-0952265e37e1/function.txt and the TranslateBone
skinning audit. Default input/rest mask resets rotations and positions on sampling.

Lookup evaluation happens on boot/input, not each animation frame. Initializers
are bounded to 96 values per method, with short dispatchers. Source preferences
and UI ranges remain unchanged. Manifest `assignments` retains the historical
ratio-probe labels for compatibility; `backend`, `independentHierarchy`, calibrated
pose receipt and connected cooked graph describe the new delivery.

Verification: 59 adapter tests, three shared transport tests, four existing
original-C++ authored stage tests and Base provenance pass. Native script/cook,
output traversal, 104-joint rest frames, shipped-template checks, ten exact
unpacked resources/buffers and five installed hashes pass. Offline weighted skin
default error is 6.66e-16 and seam separation at all maxima is zero. Stock byte
weights have sums down to 252/255; the comparison preserves those sums rather
than assuming native normalization.

Historical package: publish/20261001-071733-98def3. Loading/pose rollback remains
the user-confirmed 0.4.20. The next user screenshot reports improved but still
incorrect shape quality; 0.4.22 is superseded by the coherent frame repair.
Full prepared-surface, refined glans, egg, coupled pelvis and source physics parity
are still pending; this improvement does not claim them. Base owns the numerical
fits and documents adoption back to Wolverine and other spokes. Witcher owns
calibrated native frames, graph, UI, cooking and installation.

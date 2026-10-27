The stock-detail candidate restores Geralt's native detail layer only across
the existing skin transition. It preserves source UV0 and all ten current
texture inputs. Geometry, weights, source physics and runtime lighting-frame
transport are unchanged.

The SDK graph `engine/materials/graphs/grid_vat.w2mg`, version 163, export 55,
contains `CMaterialBlockTexCoords` with `coordinatesIndex: Int32 = 1`. The
author checks its header, name-table and export CRCs. The candidate clones the
existing native node and sockets using that observed property. Its new UV1
attribute is authored separately: runtime UV1 must equal stock runtime UV0 at
each physical weld; source UV0 remains intact.

`StockSeamAmbient` references the authentic stock Geralt `a01.xbm` and samples
it at untiled UV1. The detail mask is its red channel multiplied by the existing
Ambient blue seam weight. Only the original three native detail-mask inputs
are rewired. Current Ambient red continues to serve the source material's
second specular lobe.

The existing detail sampler uses UV1 multiplied by `DetailTile=(25,25)`, with
the authentic `detailmap_skin_02.xbm`. `DetailPower` is .5. The source material
instance must also set its existing DetailPower override to .5; it may inherit
DetailTile from this graph. Stock Material0 is untouched. Original distance
fade, RNM, alpha roughness and normal-variance SpecAA functions are retained
byte for byte, as are source specular, subsurface and anti-lightbleed code.

Normal07's earlier base-normal edge proof omits this detail contribution.
Decoded SDK detail mip0 at the actual welded stock UVs changes world normals
by median 2.71/2.50 degrees and P95 6.35/5.86 degrees for LOD0/1. Its alpha
roughness adjustment spans approximately -.031 to +.028. Actual native texture
LOD and pixel-quad derivatives were not captured, so these figures do not
establish the complete visible boundary cause. DetailAlbedoPower is zero in
both materials; this layer does not directly change base albedo.

`tools/v2_seam_detail_material.py` writes only a fresh candidate graph and
receipt. Native compiled shader bytes are retained pending official resave;
the authored graph must never be staged as a compiled result. Required gates
are official resave, UV1 import/cooked roundtrip, complete material cook,
scoped shader cache, actual shader inspection, and native visual review.

Structural tests reject wrong UV channels, tiled mask sampling, wrong mask
channels, missing seam weighting, flat detail and zero power. They also verify
that original custom functions, compiled payload and second-lobe route remain
intact. No native visual or performance acceptance follows from these tests.

The first candidate's official isolated WCC resave passed with exit 0;
`stock-detail-01/graph-compiled.json` closes its native compiler and graph
hashes. The shared skin inspector recognizes the new mode only after the full
StockSeamAmbient UV1/mask/texture contract passes. The material-instance checker
then requires DetailPower .5 and forbids contradictory detail texture or tile
overrides. Existing flat candidates retain their original flat-normal and
DetailPower zero requirements. Both test sets and the actual prior Normal07
cooked material contract pass these validators.

# Source fabric material

This records an isolated material candidate. It does not establish native visual
acceptance or replace the installed runtime.

Canonical Wolverine Meridian uses the matched linear cotton palette
`(.527115126,.496932995,.462077000)`, with the original red/blue bands. Its pouch
normal uses the derivative tangent of the live world surface and original UVs,
orthogonalized to the normalized surface normal. The bump is
`sin(96*2*pi*U)*.16`, multiplied by
`1-smoothstep(.2,.65,fwidth(U)*96)`. Color uses the matching faded cosine at
3.5 percent amplitude. The source has no artificial ambient floor, fiber sheen
or jockstrap specular term. It captures the native directional, ambient, SH and
local/spot diffuse lighting coherently for each pass.

The old native carrier approximation used a 256-pixel normal texture with the
opposite X phase and an additional V ripple. It lacked the source's exact
derivative fade, darkened the linear cotton color by `.35`, and introduced a
native specular term. These are confirmed material differences. Potential
normal texture compression/swizzling is a separate diagnostic: physical BC3
channels and pixel shader RGB alone cannot prove logical GPU channel mapping
without the actual texture SRV component mapping.

Actual native `owned-draw-18476-7.ps` already handles two-sided normals. On a
backface it reflects only the mapped normal's geometric component, retaining
the tangent contribution. For a unit reflection axis this equals the source's
base-normal flip before an orthogonal tangent bump. A test verifies that
conditional identity over 2,000 independent frames. The actual newer native PS
uses the raw interpolated geometric normal for its automatic reflection, while
the custom bump uses a normalized normal. Equivalence therefore requires checking
the affected pixels and front/back classification; it is not established for all
live interpolated backfaces. The captured raster state uses CullNone.

`tools/v2_fabric_material.py` authors
`characters/malemod/garments/fabric.w2mg` from observed native graph nodes and
native name-table hashes. It preserves the native opaque output and its facing
operation, supplies a flat native tangent-to-world basis, and computes the source
procedural raster terms from actual world derivatives. It restores the source
palette and pouch modulation, uses zero specularity, and adds no emissive or
ambient floor. Native REDengine lighting remains an engine adaptation. The
existing four material groups retain their band/strap assignment; this is not a
claim of identical per-pixel source band-edge filtering.

The internal `VarianceOffset` parameter identifies the existing four native
material roles: 0 pouch, 1 elastic, 2 red and 3 blue. `RSpecBase` is zero.
Roughness retains the previous `224/255` value, with no texture alpha dependency.
The source has no raytracing pass or raster derivatives in such a pass; the
adapter explicitly uses geometric normal and unmodulated source palette there.
This is a documented engine boundary, not a source raytracing parity claim.

`tools/build_v2_fabric_material.py` prepares the separate `carriers-08` job.
Official graph resave, all four imports, cook, texture cache and packaging pass.
All four FBX files and all four cooked native carrier buffers are byte-identical
to `carriers-07`. The generated `garment.render` contract is also byte-identical.
Shared positions, topology, normals, tangents, skinning and source numerics do
not change. Four tests cover actual HLSL compilation, the native facing identity,
typed reciprocal inputs and rejection of a disconnected derivative UV input.

The custom graph must be compiled into a current combined body/fabric native
shader cache before runtime use. Successful resave/cook alone is insufficient.
The final `carriers-09` graph adds the observed
`RT_MULTI_MATERIAL_GENERATION_TYPE` guard used by the SDK raytracing route. It
preserves the raster shader byte-identically and excludes derivatives from the
closest-hit library. The `combined-02` two-graph cache passed official compilation
and independent inspection: 16 fabric raster variants retain the source analytic
terms; 20 fabric closest-hit libraries use the documented fallback without
derivatives. The actual native `native-20261026-150618` run shows the fabric but
still has a strong lower-pouch dark fan; this remains under diagnosis.
Actual selection, default and clinical clothed views, dark-fan review, motion,
both LODs, performance and installation remain separate gates. The earlier
probe had no logged covered zero-render-target depth pass; cached shadow/depth
behavior must not be declared accepted from color coverage alone.

Receipts are in `v2/build/materials/carriers-08`, with the read-only source/native
diagnosis in `v2/build/materials/jock-shading-audit/audit.json`.

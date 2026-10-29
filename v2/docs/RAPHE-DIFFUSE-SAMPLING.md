# Local raphe diffuse sampling

The pale front bands reproduce in unlit diffuse sampling of the original
Wolverine faces. Original faces 30189 and 29795 sample flat atlas colour near
RGBA (173,121,82,255), while adjacent painted skin is darker. Both faces have
physical seam weight zero. This is independent of the generated graft rows,
new thigh donors and normal lighting. The Geralt colour adaptation makes the
flat samples visibly pale pink. Native captured target slot 2 shows the same
bands; that observation alone does not assign semantic names to target slots.

`tools/v2_raphe_diffuse.py` keeps the original diffuse sample and adds two taps
on the **same existing Diffuse parameter**. Native natural/erect overrides thus
apply to all three samples. Measured piecewise atlas edges locate adjacent skin
12 pixels beyond each edge. The helper interpolates those skin samples in the
native pow2.2 linear colour space, only inside two bounded UV regions. It keeps
the original encoded RGBA exactly outside the mask and always retains original
alpha. No texture file, vertex UV array, mesh, normal/specular path, stock SSS
branch, physical root blend, garment or numerical solver is changed.

The expanded mask has a full plateau two texels outside the measured gap and
feathers to zero six texels outside it. Vertical caps and an eight-texel width
fade keep the apex finite. Coordinates use `UV0*4096-.5`, matching texel centres.
Both native LODs use byte-identical corresponding original source maps.

Every original triangle was checked for UV aliases. The expanded support reaches
230 left-region and 305 right-region faces, with 74 and 100 original source
vertices respectively. All affected vertices have physical seam weight zero;
none of the 51 inserted vertices or incident graft faces can reach the repair.
All physical aliases remain in a narrow midline skin region. The borrowed
samples are identical between the two state maps in the measured region, while
the shared parameter preserves state behaviour elsewhere.

The strict physical-material inspector validates the three exact helper sources,
untiled original UV0, shared texture parameter, donor routes and channel isolation.
The repaired colour may feed only physical diffuse; the SSS input retains the
original raw sample. Historical pre-repair graphs remain inspectable.

The first authoring attempt (body-visual-04) failed the actual DX12 shader-cache
compiler: native custom-function output sockets return four components, while
the donor UV helper returned two. Its records are preserved and it was never
staged or installed. Body-visual-05 explicitly returns float4 coordinates and
consumes their xy components. The standalone shader check now compiles both
declared signatures and the observed native float4 socket wrapping, including a
regression test reproducing the failed float2 body. Native WCC cache compilation
and fresh game views remain separate requirements.

Private diagnosis, measurements and before/after unlit views are recorded under
`v2/build/materials/body-visual-05/raphe-source-proof/`. Native acceptance and
installation must be recorded separately; this document does not grant them.

## October 28 accepted delivery

Body-visual-05 passed official native cook/cache, fresh production90 + LOD1 90
visual cases, full features, running/GPU pose, six performance cases, campaign
save/load and actual installed showroom/running review. It is installed and the
default grey room uses it. See [delivery and limits](VISUAL-REPAIR-20261028.md).
The earlier pending-gate statements above describe implementation requirements;
the linked delivery record establishes their final observed outcome.

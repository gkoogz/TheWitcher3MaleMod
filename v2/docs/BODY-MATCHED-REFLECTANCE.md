# Body-matched anatomy reflectance

The user reported excessive anatomy shine and a white patch at its lower front.
The installed material correctly decoded the original specular texture, but
treated Wolverine's colored Phong amplitude as REDengine physical F0. These are
different material quantities. Across 15,683 original interior rows, median F0
was `(0.01521, 0.07056, 0.17300)` versus the actual Geralt UV1 target
`(0.01472, 0.01500, 0.01698)`: approximately 4.7 times the green and 10.2 times
the blue reflectance. Raising roughness alone would retain that mismatch.

`tools/v2_skin_reflectance.py` authors an explicit body-matched variant of the
existing physical skin graph. It uses the actual stock F0 spectrum and ambient
mask sampled at the established UV1. Original decoded source specular detail is
retained as an achromatic Rec.709 luminance modulation, normalized to its
hash-pinned interior median `0.042994450549721924`. Calibration reproduces the
original bilinear-wrap UV0 samples; source maps are unchanged. This modulation
is 0.946 to 1.466 across the reference interior and tapers to exactly one at the
physical weld. The stock endpoint remains exact for every source color.

Native stock roughness and the existing native secondary-lobe mask apply over
the anatomy as they do on Geralt. The SSS transition still uses the physical
seam field. Diffuse, SSS, normal transport, native RNM/detail/SpecAA arithmetic,
UVs, geometry, physics and garment rendering remain unchanged. Only the
`physicalSkinSpecular` and `physicalSkinAmbient` function sources differ.

The strict inspector recognizes the complete legacy pair and the complete
body-matched pair separately, and rejects mixed/partial variants. Historical
graphs remain valid and labeled as legacy Phong amplitude. The authored graph
must receive official resave, scoped shader compilation/cache, actual native
appearance review and the normal attachment/install gates before adoption.

The original natural diffuse sampled at every actual source row contains no
near-white pixels; lower front center samples are also skin-colored. A native
stock-response comparison is still required to establish whether the reported
white patch is a reflectance highlight or a separate defect. This document does
not declare that visual gate passed.

## Native color correction after the first reflectance comparison

The first native body-reflectance-only comparison removed the blue-white
highlights, including the visible lower-front patch, but exposed a strong
orange/brown difference from Geralt. That candidate is rejected for appearance.
The original source diffuse and source-only SSS color were still active;
unchanged texture bytes do not establish a matching skin color.

`tools/v2_skin_color_match.py` adds a measured color variant to that graph.
Natural source UV0 and the corresponding existing Geralt UV1 chart are sampled
with the observed WCC float32-to-half truncation and native pow2.2 convention.
The 15,683 interior rows produce source linear median
`(0.316338094, 0.124740945, 0.056599021)` and target median
`(0.286629487, 0.169318610, 0.173439036)`. Their fixed per-channel gains are
`(0.906085902, 1.357361928, 3.064346922)`. Those gains apply to both original
state maps, preserving spatial detail and the source's state-dependent color
differences. The physical weld retains the stock color endpoint to native
floating-point rounding; the diffuse gamma/inverse-gamma path is not an encoded
float bit-identity claim.

The native stock SSS branch is `SSS_DetailColorBleed.Color` multiplied by
itself, independent of diffuse. The variant returns that existing branch for
the anatomy, preserving complete RGBA and its exact original weld endpoint.
No albedo-dependent SSS law is invented. The strict inspector requires the
complete diffuse/SSS pair together with the complete reflectance variant and
checks the actual stock SSS wiring. Historical variants remain inspectable.

Original diffuse texels, normals, geometry, maps, UVs and state selection remain
unchanged. A conservative LOD0 base-level source UV triangle footprint with a
two-pixel gutter covers 1,605,696 texels. Both natural and erect maps remain
within linear RGB `(0.1663, 0.0815, 0.0675)` to `(0.5193, 0.3980, 0.5315)`
after adaptation, with zero clipping. Unused atlas texels include white and may
exceed one after adaptation; these bounds do not establish every native mip.
Official resave/cook and fresh native appearance/attachment review remain
required before adoption.

## October 28 accepted delivery

Body-visual-05 passed official native cook/cache, fresh production90 + LOD1 90
visual cases, full features, running/GPU pose, six performance cases, campaign
save/load and actual installed showroom/running review. It is installed and the
default grey room uses it. See [delivery and limits](VISUAL-REPAIR-20261028.md).
The earlier pending-gate statements above describe implementation requirements;
the linked delivery record establishes their final observed outcome.

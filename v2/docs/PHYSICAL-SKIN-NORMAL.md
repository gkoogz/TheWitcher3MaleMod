The physical material field uses source vertex COLOR.R as an UNORM8 weight.
Source G/B and alpha remain unchanged; stock RGBA remains unchanged. There is
no packed angle or handedness flag. The old atlas mask is not a physical field:
different surface locations reuse its texels and require conflicting weights.

`tools/v2_physical_skin_normal.py` supplies the sole HLSL function and its CPU
reference. The function consumes encoded source/stock primary normals, physical
weight, UV1, world position, and the actual raw native T/B/N interpolants. The
graph obtains these axes with three observed TangentToWorld nodes fed exact
unit-axis constants, rather than assuming WorldNormal node normalization.

Actual 2272 vertex bytecode constructs local B as normalized handedness times
cross(N,T), then transforms and normalizes T, B and N independently. There is
no Gram correction. The pixel shader linearly combines those axes. The older
world40 diagnostic reconstructed B after skinning; that is not generally the
same under a blended, nonorthogonal skin transform. The new frame oracle uses
the observed independent-axis construction with decoded captured bone poses.
It does not claim captured native GPU-palette bytes.

Raster derivatives execute unconditionally before branches. The function
constructs a UV1 cotangent frame around the normalized geometric normal while
retaining the same raw geometric-N column as the native frame. It blends the
stock world normal from this derivative frame toward the native-frame stock
response using g=w, then blends source world normal toward that result using
w. It solves the actual raw native frame to return encoded tangent space.
There is no intermediate normal clamp, normalization or angular interpolation.
The original native unpack and RNM/detail branch then execute once.

At w=0 and w=1, the original encoded source and stock inputs pass through
exactly. A flat stock tangent normal retains the model's geometric normal;
it does not substitute a stock body macro normal. Singular UV derivatives or
ill-conditioned native frames use an explicit finite encoded tangent-space
blend. RT uses that same fallback under the previously observed native guard
macros. These are declared engine material adaptations, not source physics.

The private `physical-normal-01` fixture runs the exact HLSL in offscreen
D3D11 pixel draws on WARP and AMD, without a window or Present. It tests 1,850
synthetic cases for raster and both RT guards. A separate 18,972-case fixture
uses all 31 captured bone poses, actual packed rows, all 112/92 welded samples,
and sampled source/stock normal maps for endpoint and flat-map properties.
These are math and pose tests, not a replay of native scene pixels. Actual
graph compilation, combined cache and native visual acceptance remain gates.

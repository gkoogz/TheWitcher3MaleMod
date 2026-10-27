# Source skin input port

This describes prepared source/offline inputs. It does not declare the new
native material visually accepted or installed.

The first actual B04 native test was rejected: source anatomy was invisible.
Captured vertex shaders lacked the native instancing inputs, while unchanged
stock skin retained them. That package had serialized graph data but no custom
shader cache. Official `cookmaterials pc_dx12` then exposed two build defects:
an unused declared float4 argument received the native exporter's invalid
`float4(1)` default, and the SDK omitted four shared raytracing include files.
All declared custom inputs are now bound to typed native outputs. Missing SDK
includes were recovered exactly from mutually identical embedded source copies
inside the same verified official executable, with only duplicate-include
guards added in an isolated compiler runtime. SDK files remain unchanged.

The repaired official scoped compiler completes all 1,212 unique techniques,
including skinned instancing with extra streams and raytracing. This compile
validation is recorded in `anatomy-01/build/shaders-05/compile-validation.json`;
an independent audit verifies every recovered source copy. The final native
cache is now emitted through REDkit's official `buildcache shaders` route from
the exact owned cook database and included in `package-with-shaders.json`.
Independent decompression/disassembly verifies 484 DXBC containers, including
90 skinned variants with actual INSTANCE_TRANSFORM and INSTANCE_SKINNING_DATA
inputs. The cache's 3,024 pre-processing range diagnostics exactly match an
empty stock database; no material-processing errors occurred. Its bounded
calibration receipt rejects new diagnostics or errors during material work.
The package still requires actual native selection and visual review. A
successful graph resave or technique compile alone is not material acceptance.

The original `r14_runtime.h` selects `R14-skin-erect.dds` for mechanical state 0
and `R14-skin-natural.dds` for states 1 and 2. Selection is discrete; the source
does not interpolate the two maps. The selected map feeds diffuse and SSS.
`SharedBody-normal.dds` and `SharedBody-specular.dds` supply the original spatial
normal/specular detail, at original source UV coordinates.

Exact pinned pixel-shader disassembly establishes source healthy normal decode
as `normalize((2R-1, 2G-1, 2B))`. Native PBR skin decodes `2RGB-1`, so the adapter
bakes the same source direction into that representation. Source constant c14
tiles the separate muscle/damage texture branch; it does not tile the healthy
normal/specular maps. No substitute detail texture is invented.

The initial provisional fit sampled a small stock Geralt atlas region and lost
this detail. New donor data retains every original source UV row and creates
separate body/source material groups. WCC's actual cooked half-UV stream flips
FBX V: write module FBX UV as `(sourceU, 1-sourceV)` to retain runtime source UV.
Stock body FBX UV and material remain unchanged.

`tools/prepare_v2_skin_donor.py` verifies all four canonical DDS hashes and records
both LODs' original UV/lineage and exact stock seam UVs. Generated donors are at
`v2/build/materials/source-anatomy-01`. `tools/bake_v2_skin_textures.py` prepares
natural/erect diffuse, converted normal, spatial specular and native ambient
inputs per LOD. Current final input receipt is
`v2/build/materials/anatomy-01/source-textures-03/textures.json`.

The authored material transition has three-native-unit (3 cm) support around
the cut edge. Original source diffuse bytes remain exact outside its atlas
mask. Seam normals transfer
sampled Geralt normals through the actual authored body/module tangent frames.
Eight pixels of unused chart gutter protect bilinear/mip edge sampling without
overwriting an adjacent valid source chart. Source UV aliases overlap; maximum
target UV disagreement is about .043, so a single source texel cannot satisfy
every differently mapped Geralt alias simultaneously. The strongest seam weight
selects the deterministic donor. Because those original UVs overlap, 286 module
rows outside the authored 3 cm support still sample modified seam texels; their
distance from the seam ranges from 3.0004 to 6.2604 cm, with sampled seam weight
up to .7724. Geometry and original UVs remain unchanged, but an exact 3 cm
geometric material boundary would require locally uncharting those UV aliases.
Native front/side/oblique seam review remains
mandatory; no exact seam-texel equality is claimed for conflicting aliases.

The first cached native material was visible but rejected for a metallic,
white appearance. Read-only native property inspection then established that
Engine's `Default__Texture` has SRGB=true, `Default__Texture2D` adds no override,
and the original specular, diffuse and SSS assets inherit that value. The normal
asset explicitly overrides it false. Actual target pixel DXIL decoded ordinary
diffuse with native pow2.2 but sampled source specular and source SSS as raw
encoded values. This contradicted the earlier linear-specular assumption.
Evidence is in `v2/build/materials/source-skin-audit/texture-properties.json`.
The property/default evidence supports the source sampler interpretation;
the source sampler state was not separately captured at runtime.

The corrected graph decodes SourceSpec RGB with the IEC piecewise sRGB curve,
then multiplies by the unchanged Alkali authored strength `(1,1.5,2)`. Source
diffuse is likewise IEC-decoded before the native SSS seam blend; Geralt's
stock linear SSS endpoint remains unchanged. Ordinary diffuse retains the
observed native pow2.2 path, an existing small engine approximation. The -03
specular bake decodes, blends toward stock linear F0/source strength, then
encodes, preserving original source bytes outside the transition/gutter. The
other eight input images are byte-identical to -02. No arbitrary reflectance
flattening or scaling is added. Legacy Phong amplitude and native physical
reflectance remain different lighting models requiring native review. The original
healthy Phong exponent 15 is represented by native roughness `(2/17)^.25`.
This BRDF conversion is an explicit engine adaptation, not identical lighting.
The own Ambient map stores R=seam weight times stock Ambient.B, G=roughness
transition, B=seam weight. The graph can restore Geralt's second lobe and SSS
response at the edge while retaining the source inputs over the anatomy.

New Base `normal_frame::FrameRotation(restN,restT,liveN,liveT)` captures complete
canonical tangent twist. It Gram-orthogonalizes each observed frame; a missing,
parallel or nonfinite tangent uses the byte-identical previous normal-only
rotation. The B04 adapter adopts it only for source anatomy material rows; old
B03 and stock body rows retain their established path. The source worker and
all anatomy/physics coefficients remain unchanged.

Five texture tests cover normal decode/quantization, native V/TBN orientation,
sampler direction and protected gutter. The full-frame SDK-free test covers
tangent-only rotation, rigid rotation, initial identity and fallback. Receipts
are in `v2/build/materials`; all current Base extension hashes are locked in
`v2/base-extensions.lock.json`. Official import/cook, shader binding, native
appearance, attachment matrix and installation remain separate gates.

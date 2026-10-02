# Installed REDkit rendering contract

October 2 correction: the user rejected repeated live graphics inventory probes.
Use installed shader sources first. Further gameplay observations must verify a
concrete output/lifecycle integration. Candidate observer v6 remains offline.

Primary sources are the installed REDkit's `bin/shaders/include`:
`vertexFactory.fx`, `vertexFactoryMeshSkinned.fx`, `include_computeRTData.fx`,
`globalConstantsVS.fx` and `common.fx`. Their hashes are recorded in provenance.
SDK source, native geometry and user captures are not copied into Git.

## Confirmed behavior

- Skinned stream: 16 bytes; ushort4 UNORM position at 0, byte4 bone indices at 8,
  byte4 UNORM weights at 12. Position is XYZ/65535, multiplied by QS plus QB.
- Tangent frame: 8 bytes; normal then tangent, R10G10B10A2 UNORM. Directions
  decompress as `2*x-1`; tangent W gives handedness `2*w-1`.
- **The shader normalizes skin weights by their sum.** Preserve resource bytes
  and lineage exactly; normalize when evaluating effective skin transforms.
  Raw sums 249 through 255 do not mean incomplete effective weight coverage.
- Skin buffer is vertex SRV t0. Fetch index is SkinningData.x + bone index times
  SkinningData.y. The fetched matrix is transposed; [3][3] extra data is restored
  to 1. CPU input is an explicitly decoded actor-local affine matrix, not a guess
  about live GPU memory layout.
- Frequent vertex constants are b2: QS byte 128, QB 144, SkinningData 176.
  Instanced variants can supply transforms and SkinningData separately.
- Bone matrices blend linearly. Lighting directions use that linear map and
  normalization, rather than an inverse transpose. Actor transform follows skin.

## Implemented conversion and independent SDK check

`native/skin_output.hpp` decodes native streams, normalizes weights, blends
decoded skin deltas and removes the blended transform from already posed target
positions/directions. A blend of inverse bone transforms would be incorrect.
When integrated, this permits the native shader to apply the removed transform
once. It does not prove double deformation caused the installed build's visual
problem: that build still uses the rejected reduced bone solver.

`native/skin_sdk_test.cpp` reads the actual installed packing/skinning functions
and compiles them into an isolated D3D11 WARP compute oracle. It checks all
36,547 owned vertices in both LODs, three synthetic 3D poses, mixed influences,
translation, nonuniform scaling, nonunit byte sums, palette base/stride and
wetness extra data. CPU forward and inverse output are compared with those actual
functions. Directions follow the documented linear-map-and-normalize rule.
Nonfinite results, zero weights, singular transforms and invalid indices fail.

This is a numerical shader check, not gameplay. It does not exercise the whole
vertex factory: materials, collapse variants, actor/world transforms, previous
pose, shadows and ray tracing are separate integration gates.

## Remaining output work

Float positions remain unbounded: original ushort UNORM cannot represent growth
outside its quantization box. Do not clamp. The chosen native stream/resource
backend must handle all relevant draw variants, bounds, lifetime, synchronization,
previous pose and ray-tracing data. Direction output still needs encoding for
that layout. Packed tangent decoding does not establish cooker tangent generation.

REDkit script mesh properties and SetMorphBlend declarations do not establish a
runtime arbitrary-vertex GPU update API. No C++ plugin header/library was found
in the inspected binary directory. Distinguish supported APIs from interception.
Base owns numerical anatomy/physics/controls; this format conversion belongs in
the Witcher adapter. Wolverine remains unchanged.

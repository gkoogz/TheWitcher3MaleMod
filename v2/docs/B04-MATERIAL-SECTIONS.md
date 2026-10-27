# B04 native skin sections

Development integration; not a native acceptance or installation receipt.

The original provisional graft compressed source UVs into a small Geralt atlas
patch. The new anatomy material preserves original source diffuse states,
normal/specular detail and UVs. See SOURCE-SKIN-PORT.md for decoding, native
BRDF adaptation, seam transfer and the measured UV-alias limits.

MMV2B04 retains two native resources. After source positions and normals it
stores baseline source tangents. Each resource retains its original header,
with header word 2 now storing native vertex-buffer bytes. After its eight LOD
words it stores a section count and 40-byte RenderSection records:
lod, semantic material, logical first vertex, vertex count, native position/UV/
lighting/extra offsets, physical first index and index count. Palette and
52-byte native/donor rows follow. Semantic materials are stock=0, natural=1,
erect=2; original state0 selects erect, states1/2 natural.

CPU chunk origins are logical; GPU streams and index ranges can be aliased by
WCC. The reader cross-checks both typed CPU chunks and packed GPU records.
Natural/erect variants initially deduplicated completely. The final authoring
recipe repeats one existing interior triangle only in the erect section. WCC
retains the distinct index count/range, while complete native position, bone,
weight, UV, color and normal/tangent streams remain byte-identical between the
variants. No visible surface, source geometry or physics coefficient changes.
The native material contract records this transport-only duplicate and its
actual cooked hashes. Physical collision uses stock plus one natural surface;
it does not duplicate the simulation or receiver topology.

Source anatomy rows use Base FrameRotation with observed rest/live normals and
tangents. This preserves Geralt's initial calibrated seam frame and captures
canonical tangent twist. Stock body and B03 retain normal-only transport.
Identical B04 native/donor rows are evaluated once per resource and copied to
their material aliases. A 120-frame offline comparison verifies all 78,337
output rows and all 4,279 garment vertices byte-identical to the naive path.

The parser/binder refactor also regenerates the previous B03 binding, garment,
coverage and collision binaries byte-identically. B03 and sectioned bindings
of that same old geometry produce byte-identical 43,041-row C++ outputs over
120 physics frames. These are offline compatibility checks, not gameplay proof.

New section material IDs are read from the actual native cook and normalized
through a hash-bound material-contract.json. Coverage uses 64-bit row indices:
logical state aliases exceed 65,535 even though each native section retains
local 16-bit indices. Both states retain the canonical 31,981 covered triangles
per LOD. Do not infer section origins from equal vertex positions or stale IA
slots; native draw ownership must match exact buffers and measured intervals.

The source worker remains 723865a6b294ded67146531f7056b0657da80332c40f7c321250597d1971715a.
All source geometry, numerical coefficients and canonical fitted garment remain
unchanged. Native multi-section rendering, visual attachment/LOD review,
campaign save/load, performance and installation are separate final gates.

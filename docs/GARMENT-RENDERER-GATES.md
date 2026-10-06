# Native garment draw gates

## Current soft cloth optical contract

The user's current material requirement is soft fabric with 95% optical
coverage. This is separate from persistent cloth compliance and load-bearing
contact. Shared `Material.opacity` and `Knit` alpha are .95; an adapter cannot
satisfy that requirement by writing alpha into an opaque deferred shader.

The owned `build/garment-carrier-soft6` candidate derives from REDkit's actual
`transparent_lit.w2mg`. Official scoped resave upgrades the owned copy to native
164; `tools/soft_cloth_material.py` then authors direct Opacity=.95,
Roughness=.88 and Specularity=.015 inputs. The graph retains its supported
forward lighting, Diffuse and Normal sampler paths, `RSG_Transparent` and
`RBM_AlphaBlend`. Glass refraction and reflection distortion are zero. A second
official resave compiles the edits, retaining nine actual pixel parameters.
The resulting graph SHA-256 is
`858863c94976e096509b697c06590e76e5c27a8a4e49827884ba605c4d9ed04d`.

All four rigid native material owners have been reimported with that graph.
The eight procedural textures and carrier entity are byte-identical to their
previously verified native imports. `prepare_soft_garment_carrier.py` verifies
that provenance before reuse; `prepare_garment_carrier.py --cook` selects and
validates the exact graph recorded in the job's authoring manifest. The
historical dry5 path remains independently readable.

`verify_soft_cloth_material.py` checks deterministic authoring and rejects
incorrect opacity, roughness, specularity, blend mode, disconnected normal
lighting, glass distortion and missing compiled Normal metadata. The current
proofs are `authoring.json`, `graph-resave-final.json` and
`optical-validation.json` in soft6. These establish authored native material
and compiler output. Real cook, installed draw selection and observed game
appearance remain required; offline opaque matte geometry renders do not
establish 95% native coverage.

`native/garment_renderer_test.cpp` exercises the production rigid renderer
without launching a game. Run its CMake target, then execute the binary with
no arguments for WARP and with `--hardware` for the actual graphics adapter.
The recorded hardware adapter is AMD vendor 4098/device 29772; WARP is separate.

The GPU fixture verifies four material index slices and their separate UVs,
SDK frame publication coherence, next-frame updates, character epoch changes,
Naked output and invalid actor suppression. A deliberately blocked command
queue keeps uploads in flight while observer records reset; executed bundles
transfer retained upload ownership before their own observer records reset.
Readback proves this retention after the queue resumes.

Three render targets read the final upload vertex and a rounding-edge vertex:
normal.xyzw, tangent sign, UV.xy, color alpha, position.xyz and UV2.x. This
covers the AMD full-final-record bounds requirement. UV 1.9999 and UV 0.00006
expose exponent carry and half subnormal conversions. The renderer uses the
SDK DirectX half conversion; negative tangent signs retain packed W 0.
A following native packed-input draw proves the original PSO and vertex
attributes were restored, through actual GPU readback.

The prototype 2 native entity was independently exported and inspected:
outer CEntity 1 owns component ordinals 2Ã¢â‚¬â€œ5, and embedded CEntity 0 owns 1Ã¢â‚¬â€œ4.
Both arrays point exactly to ribbed, elastic, red and blue mesh depot paths.
This proves authored native structure; cook and gameplay remain separate gates.

## Native fabric material repair

The material gate distinguishes source pixels, native graph traversal, native
import/cook, selected installed bytes and observed game appearance.

### Failed stock wetness graph candidate

The official REDkit dump of pbr_std shows that Roughness is an output socket,
not an exposed scalar material parameter. Its roughness path is Normal alpha
through the graph's wetness processing. Specularity has a separate path:
(1 - Normal.a) * RSpecScale + RSpecBase, multiplied by linearized SpecularColor,
then processed for wetness. Changing RSpecBase cannot set cloth roughness.

The matte4 candidate supplied actual Diffuse and Normal handles with
Normal.a=224/255, RSpecScale=.12, RSpecBase=0 and wetness_switch=0. Native imports
and real cook retained all five supported parameters. All 21,847 imported BC3
blocks and all 87 resident cooked blocks per normal texture decoded alpha224.
The packet and four packed buffers were byte identical to prototype2.

uild/garment-carrier-matte4-final/package.json records Base
99ff741ea95f18ed84526c35a6c3f38a37d857b6 and package
publish/20261003-174227-f0af50. The private session
uild/probe/sealed-session-20261003-174824/receipt.json selected those exact
installed content hashes, yet captured gold/brown reflective fabric. This
candidate failed visual approval. There were no competing garment namespace
resources in installed mod bundle indexes. Automatic wetness is a possible
contributor, not a proven explanation of the failed appearance.

### Owned dry-cloth graph candidate

	ools/prepare_garment_carrier.py derives an owned graph from the official
pbr_std_no_wetness.w2mg, leaving the SDK source untouched. The stock dry graph
also requires adaptation: its authoritative unnamed output scalars are
Roughness=.1 and Specularity=.2, and its deferred Normal input is disconnected.
The author changes those structurally identified scalars to .88 and .015 and
connects the existing supported Normal texture sampler, normal decode and
TangentToWorld chain to the deferred Normal input. This provides the procedural
rib normal while avoiding automatic wetness blocks.

Each socket owns a separate reciprocal CGraphConnection export. The recipe
serializes both directions and rebuilds affected export offsets/counts, child
CRCs, export table CRC and header CRC. Its reader checks bounded native tables,
property widths and authoritative traversal. Cook validation requires the
actual output scalar roles and the reciprocal Normal chain, rather than assuming
source declarations survived. No runtime shader override or image generation
is used. Texture generation and native material authoring belong to this adapter;
shared garment dynamics and geometry remain in the pinned Base.

The official native dump and all four native mesh imports succeeded for
uild/garment-carrier-dry5-final, an owned junction to E: build storage. Actual
material instances retain exactly Diffuse and Normal handles using the owned
characters/malemod/garments/cloth_dry.w2mg. The cook was initially stopped by
the strict dirty-Base gate while shared fabric dynamics were being developed.
It must be repeated on the final clean pin. No cooked or gameplay claim follows
from the import checkpoint.

CharacterNormal/TCM_Normals lost the authored alpha during native encoding.
The supported CharacterNormalmapGloss/TCM_NormalsGloss group preserved alpha224
and measured normal RGB115..140/125..130/255. The channel receipt is
uild/probe/garment-gloss-encoding/proof.json. Every new cook verifies all
imported mip payloads and the resident cooked chain. High-mip texture-cache
blocks are not independently decoded by this reader; the native cache-builder
receipt and actual rendered fabric remain separate required gates.

Source authoring initially preserves the graph's opaque compiled payload.
Structural traversal alone cannot refresh that cache. The recipe therefore
requires official `resave`, limited to our single graph namespace and the w2mg
extension, with local source control disabled and an owned temporary directory.
The actual dry5 resave scanned one graph, saved one and copied it only into the
owned readthrough depot. Its compiled payload changed; pixelParameterBlocks
increased from five to six and now includes Normal. The recipe validates the
authoritative constants and complete Normal chain again before copying that
actual native output into the authoring intake. Cook validation also requires
the compiled Normal parameter. The completed local evidence is the
`officialResave` entry in `graph-authoring.json` and `authoring.json` beside the
intake, also extracted as `graph-resave-final.json`. The earlier standalone
`graph-resave.json` records a command checkpoint whose cache was unchanged;
it is not the completed compiled-Normal proof.

The real cook, its actual graph/material bytes, and private game appearance
must still establish final delivery before visual approval. A successfully
resaved graph does not by itself prove which shader a game draw selected.

### Continuous-sheet topology adoption

The four authored native carrier meshes are rigid ownership sentinels with
192 vertices and 384 index bytes each. They do not contain the shared pouch or
strap topology. The dynamic renderer uploads the actual output mesh and splits
its triangles by the four supported material slots, so replacing the old radial
shell with the measured continuous sheet does not require reimporting sentinel
geometry. The new sheet must publish explicit `Output.layout` ranges and seam
indices; its adapters must validate those ranges without old radial offsets.

The dry5 material authoring/resave checkpoint is reusable for this topology.
Its real cook remains blocked until the shared geometry and dynamics have a
clean, adopted Base revision. Fresh static previews will record the measured
MMGRB003 semantic packet, current shared header hashes, MMGFC005 inputs, actual
layout and contact status. They are offline geometry previews with desired
matte colors, not evidence of native material appearance or accepted dynamics.

## October 4 bounded playable-material check

The unchanged compiled soft6 graph was freshly revalidated, including
deterministic authoring and seven negative optical contracts. A real cook is
blocked by the strict clean-Base gate: locked99ff741 has tracked source edits.
Do not replace the requested alpha fabric with an opaque path.

The fingerprint reader formerly inferred six records for every garment.
Official native opaque sentinels have six records (two full lighting LODs and
four reduced passes); the measured forward alpha sentinel has two. The bounded
decoder now reads the actual two/six-record payload and native LOD order. Three
fixture tests and six actual official resources pass; full lighting records
and stream fingerprints remain byte-equivalent. Both observed paths have
8/4/8/8 stream strides, so no speculative C++ layout change was made. The new
soft6 cook must still establish its own actual packed layout.

An exact E-backed intake is ready at build/garment-carrier-soft6-cook-ready,
with ready-proof.json binding copied assets to soft6. After committing shared
source and intentionally updating dependencies/base.lock.json to its clean
revision, run from this adapter:

```powershell
& 'C:/Program Files/Python310/python.exe' tools/prepare_garment_carrier.py build/garment-carrier-soft6-cook-ready --cook
```

The cooker validates actual graph, normals and rigid meshes, writes
garment.render, material-proof.json and package.json. Regenerate fingerprints
with that package's actual cooked garment directory. Verify selected native
PSO/input restoration and observed fabric separately. No package was cooked,
installed or observed by this bounded task. Native proof is
build/probe/soft6-playable-material-check/proof.json.

## Actual soft6 material-only cook â€” October 4

The earlier clean-pin blocker is resolved. Official REDkit cooked and packed
soft6 at actual Base377c59d21d7c0c624c73d73e31fd1f89449e5e17 into
`publish/20261004-152629-b38b16`. Package integrity checks all five game files.
The later metadata-only Base88c7a2a commit does not change this cook provenance.
No game install or observed opacity is claimed by these offline checks.

The cooked graph deliberately removes editor sockets and lighting blocks.
`inspect_cooked` binds the actual runtime9 parameters, values, resolved texture
imports, parameter offsets, cooked flags and Transparent/AlphaBlend enums to the
exact official-resaved source and compiler receipt. The requested95% opacity,
.88 roughness and.015 specularity are verified on that compiled authoring graph;
they are unnamed baked constants, not cooked editable scalar parameters.
Five runtime mutation negatives and seven authored optical negatives pass.
Finalization also verifies every source asset against the actual native cook
input and retains the package manifest's original Base commit. Use
`--finalize-package publish/20261004-152629-b38b16` to verify the existing cook
without rebuilding it. Source/compiler bindings do not prove native pixel output.

Actual `forward-abi-proof.json` confirms each of four soft6 materials has two
full lighting LODs with measured8/4/8/8 streams and no bone palette. The116-byte
MMCLT001 packet is byte-identical to the prior installed matte4 packet (SHA256
6ff3b309e8bc4b82afc32d5c5ff0c1cb84ff4e5bda93e2cdcc979c1ea99ae84b).
Fresh209 fingerprints are in
`build/full-runtime/fingerprints-soft6-377c59d-material-only`. A material-only
adoption must preserve all existing non-garment records and runtime binaries.
The authoritative material job is `build/garment-carrier-soft6-cook-ready`;
its package/material/ABI/negative receipts separate cook, source constants,
runtime metadata, and observed gameplay. Native appearance remains a game gate.

The observed cooked graph trailer has an encoded shader count0 while the
compiled authoring graph has2868. No cache requirement was inferred from that
field. The official buildcache help calls did not expose a shader-builder
contract. Existing prior cook outputs contain no graph resource to compare,
so they do not establish a shader-count equivalence. Actual native appearance
must resolve readiness; no opaque substitute was created.

### Explicit instance correction

The first soft6 cook is diagnostic and is not approved for material adoption:
its exposed named Opacity default remains zero and its four material instances
only serialize texture handles. Although the authoring output uses a direct.95
constant, source linkage alone does not establish live runtime opacity.
Soft7 explicitly imports Opacity Float.95 on all four owned instances. The
parser requires the exact type/value along with both native texture handles;
zero, missing and wrong-type instance opacity are rejected. Roughness and
Specularity are not exposed in the actual nine named runtime parameters, so
no unsupported instance names are invented for them. Those remain the exact
compiled graph constants. Native appearance remains unobserved until gameplay.

### Fresh soft7 material-only candidate

Official cook/cache/dependency/bundle/metadata commands all succeeded at actual
clean Base7f961e31294a1dec4ef8d230a1b4a3bff9fd6b76. The fresh package is
`publish/20261004-161401-0e89a0`; five native game files pass integrity. Every
actual cooked CMaterialInstance explicitly serializes Opacity Float
.949999988079071 with the exact existing Diffuse/Normal texture handles.
The source/compiler graph bytes remain unchanged; this is a fresh instance
correction and correctly has fresh cook provenance, not the prior377 pin.

Authoritative receipts are in `build/garment-carrier-soft7-opacity`:
`package.json`, `material-proof.json`, `forward-abi-proof.json`,
`material-only-final-proof.json`, `cooked-optical-negative-proof.json` and
`explicit-opacity-negative-proof.json`. The actual forward four-resource ABI
has two full LOD records per material and measured8/4/8/8 streams. The116-byte
MMCLT001 packet and complete209-record draw fingerprint packet are byte-identical
to the installed99ff runtime. Fresh fingerprint source hashes are in
`build/full-runtime/fingerprints-soft7-7f961e-material-only`.
This candidate can therefore be explicitly adopted as a five-file native
material-only patch while retaining existing99ff binaries, controls, geometry,
physics, packets and non-garment fingerprints. This task did not install or
launch a game; appearance, actual composited opacity and live draw restoration
remain separate observed game gates owned by the delivery agent.

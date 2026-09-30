# Anatomy skinning test 0.3.0

This version fits the actual Base reference anatomy into Geralt's bare lower
body. It retains the large source reference shape and uses native pelvis/nearby
body skinning. Secondary motion, live dilation, fluid simulation, body sliders
and the requested hotkey are not part of this test. The diagnostic console popup
does not provide those controls.

## Ownership and recipe

Base owns `surface.rest-graft`: loop correspondence, original-edge donors,
sparse source lineage, harmonic rest fitting/attribute fields, orientation
repair and deterministic skin influence limiting. Its revision is pinned in
`dependencies/base.lock.json`. These are reusable for future spokes.

This adapter owns `characters/geralt-attachment.json`, the native FBX transport,
observed bones, stock skin material mapping and REDkit packaging. `tools/wcc_fbx.py`
preserves unknown native-export properties, skeleton transforms, embedded data
and materials. An unedited stock FBX round trip was byte-identical. It is a
narrow editor for the observed WCC format, not a general FBX evaluator.

The fit maps source +X forward into observed Geralt +Y forward. It measures the
source open-boundary width and scales it to an authored target width of 10 raw
FBX units. This is a selected large fit, not a claim about the original source's
physical units. FBX unit metadata and bind transforms are preserved.

The module boundary is subdivided against actual body-edge donors, the body
patch is removed, and the fitted seam is continuous. UV aliases remain separate
render vertices with identical positions and skin weights. Every generated
vertex and face retains source lineage in adjacent local binding NPZ files.
The source pressure/support bank is pinned in Base and remains intact.

Both native LODs use the full source module topology. Final native triangle
counts are 36,738 and 35,926. Local orientation repair is bounded to 1.25 raw
export units; observed maxima were about 0.225 and 1.023. The resulting faces
have positive orientation against their reference normals. This is not a global
self-intersection proof. Skin interpolation is limited to the four influences
observed in the stock mesh, with worst discarded weight about 3.88% and 7.18%
on newly generated vertices. Original body weights remain unchanged.

The first material pass uses Geralt's stock skin. Source UV variation is mapped
into a small local region of that atlas, with exact seam UV/color correction.
It avoids a constant UV field and retains native tangent generation. Full
source anatomical material transfer and distant module reduction are follow-ups.

## Separate torso and legs

The lower body is a separate stock resource, but it shares Geralt's skeleton
with the torso. All 34 high-detail waist vertices have exactly matching named
bone weights in the nearest torso samples. Stock position differences already
exist (maximum about 0.128 raw export units). Coarser LOD tessellation differs,
so nearest-vertex comparison is not a complete boundary correspondence.

This fit preserves the original waist and ankle positions, UVs, colors and skin
weights; it does not create a new torso cut. Outer normals are preserved. A
future expansion that reaches the waist must coordinate both resources through
shared boundary constraints, as described in Base's `docs/REST-GRAFT.md`. Until
that bridge is implemented, the waist is fixed. Do not move one part and assume
the other will follow.

## Rebuild from a fresh checkout

Install Base's Python requirements, configure local game/depot/SDK paths and
resolve the exact Base lock. Then:

```powershell
python tools/mod.py doctor
python tools/mod.py attachment
python tools/mod.py build
python tools/mod.py verify
```

`attachment` exports missing stock inputs, pins the native source hash, fits the
shared module, imports through official WCC, exports it again and checks native
topology, bone lists/bind matrices, skin weights, seam aliases and unchanged
outer boundaries. Changing profiles/tools during preparation fails the build.
Replacing an earlier generated mesh requires a matching owned import record;
it backs up the previous mesh and restores it if native preparation fails.

`generated/attachment.json` ties the exact Base/profile/tool/FBX/binding/native
hashes together. Packaging rejects stale inputs, changed artifacts or missing
native verification. All game-derived outputs remain ignored. The native
resource overrides `characters/models/geralt/body/model/l_01_mg__body.w2mesh`;
the existing default-underwear entity override points to that bare mesh. Any
other appearance using this same dry bare mesh also receives the fitted model.
Armor-specific meshes and the wet mesh have not been replaced.

## Installation and user check

This version is installed locally. All five files matched the verified package;
native unbundle recovered the cooked mesh, its external vertex buffer and the
entity override byte-identically. The previous 0.2.0 package is retained in local
rollback storage. Actual appearance/movement of this new model remain unobserved.

Use the managed install/uninstall commands only after package verification.
Uninstall checks ownership/hashes and retains the previous mod in local recovery
storage. See `provenance/anatomy-test.json` and ignored `local/installation.json`
for the actual deployment checkpoint; a cooked package alone is not an install.

Restart the game, equip then remove trousers, and check the front/side view,
waist and pelvic seam, walking/rolling, inventory, armor restoration and a more
distant camera. Native round-trip and offline posed seam tests passed; actual
appearance and animation still require user observation. This is a fixed shape
that follows the character rig, not a functioning secondary-motion simulation.

## Backflow to Wolverine

The new fitter, exact donor/alias checks, bounded orientation repair and skin
sum preservation can strengthen Wolverine's future authoring/export workflow.
Offer that backport after this spoke's user test. The original Wolverine native
runtime and Base's immutable legacy snapshot were not changed. Its active final
unified collar remains the dynamic reference; this rest fit does not replace it.

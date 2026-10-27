# Local stock LOD1 waist repair

The final602 native review found a slit at the stock upper/lower waist, above
the Wolverine graft. The original lower LOD1 rim has22 geometric points and
the upper rim33. Rest upper-to-lower chord distance reaches4.744mm; actual
captured side poses reach4.81mm. LOD0 reaches about0.52mm and stays unchanged.

The selected repair replaces only52 incident stock LOD1 lower faces with63,
preserving the original interior diagonals and splitting boundary faces at
the missing upper samples. It appends34 upper attribute rows, preserving the
upper atlas split. All original authored arrays stay unchanged; the23 old
outer corner rows become inactive and official WCC drops them. Active native
LOD1 stock rows consequently change574→585 and triangles891→902. Source
anatomy, source graft, LOD0, upper body and original material/texture/shader
inputs stay unchanged. An initial free annulus and unnecessary Steiner trial
were rejected; neither is an input to this package.

`tools/prepare_v2_waist_join.py` performs topology-aware oriented matching of
the original native52 faces to authored faces. Its saved-FBX scope audit
checks9869 properties: every unrelated encoded property and all original
vertex/skin array prefixes are exact. The final corner proof preserves the
removed waist face's torso chart at the bottom and the upper body's retained
chart at the top, including the single original whole-edge atlas seam.

The official cook regenerated packed tangents on32 existing stock rows and
three shared graft rows per LOD1 source state. These raw-cook exceptions are
recorded, not described as unchanged. `tools/v2_waist_binding.py` restores only
the38 affected existing packed tangent words from the frozen350c binding. The
new34 top rows copy the actual upper binding's source CSR, packed N/T and
weight bytes, remapping the same named bones. This occurs before the existing
source precision and lighting stages. Appended stock rows bypass module CSR
indexing. No runtime geometry law or canonical numerical code changes.

The final B04 binding is9725f35b76554213daf4c884dc0374701fa501bcdd14b3028d807ab476ca819c.
All78314 existing active52-byte rows match frozen350c exactly. A freshly compiled
current SourceBinding fixture replays31 actual feature poses and18 jock poses
from both native banks. Every protected world position/normal/tangent/handedness
frame is byte-identical. The new upper/lower join gap is at most3.932µm; N/T
component error is at most3.13e-7. All63 faces remain outward.

The new lower surface continues an existing inner-band contact: unchanged
upper face1058 already intersects inner cloth faces5704/5705 in the affected
pose. The full-body contacted band-face set does not expand in any of18 poses.
No outer visible band triangle intersects the candidate; prototype exact outer
triangle separation is at least2.233mm. Existing covered pouch contacts remain
recorded. This is not a claim of global zero cloth/body contact.

Prepared output is `build/materials/waist-join-01/bindings/prepared.json`,
SHA59ae8201aac8712edd4f729cf754e9f4b59852f11e07614d6ca89c482f020c6e,
against package-with-shaders SHAe288193838518006f640bd354a60c67cf2acaf425a97d6d1141c64553f669b93.
Its17-file inventory embeds waist calibration provenance in the existing
manifest. The9002 garment samples preserve all weights/offsets; only global
upper row IDs shift11. Render bone script and canonical worker stay unchanged.

Evidence is under that job: `authoring-scope.json`, `native-waist-audit.json`,
`initial-pose-proof/proof.json`, `final-binding-proof.json`, and the explicit
stock upper Min.W/Max.W metadata equivalence receipt. Native upper GPU bytes
are exact; only unused Box W words and derived CRCs differ. No file bytes were
patched to force equivalence.

This is a prepared offline/native-cook candidate. Root still owns adoption,
module staging, fresh native visual/feature/LOD/performance/campaign gates and
installation. Passing these proofs alone does not accept or install the repair.

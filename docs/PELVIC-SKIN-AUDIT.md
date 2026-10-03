# Skin correction and radial graft checks

The shared color-transfer and refinement algorithms live in the pinned Base.
Witcher owns the measured Geralt UV samples, resource layout, native import and
cross-resource render delivery. Wolverine source and installation are unchanged.

## Deterministic skin matching

The adapter samples both sides of the original fitted attachment seam rather
than choosing an arbitrary beige color. The current 68 corresponding UV samples
produce linear-RGB gains of approximately `[0.75452, 0.94602, 2.03187]`. Applied to
the original detailed R14 diffuse texture, their median encoded RGB matches the
Geralt samples: median color error decreases from 38.704 to 0.0 RGB units. This
measurement describes the diffuse input, not the appearance under every game
light. The alpha and normal-map inputs are separate; no generated artwork is used.

Imported material reuse requires the exact Base pin, stock/source/native hashes
and original authored-atlas hash. A diffuse reuse also requires its measured
skin-match receipt. Newly generated diffuse receipts pin that receipt's hash.
An interrupted cook records each successful import immediately; an unreceipted
XBM is rejected. This prevents old uncorrected texture bytes from being assigned
new provenance merely because a file exists.

The original input-only audit did **not** establish native material correctness.
The observed pale, smooth result prompted official native XBM inspection, which
found the normal atlas imported with the default `WorldDiffuse` group and
`TCM_DXTNoAlpha` compression. Geralt's actual native normal uses
`CharacterNormal`/`TCM_Normals`; its diffuse uses
`CharacterDiffuse`/`TCM_DXTNoAlpha`. The import recipe now specifies those measured
groups and verifies the official dump after every import. The audit rejects
cached assets whose receipts do not prove the correct native encoding.

Corrected character material job:
`build/body-boundary/radial-skin-character-3`. Actual cooked UV0 agrees with the
authored atlas convention, including WCC's V flip and native half-float rounding
(maximum differences 0.00048682/0.00048659 in the two LODs). The corrected material
input audit is `build/pelvic-skin-character-3-audit.json`. This adds native
encoding/UV verification; observed appearance is still a separate final gate.

The private character-3 screenshots still showed an overly pale, smooth module.
The official `pbr_skin.w2mg` graph was then dumped in
`build/material-graph-agent/intake/pbr_skin.w2mg.xml`. Its `Ambient` texture is
packed material data: R masks detail normals, G provides base roughness and B
drives specularity. The previous white module tile was therefore not neutral
AO. At the same 68 stock attachment UVs the measured median is R=241, G=148,
B=22; white had forced roughness/specularity inputs to 1 instead of approximately
0.5804/0.0863. The updated recipe transfers those actual character material
channels while preserving source diffuse detail, corrected normal encoding and
the complete geometry. It records `ambient-match.json` and pins that receipt's
hash in native material provenance. A separate native package is
`build/body-boundary/radial-skin-packed-4`; its visual result requires an observed
game check. The earlier character-3 audit is not proof of resolved appearance.

Observed material check: private session `sealed-session-20261003-070156`,
PID 29140, screenshot `screenshot_7344.png` (Overall 100) shows a pinker skin
tone matching the nearby inner thigh and visible fine pores. The earlier
`screenshot_63314.png` had a chalky, smooth appearance. Diagnostic crops are in
`build/material-graph-agent`. This is an observed improvement under this scene's
lighting, not a claim that source anatomy shares Geralt's scars or that every
lighting condition is pixel-identical. The actual stock Ambient native resource
also independently confirms `CharacterDiffuse`/`TCM_DXTNoAlpha` in
`build/material-ambient-group-agent/intake/geralt_a01.xbm.xml`.

The graph also establishes that COLOR.B controls `ReflectionGainScale`, and
COLOR.G controls `AntiLightbleedScale` (Geralt sets the latter to zero). These
are not direct albedo tint channels. The native diffuse chain converts gamma
to linear, applies detail, converts back to gamma and applies `customColoring`;
the stock `VarianceOffset=1` makes that final color operation an identity.
No speculative vertex-color tint or image generation was added.

`tools/stage_body_material_patch.py` creates a fresh priority package while
preserving runtime contracts and selection. It checks all thirteen native
body/Overall buffers, stream descriptors, quantization, palettes, inverse binds,
material-instance handles and spatial XYZ bounds against the selected package.
The geometry and skin bytes are identical. WCC recooking changes some serialized
fourth bounding-box components; these bytes are recorded explicitly, rather
than describing the entire mesh header as byte-identical. The tool does not
install, copy Release files or edit `current-install.json`.

Supported shadow-policy experiment: official SDK
`r4data/scripts/engine/CEnvironmentDefinition.ws` declares the CMesh Bool
`mergeInGlobalShadowMesh` separately from the chunk's `useForShadowmesh` Bool.
The original official Geralt lower-body export sets the merge flag true. The
isolated `radial-skin-shadow-policy-5` job changes only that import flag to false
and native cooking confirms an explicit false Bool. Its thirteen geometry
buffers, cooked render layouts, palette/binds, material children and decoded
chunk properties are identical to packed-4. The name pool changes because the
false property becomes explicit; `stage_body_material_patch.py
--allow-shadow-merge-policy` permits only this measured metadata difference and
still checks the unchanged native chunk shadow eligibility. This is a diagnostic
for stale merged shadow geometry, not a confirmed artifact fix or suppression
of shadow casting. The normal authoring recipe remains unchanged until an
observed game result justifies adopting the policy.

## Radial recruitment and the two-resource waist

The source worker evaluates the active final UnifiedCollar radial law at actual
Geralt rest-body queries. The combined target solve includes lower body, upper
body and the anatomical attachment. Both sides of the native waist consume the
same 37 positional and skin masters in both LODs. Local triangle refinement
preserves convex sparse source lineage and distinct material UV aliases; the
attachment still satisfies its original straight-edge donor constraints.

The dedicated actual-asset audit checks those constraints and rejects collapsed
authored triangles. The existing `body_render_test` separately exercises 39
complete source control cases and checks the native position, named byte-weight
and shading welds, parallel delivery, presentation, pause and character epochs.
Its current maximum Overall case moves the torso by 0.0493421 and waist by
0.0458658 native units. These are measured outputs, not an invented unit mapping.

Run from the adapter root:

```powershell
python tools/verify_radial_materials.py --job build/body-boundary/radial-skin-packed-4 --output build/pelvic-skin-packed-4-audit.json
python -m unittest discover -s tests -p test_body_material_receipts.py -v
```

The audit writes only an ignored owned build report. It does not install, change
a game, or claim observed gameplay. The current report is
`build/pelvic-skin-packed-4-audit.json`; current native range proof is
`build/full-runtime/body-render-radial-test.txt`. The rear black patch and actual
game rendering remain separate checks; positional weld correctness alone does
not prove either one.

## Intermediate size and ramp geometry

`native/radial_progressivity_probe.cpp` exports independently initialized source
and target states using a fresh numerical worker for each state. The associated
`tools/verify_radial_progressivity.py` audits Overall 25/50/75/100, small changes
around 75 and 100, individual shape extremes and combined maxima. The current
28-state evidence is `build/radial-quality-agent-4/quality-verification.json`.

Recruitment support grows from 867 to 947 to 1,030 to 1,553 Geralt query points;
the source radial target actually displaces 66, 93, 235 and 465 points as the
annulus expands. Both native waist halves/LODs follow that direct source radial
field to a maximum difference of `1.04e-16` native units. Around Overall 75,
the left/right maximum body displacement derivatives are `0.000534` and
`0.000537` native units per UI unit. These measurements add a progressivity and
continuity check to the preexisting native range/weld tests.

All 28 states retain finite noncollapsed body triangles. The minimum area ratio
is 0.06644 at combined maxima. Ten front-body ramp checks at Overall 25/50/75/100
and combined maxima find zero strict nonadjacent triangle crossings. The test
excludes shared positional aliases and ordinary edge contact. It is not a global
intersection proof and does not test coplanar overlaps, body/anatomy collision,
or actual animated poses. Reversal relative to a rest normal is reported as
rotation rather than automatically interpreted as inversion: radial recruitment
can legitimately turn a rim around the barrel. No limiter or suppression of the
source ramp was added.

```powershell
python tools/verify_radial_progressivity.py --artifacts build/radial-quality-agent-4 --job build/body-boundary/radial-skin-2
python -m unittest discover -s tests -p test_radial_progressivity.py -v
```

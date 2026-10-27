# Optional source-interior lighting experiment

`bind_wolverine_v2.py --source-lighting --source-lighting-cases <checkpoint-dir>`
is an explicit, default-off experiment. Ordinary B04 output retains the adopted
precision-only binding. B03 never receives this operation.

`v2_source_lighting.py` matches original UVs and oriented topology against the
authoritative fitted mesh. It transforms the raw canonical source normal and
tangent through the actual placement rotation (determinant +1), then encodes
them in native 10-bit lighting words. It does not normalize or Gram-adjust the
reference vectors, alter source geometry, change runtime frame math, or touch
stock body/shared seam lighting. Native encoding still clips and quantizes.

The source frame uses normal.w times cross(normal,tangent). Its sign is preserved
through the proper placement rotation. The shader's three independently
interpolated basis vectors are not exactly representable by native normal and
tangent plus cross-product reconstruction on every refinement row.

Three imported geometry-donor aliases have different source lighting frames.
The primary optional candidate corrects two aliases within a conservative
30-micrometre captured-case policy and holds the third. A separate diagnostic
candidate corrects all three using authoritative UV/topology correspondence;
its third correction reaches 66.82 micrometres dynamically, explicitly exceeding
that primary policy. Both preserve source position baselines, skinning, UVs,
cooked geometry and worker bytes; corrected aliases affect dynamic delta transfer.

Actual SourceBinding evaluations over 31 captured source cases validate 4,428,164
main-body triangle cases. Both candidates preserve all 259,439 protected dynamic
row comparisons byte-identically. The primary introduces no new bad faces but
retains eight pre-existing triangle-case defects. The all-three diagnostic removes
all eight and introduces none. Its maximum source-expected position error is
5.90 micrometres. Normal direction error is at most 0.175 degrees; tangent P99 is
0.661 degrees, but a 20.91-degree extreme remains because the existing rigid Gram
frame delta cannot reproduce every change of raw source nonorthogonality.

Proofs are under `v2/build/materials/source-tbn-study`, in separate `experimental`
and `diagnostic-all-aliases` directories. They are CPU pre-skin comparisons of
actual source banks, not captured GPU or bone-pose replays. Neither candidate is
adopted or visually accepted. The current normal-RGB material fix removed native
skin bands without this experiment, so that successful result does not depend
on optional lighting restoration.

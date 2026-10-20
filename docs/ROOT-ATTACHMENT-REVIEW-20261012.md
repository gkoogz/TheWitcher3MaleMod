# Native root attachment reproduction

The requested repair retains the selected Original baseline's surrounding
anatomy, preserves shaft dimensions, and increases lower attachment support at
Overall / Length / Width 100. The underside needs additional clearance where
the raphe joins the pelvis. The upward-angle saddle is also in scope. Treat
these as adult anatomy teaching geometry requirements; see PROJECT-CONTEXT.
Show reviewed geometry before adopting a replacement runtime.

## Observed installed baseline

The user saved and closed their game before the isolated test. The maintained
grey platform ran the installed runtime in a private Windows station, without
host input or focus changes. Twenty-four native views covered six cases:

| State | Overall / Length / Width | Angle |
| --- | --- | --- |
| Erect | 100 / 100 / 97 | 15 |
| Erect | 100 / 100 / 100 | 15, 25, 35, 50 |
| Relaxed | 100 / 100 / 100 | 25 |

Other fixture values: glans 35, scrotum 100, hang 95, forward 100, vertical 50;
physics controls 50 except the final velocity control 51. Every case has front,
side, oblique and low-oblique captures. These are moving native samples, not a
paused reference pose or an exhaustive motion/LOD matrix.

The root narrowing and upper crease are plainly visible at upward angles.
Earlier relaxed-state, bind-pose previews are insufficient acceptance evidence
for this erect-state defect. Matching Angle alone does not reproduce state,
physics or animation. The observed output included both body resources and
49,884 vertices at every checkpoint. The full attachment gate is not passed.

Private receipt: `build/probe/sealed-session-20261012-024712/receipt.json`.
That directory contains `native-review.json`, `checkpoints.jsonl`, original
frames and `native-review-sheet.jpg`. The exact private child was closed,
scoped audio restored, temporary driver/platform files removed, all 24 original
save files verified, and saved controls remained byte-identical. The installed
DLL remains `9089e7342af9484b6f22bcd042de31e687f4e7568ddcd72c75e682da123daace`.

## Diagnostic changes are not an accepted repair

Private job: `D:/MaleModBuilds/witcher-ventral-support-20261012`.
Tracing lower boundary samples in the earlier relaxed Angle25 fixture shows
that the final attachment solve raises them roughly 8-9 cm from their recruited
targets. That is an offline stage measurement, not a measurement from the new
native erect-state captures.

Prescribing the lower or entire recruited boundary creates new ridges. A
section-radius floor with exact donor and posed-orientation constraints also
produces unacceptable local shape despite zero projected face reversals. These
tests are rejected, not installed. Do not promote their private source, test
executables or successful numerical checks as a geometry fix.

## Reproduce from repository source

`probes/native/collar_root_cases.ws` is the diagnostic source recipe. It uses
the maintained room bootstrap and existing native control/checkpoint APIs.
It also requests native deformed-vertex snapshots at checkpoints 75, 82 and 83
for the first erect, maximum-size Angle25 erect, and Angle25 relaxed side views.

Run `python tools/prepare_collar_session.py --root-review`, then launch an
integrity-verified platform package with `tools/run_iteration_world.py`, passing
the generated `build/collar-sessions/root-review/workspace/scripts/local/malemod/collar_integrity.ws`
and `build/collar-sessions/root-review/compile.json`. Use the returned receipt
with `--close` afterward. Keep captured meshes, settings and frames private.
Rebuild missing generated package resources through the official tool; do not
skip integrity checks or inherit another session's visual acceptance.

Shared geometry changes belong in Base, with pinned adoption by Witcher and
Wolverine. This checkpoint adds a reproduction fixture, not a new shared
algorithm, dependency pin, release or accepted replacement installation.

A second native session, `build/probe/sealed-session-20261012-030150`, captured
three 49,884-vertex deformed upload streams. Their FNV hashes exactly match the
native checkpoint telemetry. `mesh-captures.json` records controls, pose times
and hashes. Its child/audio/temporary files, 24 saves and controls were also
verified restored. The repository root-review recipe compiles successfully
with the official native-aware script compiler.

## October 12: captured waist and solver-stage trace

Private evidence: D:/MaleModBuilds/witcher-waist-trace-20261012.
`tools/decode_native_body_capture.py` now decodes the actual 28-byte upload
through its resource calibration. Upload positions are normalized resource
coordinates, not metres. It verifies the upload FNV, retains uploaded bone
remapping, and reports pre-skinning positions; these are not posed screenshots.
Three captures (stages75/82/83 of session030150) match recorded upload hashes.
Across both LODs the shared waist's maximum decoded alias gap is below
3.8e-8 metres. Do not reuse raw normalized coordinates as metric positions.

The baseline evaluator reproduces the original saved15 static buffers byte
for byte. For saddle triangle14064, removing ONLY the waist prescribed rows
moves the centroid -0.963mm forward, +3.014mm lateral and -0.659mm upward.
It also displaces other vertices by14.275mm/10.456mm in LOD0/1. Releasing the
waist is not a repair. The proposed1mm waist perturbation could not pass the
signed-area guard; no successful1mm Jacobian measurement is claimed.

Separate dumps before and after orientation projection show that at lower
collar sample886 (LOD0), the curvature solve moves up90.718mm; orientation
projection moves it zero. The selected upper sample's projection is also zero.
The largest projection correction anywhere is0.440mm at LOD0, zero at LOD1.
Absolute fairing is therefore a measured contraction contributor independent
of the waist alias binding and the subsequent triangle projection.

Moment-preserving and posed-ring candidates do not pass: some move lobe-core
material by27-30mm, and visible seams/ledges remain. A full donor constraint
also failed LOD1 signed-area convergence. Subsequent private radius-support
and explicit seam-tangent experiments remain unaccepted. `compose_delta.exe`
is only a diagnostic frame transporter, NOT a native orientation check.
`compose_native.exe` in this study exercises the actual native composition
and guards, but is still offline. All study renders must be labelled offline.
No new candidate has been installed or observed in the game. The existing
accepted runtime, dependency pin, bindings and rollback remain authoritative.

## Full angle-slider regression

`tools/prepare_collar_session.py --angle-sweep` composes the maintained private
room with 16 slider values: 1,5,10,15,20,25,30,35,40,45,50,60,70,80,90,100.
It covers all three states at Overall/Length/Width100, four cameras per case,
and checkpoints300-491. `tools/record_collar_angle_sweep.py RECEIPT` rejects
missing/reordered views, incorrect controls, stale surface sequences and
missing body resources. It records 192 ordered frames without claiming visual
acceptance. This is angle coverage at maximum size, not the complete attachment
gate across size, motion, LOD selection and campaign transitions.

The private per-operator arc-release experiment completed 48 offline cases;
see `D:/MaleModBuilds/witcher-waist-trace-20261012/angle-sweep/summary.json`.
Six target solves failed signed-area constraints: state0/Angle1;
state1/Angles1,5; state2/Angles1,5,10. Protected exterior displacement was zero,
but lobe-core displacement reached62.142mm. Reject this candidate. Source-side
changes also alter fitted mechanical lobe parameters, so retaining exterior
vertices alone does not preserve surrounding anatomy.

The source section projection (`section-owner25`) creates unacceptable folds.
The target-only release (`target-release-only25`) preserves source mechanics
but leaves an oblique step and moves lobe-core material3.981mm/3.798mm by LOD.
Neither is an accepted repair or an installed runtime.

Private preview sessions054502 and055103 exited before gameplay and were
closed by receipt with24 original saves verified each. The initial copy recipe
omitted the engine's bin-root gameconf.cfg/redscripts.ini and other bootstrap
files. The recipe now copies them; that source correction alone is not proof
that a relocated native preview works. Normal installed runtime bytes remain
the authoritative baseline until a candidate passes actual native review.

### Observed full-range baseline and preview recovery

Session `build/probe/sealed-session-20261012-060021` completed all192 ordered
native checkpoints with exact requested controls, fresh completed surface
sequences and both body resources observed. Three PNGs were overwritten by
the engine's ambiguous time-based filenames: screenshot_6112/6116/6119 had
creation times06:01:13/17/20 and modification times06:11:03/07/10. These were
stages302,303,304; a13.7-second gap in the surviving image sequence confirms
their location. The strict recorder rejected the189 surviving review frames.

An officially compiled three-view recapture in session061529 recovered those
stages with identical runtime hashes and matching controls. It ran from
`build/native-preview/preview-1791798261409055900/preview-3.json`, confirming
that including the missing bin-root bootstrap files makes the relocated copy
reach the native room. This used the retained original runtime, not a geometry
candidate. The final `060021/angle-sweep.json` binds189 original frames and
3 explicitly marked recaptures. All192 full-resolution frames are retained,
with eight-angle side contact sheets for each state. Archive screenshots during
future long runs to avoid the engine's filename collisions.

Both sessions are closed by exact receipts. Restoration proof is in
`060021/restoration.json`:24 original saves per session, scoped audio and
temporary room cleanup, eight user preference files restored/verified, and all
37 managed installed files hash-verified. No candidate was installed. These
baseline captures establish angle coverage and reproduce the defect; they do
not pass the attachment gate or demonstrate a repaired saddle.


## October 12: Angle 15 at 100/100/100 - rejected candidates

The Angle15 baseline is angle-sweep/s0-a15/original, not the earlier Width97
saved15 capture. Private studies remain under
D:/MaleModBuilds/witcher-waist-trace-20261012. No candidate was installed or
observed in the native room during this continuation.

The old post-solve support classifier used posed upper height >0. At this
angle it excluded all three previously traced saddle vertices12595/12596/8228.
Material classification includes them. This fixes the diagnostic selection,
not the installed deformation. Straight-cylinder radius constraints alone
are not an accepted attachment target: their successful QPs produced visible
wedges, and free-waist variants moved the waist44-54mm. Reject them.

rotating-section15 kept waist, protected boundaries and lobe cores exact,
with seam error below5e-13mm, but introduced visible creases. It is rejected.
Measured endpoint loft/profile variants reduce the side dip but create local
folds. Preserving upper seam donors increases the measured LOD0 opening
perimeter from27.351 to34.784 source units; it still does not certify complete
collar girth or visual quality. preserved-profile15 creates26/54 new opposing
face pairs in LOD0/1 (previous neighbour cosine >.5, new cosine <0).

The continuous-profile15 and spatial-profile15 SQP studies add intrinsic area
and neighbour-normal constraints. They did not complete the requested target:
2D stopped at~.4875 and3D at~.70937 of the required profile displacement after
OSQP iteration limits. Intermediate files are incomplete diagnostics. The
spatial-partial15 image shows only an intermediate LOD0; its LOD1 is baseline.
Never reuse that directory as a complete candidate.

owned-arc15 blends only immutable neutral-curve dorsal material from the
released source into the original output and prescribes original solved lobe
cores. It preserves cores within1.4e-14mm and waist/protected points exactly,
but creates93/133 new opposing face pairs and one collapsed LOD1 triangle.
Reject it. It demonstrates that core preservation alone does not repair the
coupled transition. Fit-offset transport was measured but not implemented or
validated as a cause/fix.

Base now has malemod_base/surface_bending.py and four passing unit tests.
The audit distinguishes rigid rotation from a new neighbouring-face fold and
checks intrinsic area collapse. It is a local check, not global intersection
or full seam acceptance. Seam coverage requires splitting original donor
edges at seam samples and welding diagnostic aliases. Both Witcher and
Wolverine can adopt this shared audit; no adapter pin/runtime changed.

All37 installed managed files matched the installation receipt after the
studies (angle15-installed-runtime-check.json). There are no clean live
candidate renders and no full attachment gate pass. Do not promote any of
these private prototypes as a functional repair.

# Geralt's measured pelvic recruitment

The attachment is the highest-priority invariant. Read `AGENTS.md` before any
mod edit. A positional seam test does not establish a natural ramp or correct
native shading. This repair is for Geralt; Wolverine's installed runtime is
unchanged.

## Diagnosis and construction

The old adapter sampled Wolverine's absolute pelvic field on Geralt's different
body. It left much of the opening fixed while neighboring anatomy expanded.
The first sewn repair still prescribed that field at Geralt's waist, producing
a raised shield in front of the pelvis. That candidate was rejected visually.

Base's `RootTransition` now supplies a field around the actual measured opening.
Its radial support grows with effective proximal radius, progressively recruiting
the surrounding annulus. Ordered concentric rings expand with a quintic radial falloff whose support
widens with dilation; they do not bunch onto a single barrel radius. A
concentric anterior loft carries the upper, lateral and inferior annulus
forward, fading into the abdomen. Neutral
body shape is preserved. The field has C2 fades and a guard against backward
displacement into the thighs. Dimensions use the existing measured calibration.

The adapter applies this one field to both Geralt body resources and both LODs.
The 37 common waist samples are prescribed identically. A first shared graft
solve preserves the differential coordinates of the smooth measured body
field, with optional master-space orientation constraints on body triangles.
Fairing displacement toward zero while prescribing full displacement at the
waist had created an artificial shoulder beside that resource boundary. A second solve prescribes those
body masters and fits independently moving anatomy back to the same edge.
Rest angle and shaft motion cannot rotate the pelvic ramp as a platform.

`MMRND006` retains exact original native edge donors for position and lighting.
UV aliases and the original cooked tangent-frame convention are preserved.
A cached constraint-only shared projection guards the actual native packed
body faces after welding; it preserves exact donors, aliases and fixed joins.
Valid faces pass through unchanged. This repairs microscopic underside
subdivision folds without exempting those faces from the strict local gate.
Normals are rebuilt after the final geometry and sewn to the donor normals;
each slave keeps its own UV tangent and handedness.

Script ticks can overlap rendering. Selecting geometry in `OnTick` allowed
depth and colour lists to use different anatomy poses, producing intermittent
white/background texture patches. Selection now happens after a real DXGI
`Present` or `Present1`; test Presents cannot advance it. Each command list
retains the selected immutable publication until its GPU fences complete.
A windowless SDK composition swap chain tests the actual Present detours.

## Installed October 6 result

The installed repair consumes clean Base `40dfa86` and DLL SHA256
`bfbc1e86bee9008268037a256307ee73cac503c8991d966b0b5c54bb1ccf1d0b`.
See `provenance/collar-repair.json` for the source/artifact/verification hashes.
The earlier raised-shield and script-tick candidates were rejected. The
intermediate Base 4f0148d loft was also rejected after native review exposed a
maximum-size waist shelf; the prior accepted runtime was restored before the
final differential-preserving candidate.

The full 278-case native-buffer sweep passes the seam, donor-normal and body
orientation gates on both resources/LODs. All raw and packing-resolved body
orientation counts are zero; maximum seam residual is 1.1041e-7 m. The 39-case body test preserves all
37 waist knots and presentation/pause/epoch behavior. Both the grey room and
ordinary campaign scene passed 39 native captures each, visually reviewed in
front/side/oblique views, including the reported settings, all mechanical
states, extreme angles, combined controls, minimum/default/intermediate sizes
and walking. The reviewed views contain a continuous ramp without the raised
shield, dark attachment ring or intermittent background patches.

The installed FloatDraw and windowless Present SDK checks pass. The unused
historical pre-skinned stream-output test still fails its surface-write assertion
and is not used as proof for this draw backend.

This is attachment acceptance for the tested DX12/Naked cases. Native distant
LOD transitions, ray tracing, every campaign lighting condition and garments
are not newly accepted by this repair. Numerical output includes both LODs;
close native captures do not establish a distant transition. Physics cadence
remains approximately 91–93 ms in these private runs; performance parity is not
claimed. Frozen beta.2 remains a separate release profile and exact rollback.
All private children were closed, ordinary sound/settings preserved, 24 saves
verified and transient studio/driver files removed. No user preference values,
private saves or screenshots are checked in.

## Mandatory repeatable verification

1. Verify the pinned Base source/provenance and shared root-transition and
   orientation tests. Retain the empty-constraint graft replay tests.
2. Build `collar_integrity_probe` and `body_render_test` from the same clean pin.
   Use the coherent current binding/render/worker selection, not historical
   diagnostic include snapshots. The exporter writes settled geometry: six
   150 ms updates before each static case and actual force-driven motion.
3. Export the complete 278-case sweep into a fresh owned build directory:
   `collar_integrity_probe worker binding render basePin bindingHash output`.
   Run `tools/review_collar_integrity.py --artifacts output --render renderDir
   --job bodyJob --reference-artifacts previousAcceptedExport --require-valid`.
   Inspect `profile-review.png`: both resources must appear in the meridian
   sections; checking the lower resource alone can hide an upper waist shelf. Both resources and LODs must be present.
4. Run `body_render_test render worker binding basePin bindingHash`. Require
   exact waist positions, named skin-weight bytes and normals, serial/parallel
   identity, and presentation/pause/epoch checks. Shared-root recruitment must
   cross the existing torso/leg join.
5. Compose and officially compile the complete installed script set using
   `tools/prepare_collar_session.py`; use `--campaign` for the normal scene.
   Standalone compilation of the extension misses native import declarations
   and is insufficient. The driver uses engine free-camera/locomotion APIs,
   ordered checkpoints and screenshots, with no hotkeys or physical input.
6. Launch the grey-room driver through `tools/run_iteration_world.py` with its
   exact source and compile proof. Require stages 300 through 338: 13 settings
   in front, side and oblique views, including the reported large-size settings,
   mechanical states, angle extremes, combined controls and walking.
7. Capture the owned run with `tools/record_collar_session.py receipt`. Inspect
   the actual native images for gaps, black rings, pinches, folds, plates and
   wedges. Repeat in campaign lighting through the private launcher. Numerical
   recording deliberately leaves `visualAcceptance` false.
8. Close only the recorded private child. Verify scoped audio restoration,
   unchanged ordinary settings/saves, temporary-file cleanup, managed runtime
   hashes and retention of the last accepted rollback.

The all-body orientation report retains raw projected-normal changes as a
diagnostic. Very thin original native subdivision faces can have area smaller
than the measured cook-packing uncertainty. Their count remains visible; the
additional all-body gate uses the measured positional-error bound. The local
collar gate does not exempt these faces. No numerical report substitutes for
the required native visual pass.

Generated stock-derived geometry, captures, saves and private receipts remain
ignored. The source recipe and compact evidence certificate belong in Git.
The room remains excluded from normal release payloads.

## Adoption boundary

Shared numerical construction and constraints live in Base. Native mappings,
body membership, original cook donors, render formats and the private test
driver live here. Canonical Wolverine and future spokes must pin and test the
measured-opening API before adopting it; do not copy its implementation into
independently maintained adapters. This task does not deploy a Wolverine,
garment, clinical-effect or release upgrade.

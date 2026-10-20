# Root-to-shaft motion transition, October 17

The reported step came from interacting material-presentation faults. The
replacement is installed as DLL
`39de929d7c5a43c0835211a6a162560a068708982fdfee7ac0f8f6bab7e65c9e`,
with Base module pin `37cc67f2970ed0a5225ed46d37e919b6b82114df`.
The numerical worker/profile remains at revision
`431e626cae6fb6720b552f8b20206727fe809c80`.

## Changes and causal evidence

* Pairwise section SLERP changed angular derivative abruptly at guide knots
  and at the fixed root. Radius amplified that jump into a surface step.
  Base now uses normalized quaternion Hermite interpolation with shared
  derivatives, retaining section diameter and the rigid crown.
* Pelvic clearance moved root material as much as 0.711 guide intervals beyond
  its assigned station. Binding now uses the final cleared material surface.
* Rebinding alone let part of the attached rim follow a free guide. The
  material rod now starts at the frontmost complete socket circumference;
  twelve sections run from that physical anchor through the original tip.
  The entire rim stays fixed while the first free interval continues moving.
* Additional live curvature is bounded by section radius and interval length,
  including the first half-interval. Authored rest curvature and exact segment
  lengths remain intact. This is a presentation constraint, not new collision
  physics or a change to the pinned numerical worker.
* The curved socket search exhausted eight iterations at slider 66, with a
  remaining station residual 0.000030. It now permits 32 rim-only passes and
  binds the full surface once afterward. All 100 integer slider values pass the
  captured-shape replay, including the exact failing case.
* Native temporal presentation uses the same final frames and bindings.
  Cached bindings are refreshed whenever the immutable rest-shape identity
  changes, including controls that leave root angle/radius unchanged.

Shared algorithms and regression tests live in Base; see
`MaleModBase/docs/ROOT-SECTION-CONTINUITY.md`. Other spokes can adopt the pinned
module after their own native attachment gate. Wolverine was not modified.

## Verification

Private evidence root:
`D:/MaleModBuilds/modular-anatomy-20261015/root-step-20261017`.

`build-source-delivery.json` binds 110 actual compiler inputs, dependency pin,
compiler logs and all coupled runtime artifacts. The adapter checkout is dirty;
its exact input hashes, rather than a clean-commit claim, identify this build.
`replay-probe-identity.json` binds the probe used for the final audits. Its
shape-change comparison handles differing vertex counts after a legitimate
rebuild, avoiding an out-of-bounds diagnostic read.

The native matrix includes 96 size/state/angle/shape views, 36 angle-sweep
views with pause/resume, 12 fixed-angle restart-walk views, 9 unobstructed distant
views and 39 campaign views. All close contact sheets were inspected. Obstructed
cameras in the last three full-matrix cases are superseded by the dedicated
4/8/15metre side/front/oblique session. Both body resources and both native LODs
completed draws. Campaign views use body-relative camera offsets; calibrated
true-side comparison is supplied by the grey-room captures.

All 48 captured-pose mesh audits preserve the original pelvis exactly, with
zero reversed ramp faces and no added nonmanifold edges. Replay assertions
require the zero-motion material shape and complete moving socket rim to remain
unchanged. Focused tests cover surface derivatives at root/guide knots, section
diameter, crown shape, segment lengths, bend limits and independent suspension.
All 100 integer angles replay successfully against the captured flexible shape.

In the restart-walk sequence, all 12 GPU mesh hashes differ, sequence advances 35,
display publications 91, simulation time 2.431s and actor position 4.898m. Both
shaft-tip and lobe positions vary. Fixed-angle evaluation median is 44.4 ms in
that capture workload. The mixed angle sweep is not a cached-performance test.

The first five geometry/runtime trials were rejected, including an inverted
ramp experiment and the angle66 search cutoff. One run of the final binary had
two unreadable screenshots; its complete motion sequence was recaptured and
reviewed. Rejected and incomplete evidence is retained, not used for acceptance.
The exact reviewed proof is `delivery/modular-acceptance.json`.

## Installation and scope

The guarded installer replaced 11 managed paths after the native gate, retaining
all 49 managed files in exact rollback:
`local/native-backup-modular-20261017-092643`.
The preceding accepted DLL is 38f034323a4c8bfe311c5307dfbc4d0207b0938e96f5184ae970ce3f5f528fa4.
All 31 protected save/settings/audio/control files were verified during install.
Installed startup verification is recorded separately below.

This repair targets the added live root step. It retains the authored rest
attachment and its small bounded static concavity. Very short/head-size
extremes and energetic fully-flexible motion can still fold distally. It does
not establish global self-contact, clinical calibration, 60 Hz execution, every
campaign transition, garment compatibility or parity in another game.


## Observed installed startup

Private installed-path session `sealed-session-20261017-092805` ran without a
native preview and completed grounded/movement checkpoints200/201. All three
startup/mid-walk/final native frames were inspected; the room floor and movement
render correctly. The root comparison above remains the pre-install exact-DLL
native evidence. The owned game is closed, temporary room resources removed,
audio restored, and all24 saves restored. All49 managed files and31 protected
files match their recorded hashes.

Native startup reordered equivalent input.settings sections/binding lines.
Their per-section multisets were verified equal, and the exact pre-test bytes
were restored; see `delivery/input-restoration.json`. No input mapping changed.

The existing Steam entry now references the new verified platform acceptance.
`tools/play_grey_room.py --check` passes package, compile, observed movement,
reviewed frame and all49 installed file checks. Final evidence:
`delivery/post-install-verification.json` and
`delivery/installed-native-startup.json`.

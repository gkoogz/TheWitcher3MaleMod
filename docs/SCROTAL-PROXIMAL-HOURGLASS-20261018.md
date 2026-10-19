# Proximal suspension and Hang-dependent neck

Installed October 19 after native review and exact coupled-artifact validation.
The change moves the scrotal attachment toward the pelvis and increases its
circumferential wrap from 200 to 250 degrees. The measured shaft interval changes
from [3.56114259, 15.22993039] to [3.25, 12.8]. The retained sac translates 1.5
source units toward the root before lofting. These are measured source units,
not centimeters. The complete shaft, original pelvis, retained sac topology,
donors and UVs remain exact; the sac's position differs by a rigid translation.

Geralt calibration is in `characters/geralt-modular-authoring.json`. Reproduce
with the Base authoring tools using shaft cut24, sac cut72, protected lower
region70, flare1.38695737555697, wrap125, proximal fill0.8, station bounds3.25/12.8,
rear extension0 and suspension shift1.5. The orientation solver selects handle
scale0.25. Assemble the original joined body, generate runtime/dynamic/transfer
assets, bind the native character, then rebake the neck chart with
`tools/prepare_neck_material.py` and `tools/build_neck_material.py`. Keep the DLL,
five coupled modular resources and the native material package together.

The renderer opts into Base's bounded suspension profile using the actual Hang
control. It preserves the attachment endpoints and tangents, adds fullness at low
Hang and a smooth waist at high Hang. Existing measured retraction, independent
lobe motion, shaft physics and the numerical worker remain active.

Base implementation: d89920edd2168f399ccd06263a7af0eb5318ae1c.
Numerical worker: 431e626cae6fb6720b552f8b20206727fe809c80, unchanged.
The adapter contains pre-existing uncommitted runtime code; exact114 compiler
inputs and command logs are archived. This is not a clean-checkout release.

Candidate evidence is under
`D:/MaleModBuilds/modular-anatomy-20261015/scrotal-proximal-hourglass-20261018/candidate-02`.
Eight C++ and 22 Python tests pass with no skips. Twelve baseline captured-pose
replays and 68 candidate captured-pose audits preserve the original pelvis,
boundary topology and pelvic-ramp orientation. All 252 native stages were
reviewed: 36 Hang, 96 combined controls, 36 motion, 12 angle-resume walking,
9 distant, 24 close material and 39 campaign. Six wall-occluded full-matrix far
views were excluded and superseded by the dedicated distant review. Both body
resources and both LODs completed native draws. The first narrower diagnostic
candidate was not installed.

Matched captured poses confirm 5,657 retained source vertices move toward the
pelvis, approximately 2.64 source units on average along the source forward axis
after existing runtime equilibrium placement. This is separate from the 1.5-unit
authoring translation. Shape, motion and clearance still contribute locally.
The neck chart was rebaked for its new geometry; retained material rows and
texture pixels remain exact. Its 96 float32 UV microtriangles occupy 3.06e-7 of
the chart area. No geometry collapse or reversed chart triangle is introduced
by that quantization.

The installed-path grey-room session loaded and walked; three startup/movement
images were reviewed. It closed with audio restored and all 24 original saves
verified. All 53 managed files and 31 protected files match. The engine reordered
input.settings; semantic equivalence, including duplicate entries, was checked
before restoring the exact original bytes. Steam grey-room preflight passes.
No host keyboard, mouse or focus was driven.

Installed DLL: e03b77c0219190b13f2bb487cd483b57aa2f674c7e9df5657de91614ba1e1240.
Geometry: 9e4028f089cfe41d7b527b9d9d54756c87753a95c1b98abbcd086edcd4410fb8.
Material: 03b031d6c9a8d50e8a14159b5294ccfd2ff973b9a60fd163d3b352ca8538e48b.
Native material package: publish/20261018-234909-cf9590.
Acceptance: candidate-02/delivery/modular-acceptance.json under the evidence root.
Rollback: local/native-backup-modular-20261019-003322, including all 53 prior
managed files and their original receipt. No publication or Wolverine install.

Finite native coverage includes low/default/high Hang, sizes and widths, angles,
mechanical states, walking and angle-resume behavior, both body resources/LODs,
and campaign lighting. Existing extreme distal/glans behavior remains outside
this suspension repair. No solver-frequency or performance improvement is claimed.
Observed close-matrix display evaluation median was 55.07 ms versus 49.48 ms in
the previous material run. Rapid angle changes still incur expensive rest-mesh
rebuilds. These are asynchronous mesh timings, not game FPS or numerical Hz.

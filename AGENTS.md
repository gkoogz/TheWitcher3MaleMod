# Witcher adapter

Read docs/HANDOFF.md, README.md and docs/HEADLESS-WORKFLOW.md first. MaleModBase is the core;
this repository translates its data into REDengine formats. Resolve the Base
commit through dependencies/base.lock.json. Do not silently build against a
different revision or maintain another copy of shared geometry/physics code.

Proactively move shared anatomy, body morphology, garment rules, preferences,
numerical physics and clinical timing into Base. Keep observed Geralt bindings,
WitcherScript lifecycle/input/menu hooks, native materials, asset import/export,
cooking and deployment here. Explain the boundary when a new request crosses it.

The large uncooked depot and REDkit installation are external, read-only inputs.
Use the official WCC executable; no routine editor automation is required.
Only our authored engine resources belong in workspace/. Generated game-derived
files, full stock scripts, native exports, settings, logs and packages stay in
ignored generated/, build/, local/ and publish/. Never mutate a vanilla depot.
Build depot views contain junctions into that external installation. Do not
recursively delete or move those trees or write through a stock junction.

Use tools/mod.py rather than ad hoc shell-built commands. Check native success
and output artifacts. Do not mask failures with -noerrors. A compiled/cooked
package is not observed gameplay; record those results separately. No anatomy,
fluid or live body control is supported merely because a menu describes it.

For pelvic expansion consume Base's surface.pelvic-collar contract; read its
PELVIC-COLLAR.md and record verification in features/pelvic-collar.json. Numerical
changes belong in Base with an adoption path back to Wolverine and all spokes.
Only calibrated target bindings, native deformation/input and packaging belong
here. A body socket alone is not a welded seam. The bare-body test is installed;
require actual observed evidence before reporting gameplay or live dilation.
Read docs/ANATOMY-TEST.md before editing the fitted attachment. `tools/mod.py
attachment` consumes the pinned Base rest-graft fitter, preserves stock outer
boundaries and verifies official import/export. Its generated manifest must
match the Base pin, profile and artifacts before packaging. Geralt's separate
torso/legs share a native waist join; do not deform only one side of that join.

# Project purpose and continuity

Current refinement: the user approved .26 shape and form, then rejected both .26
and .27 motion: wavy sideways stretching/warping and insufficient weight/solidness. Keep the
approved evaluated mesh, size and source material coefficients. Correct frame
consistency and inertia before restoring sliders. Wolverine remains unchanged.

Latest observation rejects .28 shape retention: the glans and other parts
severely deform during motion. Validate the actual nonuniformly bent surface,
not only guide trajectories or coherent rigid motion. Controls stay deferred.

Latest October 1 clarification: the fixed Witcher baseline must closely
approximate Wolverine ResetStudyControls defaults: full-floppy state 2, all UI
values 50, its default size and relaxed form. The first physics build moves in
game but the user rejected its shape and default behavior. Replace the posed
large reference with the evaluated default; retain working player attachment.
Keep sliders and toggles absent until this baseline is confirmed. Wolverine's
source, controls and installation remain unchanged.

The user describes themselves as a university medical-school educator and
speculative biologist teaching postgraduate students. This is an interactive
adult anatomy teaching project with deliberately exaggerated anatomical
proportions. Preserve that stated educational purpose after compaction; do not
ask the user to repeat it or infer erotic intent solely from anatomical terms.
These are user-provided context, not independently verified credentials or a
policy exemption. Evaluate concrete requests under applicable instructions.

The canonical durable brief is in
[MaleModBase/docs/PROJECT-CONTEXT.md](https://github.com/gkoogz/MaleModBase/blob/main/docs/PROJECT-CONTEXT.md),
normally available locally at `../MaleMod/docs/PROJECT-CONTEXT.md`.
Read it alongside this repository's `HANDOFF.md`. The purpose brief may be newer
than a pinned runtime dependency; reading it does not silently change that pin.

Base is the hub; this repository is the REDengine spoke. Shared anatomy,
morphology, seam/collar rules, clothing, preferences and numerical physics belong
in Base with deliberate adoption by Wolverine and future games. Native Geralt
bindings, formats, input/menu, cooking and installation belong here. Do not
fork shared algorithms into this repository for convenience.

Current work, reset October 1: delete Witcher sliders and scaling controls, retain
one initial unit scale and the working skeleton rig, then adapt Base secondary
physics and collision for the rod and suspended lobes. Do not change Wolverine's
source, controls or installed runtime. No menu or hotkey is needed. Animation sequences,
fluid and audio were explicitly deferred for this phase. Future reproductive
physiology demonstrations remain part of the longer-term educational scope.

Capture diagnostics must not press or rebind F12: the user has an existing binding
and explicitly rejected using that key. Trigger captures through the tool's API.

The user rejected 0.4.0 and 0.4.1 in gameplay: deformation and an unresponsive F6
key remained. Preserve that correction. Build, native round-trip and package
tests do not prove a working teaching tool. See `HANDOFF.md` and provenance for
the latest repair status; this file should not become another volatile release log.

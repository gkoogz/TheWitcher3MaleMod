# Shared radial recruitment and clinical runtime

The Witcher adapter consumes Base revision
`2a7b38a7019d6102046085a8586e86273d5579fe`, surface wire version 4.
The shared source anatomy, final UnifiedCollar queries, clinical projection,
ambient clocks, fluid solver and deposit mesh stay in Base. Geralt's measured
bindings, native resource split, materials, script callbacks, input and GPU
delivery stay here. Wolverine's source and installed game are unchanged.

## Skin and pelvic recruitment

The detailed source diffuse is corrected in linear RGB using 68 corresponding
Geralt/attachment seam samples. The original texture detail and alpha remain;
the normal map retains the measured source repeat. No image generator is used.
Native imports explicitly use `CharacterDiffuse/TCM_DXTNoAlpha` and
`CharacterNormal/TCM_Normals`, verified through official resource metadata.
Importing the normal as the default WorldDiffuse color texture was a measured
encoding defect. Both body and clinical carrier recipes now reject that input.
See [PELVIC-SKIN-AUDIT.md](PELVIC-SKIN-AUDIT.md) for measured color errors and
stale-import safeguards. Diffuse matching is an input measurement, not a claim
of identical appearance under different games' lights.

The worker evaluates 14,790 target body queries through the active source
radial law. Conforming local refinement supplies triangles throughout the
growing support region. Both torso and lower resources, in both LODs, use the
same 37 waist masters with identical named skin weights. Original attachment
edge donors and UV aliases remain intact. There are 49,884 native render rows.

The MMRND005 render contract records both authored rest and native cooked rest.
It applies deformation deltas to the native rest surface while the common waist
uses its canonical master position. Native normal-map frames are transported by
the geometric frame change; protected neck, wrist and ankle attributes remain
native. Body/depth/material draws must share one completed surface publication.
No shape law is independently reimplemented in the spoke.

## Live controls

F6 expands/collapses the existing live overlay. Up/Down selects a row;
Left/Right changes it; Shift uses larger steps. The existing 18 anatomy/physics
controls retain their shared contract and persistence.

Two additional rows control the clinical demonstration:

- **Ambient:** Off, Gentle, Moderate, Strong, following source clocks.
- **Ejaculation:** Start, or Cancel while the source sequence is running.

The active sequence follows the source 20-second timeline and pulse mapping.
Its final evaluated distal pose supplies the world-space nozzle. An independent
native worker advances the shared fluid solver; the game VM performs calibrated
sphere sweeps against actual loaded scene collision. Untested queries stay
deferred. No invented catch plane or foot-history floor is used.

Native opaque/clear materials draw liquid and scene-anchored deposit meshes with
the game's camera and depth. GPU resources remain immutable and fence-retained
through command-list submission. Reset, pause, character change, explicit
restart and errors invalidate stale simulation contacts and outputs.

## Future dialogue

`MaleModSetDialogueSlots(phase0, phase1)` accepts two future Wwise event names.
Both strings default to empty and are silent. Source-timed cue events cross the
typed native bridge and are polled by the VM. Character changes, restart and
faults clear stale cues. No private audio or replacement dialogue is installed.

## Verification layers

Base independently checks source geometry/physics traces, clinical surface
projection, fluid timing/deposition and imported source hashes. The adapter
checks native cooking/attributes, exact cross-resource waist publication,
serial/parallel output, material receipts, worker lifecycle, deferred contacts
and native GPU slice/readback.

Installed gameplay is a separate gate. The final delivery record belongs in
`provenance/radial-clinical-delivery.json`, with the exact DLL, assets, compiler
proof and private process receipt. Private sessions use an invisible Windows
station and engine APIs, no host focus or input, no save writes. Their scoped
audio mute is restored when the verified child process exits.

Displayed interpolation cadence, numerical solve throughput and game FPS are
different measurements. Offline replay does not prove perceptual quality,
ray tracing or far LOD transitions. The known rendering-mode limitations remain
explicit until separately observed.

## Installed October 3 checkpoint

The final private 20-case run has been observed with the installed module;
all four visual gates pass. See HANDOFF.md and the delivery certificate for
exact hashes, actual scene contacts and numerical/display timing. The rear
patch was a final-vertex lighting-view bound defect reproduced on AMD hardware;
complete native lighting records fix it. Fluid shifted views now also expose
complete records. Neither fix suppresses source deformation or shading.

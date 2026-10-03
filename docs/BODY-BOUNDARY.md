# Shared waist, materials and motion presentation

October 2, 2026. Base pin: `acda34e7b12a923c2162d32e3c015485e3108efa`.
Wolverine's source and installed runtime are unchanged.

## Ownership

Base owns measured-loop refinement, original-edge lineage, movable prescribed
boundary constraints, material-atlas layout and rotation-preserving presentation.
The existing final unified numerical solver is unchanged. Geralt's two actual
resources, FBX conventions, native palettes, shaders, overlay and cooker remain
in this adapter. Both resource geometry and their binding/render contracts must
be adopted together. See Base `docs/REST-GRAFT.md` for other-spoke adoption.

## Waist and upward recruitment

`tools/prepare_body_boundary.py` consumes the lower motion cage and the actual
`t_01_mg__body_hires.fbx` export. The similarly named `geralt-upper.fbx` export
is feet and must not be substituted. Four actual waist loops are refined at 51
common angular samples, with recorded projection and exporter-knot tolerance.
Upper and lower remain separate resources. Original edge donors, UV aliases,
attachment seam and source module lineage remain intact. Neck, wrist and ankle
boundaries remain protected.

MMBIND03 combines lower body, upper body and module into one per-LOD collar
domain. Canonical waist masters take their nonzero motion from shared source
body donors. The coupled interior solve recruits the torso above the waist.
Matching joint names publish one skin field to both halves and both LODs.

MMRND004 retains two native resources and four LOD sections, 43,276 native rows
and their actual palettes/quantization constants. Both halves use the same
canonical positions and named weight bytes; lighting normals are joined per
LOD. Static torso LOD streams and packed lower morph output have different
native view origins. The renderer selects the actual static LOD by its exact
owned upload/UV offset and handles position-only depth passes as well as lit
passes. Original shaders, other streams, material handles and native skinning
are preserved. One command list pins one immutable whole-body upload, retained
through all consumption fences.

## Material correction

The previous tiny Geralt UV patch produced nearly constant beige. New native
material handles bind a two-tile atlas containing the full stock Geralt diffuse
and full source natural anatomy diffuse. Anatomical UVs come from original
source lineage; FBX V is inverted before WCC's observed import inversion.
The full normal atlas bakes the source's observed repeat of 16. Geralt ambient
occlusion remains on its tile; anatomy AO is explicitly neutral white. Source
specular is not relabeled as AO. Official imports, dumps, texture-cache build,
packing and retained handles on both resources were checked.

This restores anatomical color/detail. It does not claim identical lighting
between the two games: Geralt's native skin shader remains authoritative, and
state-dependent source diffuse/specular/SSS equivalence is not implemented here.

## Motion cadence

Completed source surfaces arrive more slowly than game frames. Lighting is
rebuilt once per complete solution. A separate display worker presents between
solutions using the shared material frames and shortest quaternion rotation.
Distal glans and each lobe use a rigid frame; proximal influences fade at the
attachment. Body/waist aliases interpolate together. Controls, paused edits and
new character epochs snap to coherent completed states.

The final private run measured median 49.71 completed display publications per
engine second, versus 17.15 complete numerical surfaces. The display targets
60 Hz but is not a guaranteed 60 Hz simulation or game FPS benchmark. Source
fixed steps, contacts, numerical constraints and accepted elapsed time were not
reduced. This avoids presenting every solver arrival as a visible jump without
misrepresenting numerical throughput.

## Overlay repaint

F6/arrows/Shift controls retain their original setter path. The layered panel
paints into a complete memory bitmap then performs one BitBlt, suppresses
background erasure and avoids timer-driven repaint/show calls when nothing
changed. SDK panel rendering, limits and navigation passed. The private game
driver does not synthesize physical F6 input, so perceptual flicker in an
ordinary interactive session is not claimed as independently observed.

## Build and verification checkpoint

Current ignored artifacts:

- Authoring/cook: `build/body-boundary/common-waist-6`.
- Bindings: `build/full-runtime/geralt-bindings-acda34e-complete`.
- Render: `build/full-runtime/render-body-acda34e-final`.
- Profile: `build/full-runtime/runtime-profile-acda34e-body`.
- Fingerprints: `build/full-runtime/body-fingerprints-acda34e-final`.
- Staged selection: `build/full-runtime/current-install.json`.

Bindings were prepared from job 5. Every array in its four part NPZs was checked
identical to job 6; job 6 corrects authored FBX UV V only. Final cooked/native
UVs were independently inspected against job 6. Material metadata records reuse
of identical official imports; it does not claim they were converted again.

Base tests/provenance passed. The current C++ body test passed 39 full source
cases, all control extremes and combined maxima, exact boundary positions and
named skin bytes across all four sections, shared shading, serial/parallel byte
agreement, nonzero upper/waist recruitment, intermediate presentation and
pause/epoch snapping. Actual D3D12 WARP readback passed for morph and static LOD
slices, including absent optional lighting streams and restored bindings.
Managed rollback fixtures passed. Official native-aware script compilation
passed with actual registered imports rather than script stubs.

Final installed private session:
`build/probe/sealed-session-20261002-230911/receipt.json`. All 64 ordered control,
movement, pause/edit/resume and actual save-reload cases passed with 43,276 rows,
body resource mask 3, completed draw flags 853 and no runtime/render faults.
SDK frames were inspected. The process was closed by its recorded PID/creation
time; the temporary Continue source was removed by hash. Private audio was
muted and the prior session mute state restored on exit. No host focus/input or
save writes were used. Ordinary game sound is not intentionally muted.

`provenance/body-delivery.json` is the current certificate; the older
`provenance/native-delivery.json` is historical. Verify with:

```powershell
python tools/record_body_delivery.py
```

The managed installer owns 16 files including a separate early-loading body
patch. Original .31 rig/entity/graph package hashes remain unchanged. Exact
rollback to the pre-body 11-file build is available in
`local/native-backup-20261002-224514`. Later backups retain intermediate 16-file
builds. Do not roll back by deleting arbitrary game files or changing settings.

Storage-only junctions move owned `build/body-boundary` and `publish` output to
E:. They are not stock-depot links. Native read-through depot trees contain
stock links and must never be recursively removed or moved.

Remaining verification limits: real far-LOD transition, ray tracing, exclusive
fullscreen, interactive F6 flicker and an end-to-end game FPS benchmark. Both
LODs pass offline/native layout checks. Existing measured capsule contacts
remain approximate. Clinical sequences, fluids and audio/chatter remain deferred.

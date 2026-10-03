# Installed full native runtime

Base is pinned at `166cb02fd55c15f459ef58ffcc49f7cac27cee3c`. The adapter uses
its complete Win32 source Session, all 18 controls, morphology, coupled pelvic
collar, constraints and collision. Wolverine is unchanged. Geralt-specific
bindings, pose sampling, skin palettes, draw layout, input and installation stay
in this repository. Numerical laws are not independently forked here.

## Native rendering and waist correction

The owned packed resource is pre-skin morph input. The live renderer clones the
original DX12 pipeline with an unbounded float3 position and a 28-byte row,
preserving original shaders, UVs, materials and weight bytes. Added anatomy
bone influences map to the observed pelvis entry of their own LOD. The native
shader applies the current game pose exactly once. Uploads survive all consuming
queue fences, and command bindings are restored after each owned draw.

The separate stock torso requires the lower body's open waist edge to retain
its original cooked attributes. The October 2 seam correction preserves cooked
positions, normals and tangents for all 106 protected render aliases across
both LODs, including ankles. Interior lighting still follows the live surface.
The regression exercises all 17 slider minima/maxima and combined maxima,
checking boundary position, packed lighting and skin bytes independently.

## Controls, lifecycle and contacts

F6 expands/collapses the live overlay; Up/Down selects, Left/Right adjusts,
Shift increases the step. Default is state 2 and all 17 sliders at 50.
Native control storage uses atomic replacement; installation, private testing
and rollback preserve user preferences. Old .31 mesh-bank scaling is suppressed
in full mode; its cooked resources and the working rig are retained.

Source simulation and target composition run outside game/render callbacks.
Pause retains physical state and permits zero-time edits. Resume excludes pause
time. Save reload creates a fresh character epoch and source worker. Both target
LODs and independent lighting are parallel with byte-identical serial checks.

Pelvis contacts are fitted to 191 measured stock donor samples. Both thighs use
measured stock envelopes and observed animated endpoints. These capsules are
approximations, not an exact triangle body hull.

## Evidence and limits

`provenance/native-delivery.json` records current installed hashes and separate
SDK, numerical and gameplay gates. Captured images/poses and game assets stay
ignored. Earlier 64-case private gameplay verification covered every control,
combined maxima, running, paused edits/resume and actual save reload. The waist
patch passed the same 64-case installed verification; use HANDOFF for its receipt.

Timing reports separate source throughput, preparation and VM callback costs;
none is a game FPS benchmark or proof of perceptual motion parity. Camera
controller distance requests were executed, but actual far distance/LOD selection
was not established. Existing ray tracing is disabled and remains unverified.
The supported native adapter is the pinned installed DX12 executable; DX11 and
other executable revisions require their own validated bridge. Animation
sequences, fluid and audio are deferred.

## Managed installation

`python tools/mod.py install-native` verifies the Base pin, compiler artifacts,
production contacts, render packet and all previous owned targets. It refuses
replacement while Witcher runs or if an owned file changed externally. Backups
and atomic receipts support `python tools/mod.py restore-native --backup <path>`.
Rollback tests cover exact restoration, partial-copy failure and preserving
preferences/unmanaged changes. Current compilation and generated assets are
local prerequisites; this is not yet a generic redistributable installer.


## Historical checkpoints (superseded)

# Full Base runtime development

## Current native integration stage

`runtime_controller.hpp` connects all 18 validated Base values and calibrated
pose conversion to the asynchronous full source/target pipeline. Accepted input
advances the filter and clock; rejected input does not. Pauses reset the motion
filter on resume, preserve physical state, and exclude elapsed pause time.
Paused control changes submit a zero-time source/target preview. Results carry
the exact accepted pelvis delta, simulation time and contact calibration status.
`runtime_host.hpp` creates/replaces workers on a manager thread outside engine
locks. Character epochs prevent displaying another lifetime's geometry.

`engine_bridge.cpp` registers MaleModNativeFrame and MaleModNativeOverlayOpen.
`probes/native/runtime.ws` supplies actor-local pelvis/thigh input from CR4Game
OnTick and handles the panel's own pause reason/input context. Official WCC
compilation uses real native RTTI imports, not script stubs. The controller test
matches 48 changing frames to serial source wire bytes and both target LODs,
then verifies zero-time edits, long pause/resume and worker replacement.
These callbacks have not been observed in the game. The development script
latches an explicit input fault on overload rather than silently losing steps;
this is not a completed production performance policy.

`prepare_runtime_profile.py` stages hash-locked DLL-local worker/bindings and
measured calibration. A complete Geralt pelvis contact envelope is required
for production. Explicit diagnostic source contacts do not satisfy that gate.
No new runtime profile or DLL has been installed; .31 is preserved.

`float_vertex_pipeline.hpp` supplies immutable unbounded float-position/skin
uploads, a strict layout-compatible PSO clone, and resource retention until all
consumer fences complete. Its D3D12 WARP test draws and reads back positions
outside packed range with unchanged bone/weight/UV attributes and verifies
multi-fence lifetime. Actual game draw/actor/PSO ownership, skin palette storage,
normal/tangent reconstruction, bounds, prior positions and ray-tracing output
are still required. This backend is not a live mesh replacement.

`overlay_panel.cpp` implements a separate mouse panel with all controls. The
actual preview and control hit/range checks pass; see OVERLAY.md for unobserved
game input/display gates. Preferences do not yet persist between launches.

Latest user authorization allows unattended game open/close. Supported native
computer control failed before initialization, including after reset/retry;
Space/Continue cannot currently be operated unattended. No new build was
launched or installed. This limitation is recorded in HANDOFF.md.

October 2: SDK-first rendering correction is in SDK-RENDERING.md. Native stream
decoding and inverse blended-skin output now have an independent comparison with
the installed REDkit shader functions. This is offline conversion proof, not
installed output. Stop the graphics restart/inventory loop; v6 stays offline.

Authorized scope: full source solver/surface, all 17 sliders and the 3-state
selector, separate overlay. Wolverine stays unchanged. No replacement for .31
has been installed; the user confirms its Overall scaling and rejects physics.

## Character-specific inputs

`characters/geralt-runtime-bindings.json` records the observed 104-joint rig,
stock 94-joint prefix, pelvis index, added parents, measured basis/root/scale,
both LOD lineage artifacts and hashes. Base separates position, direction and
length conversion. Source collar vertex indices are not Geralt bone indices.

The shared C++ target collar consumes Geralt's unique topology and original
body-edge donors. Both seam halves and UV aliases use the same solution. Waist
and ankle boundaries remain protected. Expansion across another native resource
boundary requires shared bindings driving both sides first.

The thigh envelope is measured from retained stock-influenced body vertices:
native radii about 0.11750/0.11667. The new bridge does not yet publish animated
endpoints. The Geralt pelvis capsule remains null/un-calibrated in the profile.
Do not describe reference contacts as Geralt evidence. Native motion sampling,
gravity/inertia conversion and full contact calibration remain integration work.

## Verification

Base owns the verified Win32 source Session, numerical contact interface, wire
format, coordinate/sparse-delta bindings and coupled target collar. No copied
numerical fork lives here. `verify_live_graft.py` compares C++ Base with Python
Base at all eleven Overall keys in both Geralt LODs: 22 cases pass the 1e-8 gate,
worst error about 1.82e-9, zero seam/protected-boundary drift. Repeated cached
solves are identical; construction and cached solve timing are recorded separately.
This does not validate every combined target control extreme or native output.

The source Session passes 37 shape cases, 33 physics cases and the 180-frame
original-source trace. Reference-equivalent contact calibration has zero error;
a larger radius changes contact response. Both wire architectures pass lossless
and malformed-input tests. Reports stay in ignored build output with hashes.

## Native readiness probe

`surface_worker.cpp` links Base's Win32 library. `surface_transport.hpp` owns a
random private channel and child process; its job cannot terminate an existing
user game. Full surface/mechanical output crosses the codec to an x64 client.
The worker now consumes Base's verified process-global `/fp:precise` parallel
recipe. Source arithmetic, constraints and collision publication are unchanged.
Wire 3 exports the actual cached collar support frame independently of the live
guide; the target updates its metric under that source lifecycle. A new character
lifetime requires a new worker process. The TLS/strict recipe remains available
as a separately verified development option.

`engine_bridge.cpp` remains a readiness/integration probe. Actual game hash,
registration RVAs, function size, bytecode layout and prefixes are in
`characters/game-native-profile.json`. The game uses an ASCII name pool.
The initial UTF-16 mistake caused the user's missing-import error (process
16836); the earlier success flag proved only callback completion. Corrected
registration validates the exact named function pointer in the RTTI registry.
Actual WitcherScript calls succeeded in processes 11604 and 23868. Process 27832
also passed typed int/float/Vector input and return, all 18 control setters and
readbacks, invalid input rejection, and restoration to defaults. The main-menu
OnConfigUI wrapper triggers that test without a key. These control calls still
do not drive the source solver or native vertices.

Process 21512 subsequently passed the same complete typed/control test. Its
script callback arrived after the launcher's observation timeout; the late
status read establishes success, rather than assuming timeout means failure.
The user loaded a save with Geralt visible, but the original graphics observer
still reported device/copies without any IA vertex binding.

`compile_native_scripts.py` supplies native import RTTI to an owned official
WCC child before script compilation. Its separate compiler-native-profile is
from actual WCC disassembly, not editor or game offsets. Imports are not replaced
with script stubs. The official compiled result and hashes are retained.

`run_native_probe.py` stages only its temporary readiness addon, launches the
owned native module, and removes the addon after the probe. It preserves all
five installed .31 file hashes, settings, game binaries and key bindings. The
process is left for the user; the launcher never kills a resumed game.
`graphics_probe.cpp` observes actual SDK device/list/resource calls and writes
bounded ignored metadata. It does not modify vertices, skin, shaders or draws.

The next observer build fixes a concrete diagnostic flaw: copy and direct
command lists expose different SDK method addresses. The old observer retained
only the first implementation's trampoline. The revised observer keeps up to
16 independent method trampolines and records implementation identities plus
first direct/indexed/indirect draw and root-SRV observations. The owned WARP SDK
smoke test reproduces distinct copy/direct method addresses and observes both
copies and vertex bindings. It has not yet been observed in Witcher. Its build
is separate from the DLL currently loaded by process 21512. New launcher
receipts identify process creation time as well as PID, and status reads check
that lifetime before invoking an already loaded owned export.

`export_live_bindings.py` generates version-2 Geralt topology/lineage artifacts
from the observed fit/cage and pinned Base. `target_surface.cpp` consumes them,
transfers complete anatomy and both body sections, calls Base recruitment and
GraftPlan, preserves native rest defaults and reconstructs both LODs. The full
composition passes 162 offline cases (11 Overall states plus 37 shape and 33
physics states, both LODs), worst native-coordinate error about 1.52e-11 against
Base Python. Welds are below 1e-10 and protected boundaries have zero movement.
Cached composition measured roughly 4.3-7.7ms; changing collar frames requires
new factorization. These costs exclude source evaluation and GPU delivery.
The moving 180-frame pipeline now uses 22 source metric generations instead of
refactoring on every moving root. Both LODs take about 6.5ms median; source plus
transport about 33ms median on this host, with larger shape-change spikes.
The original offline source benchmark and extracted numerical kernel take about
25ms and 26ms per update respectively. These are development CPU measurements,
not gameplay FPS. Exact fresh-plan comparisons still pass in all 48 checks.

`surface_service.hpp` adds a dedicated asynchronous composition thread with an
eight-request bounded queue. Every accepted input retains its controls, dt and
contacts and is evaluated in order. Full/Busy are explicit caller backpressure;
the eventual engine controller must retain/retry input or report overload.
There is no silent dropping/coalescing of physics steps. Complete immutable
results carry their sequence and original input together. Invalid/reset inputs
are rejected; a character reset creates a new service/worker process. Shutdown
occurs outside engine/loader locks. A 48-frame changing-control/motion test
exercises queue backpressure and matches serial source wire bytes and both LOD
positions exactly. This service is not yet attached to a game callback, and
its numerical checks do not establish live responsiveness or sustainable FPS.

Native skin, bounds, normals/tangents, resource output and every-control UI
remain separate gates. The old cooked anatomy uses a quantized position/skin
stream with two LOD chunks; the source cooked format is 164 and must not be
passed through the older authoring converter. Actual official dump and buffer
inspection are retained in ignored build artifacts. `native.lock.json` pins
MinHook and planned ImGui; ship both required licenses with a future package.
The independent read-only format-164 reader validates header, table and export
CRCs, recovers exact quantization constants, and decodes actual per-LOD palettes
and inverse binds. Both inspected LODs match authored topology and named weights
within one byte of quantization; inverse binds differ by less than 2e-7. The
cooker's flipped-V, binary32, truncating half-float UV rule matches every vertex
exactly. Native tangents, output synchronization and the currently drawn resource
still need verification. This inspected neutral resource is not proof of the
active .31 morph mesh.

The controller template now declares `statemachine class`. The complete installed
script with that one declaration correction compiles through official WCC with
all five native imports. This removes the reported state-machine warning in the
verified source; the installed .31 script is preserved pending the full package.

## Remaining gates

October 2 measured-input checkpoint: the automatic six-import script probe
compiles through official WCC and runs in the hash-locked game. It skips pause
and captures 240 actor-local pelvis/thigh poses over 4.25 seconds of foreground
movement. The adapter now applies the native pelvis inverse bind, Base's full
affine origin/basis/scale calibration and its exact source motion filter. The
240-frame offline two-LOD replay passes with 216 nonzero force frames, maximum
force 2.35261, and contact-coordinate round-trip error 3.87e-8 native units.
Median source/transport cost is 32.8ms and both target LODs 9.1ms in this replay.
It deliberately uses source default contacts as a diagnostic: Geralt's pelvis
capsule remains uncalibrated. No measured contact or live solver output is claimed.

Exact SHA256 matching of owned upload ranges identifies the installed anatomy
resource family, including Overall 50 and 60 vertex buffers. All family index
buffers share the same topology, and preload uploads do not establish which
mesh is currently drawn. Created indirect signatures are Dispatch/12 bytes,
Draw/16 and DrawIndexed/20; they contain no vertex-view or root changes. The
current live observer sees UI draws but has not identified the anatomy draw.
v4 includes bundles, returned graphics interfaces and multiple device methods,
but still saw only UI draws. Read-only prologue inspection showed its hooks
were intact. v5 observes Reset and all supported graphics versions: list reuse
exposes another implementation and live indexed draws/root SRVs/57 vertex
formats are now visible. This identifies the missing observer coverage.
v6 associates exact owned upload ranges with actual vertex/index bindings and
indexed draws, clears state on Reset and retains matched resources against GPU
address reuse. Its SDK tests pass without GPU submission, including simulated
draw metadata and proof that Reset clears ownership. v6 has not run in game.

1. Native performance: source-global strict arithmetic failed scrotum-100 at
   0.00011677211. Matching the original `/fp:precise` recipe passes all 37 shape,
   33 physics and 180 changing-motion cases without changing the 0.0001 gate.
   Ordinary TLS/x64 and process/precise/x64 diagnostics still fail, so no x64
   numerical kernel is deployed. A nonblocking worker lifecycle and real game
   frame-rate/motion measurements remain required.
2. Complete measured pelvis contacts and animated coordinate/motion inputs.
3. Connect typed native motion/control inputs to the complete source Session;
   readiness registration and script invocation are observed.
4. Implement verified vertex output, native skin/normal/tangent transport,
   resource/LOD lifecycle and coupled Geralt deformation without double skinning.
5. Verify the implemented native panel in game; finish every control output path,
   preferences and input focus
   without assigning an arbitrary bound key.
6. Pin a clean committed Base, cook/package through the adapter workflow, verify
   installation/rollback hashes, then observe gameplay and native performance.

Wolverine remains authoritative and has not migrated to Base. Its adoption path
is documented in Base's FULL-RUNTIME-ADOPTION.md; no automatic installation or
claim of complete hub/spoke migration accompanies this development checkpoint.

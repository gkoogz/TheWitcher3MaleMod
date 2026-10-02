# Full Base runtime development

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
5. Implement the overlay, every control output path, preferences and input focus
   without assigning an arbitrary bound key.
6. Pin a clean committed Base, cook/package through the adapter workflow, verify
   installation/rollback hashes, then observe gameplay and native performance.

Wolverine remains authoritative and has not migrated to Base. Its adoption path
is documented in Base's FULL-RUNTIME-ADOPTION.md; no automatic installation or
claim of complete hub/spoke migration accompanies this development checkpoint.

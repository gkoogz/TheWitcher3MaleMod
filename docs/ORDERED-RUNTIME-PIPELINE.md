# Independent physics, skin preparation and presentation

The former modular path admitted another numerical sample only after reference
skin, target geometry and presentation had progressed. A costly mesh operation
therefore delayed physics and slider feedback together.

The new adapter runs three independent stages:

1. Ordered numerical stepping in a dedicated process.
2. Ordered retained-skin preparation in another process, followed by a mesh
   worker that coalesces obsolete display endpoints.
3. Current control presentation on the most recent prepared geometry.

Both numerical processes receive identical accepted inputs. Intermediate skin
samples still advance the original solver with their original time, controls,
contacts and impulses. Only the displayed endpoint coalesces. Queue admission
is atomic, bounded and retried on backpressure. Lifecycle resets replace both
processes. Size edits defer expensive exact refitting until a 250 ms quiet
interval; angle edits bypass that delay.

Reusable bounded workers, cached material transforms and ordered normal
reductions reduce mesh work without changing its packed output. The retained
skin still includes the original final collar correction: an attempted shortcut
failed donor parity and is not shipped.

## Source and character identity

Shared APIs, numerical stepping and deterministic geometry belong to Base.
Witcher owns the queues, process transport, observed body bindings and rendering.
`dependencies/worker.lock.json` pins Base
`5ae173f45c5ce5687c4c44ad179bcbf15f3e0e13`. Character binding revision
`431e626cae6fb6720b552f8b20206727fe809c80` remains unchanged. The runtime
profile changes only its worker executable digest. Both production builds have
dirty-source and unverified-library opt-ins disabled.

Native DLL SHA256:
`2ceb410e92dc53c42a092362d9d36f90b01f41eda6df2d335579dfaf0b17534d`

Worker SHA256:
`d5120a7f81cfbe5f59234de210d0aaabe55b99c89d04feb8f96c5c00bc070044`

Wolverine is unchanged. It and future adapters can adopt the shared APIs through
their own pinned, tested integrations.

## Measurements and validation

Final native grey-room measurements on this workstation:

| Measurement | Result |
| --- | --- |
| Median numerical update | 10.03 ms |
| Median mesh preparation | 39.81 ms, preceding candidate 64.60 ms |
| Display publications | 42.53 per wall-clock second |
| Width / angle acknowledgement interval | 136.8 / 148.3 ms |

Acknowledgements include the driver's intentional 100 ms hold. Publication rate
is not game FPS. No fresh matched Wolverine benchmark was run, so exact
Wolverine performance parity is not established. Mesh preparation remains the
dominant cost.

The numerical/donor replay checks 240 samples, including moving contacts, all
mechanical states, controls and cumulative impulses; numerical state and all
7,218 retained donor rows match the reference exactly. Six final packed native
buffers also match the reference. Split-stream tests preserve the final state
while numerical updates advance independently of skin. Shared geometry,
root-articulation, ordered-normal, task-arena, live-control, presentation,
worker-adoption, preview and installer regressions pass.

The exact final DLL completed 96 grey-room matrix checkpoints (97 captures),
39 campaign checkpoints and the pulse/slider cadence run. Both body resources
and both native LODs completed GPU draws; no recorded modular draw failure.
Owned sessions closed, audio was restored and all 24 original saves verified
after each final session. Capture review includes front, side and oblique
views, size/angle combinations, all mechanical states and walking.

The pelvic root remains continuous in the reviewed matrix. A localized angular
shading transition remains on the side of the scrotal connection in a campaign
close-up; this is distinct from the root-to-pelvis join and is not claimed fixed
by this performance change. Broad material and geometry perfection, every
campaign transition and extended soak stability are not certified. A corrupted
index seen in an earlier diagnostic candidate is now guarded by validated
topology; its original writer has not been identified.

Private, hash-bound build, parity, native, visual and installation records live
under `D:/MaleMod/Work/witcher/runtime-rearchitecture`. They are not source
assets and are excluded from Git. The installation receipt is authoritative for
whether this candidate has actually replaced the installed runtime.

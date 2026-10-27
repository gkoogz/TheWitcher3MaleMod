# Rigid garment draw frame

The running regression was a renderer transform mismatch. Actual native body
vertices matched their selected CPU pose within10micrometres, while all four
garment materials shared a286.6775mm translation from their CPU world positions.
Their immutable source serials matched, so serial ownership alone did not detect
this independently delayed carrier instance transform.

Garment positions already contain world coordinates. The renderer subtracts the
immutable feed origin for native quantization. Its cloned native rigid pipeline
now reads identity-plus-that-origin from three owned INSTANCE_TRANSFORM inputs.
The carrier still updates scene bounds; all other instance attributes, shaders,
geometry, fitting and physics remain unchanged. The matrix occupies48bytes at
vertexBytes+32 in the existing fenced vertex upload; native vertex view lengths
and the24byte AMD padding remain intact. A zero stride repeats those rows for
arbitrary firstInstance and instance counts. Normal and exception paths restore
the exact previous slot and pipeline.

The rewriter rejects malformed/partial matrices, unsupported formats/rates and
slot exhaustion before mutation. CPU tests and actual native-VS AMD/scoped
synthetic-WARP fixtures cover these contracts, wrong carrier rotations and
translations, nonzero firstInstance and multiple instances. Native running
GPU/CPU pose checks and the complete gameplay gates remain separate evidence.
See docs/HANDOFF.md for exact current source/binary/bank identities and status.

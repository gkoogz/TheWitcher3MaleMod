The CPU-only command checks an actual MMGP1 bank against the exact immutable
geometry and pose selected for each native draw:

```powershell
& 'C:/Program Files/Python310/python.exe' tools/analyze_v2_position_capture.py --bank <bank> --output <bank>/selected-pose-analysis
```

The output directory must be fresh. The command does not launch, build, stage,
cook or modify bindings. It verifies the closed observation inventory and preview
hashes, then binds the source geometry to the actual staged B04 file. It reads
the GPU world-position/primitive-ID/depth images, selected body/cloth uploads and
their matched 6080-byte pose envelopes. Body skinning repeats the production
ordered float32 affine operations. The original 78,337-row capture was checked
byte-for-byte against the production C++ skinning oracle.

A successful exit requires all seven draws to select the current latest serial,
share epoch/serial/presentation/present/pose revision, and match the **selected**
pose. The 99th-percentile plane-distance limits are 25 micrometres for body and
10 micrometres for cloth; triangle-distance P99 must be below 50 micrometres.
Maximum triangle distance is reported separately: fixed subpixel rasterization
can extrapolate a boundary fragment beyond the mathematical CPU triangle edge.
Non-triangle pipelines, active morph composition and pixel depth writes require
a different oracle and are rejected.

For a failing historical bank, `--diagnose` writes the failing report without a
nonzero exit. Optional `--diagnostic-next-pose <same-bank-capture.pose>` measures
an alternate captured pose. This diagnostic never changes the selected-pose gate.
The initial bank's 1596-selected/1597-native mismatch remains a failure even
though its next-pose diagnostic matches the GPU within micrometres.

The report includes actual band/body depth overlap and same-ray world gaps.
Back-band geometry can legitimately be behind the body; depth overlap alone is
not a penetration or visual-acceptance proof. Native visual and motion review
remain required. PNG file modification times do not establish pixel exposure
times or source-frame identity.

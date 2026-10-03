# Native lighting input bounds

The rear black patch was traced to the adapter's lighting vertex-buffer view,
not the shared anatomy solver, pelvic recruitment or texture generation.

The previous view began at byte 20 of an interleaved 28-byte vertex and used
`SizeInBytes = vertexCount * 28 - 20`, `StrideInBytes = 28`. On the installed
AMD Radeon RX 7900 XT, the final partial record returns zero lighting input.
The upper torso's final LOD0 vertex 5456 is a rear waist UV alias; its adjacent
triangle is native face 0. A zero normal and tangent produce a degenerate
decoded frame in the character material. LOD1 has the corresponding vertex 3390.

## Independent GPU evidence

An owned, non-game process rendered 65,536 packed lighting records through both
the old view and a complete native 8-byte view. The previous 65,535 records
matched. On AMD the last normal decoded as `(0,0,0)` instead of
`(.120235,.439883,.771261)`: exactly three component mismatches. WARP reported
zero mismatches. Thus WARP-only tests did not reproduce the hardware behavior.
The ignored evidence is `build/probe/last_lighting_fetch-amd.txt` and
`last_lighting_fetch-warp.txt`; no captured game data is required by that test.

Private gameplay isolation also established that upper replacement alone
introduced the patch; retaining the native lighting stream while replacing
position/skin input was clean. Replacing lighting alone reproduced the patch.
Every upper native position, skin index, weight, normal and tangent was checked
against the cooked resource during the separate rest-identity diagnostic.

## Correction

The adapter now retains the engine's 8-byte normal/tangent stream contract.
Immutable uploads contain a separate compact lighting tail. The native morph
compute composer writes its fully evaluated lighting to an equivalent tail.
Both use `SizeInBytes = vertexCount * 8`, `StrideInBytes = 8` and keep every
record complete. Native shaders, materials, root parameters, shadows and
all body/anatomy deformation remain active. Resource retirement and queue
fences retain both streams together.

The pipeline validates native lighting format, slot and offsets before using
that stream. Ambiguous static LODs fail closed; position-only shadow passes
select their LOD from the exact owned position stream rather than unused UV
bindings. The original graphics bindings and compute state are restored.

Run the renderer SDK regression on both backends:

```powershell
build/native-runtime-controller/Release/float_draw_renderer_test.exe
build/native-runtime-controller/Release/float_draw_renderer_test.exe --hardware
```

The second command uses the high-performance hardware adapter. Both tests
exercise static LOD slices, final-vertex lighting, actual native morph input,
immutable publication boundaries and fence retirement. This document records
the independently proven input defect and correction. Both the WARP and AMD
last-vertex regressions passed. The full production renderer was then observed
in private game process 1408: rear checkpoint 75 (`screenshot_85333.png`) has
no black patch, with both body resources and all dynamic output enabled. The
20-case live verification and installed artifact receipt are recorded separately
in the delivery handoff. Temporary native readbacks, split/suppression modes
and extra pixel-shader capture were removed after this observation.

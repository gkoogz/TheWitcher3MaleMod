# Phase-specific liquid rendering and receiver repair

This change follows the frozen 0.5.0-beta.1 package. It is not included in that
published package and does not modify its artifacts.

## Measured failures

The actual compiled `transparent_lit_vert` vertex shader from owned clear draw
31192-16 ignores COLOR. Its pixel shader obtains alpha from sampled Diffuse.a
and material opacity. The prior white CharacterDiffuse/TCM_DXTNoAlpha map has
alpha1, so the material opacity0.82 presented preliminary flow as milky white.
Source density/fade was uploaded as vertex alpha but ignored by this graph.

A new phase-specific native service fixture reproduces the missing main floor
contacts under the same 96-query/frame VM budget. With prior queue expiry of 8 seconds for
completed requests and 30 seconds for pending requests, slots reached 4096 at 10 seconds;
issued requests stopped at 14848, clear volume 0.84 deposited, opaque volume 0 and
final-pump volume 0. Earlier aggregate floor tests therefore did not establish
main-pump ground deposition.

## Repair

Base tags each impact, field and receiver vertex as clear or opaque. Main
impacts retain their node birth time. The cumulative final-pump ledger requires
opaque birth at or after 11.5 seconds, so an earlier pump landing late cannot pass.
Timeline/cues end at 20 seconds; existing liquid can finish pending physical receivers.
Passive mode waits for the existing main flow to drain.

Moving particle and floor projection queries have separate keys. A live
particle refreshes its request each solver step. Requests abandoned by retired
particles expire after 0.35 seconds; floor projection requests retain 3 seconds for source
retry scheduling. Capacity 4096 and native VM budget 96/frame are unchanged.
The test fixture now receives 266.05 opaque units, including 17.85 final-born
units in 10 contacts, and produces 440 receiver vertices. This is an offline
callback fixture; installed game terrain proof remains a separate gate.
The same96-query/frame receiver at20FPS also receives17.85 final-born units
in10contacts and produces416 receiver vertices; its total opaque ledger is
239.00units. This checks the smaller query budget per second at low frame rates.

A deterministic 256x256 alpha ramp is imported into the clear material as
CharacterDiffuseWithAlpha/TCM_DXTAlpha. Native metadata is officially dumped
and checked. The supported graph's actual Diffuse.a input reads opacity from
UV.x: low alpha 0.14 for preliminary/passive airborne flow, and source density
and fade times phase opacity for ground marks. Main airborne flow retains
opaque pbr_std. No custom shader, generated art or synthetic floor is used.
Opaque and clear carriers keep their existing two-resource draw contract.
Transparent graph defaults retain native lighting and refraction. Unsupported
parameter overrides are omitted.

## Gates

- Base source replay: 15/30/60/120FPS, 800 ms hitch, node/mesh/volume parity.
- Separate clear preliminary and final-born opaque receiver ledgers.
- Coincident clear/opaque fields and post 20-second deferred receiver completion.
- Adapter bounded 96-query handoff; epoch, cancellation and fault isolation.
- AMD hardware last vertex input bounds retained, plus phase-specific alpha
  atlas UV coordinates. Software WARP alone is insufficient for bounds.
- Native package: correct alpha-preserving diffuse and normal texture groups.
- Before delivery: actual game preliminary/passive material appearance, white
  main emissions, and final-born ground volume/count plus opaque floor geometry.

Wolverine adoption and common API are documented in Base
`docs/CLINICAL-SEQUENCE.md`. Its immutable legacy snapshot remains unchanged.

## Private game capture plan

The driver retains stages64..83 and adds the following authored SDK cases.
The complete ordered run is64..116. Its observer allows420seconds and records
the last native telemetry when that deadline expires. No host input is used.

| Stages | Capture |
| --- | --- |
|84..89|All three states at maximum overall, minimum/maximum angle, side camera|
|90..101|Naked/Jockstrap, baseline/maximum overall, all three states|
|102..107|Both styles and all states at maximum overall during actor movement|
|108|Cancel, Naked, real terrain relocation and settled emitter|
|109..110|First and second preliminary clear emissions|
|111..112|Opaque main emission and final pump side view|
|113..115|Actual floor view,20second timeline completion and physical drain|
|116|Explicit cancellation clears sequence, fluid, deposits and receiver ledger|

Stage114 requires positive opaque final-born deposited volume and contact count
from the native service. Its wait is bounded12seconds: a receiver failure is
captured as zero telemetry for the delivery gate to reject. Missing garment
output waits at most12seconds; missing native/GPU checkpoint waits15seconds
and stops the ordered run. A numerical phase ledger proves receiver ownership;
clear/milky appearance still requires review of the actual rendered captures.

# Geralt animation following investigation

## Observed failure

The October 1 05:05 user screenshot of 0.4.18 reports:

- `Boot: player root has 94 bones; expected 104 | attempts: 7`
- Graph active=false, accepted=false, no slider callbacks and no pose samples.

The model's movement with the actor did not establish pelvis animation. The
ten authored mesh bones were absent from the effective player skeleton. Zero
pose diagnostics were uncollected measurements, not successful following.

## How the animation reaches this mesh

Geralt's normal animation graphs produce local bone transforms. The skeleton
hierarchy composes those into model-space transforms. Mesh skinning then maps
each mesh palette name to its actual attachment's skeleton provider and combines
that pose with inverse bind matrices and vertex weights.

Read-only inspection of the licensed REDkit executable and symbol map found:

| Native function | Finding |
| --- | --- |
| CMeshSkinningAttachment::GetCachedData | Queries its parent skeleton provider and the mesh's mapping cache |
| CMeshSkeletonMappingCache::GetMappingEntry | Matches palette names against provider names; missing names become -1 |
| SkeletonBonesUtils::GetBoneMatricesModelSpace | Writes identity when a palette index is missing or outside the pose array; no authored-parent fallback |
| CAnimatedComponent::CalcTransforms | Limits model-space computation by pose count and skeleton LOD count |
| CEntityTemplate::CreateEntityInstanceFromCompiledData | Loads the existing compiled entity buffer |

The stock collar weights still mapped to pelvis, thighs and roll joints. The
interior had been transferred to authored `mm_*` weights. A 94-bone provider
could animate the collar while leaving that interior in the actor frame. This
explains the reported stretching without assuming an incorrect shared solver.

The installed SDK and map hashes are recorded in local inspection receipts.
Neither SDK files nor a game process were modified by this investigation.

## The missed template layer

The stock `gameplay/globals/resources/gameplay.xml` Geralt alias is
`gameplay/templates/characters/player/player.w2ent`. `GeraltForUI` is
`characters/player_entities/geralt/geralt_player.w2ent`.

Both contain their own flattened moving-agent root with a stock skeleton import,
despite including the ancestor `player_base_m`. Patching the ancestor alone did
not change these concrete resources. The screenshot confirms the resulting
runtime count, rather than merely suggesting a graph timing problem.

The repair patches both concrete imports in each resource, including the
embedded compiled buffer. It preserves length, every other byte and all nested
header/string/export CRCs. The observed gameplay resource is version 163; the
Geralt appearance resource is version 164. Other versions are rejected.

## Preserve compiled behavior state

An ordinary recook of the redirected templates inherited the base's single
Cutscene slot, losing seven slots in Geralt's existing compiled state. The
stronger loaded-template gate rejected that output. It was never installed.

The candidate retains each stock compiled entity and changes only its rig
imports/CRCs. The intermediate recook is archived outside the bundle tree. Native
loaded inspection must preserve all eight slots, their names, graph paths,
order and scheduling flags, as well as animation, ragdoll and steering bindings.
The private 104-joint rig retains every stock rest frame/control property and
keeps all weighted authored joints inside the model-space LOD update range.

Two SDK assertions were reproduced by a separate cook of the exact untouched
stock templates: the `isChainAttack` / `man_swimming_jump_dive_stop` CName
collision at hash 2873949622 and component.cpp:208's transform-parent assertion.
Their acceptance is restricted to these stock inputs, the recorded SDK hash,
unchanged baseline files/logs and those exact diagnostics. New assertions,
resource failures, CRC changes, missing behavior slots or altered root bindings
still fail. The baseline receipt and original rejected outputs remain local.

## Offline animation control

`tools/audit_animation_skinning.py` reads an official native dump of Geralt's
movement set. Idle, walk and forward run have 94 stock tracks. It checks the
original stock-palette rest graft in both LODs: seam aliases remain coincident,
and distal pelvis-bound vertices keep their pelvis-local position.

The calibrated decoder handles only observed normal clips and native truncated
float/XYZSignedWInLastBit formats. Walking/running use the inline 35-bone core
and the stock constant fallback for streamed tail bones. Deferred frames are
not inferred. The ordinary idle clip has constant pelvis motion; additive idle
sway and the complete runtime graph blend remain separate gameplay checks.
Root is reset, but extracted trajectory in other tracks is not subtracted.
Raw centroid travel is not a gait amplitude or physical-unit measurement.

This control proves stock-palette compatibility offline. It does not establish
execution of the authored-joint graph or rendered movement in the game.

## Verification and adoption

Run adapter tests, native loaded graph/rig/template gates, exact native unbundle
comparison and managed installed hashes. Then observe boot=attached, graph
active/accepted, pelvis-relative pose samples, idle sway, walk/run/turn,
waist/ankle continuity and scale 0.8/1.2. The final gameplay gate is independent.

This repair belongs in the Witcher adapter. Shared geometry, bindings and
physics are unchanged. Wolverine and every future spoke should verify effective
runtime palette mapping and parent inheritance, independently of asset names,
rest-frame exports and build success. Keep Base geometry/bindings pinned together.

Primary format guidance: CDPR's [skinned mesh guide](https://cdprojektred.atlassian.net/wiki/spaces/W3REDkit/pages/6326771)
and [animation workflow](https://cdprojektred.atlassian.net/wiki/spaces/W3REDkit/pages/6326649).

# Native pose graph: failure and required gates

## Failure isolated September 30, 2026

Versions 0.4.5, 0.4.7 and 0.4.8 cooked and exposed vector variables, but their
cooked output and every cached pose/scale-control input were NULL. Gameplay
confirmed no resizing and a lower body that did not follow torso idle motion.
The user reported variable acceptance true in 0.4.7. That flag establishes only
variable storage, never execution of connected pose nodes.

The generated graph supplied compiled buffered node tables and cached input
pointers, but omitted `sourceDataRemoved`. Its native default is false.
REDkit `CBehaviorGraph::CacheConnections` therefore rebuilds inputs from editor
socket topology, which this compiled authoring format does not contain. It
clears the authored pointers. Marking the complete compiled graph consistently
with `sourceDataRemoved=true` preserves the cached chain through native cooking.

This is native serialization evidence, not gameplay confirmation. Never set
this flag while leaving uninitialized tables/inputs. The official script-aware
cook now dumps both entity and graph. `verify_deformation_graph.py` traverses
from the authored output through ten scale nodes and 94 stock ParentAlign nodes
to TPose, verifies the ten named vector links and matches observed rig order.
It rejects NULL inputs, missing controls, cycles and wrong names/order. Installing
any deformation package requires that verification in its manifest. Previous
packages fail the new gate and must not be reinstalled as deformation candidates.

The native constructor leaves an unused top/output pair with node id zero in
the object tree. Verification excludes only its disconnected output, never an
authored output. Graph buffers choose the authored top and output. More than one
such default, a connected default or multiple authored outputs are rejected.

## Extended skeleton update coverage (October 1)

0.4.15 also failed observed animation follow. Reviewing the preserved stock rig
metadata found `lodBoneNum_1=40` in the private 104-joint skeleton. Offline native
inspection shows CAnimatedComponent::CalcTransforms bounds model-space conversion
by GetLodBoneNum; all ten appended joints lie outside the reduced-detail prefix.
0.4.17 sets that private limit to 104 and verifies it after official cooking.
The original shared rig is untouched. Keep stock bind data and control metadata,
but do not preserve a cutoff that excludes newly referenced joints.

A bounded native script measurement reports actor-relative pelvis/root motion
and parent-relative root-position error. It is read-only and stops after 60
samples. It distinguishes a native bone update failure from a rendered skin
binding failure. Gameplay confirmation is pending; 0.4.16 measurement-only was
never installed. Symbol evidence: CalcTransforms at 0x142700160,
GetLodBoneNum at 0x1426fa950 and skeleton GetBonesModelSpace at 0x1426eabb0 in
the hashed licensed offline editor. Reports remain under ignored build/probe.

## Authored joint follow and numeric serialization (October 1)

0.4.14 scaling is user-confirmed, but added joints stay steady during idle sway,
stretching their base. It is a failed animation-follow test, not pose parity.
0.4.15 adds a reference LS branch masked onto only authored indices 94..103,
then scale; it keeps the preceding player's stock pose and root motion. The
connected native output has 23 pose nodes. Its playback subsequently FAILED; see the LOD correction above.

The first rest-mask cook was rejected: constant and mask weights became zero.
Pinned vendor CFloat.SetValue accepts float/double, but ignores integer JSON
values without an error. `prepare_motion.scalar` now casts Float values before
serialization. Native mask checks require full weight, exact names/indices,
active unsynchronized override input and unchanged root-motion policy. The
license-free converter round-trip regression is skipped only when the pinned
local converter is unavailable; native cooking remains an installation gate.

## Related native findings

- 0.4.12 improved the gap but FAILED moving-pose parity: the user reports a
  smaller waist separation that resolves at idle and opens with every step.
  Native `CBehaviorGraphInputNode::Sample` copies `GetPoseFromPrevSampling`;
  `CBehaviorGraphStack::Sample` caches the component's existing sampled pose
  immediately before evaluating each graph. However, PrepareForSample calls
  ResetPoseLS(true) before the first graph and replaces that mapped pose with
  reference pose. **0.4.13-attached-pose-test is HELD, never installed**: InputNode
  in an ordinary helper's first graph would still lose stock animation. The
  build and installer reject that route. InputNode in an additional player
  graph layer instead consumes the preceding stock graph's current output.
  The next candidate preserves original appearance autobinding to the player,
  extends only its private rig, and appends an owned graph with AttachBehavior.
  It never calls ActivateBehaviors, UnfreezePose or UpdateByOther on the player.
  This buffer-path evidence is offline, not proof of gameplay timing.
  The native ScaleBone sample multiplies scale,
  so ten unconditional scale-only ConstraintReset nodes protect authored joints
  against frame-to-frame accumulation. They preserve translations/rotations;
  scalar motion channels are rejected for this isolated candidate until their
  absolute rest/reset policy is established. Stock waist/ankle bindings and
  geometry are unchanged. No fixed offset hides the discrepancy.

- The user rejected 0.4.10: waist separation remains and an ankle gap is also
  visible. Identity-root policy alone does not establish pose parity.
  Native localSpace=true ParentAlign reads GetBoneTransformLocalSpace through
  the parent SBehaviorSampleContext. localSpace=false invokes
  ISkeletonDataProvider vtable slot 0x48, verified as GetBoneMatrixModelSpace,
  reading the component's model-space matrix buffer and converting via the
  already aligned ancestor pose. This is a distinct stream, not world-space
  copying. 0.4.12 isolates this model-space policy with the same scale probe;
  it must pass gameplay before secondary motion or full controls are layered on.
  The 0.4.11 graph-to-dangle package is held because it retains the failing local
  pose path. No fixed mesh translation was used to hide the discrepancy.

- 0.4.10 preserves observed bone-zero identity instead of ParentAlign copying
  animated Root. Native `OnParentUpdatedAttachedAnimatedObjectsLS` copies mapped
  parent local poses, then overwrites the first transform with identity. In
  contrast, ParentAlign local-space sampling calls GetBoneTransformLocalSpace,
  which reads the parent's sample context. Root extraction therefore needs
  explicit matching policy. The observed rig is bone zero Root, parent -1,
  identity bind; authoring rejects other roots. Cooked graph has 93 stock
  alignments and ten scales plus 60 connected scalar transform stages.
  Gap repair remains unobserved until the user tests the same actions.

- ParentAlign caches its transform parent in OnInitInstance; OnActivated does
  not rerun parent discovery. A bounded delayed second graph remains a separate
  lifecycle test. It has not independently proved a working parent connection.
- UpdateByOtherAnimatedComponent schedules the receiving helper after the
  player. It does not copy a pose and must never make the player depend on itself.
- The current native graph slot RTTI does not retain the legacy converter's
  alwaysLoaded flag. Do not claim lazy creation based on that flag. Native stack
  Init selects the first slot; explicit activation constructs the second instance.
- Native JSON object ownership must be parent-before-child in source and the
  embedded flat compiled tree; otherwise the cooked skinning attachment is lost.
- Source editor sockets need their actual native classes and input-to-output
  serialized connection direction. Two exploratory socket candidates were
  rejected (NULL inputs/native load assertion); none were installed. Their
  uncalibrated path was removed from the active authoring tool.

Evidence was read from the licensed offline REDkit editor and symbol map.
Reports hash inputs under ignored build/probe. No SDK changes or game-process
attachment is required. Key symbols: CBehaviorGraph::CacheConnections,
CBehaviorGraph::OnPostLoad, CBehaviorGraphStack::Init,
CBehaviorGraphStack::InternalActivateBehaviorInstance,
CBehaviorGraphConstraintNodeParentAlign::OnInitInstance and OnActivated.

## Packaging and user diagnostics

The effective player template is a separate gate. A private rig on
`player_base_m` did not establish the skeleton used by the flattened concrete
Geralt templates. The 0.4.18 user screenshot shows a live 94-bone root and an
inactive graph. 0.4.19's SDK source-cache preservation failed with loading CTDs
and is blocked. 0.4.20 redirects the actual shipped cooked gameplay/appearance
templates. Require unchanged shipped bytes except imports/CRCs, cooked flags,
loaded root/binding parity against the same shipped source, and the 104-joint
rig/LOD and connected output. See [ANIMATION-FOLLOW.md](ANIMATION-FOLLOW.md).
The SDK loaded source view contains eight slots; REDkit's loaded shipped view
contains one Cutscene slot. Do not substitute one kind of evidence for the
other or claim a source inspection establishes the live game stack.

Native entity/graph XML dumps are diagnostic outputs. Exclude those exact paths
from bundle input; retain unrelated authored game XML. Native unbundle must
recover exactly the candidate's expected resources/buffers and match their cooked bytes.
One 0.4.9 package accidentally bundled its graph dump and was rejected before
installation. Repacking preserved compiled/cooked resources and reran official
pack and metadata commands; its manifest records inherited cook evidence.

The 0.4.9 menu includes three disabled diagnostic rows showing graph activation,
callback count/requested scale, and actual vector readback/frozen pose. Close
and reopen the menu to refresh them. They are status rows, not source controls.
Observed 0.4.9 gameplay now confirms distinct 0.8/1.2 scale results and improved
torso/leg tracking. Some animations still open a vertical waist gap. Screenshot
readouts show active=true, accepted=true, 27 changes, requested/readback=0.8,
frozen=false. Investigate root pose handling/sampling before claiming pose parity.
No console setup is needed. The single test slider remains separate from the
full 18-control implementation and cannot establish dynamic pelvis or XPBD parity.

## Hub and spoke adoption

This defect and fix belong in the Witcher adapter. Base owns anatomy, rest
geometry, control laws and numerical dynamics. Wolverine uses a different native
output path, so copying this REDengine flag into it would be inappropriate.
The reusable lesson for all spokes is to verify the complete path to rendered
output, separately from accepted parameters and resource/class existence.
Offer the shared original-code shape/rest/material fixtures back to Wolverine;
keep its authoritative runtime unchanged until an adapter adoption is tested.

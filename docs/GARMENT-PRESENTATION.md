# Garment pose coherence

Cloth generation runs asynchronously. Its world coordinates belong to the
complete body delivery used for that generation; they must not be drawn against
a newer actor origin or bone pose without transport.

`GarmentPresentation` caches every cloth vertex's measured lineage and skin
weights on the geometry worker. It separates the weighted donor anchor from the
solved cloth offset. For old/new weighted donor maps B and C:

- Offset: `inverse(B) * (oldCloth - oldAnchor)`.
- Display: `newAnchor + C * offset`.
- Normal: `inverse(transpose(C)) * transpose(B) * oldNormal`.
- Tangent: `C * inverse(B) * oldTangent`, orthogonalized to the normal.

The current body geometry supplies the donor positions; the exact completed
current `RenderPose` supplies actor and bone transforms. Rigid motion preserves
cloth distances. Articulated donors retain their measured blend. Changes in the
anatomy surface update the anchor without replacing the simulated offset.

`GarmentService::Submit(shared_ptr<const RenderDelivery>, const RenderPose&, bool paused)`
publishes this bounded presentation step independently of the geometry worker's
immutable raw publication. A stale epoch suppresses display and support. Naked
clears the displayed garment immediately. A new active SDK pose queues a genuine
shared cloth update even when the completed body geometry pointer is unchanged.
An identical timestamp and geometry do not queue duplicate solves. The worker
receives accumulated active time when intermediate requests are overwritten;
paused wall time is excluded. Epoch, clock discontinuity and style changes
invalidate in-flight publications before they can restore stale fabric/support.

The bridge must use one captured `RenderDelivery` for body, garment and clinical
feeds. A lightweight immutable request combines the completed geometry and its
completed controls with the current captured SDK pose. Contacts and all donor
samples use that same pose, observed stock bone matrices and actual inverse binds.
Measured thigh endpoints are bones 15/16 and 18/19. Mixing current thigh samples
with an older actor/body delivery is prohibited. Support acceleration remains in
canonical source coordinates, so actor/pelvis presentation rotation does not
change the numerical law or timing. Gravity is supplied along game world Z,
with the source's measured magnitude converted through the character calibration.
The first ten completed controls define a restRevision; animated poses and
stiffness/weight/bounce/velocity controls do not invalidate the rest fitter.

## Historical presentation checks, 2026-10-03

`garment_presentation_test` verifies identity, rigid rotation/translation and
distance preservation, articulated translation/rotation, normal/tangent
orthogonality under a blended shear, changed anatomy geometry, Naked and epoch
rejection. Its optional actual-artifact mode also exercises the asynchronous
service against the final 2062b2d Geralt bindings and 3,444 cloth vertices.

Across 240 frames, the actual service Submit measured mean 0.468 ms, p95 0.663
ms and maximum 0.741 ms on this host. Cache construction runs off the game VM.
These are offline timings; graphics frame coherence and moving gameplay remain
separate private-game verification gates. Runtime deliveries expose
`presentationMilliseconds` and `poseSeconds` for that verification.

## Historical corrected clean geometry adoption

That checkpoint pinned Base `c49eea156ab3b6e989f22c52a128123850470dae`.
The corrected garment has 4,068 vertices and 7,764 triangles. Its lineage and
complete donor pose transport remain the same contract; the old 3,444-vertex
fixture timings above describe the historical presentation gate only.
The shared correction passes 96 actual Wolverine source states and 41 Geralt
control/articulated binding cases, including material spacing, whole-triangle
capsule clearance and actual fabric-surface sewing. Numerical work remains on
the latest-request asynchronous worker; presentation remains a separate step.

Fresh inputs are `build/full-runtime/garment-bindings-c49eea1-contact-shape`
and `build/full-runtime/render-c49eea1-contact-shape`; both manifests bind the
clean Base pin and exact current render/binding hashes. The clean 48-frame
worker proof is `build/full-runtime/worker-proof-c49eea1-contact-shape/manifest.json`.
These are source/native proofs. Final private game moving-coverage and appearance
verification remain pending the integration owner's observed receipt.

## Persistent fabric integration gates

`garment_cadence_test` checks overwritten-request elapsed time, pause/resume,
same-geometry moving poses, morphology ticks and explicit clock/epoch resets.
The artifact mode of `garment_presentation_test` additionally requires actual
shared state, fixed substeps and coherent completed pose/control publications.
These lifecycle gates pass for the diagnostic integration candidate.

`garment_dynamics_test` is a separate strict gate using evaluated source/target
geometry, current Geralt classic strap donors, calibrated RuntimeProfile thigh
and pelvis capsules, actor rotation/translation and articulated legs at varying
active intervals. Every case requires material/sewing and collision/coverage
budgets. Failure captures include inputs and output; they do not include prior
persistent cloth state, so a static input replay is not dynamic replay proof.
The actual Geralt gate currently exposes shared moving coverage budget failures;
this candidate is not yet accepted as a working fabric simulation. No cadence
or transport timing can substitute for that gate and subsequent private gameplay.

The adapter sampler preserves the original float skin composition and transform
order. Identical packed bone/weight tuples share a composed map within one pose;
a worker-owned immutable tuple table is reused only after validating all sampled
packed attributes. Presentation caches measured lineage/native influences while
recomputing solved offsets and current transforms. Donor or skin changes rebuild
that cache. Independent original-operation and cached-versus-full tests exercise
the unchanged mathematics and cache invalidation.

Delivery timings distinguish sampling, shared update, presentation construction,
SDK display transport and the optional first-failure diagnostic export. The
diagnostic file write can take tens of milliseconds and must not be mistaken for
healthy steady solver cost. The measured candidate still exceeds retained active
time under moving contacts; a clean, performant shared fabric pin remains required
before adoption or installation.

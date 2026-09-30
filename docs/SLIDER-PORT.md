# Full source slider port: resume here

User request September 30: port every Wolverine size/deformation/physics control,
reconstruct the dynamic pelvis, and retain the interim native pause menu. Prefer
live deformation eventually. Animation, fluid, audio and other non-sliders are
explicitly deferred. Read `PROJECT-CONTEXT.md` and Base's `AUTHORED-SHAPE.md`.

The installed 0.4.4 test remains unchanged. The user confirms its native menu is
visible; tuning effects and persistence are not yet observed. It still has just
the three REDengine-specific controls. This pass does NOT complete the 18-control
runtime port or install a new test. Do not tell the user it does.

## Source control coverage

The authoritative IDs/ranges/mapping remain in pinned Base's
`modules/live-controls.json`. These 18 controls correspond to source UI rows
excluding THROB and IDLE CHATTER. Source startup-camera/video controls are also
deferred. Do not duplicate a manually edited scale table in this spoke.

| Base ID | Active Wolverine behavior | Current output work |
| --- | --- | --- |
| state | Smooth mechanical mode; rod/root gravity, compliance and shape regimes | Shared UI contract only; native state binding pending |
| overall | Authored overall/width grid; coupled diameter and pelvis | Early authored stage verified; native output pending |
| length | Authored length delta, logical sections and refined head-length correction | Early authored stage verified; later stages/native pending |
| width | Authored grid and shaft/pouch ownership, growing pelvis support | Early authored stage verified; native output pending |
| glans | v5 remap, R14 growth weights/lower correction and logical head profile | Contract extracted; refined transport/native pending |
| scrotum | Pouch-owned authored scale, egg rest fit/suspension dimensions | Early authored stage verified; egg/native pending |
| hang | Suspension-weighted offset after logical rest surface construction | Separate source hang field verified; native pending |
| angle | Pelvic angle-follow, posed shaft frame, root angular drive | Early angle/flare verified; later pose/native pending |
| forward | Authored source-space delta | Early authored stage verified; native pending |
| vertical | Authored source-space delta | Early authored stage verified; native pending |
| shaft_stiffness | Raw UI sets bend compliance in `StepConstraintSolver` | Contract extracted; authored solver/native pending |
| shaft_weight | Mapped value sets rod mass and `StepRootSuspension` mass | Contract extracted; authored solver/native pending |
| shaft_bounce | Raw UI sets drag and `PDPrepareBend` Kelvin-Voigt ratio | Contract and shared bend kernel extracted; native pending |
| shaft_velocity | Mapped value sets gait/side acceleration response | Contract extracted; authored solver/native pending |
| scrotum_stiffness | Raw UI sets suspension/shear compliance and torsion | Contract extracted; authored solver/native pending |
| scrotum_weight | Mapped value sets lobe mass/inertia | Contract extracted; authored solver/native pending |
| scrotum_bounce | Raw UI sets lobe drag and suspension damping ratio | Contract extracted; authored solver/native pending |
| scrotum_velocity | Mapped value sets lobe acceleration response | Contract extracted; authored solver/native pending |

Physics consumes both raw UI and mapped values. Do not wire all eight to
REDengine's three gravity/damping/speed properties. The native dyng simulator
caches its own arrays; changing resource fields plus a reset has not been proven
to refresh those caches. Separate shaft and lobe behavior needs a real backend.

## Pelvis work completed in Base

The hub now evaluates the early authored coarse stage against 1,300 original C++
samples. It also builds a coupled fitted-graft collar domain with original-edge
donors, shared UV aliases, explicit part-boundary locks and a continuous area
correction bound. This adapter's `tools/probe_pelvic_domain.py` uses the actual
fitted Geralt LOD bindings and reverses the measured fit into source space.

The rest-fit alignment origin `[11.4565234, .10706377, 83.5382652]` is DIFFERENT
from source anatomical shaft root `[9,0,84.3]`. Target transform is the measured
profile basis/scale/translation. Never substitute the fit origin for the logical
root or infer SI units. Test frame/radii are explicit synthetic fixtures; the
real logical/Raphe guide is not reconstructed by this probe.

Across both LODs and three radius fixtures, checked outputs have zero inversions,
zero body/module seam error, zero stock outer-boundary drift and donor errors
below 1.5e-14 source units. The raw correction initially inverted 10–20 triangles.
The conservative bound accepts only about 17–36% of the synthetic correction.
That is an unresolved shape-accuracy gate, not full-range support. Improve the
actual guide/targets/local support before declaring extreme sliders usable.

## Native output probe

`python tools/probe_control_graph.py` exports the locally licensed stock
`pc_scabbards.w2beh` with the pinned converter, constructs an owned seven-object
graph, and cooks it with official WCC. The graph contains a parent pose input,
one vector variable, a scale node for authored bone `mm_shaft_00` and output.
The native cook retains all required node types and emits a hashed resource.
An official source-resource dump verifies the cached node references and variable.

This is isolated under ignored `build/control-graph/`; it is not in any installed
entity or package. A successful cook does not establish the parent socket's
runtime pose, Geralt's leg-motion preservation, full independent sliders, or
dangle compatibility. Treat these as the next output gates:

1. Bind an authored animated component using the observed stock rig plus new
   joints. Establish parent/pose inheritance without rewriting version-164 player
   resources through the version-159 converter.
2. Demonstrate one actual variable-to-bone deformation in-game while preserving
   the existing good rest shape, leg animation and exact seam.
3. Demonstrate how that component supplies rest poses to secondary motion. The
   native dangle solver's cached rest frames/lengths need a proven update path,
   or a supported small-cage shared solver output replaces that backend.
4. Complete source rest/refined guide preparation in Base. Fit/output the coupled
   pelvis and attachment together, with each LOD's retained stock boundaries.
5. Add all verified controls to the native menu by generating their declarations
   from Base; persist portable preferences separately from backend tuning.
   Rebuild the serialized entity when adding editable controller handles.
6. Run native round-trip/package checks and observed endpoint/combinations,
   movement, equipment/save, contacts and actual CPU timing checks.

Avoid per-vertex WitcherScript loops, copying Base into this repo, or pretending
disabled/stored/no-op menu entries satisfy the task. Rest preparation should run
on control changes; the frame loop should operate on a small motion cage.

## Pin and rebuild caution

The lock now adopts Base `26944f8` for shared authoring/domain work. Installed
0.4.4 assets remain their verified earlier bytes. `build/motion/latest.json` still
records the older cage provenance; `build_motion_release.py` deliberately rejects
that pin mismatch. Prepare/reverify a cage against the new pin for a full release,
or prove a narrow adoption with file hashes. Do not rewrite old evidence to imply
that this new algorithm ran in the installed game.

Wolverine adoption: use the new original-code oracle, body-part boundary locks
and seam/area checks to strengthen its authoring tests first. Keep its current
full native runtime authoritative. No backport or installation was performed.

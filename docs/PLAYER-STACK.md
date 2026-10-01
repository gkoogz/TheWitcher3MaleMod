# Player stack pose candidate

October 1, 2026. 0.4.12 improved idle alignment but the user still observes
waist separation during each step. Treat that result as failed gait parity.

Native offline inspection shows ParentAlign reads another sample/matrix buffer.
An ordinary helper InputNode is also insufficient: PrepareForSample resets the
first graph to reference pose. The 0.4.13 helper candidate is held and prohibited
from installation. These are adapter scheduling findings; Base anatomy is intact.

## Replacement route

`tools/player_stack.py` appends a scale-only graph to the original player stack.
InputNode reads the preceding graph's output, including its current root and
stock bone pose. Ten resets affect only authored joint scale, followed by ten
named scale nodes. The native connected output has 21 pose nodes, no ParentAlign.

The original stock-style orphan appearance mesh binds through the game's
appearance system. There is no separate lower-body animated component, sampler,
dangle output or authored skin attachment in this isolated test. Appearance
autobinding and rendered pose parity still require observed gameplay.

The player's private rig has the original 94 bones followed by the ten existing
authored joints. All stock rest transforms, parents and other rig objects are
preserved. Only Geralt's `player_base_m.w2ent` imports that private rig. Shared
`man_base.w2rig` is not overridden for other characters.

The observed player and parent resources are format 164. Do not rewrite them through the
format-159 converter. `player_rig_redirect.py` changes two equal-length rig
imports inside verified string tables, then updates nested export/table/header
CRCs inside-out. It rejects other changes, unknown versions or mismatched CRCs.
Native cooking/loading must then retain stock animation, behavior, ragdoll and
steering bindings. The controller's new graph handle must also survive cooking.
The player's include redirects to the private parent template; patching only
compiled rig references fails because native cooking regenerates inherited data.
Shared stock parent and skeleton resources remain untouched.

The cooked private rig is also format 164. The converter deliberately rejects
that format. Its 104 names/parents come from the official native XML dump;
`native_rig_frames` verifies the native export CRC/bounds and its trailing
104 x 48-byte position/quaternion/scale records against the authored recipe.
All stock control-rig metadata handles and LOD policy must survive native loading.

At startup the script verifies all 104 observed/authored names, adds one owned
runtime slot and calls AttachBehavior. It never replaces existing player
behaviors, changes freeze state or reschedules player sampling. On removal it
detaches and erases only its own slot. There is no per-frame script polling.

## Reproduction and gates

Installed test: **0.4.15**, `publish/20261001-014011-2cda1b`, built against Base
`466aebb`; cage geometry remains `ca78de0`. 46 tests pass, 23 native pose nodes
are connected, eight resources round-trip exactly and five installed hashes
match. Gameplay observations are pending.

**0.4.14 FAILED authored joint follow:** scaling works, but idle sway leaves the
anatomy unnaturally steady, stretching its base. Waist/ankle parity was not
separately reported. 0.4.15 tests a reference-pose branch plus BlendOverride
with constant full weight on exactly authored indices 94..103; all stock bones
and root motion retain preceding player output. Native TPose copies reference
LS transforms; Reset translation/rotation instead produces zero/identity and
must not be used to reconstruct rest transforms. Native child propagation scans
later parent indices, so there is no evidence for reordering the rig's subtrees.
This remains an unobserved fix hypothesis.

The first rest-mask cook was rejected before packaging because integer-valued
Float JSON properties were silently omitted by vendor CFloat.SetValue. The
constant and weights became zero. `scalar` now emits float tokens and the binary
converter round-trip regression plus strict native mask gate require full weights,
correct names/indices, an active unsynchronized rest branch and preserved root motion.

Use the pinned Base and licensed inputs recorded in the candidate's provenance.
The input-node graph probe is generated with:

```powershell
python tools/build_native_converter.py
python tools/probe_deformation_bridge.py --identity-root --attached-pose
python tools/player_stack.py build/motion/deformation-<new job id>
python tools/verify_motion_package.py --directory publish/<candidate>
python tools/deploy_motion.py install --directory publish/<candidate>
```

Use `--rest-joints` for the authored-only reference-pose mask test (0.4.15).

The builder currently requires the locally observed player native dump/hash;
on a new machine reproduce `tools/inspect_native.py` for the recorded stock
player resource and pass its `inspection.json` with `--player-inspection`.
Never bypass the
hash or native gates. Installation requires the game closed, connected graph,
private rig native verification and matching unpacked resources.

If this candidate regresses, close the game and run native packed verification
and deployment for the exact 0.4.12 package `publish/20260930-231057-0fb1c4`, or
the user-confirmed 0.4.4 baseline `publish/20260930-183505-9d2838`. Recheck package
integrity and current managed installation before restoration. The 0.4.12 files
are also archived at `local/uninstalled/modMaleMod-7734febcc20a`; generic rollback
is still the historical static baseline, not the latest candidate.

This is a pose/scale diagnostic, not all 18 source sliders or active physics.
The grey rows are activation, callback and readback diagnostics. Full controls,
coupled dynamic pelvis and secondary motion are subsequent gates. Animation
sequences, fluid and audio remain deferred.

For every spoke preserve a single native pose authority across original body
boundaries and test movement separately from rest fitting and variable storage.
The particular graph/rig mechanism belongs only in Witcher; shared morphology
and solver improvements have their Wolverine adoption paths in Base.

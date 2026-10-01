# Resume here: Witcher adapter

Checkpoint: 2026-10-01. Read `AGENTS.md`, `README.md`, `HEADLESS-WORKFLOW.md`
and [Base's handoff](https://github.com/gkoogz/MaleModBase/blob/main/docs/HANDOFF.md).
Chat history is not required. Inspect Git and local evidence before assuming
the installed package still matches this record.

## Current size repair: 0.4.23 installed

The user's next screenshot reports 0.4.22 is closer but still incorrect, with an
uneven shaft and sharp distal transition. It establishes loading and visible
enlargement, not exact settings or gait parity. Installed `publish/20261001-074941-b04b52`,
Base `3119d70`, consumes source radius/span measurements in the calibrated export
axis rather than coarse-default displacement vectors in a different posed frame.
All shaft joints share uniform radial scale; both crown joints implement one
similarity transform. Independent lobe fits remain. Defaults, stock bones and
the shipped-template loading repair are retained. Full surface parity is pending.
59 adapter tests, three coherent transport tests, three rest-frame oracle tests,
four authored oracle tests, Base provenance, native cook/graph/rig/template gates,
ten packed resources and five installed hashes pass. Offline default bind and
all-max seam checks pass. New shape quality/moving gameplay is unobserved.
Working rollback stays 0.4.20. See SOURCE-SHAPE-SCALING.md and size-controls provenance.

## Ownership and dependency

This is a separate engine adapter repository. `dependencies/base.lock.json`
is the authoritative exact Base revision and defaults to sibling `../MaleMod`.
Shared geometry, morphology, garment/preference contracts, numerical physics
and clinical timing belong in Base. Native exports, observed Geralt bindings,
WitcherScript, engine materials, input/menu, cooking and deployment belong here.
Changes in Base require deliberate adoption and testing in each spoke.
Wolverine has not yet migrated its authoritative runtime to consume Base.

## Current implementation

**0.4.21 FAILED maximum-slider shape quality; superseded by 0.4.22.**
Package `publish/20261001-063505-7a41a8`, built against Base `15758e5`, unchanged
cage `ca78de0`. Source pin `4df2302` adds only later shared docs.

The first tranche adds overall size, length, width, glans size and scrotum size.
UI ranges/defaults and normalized source samples are generated from pinned Base.
The shared transport math lives in Base; native frame/joint assignments, UI and
persistence belong here. Every authored scale variable is updated on input or
boot, with factors at hierarchy roots to avoid compounded descendant scaling.
Defaults retain the fitted rest shape. This is a small-cage preview, not source
authored-surface, refined glans, coupled-pelvis or physics parity. Remaining
controls have no placeholder/no-op menu rows. Read `docs/SLIDER-PORT.md`.

58 adapter tests, three shared transport tests, Base provenance, native script
compilation/cooking, graph/rig/template gates, ten unpacked resources/buffers and
five installed hashes pass. The initial long initializer hit a parser limit;
five bounded methods compiled. The rejected build was never installed.
See `provenance/size-controls.json`. Test five controls independently, then
combinations while moving; observe close/reopen and restart persistence.

**0.4.20 has observed working loading/pose**, confirmed by the user at 06:21.
Screenshot: first-attempt attached boot, graph active/accepted, readback 1.0,
60 samples, pelvis motion 0.151142, added root motion 0.164259, maximum follow
error 0.000116, pelvis index 9/root index 94, 104 parent entries. It has zero
slider callbacks in that image; that is not evidence of the new controls.
It is the managed working rollback, archived at
`local/uninstalled/modMaleMod-7461db09d18a`, with its F6 bindings retained.

**0.4.19 FAILED loading-screen CTDs** twice at 05:57:52 and 05:59:18.
Windows records 0xc0000005 at witcher3.exe RVA 0x1e06862; the exception is a null
read at 0x80. SDK source entity caches had been copied into cooked output.
Native inspection did not establish game-loader compatibility. That staging
path and installation of those packages are now blocked. Failure provenance:
`provenance/effective-player-0.4.19-failed.json`; archive:
`local/uninstalled/modMaleMod-0a084fad9784`.

The repair extracts the actual shipped gameplay/UI player templates through
official WCC unbundle, requiring the compressed payload's size/CRC and exact
official extracted bytes. Their 16/153 embedded headers retain cooked flags 6;
only two equal-length rig imports and dependent CRCs change in each template.
The intermediate recook is archived outside bundle input. Native loaded root
and scheduling parity is checked against the same shipped source. REDkit's
shipped loaded view has one Cutscene slot; the SDK source view has eight.
Do not describe native source inspection as observing the live player stack.

The 104-joint private rig, graph/rest mask and bounded startup/pose checks remain
in place. Shared geometry, anatomy and numerical physics are unchanged.
56 adapter tests, Base provenance, native graph/rig/template gates, ten exact
unpacked resources/buffers and all five installed file hashes pass. See
`docs/ANIMATION-FOLLOW.md` and `provenance/effective-player.json`.

The 0.4.20 loading/pose gate is now observed. New-control effects, persistence,
full surface shaping and secondary physics remain separate gates.

**0.4.18-boot-recovery-test FAILED observed following.** Package
`publish/20261001-031309-f1ed02`, Base `4b4719f`, unchanged cage `ca78de0`.
The prior 0.4.17 screenshot had an inactive graph and zero callbacks, so its
pose samples were unavailable. The new player-stack script reports the exact
boot exit in a grey F6 menu row, reacquires the player root, retries a missing
root/skeleton or incomplete 104-joint load for at most five seconds, and removes
an owned slot if `AttachBehavior` fails before retrying. It does not poll after
the bounded startup. A graph handle or rig-name mismatch stops with a reason.
Native script compilation/cooking, 47 adapter tests, package integrity, exact
unbundle comparison of eight resources/buffers and five installed hashes pass.
The previous installed candidate is archived under
`local/uninstalled/modMaleMod-d6b0e5eb4ae8`. Re-equip trousers, wait ten seconds,
then inspect the boot, graph, scale and pose rows. A successful graph boot and
60 pose samples still do not prove rendered hip/waist/ankle parity; test idle
sway, walk/run/turn and scale 0.8/1.2 in gameplay. Do not report 0.4.18 as a
motion fix. The screenshot now identifies its actual exit: the player remains
on the 94-joint stock skeleton. This historical build used Base `4b4719f`.

**0.4.17-full-joint-lod FAILED observed gameplay.**
Package `publish/20261001-021142-cf7e81`, source job
`build/motion/player-stack-c38bc5dd963b`, Base `3b10594`, cage `ca78de0`.
Source pin `09d7cf5` adopts the shared LOD requirement/checkpoint only.

**0.4.15 FAILED:** the user reports no attachment-follow improvement; the model
tracks WASD but stays steady during idle sway, stretching its base. 0.4.14 had
the same failure, despite observed scaling. Do not report either as working.

Review found a concrete omitted extension: the private 104-joint rig kept the
stock 40-joint reduced-detail update limit. Native CalcTransforms clamps the
model-space update range by GetLodBoneNum, excluding all authored joints at
indices 94..103 in that mode. `--full-joint-lod` raises the private limit to 104.
Native verification requires the cooked limit to cover every added joint.
47 tests, stock rest-frame/control metadata preservation, 23 connected pose
nodes, eight exact unpacked resources and five installed hashes pass. These
offline/native gates did not predict the runtime failure. The user's
2026-10-01 02:25 screenshot shows `Graph active: false`, scale `accepted: false`,
`Slider changes: 0`, requested scale 1.0, graph readback 0.0, zero pose samples,
zero pelvis/root motion, and untouched diagnostic defaults (pelvis index 0,
root index 0, parent entries 0). The UI thumb displays 0.94. The bounded pose
capture did not run; its zero motion and error readings are missing measurements,
not evidence of successful tracking. The user reports the attachment moves
roughly with WASD but does not follow Geralt's actual hip/idle animation and
appears anchored to another moving reference. Treat 0.4.17 as a failed install
candidate, not a fix.

The candidate also includes `--measure-pose`: after a two-second settling delay,
60 read-only samples at 0.1 seconds capture actor-relative pelvis/root movement
and root position error in pelvis coordinates. This stops after six seconds;
there is no permanent script polling. Re-equip trousers to start another capture.
F6 -> **MaleMod - player pose test** contains the original scale probe, three
old diagnostics and three new measurement rows. A valid capture requires the
controller and graph to boot; the latest screenshot confirms that did not happen.
0.4.16 measurement-only package `publish/20261001-020823-8b1758` was never installed.

The LOD omission is an observed native data defect; its causal role in gameplay
was not verified and it did not yield an active graph in this installed test.
Next agent: inspect component/controller lifecycle and graph boot diagnostics
before changing rig bindings again. Surface each boot exit reason, confirm the
menu callback and runtime controller refer to the same component, reacquire the
player root when needed, and make bounded recovery idempotent so it cannot append
duplicate behavior slots. Preserve zero idle polling and report failure state in
the menu. Do not infer the attachment anchor from this screenshot; the graph
never activated and no pose capture ran. Shared Base REST-GRAFT.md adds
update-range coverage to all spoke adoption checks. Full 18 controls, dynamic
pelvis and active secondary motion remain incomplete. Test idle, walk/run/turn,
waist/ankles and scale .8/1.2 only after graph activation and readback work.
Previous 0.4.15 archive: `local/uninstalled/modMaleMod-fdf18dbc0c66`.
Generic rollback still targets the older static baseline. Use exact-package
verification/deployment for a deliberate recovery; see PLAYER-STACK.md.

**0.4.13-attached-pose-test is HELD, NEVER INSTALLED**, package
`publish/20261001-000237-219d76`: PrepareForSample resets a helper's first graph
to reference pose. InputNode is valid only after a preceding player graph.
The old builder and installer reject the unsafe helper route. Early player
builds were rejected before packaging for a dropped graph handle and inherited
rig recaching; custom schema and private parent include repairs pass native gates.

**0.4.10-root-pose-test FAILED observed gameplay:** the user still sees body
separation and an ankle gap. Root identity alone did not repair it.
0.4.11-connected-motion-test was compiled/packed but is held, never installed:
it feeds the same failing local pose path into the native dangle.
Historical **0.4.12-model-pose-test**, from `deformation-d11b02d4bcc7`:
93 inherited stock bones use model-space ParentAlign, which reads the parent's
bone-matrix buffer rather than its animation sample context. Native initial
script-aware cook/traversal, all six exact packed resources, five installed
hashes and 37 tests pass. **Observed improved but FAILED gait parity:** the user
reports a smaller waist gap that resolves at idle and bobs open with each step.
No fresh scale/ankle diagnostics were supplied. Historical package
`publish/20260930-231057-0fb1c4`, Base `c7f78e3`, cage `ca78de0`.
It uses 93 model-space stock alignments and ten scale nodes (104 connected pose
nodes); scalar motion channels are left for the later candidate. Previous 0.4.10
archive: `local/uninstalled/modMaleMod-a156f580687f`.
See NATIVE-POSE-GRAPH.md. Full source sliders and dynamic pelvis remain incomplete.

Historical installation: **0.4.10-root-pose-test**. Package
`publish/20260930-224402-e6260b`, Base `81fe047`, cage geometry `ca78de0`.
The native attachment copies its parent pose then clears bone zero to identity;
ParentAlign was reintroducing animated Root into the helper. The candidate
preserves the observed identity root from TPose and copies the other 93 stock
bones. It also retains all 60 scalar translation/rotation inputs for the ten
authored joints. Native cook/output traversal, exact six packed bytes and 35
tests pass. Five installed hashes match the receipt. This is a root-gap hypothesis,
not an observed fix. Menu remains one scale probe and three diagnostic readouts.
Immediately previous working-scale 0.4.9 archive:
`local/uninstalled/modMaleMod-8deffd131d19`. Generic rollback still targets the
historical static baseline; use a specifically verified package when recovering.

Latest user observation: **the 0.4.4 native pause-menu category is visible**.
Actual tuning effects/persistence remain unconfirmed. The next request is the
full 18-control port with a dynamic coupled pelvis; read `SLIDER-PORT.md` first.
Base `95da934` adds original-code-verified rest-frame measurement alongside
shared early shape, material laws and the protected graft collar domain. Its
46 tests and provenance pass; rest-frame fixtures compare 3,240 original C++
samples. Complete preparation/glans/coupled dynamics remain unresolved.

0.4.5 graph-to-dangle FAILED observed gameplay: no meaningful resizing and
lower-body offset. 0.4.6 direct output FAILED its native skinning attachment
gate and was never installed. Parent-before-child JSON ownership ordering fixes
that serialization bug without weakening verification. 0.4.7 then passed strict
native binding and all six packed byte checks, but FAILED gameplay too: no
scale change, lower half misaligned, variable accepted **true**. Accepted is not
proof of visible deformation or even a changed requested slider value.

The verified **0.4.4-native-sliders-test** baseline was restored after 0.4.7,
then replaced by 0.4.8, which also FAILED observed gameplay: the user saw torso
idle motion without matching leg motion, and no resizing. Console diagnostics
were not accessible; numeric values remain unknown.

**0.4.9-connected-graph-test has an observed working scale bridge.** The user
reports visibly different results at 0.8 and 1.2 and much improved torso/leg
tracking. Some animations still open a temporary vertical waist gap. The menu
screenshot shows graph active=true, accepted=true, 27 callbacks, requested and
readback=0.800000, frozen=false. The three grey rows are intentional diagnostic
readouts, not missing source sliders. Full 18-control/pelvis work remains pending.
Historical
package `publish/20260930-222053-e9fa95`, Base `95da934`, unchanged cage geometry
from `ca78de0`. Native script compile/cook, strict rig/skin and delayed slots,
full 105-node pose/scale chain, observed stock rig name order, all six unpacked
byte checks and 33 tests pass. Five installed files are receipt-verified.
F6 -> **MaleMod - isolated pose test** exposes one scale row and three disabled
diagnostic rows. Close/reopen the menu to refresh activation, accepted flag,
callback count, requested scale, actual graph readback and frozen-pose status.
No console setup is required. Source controls, dynamic pelvis and visible
secondary motion are incomplete in this direct output test.

The decisive discovered bug: cached inputs were authored without the compiled
`sourceDataRemoved=true` flag. Native recaching interpreted the graph as editable
source, rebuilt it from absent editor sockets, and cleared every connection.
An accepted variable thus never reached its disconnected scale node. The new
native output traversal rejects previous candidates and verifies each named
scale variable and all inherited stock pose inputs. See `NATIVE-POSE-GRAPH.md`.
An initial 0.4.9 bundle included diagnostic graph XML and was rejected before
installation; the installed repack preserves verified cook bytes and reruns
native pack/metadata. Dump paths are now excluded explicitly from bundle intake.

The delayed second instance is retained as a separate lifecycle hypothesis:
ParentAlign caches its animated parent in OnInitInstance, and OnActivated does
not rediscover it. This has not independently established correct parent
attachment. Current RTTI drops the legacy `alwaysLoaded` flag; do not rely on it.

Recovery baseline: **0.4.4-native-sliders-test**, local package
`publish/20260930-183505-9d2838`, Base
`ca78de046a7be63ccb316c7a9b9c12bc7ce3293f`. The recovery baseline is archived at `local/uninstalled/modMaleMod-f1b87204c689`; validate receipt
and use the managed installer after native exact-package unbundle verification.
Read `LIVE-MOTION-TEST.md` and
`WCC-SCRIPTED-COOK.md`. The custom-class cooking blocker is resolved by running
compilation and native cooking in one version-pinned WCC process. Native dump
verifies that the script handle and dangle component reference the same constraint.
All four packed native resources/buffers match their cooked bytes. Five installed
files are receipt-verified. F6/arrow/F8 input bindings were added with a backup.

**0.4.0 was rejected by gameplay testing:** it loaded and produced motion,
but undulated badly and F6 was unresponsive. 0.4.1 replaces the item callback
with `MaleModMotionComponent` lifecycle initialization (including a ready HUD
message), a bounded startup retry, no closed-panel ticking, lower momentum
retention, motion envelopes capped at 0.015 native units and 13 structural links.
The native component and its constraint reference survived cooking.

**0.4.1 was also rejected:** user screenshots show crushing/twisting and F6
remained unresponsive. Tuning limits alone did not solve the problem.

**0.4.2 restored the shape, per user feedback; F6 still failed.** The user also
confirmed the controller-ready load toast, establishing that the loose script
and component initialization run in this installation. Do not pursue a missing
compiled-script package as the explanation for this observed F6 failure.

Historical 0.4.2 implementation: Native EvaluateTransforms aims a
joint's positive X axis at its single child. The old authored frames were about
88-92 degrees out of alignment even at rest. The new cage orients those frames
and its skin inverse binds together; the native export verifies the alignment.
`CPlayerInput.Initialize` now registers F6 using an official wrapper annotation.
Controller lookup checks the player and mounted inventory entities. Missing
controllers produce a diagnostic dialog instead of a silent F6 failure.

**0.4.3 failed the visible-menu test:** the user reported multiple toasts but
no visible menu or sliders. Exact toast text was not supplied. Its earlier
implementation: It registers F6 directly in
that observed component initialization and removes the separate CPlayerInput
wrapper. It unregisters on detach/destruction, leaves no closed-panel polling,
and adds bound-key-count and panel-open/closed toasts to separate input failures
from HUD failures. The exact earlier failure location is not yet proven.
Four native bundle/cache files are byte-identical to 0.4.2; serialized controller
fields and physics settings are unchanged. Full REDkit script compilation,
native unbundle verification, 26 adapter tests and all five installed hashes
passed. See `scriptPatch` in the release provenance for inherited native cook
evidence versus newly compiled script evidence. Live F6/HUD remains unverified.

**0.4.4 replaces the debug HUD with native Scaleform slider rows.** F6 requests
the standard CommonIngameMenu carrying the active controller reference. Select
**MaleMod - motion controls** for gravity, momentum retention and speed. Menu
callbacks clamp/apply values and persist on close. Escape resumes gameplay;
this is a paused native menu, not the requested unpaused corner overlay. It
contains no size sliders and does not claim Wolverine parity. Startup/open/close
toasts, debug HUD drawing and panel ticking were removed. Serialized component
fields were retained for compatibility with the unchanged cooked entity.

Full official compilation, 26 adapter tests, unchanged-field checks, native
unbundle verification and all five installed hashes passed. Native bundle/cache
bytes match 0.4.2/0.4.3 exactly. The user confirms the native menu is now visible;
actual tuning effects and persistence remain pending. Read
`provenance/native-slider-menu.json` for the stock interface evidence. No shared
Base algorithm changed. The installer still retains historical arrow/F8 bindings;
this UI no longer uses them. Future cleanup should remove only owned bindings.

The installed package was built against Base `ca78de0`. The current lock adopts
`fb325ae` for shared authoring and physics laws. These new algorithms do not run
in the restored package. `provenance/base-context-adoption.json` describes only
the earlier documentation adoption; it is not evidence of this newer adoption.
Read [PROJECT-CONTEXT.md](PROJECT-CONTEXT.md) for the user's educational purpose,
phase scope and deferrals. No Wolverine runtime or Base algorithm changed.

The backend still exposes only gravity, momentum retention and simulation speed.
Live size, full Wolverine controls, calibrated contacts, tuning persistence and
measured FPS remain unfinished/unverified. Do not label this a completed 1.0.
See `provenance/motion-release.json` for native and installed-file evidence.

The runtime code is `probes/runtime/maleModPhysics.ws`, explicitly consumed by
`tools/build_motion_release.py`; ordinary `tools/mod.py build` still rebuilds the
static 0.3 baseline. Use `tools/deploy_motion.py` for managed test install/revert.
Do not replace the test with that baseline accidentally. The previous static
installation is preserved at `local/uninstalled/modMaleMod-1291bcd1ecb4`, with
`local/motion-rollback.json` and `local/input-bindings.json` recording recovery.

Shared cage authoring and the 18-control catalog remain in pinned Base. This
continuation changed only REDengine tooling, native resource verification,
WitcherScript HUD/input, and deployment. No shared algorithms were forked.
Animation sequences, fluids and audio remain deferred.

## Historical 0.3 appearance checkpoint

Installed checkpoint: **0.3.0-anatomy-skin-test**, local package
`publish/20260930-061425-92ce53`. All five installed files matched the verified
package. The official unbundler recovered the mesh, external vertex buffer and
underwear entity byte-identically to cooked inputs. Previous version retained
under `local/uninstalled/modMaleMod-a23481b8b7f8`. Installation receipt and
packages remain local; tracked evidence is `provenance/anatomy-test.json`.

Version 0.3.0 is the first fitted anatomy skinning test. Its installed Base was
`abfbc54f3d178a5f05477df9cb506fe1cf3f36ee`. Read `docs/ANATOMY-TEST.md` and
`features/rest-graft.json`. Native preparation is reproducible through
`python tools/mod.py attachment`; packaging refuses stale Base/profile/artifact
hashes. Shared rest fitting and lineage are in Base; native FBX, observed Geralt
bones, skin atlas mapping and cooking remain here.

Official import/export preserved both LOD triangle sets, all 13 skinning bones,
bind matrices and weights within numerical tolerance. Seam aliases have zero
position/weight differences. Original waist/ankle positions and attributes were
preserved. Source unit calibration is an explicit authored reference-width fit,
not inferred physical source units. See `provenance/anatomy-test.json` for the
latest build/deployment record; inspect the local receipt before changing the
installation. Appearance is user-confirmed; motion remains pending user testing.

Geralt's torso and legs are separate resources sharing the native rig. Their
existing waist join is retained. Expansion reaching it requires both resources
to use shared boundary constraints; that live bridge is still future work.
The fitted shape follows stock skinning. No secondary motion, live dilation,
fluid runtime, hotkey or live editor is claimed. Source material transfer and
module LOD reduction are also follow-ups.

## Previous installed checkpoint

Implementation checkpoint: `93ade78d5749917bfa787c4b8267c2ff4cf31fd7`.
Subsequent documentation/pin commits may exist. Current source contains the
official headless pipeline, managed install/uninstall and the bare-body recipe.
The current Base dependency adds the offline collar contract for future fitting.

The previous **0.2.0-bare-body-test** was built against Base
`414823b08ee3340755afcee502a16869a512c6c0`, not the newer collar revision.
Its recorded local package is `publish/20260930-042903-749fcb`; receipt:
`local/installation.json`; target:
`E:/SteamLibrary/steamapps/common/The Witcher 3/Mods/modMaleMod`.
Those ignored files are machine state, not Git artifacts. Tracked evidence is
in `provenance/bare-body-test.json`; recipe in `recipes/bare-body.json`.

The default `Body underwear 01` entity is redirected to stock bare lower body:
`items/bodyparts/geralt_items/legs/bare/l_01_mg__body_underwear.w2ent`.
Official unbundle verified the intended entity without a boxer mesh. User
feedback: "we get a barbie state. Half way there". Bare appearance is confirmed;
movement, seams, inventory and armor transitions are not. It is an item-template
override, not a check that every armor slot is empty.

That earlier version had no attached anatomy. Version 0.3.0 adds the fitted
rest surface. `MaleModInfo()` remains only a diagnostic popup; dynamic collar
integration is still tracked separately in `features/pelvic-collar.json`.

## Local prerequisites and recovery

Recorded paths on this machine:

- Game: `E:/SteamLibrary/steamapps/common/The Witcher 3`
- Depot: `E:/SteamLibrary/steamapps/common/Witcher 3 Mod Depot`
- SDK: `E:/SteamLibrary/steamapps/common/The Witcher 3 REDkit`
- Base: `C:/Users/Administrator/Documents/ChatGPT/MaleMod`

On another machine use `config/local.example.json` to configure ignored
`local/config.json`, obtain the official local inputs and resolve the Base lock.
Run `python tools/mod.py doctor` and adapter tests first. Regenerate exports and
packages through `tools/mod.py`; do not expect ignored `build/`, `generated/`,
`publish/` or `local/` to exist after cloning. Never recursively clean a depot
view containing junctions to stock assets.

Installation is a separate requested action. Existing `Mods/modMaleMod` is
protected: install refuses it; uninstall validates the local receipt/hashes and
moves the owned directory to local recovery storage. If the receipt is missing,
inspect ownership instead of fabricating one or overwriting the directory.
No save/settings files need to be copied into Git to resume development.

## Evidence and next work

Historical bare-body verification: 11 adapter tests; official native export/import, full
script compile, cook, pack, metadata, unbundle and package integrity passed.
See `provenance/native-toolchain.json` and `provenance/bare-body-test.json` for
different build scopes. Bare appearance is the only observed game result.

Read `GERALT-BODY-CANDIDATE.md` before fitting: `t_01_mg__body_hires` is torso;
`s_01_mg__body_hires` is feet. The historical export `geralt-upper.fbx` was feet,
not torso. Raw FBX coordinates do not establish native units or bone mappings.

Current checks: 14 adapter tests and 23 shared Base tests pass. Next, collect the
user's observed appearance/moving-pose results, then improve materials and module
LOD where needed. Live controls require authored morphs or a verified deformation
bridge. Preserve the shared collar law, exact seam bindings and protected waist.
Offer the new shared fitting/verification tools back to Wolverine for future
authoring; its authoritative runtime remains unchanged. Test maximum expansion
and moving poses with normals/contact before claiming live support.

The earlier declaration-probe checkpoint pinned Base `db3ec9d64f68b478d6bae76d0680108539a9eb0c`
for the shared control contract. Its checks were 27 Base and 16 adapter tests.
The installed package remains pinned to the older revision recorded above.
The new native constraint declaration probe compiled successfully; it has not
been bound to the render mesh. See `provenance/runtime-probe.json`.
The rest attachment was regenerated under this pin and again passed official
native import/export checks. Its authoring FBX matches the previous fit byte
for byte; installed package files were verified unchanged. Generated manifest:
`generated/attachment.json`; local job `build/attachment/fit-20260930-070708-d52066`.

Latest source pin: `ca78de046a7be63ccb316c7a9b9c12bc7ce3293f` (shared cage authoring).
Checks: 31 Base tests, 19 adapter tests, Base provenance and official native
motion mesh round-trip. Current isolated job: `build/motion/cage-ec7d87338fd8`.
Stock-class cage resources cook; custom controller-item cook fails with
`Unable to create uncached entity`. No deployment was attempted. The current
rest attachment was also regenerated and reverified under the new pin at
`build/attachment/fit-20260930-075013-7ae7f2`, keeping the normal 0.3 build usable.
All five installed 0.3.0 file hashes were rechecked unchanged.

At handoff update this document, feature status, provenance and the dependency
lock for any intentional adoption. Keep installed build provenance unchanged
until an actual rebuild/deployment occurs.

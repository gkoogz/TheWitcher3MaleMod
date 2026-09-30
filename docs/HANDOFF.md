# Resume here: Witcher adapter

Checkpoint: 2026-09-30. Read `AGENTS.md`, `README.md`, `HEADLESS-WORKFLOW.md`
and [Base's handoff](https://github.com/gkoogz/MaleModBase/blob/main/docs/HANDOFF.md).
Chat history is not required. Inspect Git and local evidence before assuming
the installed package still matches this record.

## Ownership and dependency

This is a separate engine adapter repository. `dependencies/base.lock.json`
is the authoritative exact Base revision and defaults to sibling `../MaleMod`.
Shared geometry, morphology, garment/preference contracts, numerical physics
and clinical timing belong in Base. Native exports, observed Geralt bindings,
WitcherScript, engine materials, input/menu, cooking and deployment belong here.
Changes in Base require deliberate adoption and testing in each spoke.
Wolverine has not yet migrated its authoritative runtime to consume Base.

## Current implementation

Current installed test: **0.4.1-component-motion-test**, local package
`publish/20260930-085405-ea0d8e`, Base
`ca78de046a7be63ccb316c7a9b9c12bc7ce3293f`. Read `LIVE-MOTION-TEST.md` and
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

**Awaiting 0.4.1 feedback:** restart, equip/remove trousers, check the ready
message, walk, F6. See `provenance/motion-release.json`.
The installed backend has gravity, damping and simulation-speed tuning. It does
not yet implement live size, the full 18 Wolverine controls, calibrated contacts,
or verified FPS. Appearance was observed for 0.3; some unstable motion was
observed for 0.4.0. Corrected 0.4.1 motion, corner HUD and saved tuning are
not yet observed. Never label this test a completed 1.0.

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

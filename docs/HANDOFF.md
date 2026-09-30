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

## Implementation versus installed state

Implementation checkpoint: `93ade78d5749917bfa787c4b8267c2ff4cf31fd7`.
Subsequent documentation/pin commits may exist. Current source contains the
official headless pipeline, managed install/uninstall and the bare-body recipe.
The current Base dependency adds the offline collar contract for future fitting.

The installed **0.2.0-bare-body-test** was built against Base
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

There is no attached anatomy or working live body editor/hotkey yet. The console
function `MaleModInfo()` only opens a diagnostic popup. Collar target calibration,
seams and native deformation remain null in `features/pelvic-collar.json`.

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

Historical verification: 11 adapter tests; official native export/import, full
script compile, cook, pack, metadata, unbundle and package integrity passed.
See `provenance/native-toolchain.json` and `provenance/bare-body-test.json` for
different build scopes. Bare appearance is the only observed game result.

Read `GERALT-BODY-CANDIDATE.md` before fitting: `t_01_mg__body_hires` is torso;
`s_01_mg__body_hires` is feet. The historical export `geralt-upper.fbx` was feet,
not torso. Raw FBX coordinates do not establish native units or bone mappings.

Next: measure actual Geralt frame/scale/rig, fit opening and exact seam donors,
refine support while preserving UV/skin lineage, then export verified morphs or
implement a real runtime deformation bridge. Develop reusable math in Base and
pin its tested revision here. Test maximum expansion and moving poses with
normals/contact before claiming live support. Hotkey/menu integration follows a
working native control path; the menu itself cannot establish deformation.

At handoff update this document, feature status, provenance and the dependency
lock for any intentional adoption. Keep installed build provenance unchanged
until an actual rebuild/deployment occurs.

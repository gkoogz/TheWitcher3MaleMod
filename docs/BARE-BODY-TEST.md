# Bare-body user test, version 0.2.0

The requested game deployment was performed by this adapter, separately from
Base's offline extraction work. Package cooking, packing, metadata and integrity
checks passed. The official unbundler recovered one intended native entity.
Its mesh references contain the stock bare lower body and no underwear mesh.
The user confirmed the bare appearance after installation. Movement, seams,
inventory preview and armor transitions have not yet been confirmed.

## What is installed

`Mods/modMaleMod/content/` contains one native entity override plus the existing
diagnostic script. The override is:

`items/bodyparts/geralt_items/legs/bare/l_01_mg__body_underwear.w2ent`

The generated resource is copied from the stock bare-legs entity, whose hash is
pinned in `recipes/bare-body.json`. This retains the existing `Body underwear 01`
item ID/equipment handling but swaps its entity's visible content to Geralt's
bare skin mesh. The bare entity has no boxer component. Stock rig/weights,
materials and LODs are reused. It does not change armor items or the stock depot.
Experimental imported probes are explicitly excluded from this package.

This is a default underwear item override: any other use of that same item
template also uses bare legs. It is not a runtime condition that queries whether
every armor slot is empty. Other underwear variants or costume-specific fallback
items have not been overridden without an observed need.

## Test now

1. Restart Witcher 3 so its mod depot is mounted.
2. Load a save, equip trousers, then remove them to refresh cached equipment.
3. With armor removed, check that the boxers are gone and torso, pelvis, legs,
   hands and feet meet normally.
4. Check walking, crouching/rolling, inventory preview and re-equipping armor.
5. Report a screenshot or errors if boxers remain, a seam opens or geometry is
   missing. Appearance is confirmed; these additional checks remain pending.

No save file, user input settings or existing mod directory was replaced.
The local installation receipt records installed hashes and Base commit. The
bare-body build used the prior Base revision; the newly extracted collar is
for future anatomy fitting, not active in this installed test.

```powershell
python tools/mod.py build
python tools/mod.py verify
python tools/mod.py install
python tools/mod.py uninstall
```

Install refuses an existing destination. Uninstall checks the receipt, refuses
edits/additions or junctions, and moves the owned mod to ignored local storage
for recovery. It does not recursively delete user changes.

## Preparing the attachment through Base

Read Base's `docs/PELVIC-COLLAR.md` and `modules/pelvic-collar.json`. The active
Wolverine final solver recruits a growing asymmetric pelvic region and solves
body/attachment together with hard original-edge seam donors. Its source-derived
math and offline constrained evaluator now live in Base. Do not implement
another independent dilation law in this repository.

Witcher must still supply a measured frame/scale, fitted opening, seam donors/
UV aliases/skin weights, enough local support topology, the actual guide,
normal/tangent reconstruction and a verified native deformation path. Continuous
live expansion is not implemented by this appearance override. The shared C++
kernel cannot load as a WitcherScript plugin without a real runtime bridge.
Use the same feature contract when returning improvements to Wolverine and
future spokes, then validate each native adapter separately.

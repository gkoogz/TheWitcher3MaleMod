# Selected starting body: stock Geralt bare, dry

The game already contains the anatomically blank body needed for fitting.
Use the dry bare body parts as the Witcher character surface; attach shared
MaleModBase modules through the adapter after validating skinning and seams.
The wet bath variant is useful reference data. No need to model a pelvis from
scratch or remove boxer geometry from the default unequipped outfit.

## Observed body parts

Mesh paths below are relative to `characters/models/geralt/body/model/` in the
external uncooked depot. Item templates are under
`items/bodyparts/geralt_items/<slot>/bare/` in REDkit `r4data/`.

| Purpose | Native item | Entity template | Mesh |
| --- | --- | --- | --- |
| Dry bare legs/pelvis | Body legs 01 | legs/l_01_mg__body.w2ent | l_01_mg__body.w2mesh |
| Dry bare torso/arms | Body torso 01 | trunk/t_01_mg__body.w2ent | t_01_mg__body_hires.w2mesh |
| Dry bare hands | Body palms 01 | gloves/g_01_mg__body.w2ent | g_01_mg__body.w2mesh |
| High quality bare feet | Body feet HighQuality | shoes/s_01_mg__body_highres.w2ent | s_01_mg__body_hires.w2mesh |
| Wet legs/pelvis | Body legs wet | legs/l_01_mg__body_wet.w2ent | l_01_mg__body_wet.w2mesh |
| Wet torso | Body torso wet hires | trunk/t_01_mg__body_wet_hires.w2ent | t_01_mg__body_wet_hires.w2mesh |
| Default boxer outfit | Body underwear 01 | legs/l_01_mg__body_underwear.w2ent | l_01_mg__body_underwear.w2mesh **and** l_01_mg__underwear.w2mesh |

Item-to-template mappings were read from
`gameplay/items/_technical_items_defs.xml`; entity-to-mesh references were
observed directly in the native entity files. Head, hair and facial components
remain separate and should retain the character's existing setup.

**Correction:** the earlier adapter incorrectly labeled
`s_01_mg__body_hires.w2mesh` as the upper body. It is the feet. The old local
`build/exports/geralt-upper.fbx` filename is misleading and contains those feet.
`characters/geralt.json` is now corrected. Torso meshes start with `t_01`.

## Bath scene evidence

The opening bath cutscene resource is:

`animations/cutscenes/prologue/q001_beginning/cs001_geralt_and_yen/cs001_geralt_and_yen.w2cutscene`

Its string table contains Geralt's player entity and the item references
`Body legs wet`, `Body palms wet`, `Body feet HighQuality`, and
`Body torso wet hires`. This is resource inspection, not an observed playback
trace. `geralt_inventory_debug__naked.w2ent` also contains the dry bare item names.

The native exporter produced the wet and dry lower bodies. Their raw vertex
and triangle arrays are **exactly identical in both exported LODs**. Their
material XML differs: the wet mesh uses a local skin material with an Ambient
texture override. This does not establish equivalence of every skin attribute,
material, bone weight or runtime effect.

## Geometry inspection

| Exported resource | Geometry 0 vertices / triangles | Geometry 1 vertices / triangles |
| --- | --- | --- |
| Dry lower body | 951 / 1,650 | 504 / 822 |
| Wet lower body | 951 / 1,650 | 504 / 822 |
| Dry torso | 4,268 / 8,098 | 2,193 / 4,046 |
| High quality feet | 2,378 / 4,188 | 1,301 / 2,094 |

Export XML lists LOD distances 0 and 6 for these resources. Raw positions from
the first geometry were rendered in two views with neutral shading. The pelvis
is visibly blank, without modeled external genital anatomy or boxer geometry.
The assembled preview shows torso, legs and feet; head and hands are omitted.
It is not a welded mesh or a skin-deformation test. It uses raw export units;
native game-unit calibration remains unresolved.

Local artifacts (ignored, not copied into Git):

- `build/probe/geralt_lower.fbx`: previously verified dry lower-body export.
- `build/inspection/candidates/t_01_mg__body_hires.fbx`: dry torso export.
- `build/inspection/candidates/l_01_mg__body_wet.fbx`: wet lower-body export.
- `build/inspection/body_geometry.json`: counts, bounds, model names and hashes.
- `build/inspection/geralt-base-candidate.png`: inspected geometry preview.

The large FBX files retain embedded stock textures and adjacent material XML.
Keep these local. `tools/inspect_wcc_fbx.py` reads raw arrays from WCC exports
using numpy; it does not evaluate FBX transformations or skin deformation.

```powershell
python tools/mod.py export characters/models/geralt/body/model/t_01_mg__body_hires.w2mesh build/exports/geralt-torso.fbx
python tools/mod.py export characters/models/geralt/body/model/l_01_mg__body_wet.w2mesh build/exports/geralt-lower-wet.fbx
python tools/inspect_wcc_fbx.py build/exports/geralt-torso.fbx
```

## Next fitting gates

Preserve the stock skeleton, skin weights, LODs and material references. Check
waist/ankle/wrist/neck seams and deformed poses before attaching Base's module.
Use native body items/appearance bindings for runtime selection; normal
unequipping may restore underwear, so an explicit adapter path is required.
No game settings, equipment or active mesh were changed during this discovery.
Shared anatomy or garment changes belong in Base; native Geralt bindings and
appearance selection belong here.

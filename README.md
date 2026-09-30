# Witcher 3 anatomy teaching mod — first draft

This repository starts a **clinical, speculative biology** port of the
[Wolverine Anatomy Tool 2.0 Beta 1](https://github.com/gkoogz/XMenOriginsWolverineMaleMod/releases/tag/v2.0.0-beta.1)
to *The Witcher 3*. The first deliverable is an OBJ reference exported from
the Wolverine rest cage, together with the exporter and a REDkit handoff.
It is **not yet an installable Witcher mod**.

## Available now

- `reference/wolverine_anatomy_rest.obj`: source topology, rest positions and UVs
  (2,388 vertices; 4,596 triangles). Coordinates remain in Wolverine model
  space. It is unrigged and has no Witcher materials or animation.
- `reference/wolverine_anatomy_rest.json`: source and output hashes.
- `tools/export_wolverine_reference.py`: deterministic exporter. It uses only
  Python's standard library and reads the public source headers.

To regenerate from a checkout of the source repository:

```powershell
git -C ..\XMenOriginsWolverineMaleMod checkout v2.0.0-beta.1
python tools/export_wolverine_reference.py --source ..\XMenOriginsWolverineMaleMod --output reference\wolverine_anatomy_rest.obj
```

The exported input headers were checked against release commit
`f5bdef8eb112b4dbbd09c39a276b1cc250244153`. Use a separate source
checkout for this command if another task depends on its current branch.

## Porting route

1. Install [The Witcher 3 REDkit](https://www.thewitcher.com/na/en/redkit/modding)
   and its Blender plugin. Export Geralt's appropriate body entity as FBX.
   Record the game's build, entity path, body part, skeleton and outfit state.
2. Import that FBX into Blender with the official guide's bone-axis settings.
   Import the OBJ reference separately. Determine the coordinate transform,
   scale, anatomical attachment, and skin boundary against Geralt's body.
   Treat the screenshot's white boxers as a **coverage and clipping check**;
   it does not reveal the underlying mesh or skeleton.
3. Build a Witcher-specific mesh and UV/material set. Transfer weights to
   Geralt's exported skeleton, fit the body seam, and check deformation through
   idle, locomotion, combat, inventory, and outfit changes. Do not substitute
   this OBJ directly for a skinned body part.
4. Import the skinned FBX through REDkit's Asset Browser, assemble a reversible
   mod, and test it in game. Keep game archives, extracted proprietary assets,
   local settings, and captures out of Git.
5. Rebuild the teaching sequence as a Witcher-specific controller with
   independently toggled anatomy, animation, fluid visualization, and camera.
   Validate timing and teaching labels before adding detailed effects. The
   Wolverine D3D9 proxy, WBX patches, and installer cannot be reused as-is.

The official [skinned-mesh workflow](https://cdprojektred.atlassian.net/wiki/spaces/W3REDkit/pages/6326771)
documents FBX export from REDkit, Blender bone axes, separate mesh/animation
exports, and mesh import back through the Asset Browser.

## Current limits

No REDkit project, Geralt FBX, fitted mesh, rig weights, Witcher scripts,
in-game effect, or installer is included. The source tool's 35,000-triangle
runtime surface is evaluated from additional Wolverine-specific deformation
data and cannot be recovered by treating the rest cage as a finished asset.
The exported mesh is a reproducible starting reference, not a validated
anatomy model or a tested Witcher 3 replacement.

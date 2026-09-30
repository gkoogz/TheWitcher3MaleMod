# Work from chat, build with official REDkit

Routine work uses `python tools/mod.py`; the editor is optional. The checked-in
`project.json` is **our CLI recipe**, not an invented native REDkit project file.
`workspace/` contains authored resources in the engine's depot-relative layout.
The CLI combines those with ignored generated native resources and invokes the
installed official WCC binary. The output uses the game's regular mod layout.

## Layers and ownership

| Location | Purpose | In Git? |
| --- | --- | --- |
| MaleModBase | Geometry, generic skeleton/sockets, preferences, shared physics and clinical code | Separate pinned repo |
| `dependencies/base.lock.json` | Exact Base commit and resource paths | Yes |
| `characters/` | Observed game resources and bindings, with unresolved facts explicit | Yes |
| `workspace/` | Our authored WitcherScript and native engine resources | Yes |
| `generated/workspace/` | Local imports or modified game-derived resources | No |
| REDkit `r4data/` | Stock scripts, entities and other engine data | External input |
| Uncooked Mod Depot | Stock meshes and textures | External input |
| `build/` | FBX exports, combined scripts, native cooking jobs, logs and checked directory links | No |
| `publish/` | Game-format packages, manifests and ZIPs | No |

The three engine layers are documented in CDPR's
[collaboration guide](https://cdprojektred.atlassian.net/wiki/spaces/W3REDkit/pages/6328326/Collaborating+on+mods).
FBX and its adjacent material XML are described in the official
[skinned mesh guide](https://cdprojektred.atlassian.net/wiki/spaces/W3REDkit/pages/6326771).
The editor's [publish guide](https://cdprojektred.atlassian.net/wiki/spaces/W3REDkit/pages/6328254/Publishing+mods)
describes cooking into bundles, caches and metadata. This CLI uses those same
native formats, while managing the build itself.

## Local setup

Run commands from this repository's root. The example config matches the paths
provided for this machine. To use another machine, copy
`config/local.example.json` to `local/config.json` and edit the paths. Private
configuration is ignored. Keep the checkout in a path without spaces: this
installed WCC's startup path parser is sensitive to quoted path arguments.

```powershell
python tools/mod.py doctor
python tools/mod.py base
```

`doctor` verifies the official tool, game, depot, declared Geralt resources and
exact Base HEAD. A dirty tracked Base or different HEAD is rejected. Update the
lock intentionally when a new shared revision is ready. `base` evaluates the
shared generator through that checkout; it does not copy the generator into
this adapter or imply that GLB can be loaded directly by REDengine.

## Export, edit and import

```powershell
python tools/mod.py export characters/models/geralt/body/model/l_01_mg__body.w2mesh build/exports/geralt-lower.fbx
python tools/mod.py import-mesh build/exports/geralt-lower.fbx characters/malemod/body/geralt-lower.w2mesh
```

The first command exports actual stock data. It keeps the large FBX, embedded
textures and material XML local, and records source/output hashes. The second
creates an engine mesh in `generated/workspace/`. Revisions use new output paths
so another experiment cannot silently replace an earlier one.

Editing the exported geometry can be automated too, for example with Blender
in background mode. Preserve skeleton, weights, material names, LODs and the
material XML. Unit/axis calibration and the body seam are separate fitting work;
export/import success alone does not validate them. No anatomy attachment has
been inferred just from a filename or a screenshot.

## Native commands and discovered 5.0 behavior

These signatures are from the installed executable and bundled CDPR cooker
recipes, then exercised locally. Do not apply old ModKit instructions blindly.

```text
wcc_lite export -depot=local -file=<resource.w2mesh> -out=<absolute.fbx>
wcc_lite import -depot=local -file=<absolute.fbx> -out=<absolute.w2mesh>
wcc_lite compilescripts <combined-script-directory> -out=<directory>
wcc_lite cook -platform=pc -mod=<workspace> -outdir=<cooked-directory>
wcc_lite buildcache textures -platform=pc -db=<cook.db> -out=<texture.cache>
wcc_lite buildcache physics -platform=pc -db=<cook.db> -out=<collision.cache>
wcc_lite dependencies -db=<cook.db> -out=<dep.cache>
wcc_lite pack -dir=<cooked-resources> -outdir=<bundles-directory> -compression=lz4
wcc_lite metadatastore -path=<content-directory>
```

The CLI adds `-uncookDir <directory>` and `-workspaceDir <directory>`, with a
trailing separator, plus `-noninteractivecrash`. These startup arguments use
separate tokens, unlike the commandlet's `-file=...` options. A checked local
read-through depot provides a path with no spaces. Untouched stock directories
are checked junctions; only overridden branches become real directories holding
our files and any stock siblings. It does not copy or move the huge depot.
The tested commandlets could resolve stock resources through `-uncookDir` but
could not resolve custom resources through `-workspaceDir`. The read-through
view puts those custom files in their readable layer too. Never recursively
clean these junction trees or write through a link into the external depot.
Absolute `-depot=<directory>` aborts with a SplitEditorDepot
remap assertion in this version; use the virtual depot and `-depot=local`.

The 5.0 importer accepts an absolute output. A relative output writes beneath
the installation's `bin/` directory instead of the requested workspace. The
wrapper validates and passes an absolute output inside this repo. WCC also
creates a localization SQLite database in its writable workspace. Cooking gets
a separate explicit asset intake so that database cannot become a cook seed.
The initial
probe that exposed this behavior was recovered into the repo and its stray
file removed. Future imports use the corrected path.

The exported FBX embeds textures and can be much larger than the source mesh.
The lower-body probe was about 134 MB. Keep it in ignored local outputs.

## Compile and package

```powershell
python tools/mod.py compile
python tools/mod.py build
python tools/mod.py verify
```

Compilation uses local copies of the installed stock scripts plus authored
workspace scripts. Those stock files and the full `.redscripts` result are not
committed or shipped. The package keeps the authored loose scripts, which the
game merges/compiles as a local mod, following CDPR's
[official script mod layout](https://cdprojektred.atlassian.net/wiki/spaces/W3REDkit/pages/36241465).
This is a supported local-mod layout; it does not claim byte-for-byte equivalence
with every editor publishing option. Assets use native cooking, texture/physics
caches, dependency cache, bundles and metadata. Each build uses a fresh job
directory and only updates `publish/latest.json` after every required command
and artifact check succeeds.

Builders may leave empty files when there is nothing to cache. The CLI accepts
this only with explicit native evidence: zero eligible files, or every physics
input reported as a mesh without collision. It removes those empty, job-owned
files rather than shipping invalid caches. Missing expected nonempty artifacts
remain build failures. Initialization warnings remain visible in local logs;
commandlet errors and nonzero exits stop the build.

```text
publish/<build>/
  Mods/modMaleMod/content/
    bundles/*.bundle      # when native resources are present
    texture.cache         # when the builder has eligible resources
    collision.cache       # when the builder has eligible resources
    dep.cache
    metadata.store
    scripts/local/*.ws
  build-manifest.json
```

The ZIP can be inspected or installed using its `Mods/` tree. Building does not
install it or publish to Steam Workshop. The build manifest includes file
hashes, native tool identity, Base commit and `gameplayTested: false` until a
separate observed game test is recorded. `verify` detects changed files, missing
files and unexpected files before any deployment.

The diagnostic `MaleModInfo()` console function is the only authored runtime
behavior in this foundation. It opens the game's standard message popup. It
does not provide body edits, hook F8 or run the shared C++ solver.

The subsequent 0.2.0 bare-body test adds the native entity recipe in
`recipes/bare-body.json`, installed at the user's request. `generatedResources`
in `project.json` restricts cooking to the intended override and excludes the
earlier imported probe. See BARE-BODY-TEST.md for deployment, rollback and the
distinction between installed assets and observed gameplay.

The first local end-to-end test packaged an imported stock lower-body probe
at `characters/malemod/probes/geralt_lower.w2mesh`, plus the diagnostic script.
It does not replace Geralt's active appearance. The official unbundler recovered
the cooked mesh and external buffer with hashes identical to the packer's inputs.
ZIP CRCs and all five packaged file hashes passed. Tool identity and results
are recorded in `provenance/native-toolchain.json`; the game-derived test data,
full logs and package itself stay local. A fresh clone can build the diagnostic
script alone, then add native imports using the documented commands.

## Next: playable anatomy and live editing

The exported Geralt data makes the next steps scriptable, but they remain
distinct gates: inspect native rig/units, fit the shared module and body seam,
author native appearance/component bindings, implement supported live controls,
then wire the official settings menu and hotkey popup. Record support in
`characters/geralt.json` only after testing the implementation.

The installed script APIs include `CComponent.SetScale`,
`CMorphedMeshManagerComponent.SetMorphBlend`, `CInputManager.RegisterListener`,
`CInGameConfigWrapper` and the game's popup manager. These give concrete routes
for the UI, but arbitrary independent body morphs need authored native morph
assets or another verified deformation bridge. A C++ Base header is not a
WitcherScript plugin. The shared fluid solver still needs an implemented native
or translated runtime, rendering and collision integration.

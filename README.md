# The Witcher 3 MaleMod adapter

Translation layer from [MaleModBase](https://github.com/gkoogz/MaleModBase) into
REDengine. This repository can be developed from chat and built with the
**official REDkit command-line tools**, without operating its editor.

**Resuming without chat history? Start with [the handoff](docs/HANDOFF.md)**
Read [the durable educational context](docs/PROJECT-CONTEXT.md)
and Base's [repository map](https://github.com/gkoogz/MaleModBase/blob/main/docs/HANDOFF.md).

The installed candidate is **0.4.10-root-pose-test**. F6 ->
**MaleMod - isolated pose test** exposes one scale probe plus visible diagnostics.
The earlier compiled graph was recached from absent editor connections, clearing
all pose/scale inputs. 0.4.9 now has user-confirmed visible resizing at 0.8/1.2
and improved leg tracking, with an animation-dependent vertical waist gap.
0.4.10 follows the native attached-component identity-root policy; 93 stock
alignments, ten scales and 60 scalar channels pass connected-output verification.
All six packed byte checks and 35 tests pass. The waist fix awaits gameplay.
See [the native graph fix](docs/NATIVE-POSE-GRAPH.md).

Recovery baseline: **0.4.4-native-sliders-test**, whose menu is user-confirmed.
Full source controls, coupled pelvis, numerical physics parity and an unpaused
corner overlay remain unfinished. Source controls are not represented by the
three engine-specific parameters or the current test row.
See [the handoff](docs/HANDOFF.md) for installed/recovery evidence.

Read [test and rollback instructions](docs/LIVE-MOTION-TEST.md). The previous
0.3 static appearance test is preserved for rollback. The user confirmed its
appearance, but that is not evidence for the new dynamic build. Shared anatomy,
weights and control contracts stay in Base; this repository owns REDengine
translation. [Script-aware cooking](docs/WCC-SCRIPTED-COOK.md) needs the exact
verified local REDkit build and adds no runtime hook to the game.

Version 0.2.0 redirects Geralt's default underwear entity to his stock bare
lower body. It has been cooked, verified and installed locally for user testing.
Restart the game and equip/remove trousers to refresh cached equipment. See
[bare-body test](docs/BARE-BODY-TEST.md). The user confirmed the bare appearance;
movement, seams and armor transitions still need confirmation.

Verified locally with the installed official tools: stock mesh export, FBX
import, full script compilation, cooking, dependency cache, bundle packing,
metadata generation and native unbundle recovery of the mesh plus buffer.
Package/ZIP integrity and fourteen adapter tests passed. Texture/physics builders
were exercised; this probe needs neither custom texture nor collision caches.
See [native evidence](provenance/native-toolchain.json). Broader gameplay remains
unverified. See the current checkpoint above for subsequent gameplay feedback.

## Structure

- `dependencies/base.lock.json`: exact shared Base revision.
- `workspace/`: authored resources in native depot-relative layout.
- `characters/`: observed game resources and explicit unresolved bindings.
- `tools/mod.py`: inspect, evaluate Base, export/import, compile, cook and package.
- `generated/`, `build/`, `publish/`: ignored local game-derived assets and outputs.
- `reference/`: historical first Wolverine export, superseded for new work by
  Base's versioned source assets. Do not extend shared modeling here.

## Commands

Run from this repo's root; configure another machine with `local/config.json`
using `config/local.example.json` as the template.

```powershell
python tools/mod.py doctor
python tools/mod.py base
python tools/mod.py attachment
python tools/mod.py export characters/models/geralt/body/model/l_01_mg__body.w2mesh build/exports/geralt-lower.fbx
python tools/mod.py import-mesh build/exports/geralt-lower.fbx characters/malemod/body/geralt-lower.w2mesh
python tools/mod.py compile
python tools/mod.py build
python tools/mod.py verify
python tools/mod.py install
python tools/mod.py uninstall
python -m unittest discover -s tests -v
```

Packages contain `Mods/modMaleMod/content/` with native bundles, caches,
metadata and authored scripts. They are generated in `publish/` alongside a
hash manifest and ZIP. Building does not activate the mod; `install` is the
separate deployment command. The stock depot remains external; it is not copied
into Git. `recipes/` pins native source overrides; `features/` tracks consumption
of Base contracts and keeps target runtime support explicit.

See [headless workflow](docs/HEADLESS-WORKFLOW.md) for native command signatures,
the confirmed REDkit 5.0 path-parser/importer behavior, source ownership and
remaining runtime gates. Shared changes go into Base; engine translation stays
here, as described in [AGENTS.md](AGENTS.md).

The selected blank-body starting point is Geralt's stock dry bare torso, pelvis,
legs, hands and feet. See [body candidate](docs/GERALT-BODY-CANDIDATE.md) for the
exact item/template/mesh mappings and comparison with the opening bath scene.

# The Witcher 3 MaleMod adapter

**October 11 local startup repair:** Steam build 25773555 is observed working
with the installed native compatibility update and narrow startup-movie helper.
See [repair identities, verification and rollback](docs/HANDOFF.md).
The published frozen payload has not been updated by this local repair.

Repository-only development room: [portable grey sandbox delta and setup](dev/sandbox/README.md).
Use it first for future modeling, clothing and physics iteration. It is excluded
from anatomy releases; every new machine generates its own cooking/gameplay proof.

**Grey studio:** the desktop `Witcher 3 Grey Sandbox` shortcut now binds a
reviewed playable room, with complete body output and clean movement captures.
The black floor artifact was corrected in the studio's particle pass. See
[sandbox status and limits](docs/ITERATION-SANDBOX.md). The stock world remains
loaded beneath the room; numerical physics cadence was not improved by this fix.

Translation layer from [MaleModBase](https://github.com/gkoogz/MaleModBase) into
REDengine. This repository can be developed from chat and built with the
**official REDkit command-line tools**, without operating its editor.

**Resuming without chat history? Start with [the handoff](docs/HANDOFF.md)**
Read [the durable educational context](docs/PROJECT-CONTEXT.md)
and Base's [repository map](https://github.com/gkoogz/MaleModBase/blob/main/docs/HANDOFF.md).

Frozen beta.2 native DX12 payload: Base `99ff741`, all 18 source controls,
full source numerical physics, live coupled pelvic recruitment and both Geralt
LODs. Wolverine adoption is managed in its own adapter. F6 opens/closes the separate live panel; arrow keys
select/adjust and Shift increases the step. Defaults match Base's full-floppy
reset. The original .31 cooked resources remain as the rig/fallback.

The newer development source is pinned independently to Base `421a786` and
includes unfinished persistent-cloth candidates. The frozen release is not a
claimed rebuild of that source. Existing static clothing remains a preview.
See [development and release status](docs/DEVELOPMENT-STATUS.md).

The current radial implementation drives both torso and lower body from shared
waist bindings. It adds deterministic skin matching, source clinical timing,
ambient modes and fluids with actual scene collision. The rear lighting buffer defect is fixed and the final build passed 20 private
gameplay cases; see [RADIAL-CLINICAL](docs/RADIAL-CLINICAL.md). Read
[FULL-RUNTIME](docs/FULL-RUNTIME.md), [OVERLAY](docs/OVERLAY.md) and the current
handoff for evidence, installed hashes, measured timing and verification limits.
Source/target parity and completed GPU output are recorded separately from user
acceptance, FPS and untested rendering modes. Clinical and ambient controls are implemented; future dialogue slots are silent.

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

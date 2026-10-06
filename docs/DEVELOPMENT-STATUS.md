# October 5 repository and release boundary

The working source checkpoint contains the shared collar/menu/clinical adoption,
garment presentation and persistent-cloth experiments, plus the grey studio.
The development Base lock is `40dfa861eda0dce9d1b014ba3ed00732bf3c1e3f`.
These source changes are preserved for future development; the failed new cloth
and soft-material candidates have not been accepted or installed.

## Frozen beta.2

`release/profiles/0.5.0-beta.2.json` pins all 40 accepted installed bytes against
Base `99ff741ea95f18ed84526c35a6c3f38a37d857b6`: 35 native files and the five
required .31 rig/fallback files. The runtime DLL is
`d475488fefe405213de5df058ccaa5c94190ee2089bead7920e1450fe5750099`.
`provenance/frozen-beta2-delivery.json` identifies the payload independently of
the current source checkpoint. Historical `native-delivery.json` remains intact.
The release is an exact frozen installation, not a claimed build of this newer
source. Its numerical worker has a 48-frame byte-identical Base99ff wire5 proof;
an exact adapter source commit for that DLL is not recorded in the frozen receipt.
Do not claim that checking out the release tag rebuilds byte-identical DLLs.

The corrected collar/clinical/menu work is preserved in this baseline. Existing
static clothing remains an opt-in preview with unresolved material/fit limits;
the walking persistent-cloth design is unfinished. Numerical physics cadence,
ray tracing and distant LOD visual behavior retain their recorded limitations.
Dialogue assets remain deferred. A complete installer is not perfect parity.

The beta.1 profile and published archive are immutable. The beta.2 builder accepts
only its declared exact installation; it does not rebuild or silently adopt new
source candidates. The installer supports clean installation, recognized beta.1
and manual-snapshot upgrades, exact backups/rollback and uninstall. Preferences,
user settings, saves and other mods are not payload files.

## October 6 installed attachment repair

The development runtime now has Geralt's measured concentric pelvic recruitment,
shared upper/lower waist, original seam donors and render-thread pose selection.
It is installed separately from frozen beta.2. The 278-case buffer sweep,
39-case body/render test and 78 native grey/campaign views passed their recorded
attachment scope. See `COLLAR-REPAIR.md` and `provenance/collar-repair.json`.
Private sessions, saves/settings/audio and rollback were verified. Native
distant transitions, other rendering modes, garments and performance parity
remain outside this acceptance; measured private cadence is about 89 ms.

## Repository-only room

Read `dev/sandbox/README.md`. This compact delta derives own resources from the
local SDK, starts a fresh stock q002 test bootstrap and builds a real physical
grey studio around Geralt. The original world remains underneath. It needs the
released native MaleMod plus SDK/build prerequisites when starting from vanilla.
No private save, frame or acceptance receipt is an input on another machine.
Actual cooking, gameplay movement and visual acceptance are regenerated locally.
The release builder explicitly rejects developer/private and studio paths.

## Verification

The reference private room had both body resources, 49,884 vertices, 7.609m
grounded locomotion, clean start/middle/end images and live solver publication.
Studio-only `SHOW_Particles=false` removed the moving floor artifact. Cadence was
72.0192ms; F6 interaction was not directly tested in that room acceptance.
Save/audio cleanup and all 40 installed hashes passed. No new game was launched
or installed while preparing this source/package checkpoint.

Packaging tests use isolated installer fixtures, separately from prior observed
gameplay. `tools/test_beta_release.py` verifies clean40, prior30 upgrade, exact
rollback (including added10 removal), edited-file refusal and uninstall/rollback.
It also checks managed40 idempotent upgrade, tampered-payload refusal and the
supported executable hash before mutation.
`tests/test_sandbox_package.py` also verifies new-machine receipt generation,
release exclusions and portable shortcut paths. The private launcher has a
standalone MSVC/WindowsSDK build. Shared cloth gates and their unresolved failures
are recorded in Base's DEVELOPMENT-STATUS and this adapter's garment handoffs.

The repository source audit passed 157 tests including historical installer
fixtures. A fresh tracked-only adapter plus the prescribed sibling Base checkout
passed 145 tests (four optional local-runtime/archive cases skipped). The portable
25-file sandbox delta passed normalized-text identity checks in that export.
Fresh vanilla gameplay/cooking was not performed during this packaging task;
the procedures regenerate those proofs instead of shipping private host inputs.

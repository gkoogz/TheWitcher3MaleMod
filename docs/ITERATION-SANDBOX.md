## October 5 — playable grey studio; movement artifact resolved

The maintained portable development package and reproduction path are now
in `dev/sandbox/README.md` and `tools/sandbox.py`. Start there; the long sections
below preserve diagnostic history and include abandoned standalone-world paths.

Use the desktop `Witcher 3 Grey Sandbox.lnk`. It binds package
`publish/20261005-151112-3a10d9` and reviewed acceptance
`build/probe/sealed-session-20261005-212614/platform-acceptance.json`, without
preview mode. Complete body output, owned floor collision and 7.609 metres of
grounded movement passed. Start, mid-walk and end frames are clean.

The black movement patch was isolated to the engine particle pass; the owned
studio now disables `SHOW_Particles` once its floor is ready. See
[the repair evidence](SANDBOX-FLOOR-REPAIR.md). This adapter scene fix leaves the
installed native anatomy runtime and Wolverine unchanged. Manual script compile
and exact launcher preflight passed. The private test is closed; all 24 original
saves, 40 managed files, original graphics preferences and scoped audio are
preserved.

Remaining limits: stock q002 is still loaded underneath, so this is not yet the
smallest standalone world. Simulation cadence remains 72.0192 ms. Existing F6
integration was retained but its panel/input was not exercised in this test.
The following dated entries are historical development checkpoints.

## October 5, 12:18 — actual transient platform and installed anatomy draw

The modern native-layer package `publish/20261005-105925-01fd6f` passed cook,
physics, dependencies, pack and four fresh official readbacks. Native world
ownership is world1 -> root5 -> group6 -> floorInfo7. The exact cooked world is
SHA256 `44d465ff39e1254b656019e20c120c9f238417bff1aab1580c7b5d4825574325`.
The unchanged warm driver in private PID19676 still stalled after its public
world transition; native ownership correction is not a sufficient gameplay fix.
Its outcome is `build/probe/sealed-session-20261005-111433/sandbox-outcome.json`.
The exact child is closed, audio restored and saves/runtime verified.

The supported alternate route retains the proven q002 stock-world bootstrap
and creates a transient owned physical floor via the public `CreateEntity` API,
`doNotAdjustPlacement=true`, `PM_DontPersist`. Tiny floor package
`publish/20261005-114630-5c86e7` contains no new world. Official native resave,
cook, physics cache, pack and actual entity/mesh readbacks pass. The original
anatomy DLL, worker, controls and all 35 managed files remain unchanged.

Private PID17080 and corrected-controller PID8720 both measured the exact own
floor collider through `StaticTraceWithAdditionalInfo`: component.GetEntity()
matched the transient floor, hitZ32.6033478 and normal(0,0,1). The fresh player
stood on that surface. Both produced native checkpoint200 with completed
anatomy draw, 49,884 vertices and renderFlags853. First proof is
`build/probe/sealed-session-20261005-115210/platform-outcome.json`. Controller
movement and rendered image are not yet accepted: a rootless pause occurred
around engine9 seconds. Both children are closed and their fresh original saves,
scoped audio, temporary files and managed runtime are verified restored.

`iteration_platform.ws` v3 adds explicit pause-reason diagnostics, guarded public
`HideFirstTutorial` only when reason tutorial and HasActiveTutorial are both
true, and native `TakeScreenshot` after the accepted anatomy draw. It retains
stock-world scenery for now; do not describe it as an accepted minimal studio
or a newly solved persistent garment simulation. The F6 implementation remains
the installed native overlay; isolated visual menu acceptance is separate.

## October 5, 09:15 â€” supported HUD retirement is insufficient

The bounded supported diagnostic `iteration_warm_nohud.ws` compiled with the
official compiler, entered stable stock gameplay, and removed all 27 present
HUD modules through `DiscardHudModule`, using the actual registered names.
Independent readback reported 27 removed, zero remaining (28 names checked).
After a deferred public world transition, PID20544 still failed before the own
studio's callback. Its exact exception is retail RVA `e6ba27`, with a deleted
object pointer; it is not yet matched to a named SDK routine. Retiring the
campaign HUD is therefore not a sufficient fix. No GC bypass or address patch
was applied. The exact receipt/context is
`build/probe/sealed-session-20261005-085724/`; the child is closed, scoped audio
restored and fresh saves/installed runtime verified.

The next source control uses SDK-native layer directory population. Measured
`CWorld::OnCook` calls `EnumerateLayersStructure` if the world root is null,
constructs/populates native layer ownership, then sets the embedded layer flag
for serialization. The previous source instead hand-authored the legacy
embedded `CLayerGroup`/`CLayerInfo` tails. `--native-layer-structure` omits those
tails in the uncooked source, matching the SDK reference world's modern source
flags; its floor, terrain, player and quest remain unchanged. Two input
ownership tests pass. Native root/floor readback and gameplay remain pending;
this is a concrete authoring comparison, not a proven cause or fix.

Three depot reuse tests now reject changed/missing inputs, unrelated views and
writable commandlets. The iteration recipe reuses its hash-validated first
cook intake only for read-only physics/dependencies/pack/metadata commandlets;
resave/import/cook cannot use that reuse path. Four native dumps reuse one
view. Task-owned copied shader caches are compressed through NTFS without
changing bytes or stock files; the exact storage receipt is
`build/iteration-package-preservation/cache-compression.json`.

## October 5, 08:32 â€” corrected extent tested; precise HUD traversal fault

Corrected256 package `publish/20261005-074958-637bc7` passed all four fresh
cooked native reference readbacks, legal clipmap/mip sizes, physics cache,
dependencies and packing. Its smallest legal world extent is256; the floor,
one original terrain tile and minimal quest are unchanged. This remains native
acceptance only. Cold PID18196 failed before the own player/loading callback.
The proper exception context matches retail RVA27fb77d to SDK
`TLSFAllocator::RemoveBlockFromFreeList`; its neighbor pointer is noncanonical
`0x21002100210021`. That proves corrupted free-list data, not its original cause.

The corrected package was then tested once through the already working stock
bootstrap using the bound warm driver. PID21708 entered stock gameplay atTick184,
advanced toTick240 and scheduled the public own-world transition atTick259.
It exited before the studio's loading callback. The exact exception is retail
RVA2046bc0, matched to SDK `CHud::OnSerialize` at142063164: traversal of the HUD
module hash buckets (count at+d8, buckets at+f8, node value at+10/next at+20)
while native GC visits their object references. The current node pointer is
deleted-memory marker `0x5dde5dde5dde5dde`. This narrows the failing lifecycle
to HUD reference traversal; it does not identify who first invalidated the node.
Do not change terrain or patch/disable GC based on this crash.

Proper contexts and exact dump hashes are in
`build/probe/sealed-session-20261005-080235/crash-context.json` and
`build/probe/sealed-session-20261005-082729/crash-context.json`. The reusable
read-only helper `tools/inspect_private_crash.py` uses the exception stream's
AMD64 context, verifies its RIP, and labels scanned stack addresses as candidates
rather than an unwound call stack. SDK evidence is
`build/probe/disassembly-83735ade0ed4` and `disassembly-9f54e8155bce`.
Both exact private children are closed, scoped audio restored, temporary world
files/driver removed and fresh original save files verified. Playable own-floor,
walking, anatomy/F6 and rendered-frame acceptance are still incomplete.

## October 5, 07:47 â€” measured world extent correction and warm transition

User confirmed their save opens outdoors in ordinary gameplay, then explicitly
closed the game. A fresh24-file/eight-slot baseline was established; the latest
outdoor autosave was copied read-only. Selection is inferred from recency and
thumbnail, not proven load history. Old backups are never restored over this
new baseline. The native signed-VLQ facts reader now checks complete266-entry
quick/current-auto and375-entry manual blocks through exact EBDF. Five manual
raw nontext UTF16 keys are preserved as code units, never treated as named facts.
Five focused reader tests pass; no campaign/tutorial facts were applied.

Private warm-control PID21052 entered real stock q002 gameplay (Tick240) and
scheduled the public ScheduleWorldChangeToPosition API atTick256/engine4.962s.
The transition into the unchanged own studio stalled before the second loading
callback. This rules out cold tutorial initialization as a sufficient fix; it
does not identify the stalled subsystem. The exact owned thread dump is
`build/iteration-storage/witcher3-21052-warm-transition-threads.dmp`. Child closed,
scoped audio restored, five world files/driver removed, fresh24 save hashes exact.

Read-only SDK evidence identifies another concrete native authoring invariant:
CWorld::InitializeOcclusionCulling requires `iWorldDimensions % iTileSize == 0`
with tileSize256, then derives worldDimensions/256. The former extent128 gives
zero tiles. The author now uses the smallest legal extent256; terrainSize128,
one measured terrain tile and visible floor32 remain unchanged. Two extent and
seven clipmap tests pass; native readback/recook is in progress. Launch now
requires hash-bound cooked nonzero occlusion dimension evidence. This is an SDK
correction, not an observed fix until corrected gameplay advances. Evidence:
`build/iteration-storage/occlusion-dimensions-sdk/proof.json`.

## October 5, 06:40 ï¿½ observed stock quest comparison and save reference

Stock-bootstrap diagnostic package `publish/20261005-062208-1ad7af` passes
resave/cook/physical cache/pack and exact17-root-block quest readback; source
quest is copied natively, not rebuilt through the legacy converter. PID20012
accepted its request and created Geralt in the own world at loading callback
Tick185, then stalled with no later gameplay/anatomy checkpoint. The bounded
child was closed; its save transaction verified all24 originals, audio restored
and temporary files removed. Known-working stock quest alone does not resolve
the own-scene startup. Its external campaign phases are diagnostic dependencies,
not the requested final minimum runtime.

User expressly authorized read-only examination of the post-tutorial save.
There are8 slots (3automatic,3checkpoint,1manual,1quick), not24slots. The sole
manual save and the latest quick save were copied/hash-verified in owned
`build/iteration-storage/post-tutorial-reference-20261005`; no original was
loaded or modified. The manual thumbnail shows clothed Geralt in the inn,
consistent with the user's post-tutorial description. The bundled save reader
can decode compression and variables, identifying `game\witcher3.redgame`,
but its typed fact decoder cannot interpret the complete SBDF raw facts block.
Two literal names are visible in that block: `tut_stash_fresh_playthrough` and
`tut_skipped_exploration`. No inferred fact values were applied. Receipt binds
original/copy/reader/raw-blob hashes and this limitation.

## October 5, 06:17 ï¿½ startup boundary and save recovery

The custom world has produced its own native depot path and Geralt at
`[0,0,0.03]` during loading, but reliable physical-floor, walking, anatomy,
F6 and rendered-frame acceptance remain incomplete. Stock control PID11840
entered `levels\prolog_village\prolog_village.w2w` and continued through
Tick240/360 under the same isolated launcher. This establishes that the private
station can advance gameplay; it does not establish the requested own studio.

Current native package `publish/20261005-054238-d5d243` includes the legal
256/two-level clipmap, explicit map-pin/hunting defaults and a live Start/timer
quest. Its authoring/cook/reference proofs pass. PIDs7360 and5152 reached the
own-world/player loading callback, then failed; their retail exception RVAs
are `0x27fb78e` and `0xedcf32`, respectively, not yet mapped to unique causes.
Deferred RequestNewGame/root-menu closure now compiles correctly outside
OnMenuShown. PID6188 still exited before world/player, this time at the already
observed REDGalaxy64 worker RVA`0x1c5240`. Do not attribute this to terrain or
claim that deferred closure solves platform startup.

The stock control created a private checkpoint at05:10:13 and rotated one
original checkpoint trio. An early title-menu no-save lock did not suffice.
All three original files were recovered from their SHA256-verified backups;
the exact new private trio was preserved outside gamesaves and removed. All24
original save hashes and all35 installed runtime hashes match. Recovery:
`build/iteration-storage/checkpoint-recovery-20261005/receipt.json`.

The driver now reacquires the native no-save lock before game callbacks and
Tick when native AreSavesLocked is false. This is not yet proof that native
checkpoints are blocked. The sandbox launcher also snapshots every ordinary
save, validates originals before cleanup, restores only missing originals and
archives only newly created automatic saves bearing the private-driver metadata.
Changed originals/foreign additions fail cleanup without being overwritten.
Four focused transaction tests pass. PID6188's closed receipt binds this save
transaction; its24 originals are exact and no new save was created. All private
children are closed, process-only audio restored, five world files and temporary
driver removed. No host focus/input or desktop switch was used.

Next bounded comparison is an explicitly labelled `--stock-bootstrap-control`
package: the actual native q002 quest that advanced the stock control, with our
unchanged own floor/world/player spawn. Native source bytes,17 root blocks,
resaved/cooked graph and external phase provenance must pass before launch.
It is a startup diagnostic, not a finished minimal dependency footprint or
scene/physics success. Native scene polish and cost measurements remain gated
on actual entry, grounded movement and native rendering.

# Native iteration world â€” October 5 checkpoint

## Current corrected terrain and platform boundary

`publish/20261005-021828-3b56b8` preserves the single native tile and now uses
SDK `CClipMap::Reinit`'s measured derivation: total resolution 1024, clip size
256, two stack levels. Cooked coarsest height/control buffers are each 131072
bytes and color is 32768 bytes. The exact native receipt is
`build/iteration-storage/world-7f4e57767109/native-links-cooked.json`. Official
resave/cook/physics/dependencies/pack and all resource-reference readbacks pass.
This is native authoring evidence, not a playable-world claim.

Private PID 692 produced a player at the origin during loading (tick 240), but
did not establish the strict own-world identity, grounding, movement or anatomy
checkpoint. A read-only thread snapshot found three threads spinning on one
allocation-related lock; its owner and cause are unproven. Available memory
does not establish an out-of-memory condition. The exact snapshot is
`E:/MaleModBuilds/isolation-capability/witcher3-692-live-threads.dmp`.

The unchanged-package path-readback retry, PID 4488, crashed in a separate
module: `REDGalaxy64.dll` RVA `0x1c5240`, read address `0xffffffffffffffff`.
The deleted-memory marker and captured callback/worker return chain are a
platform-integration diagnostic; they do not justify modifying terrain or
bypassing authentication. Dump:
`E:/MaleModBuilds/isolation-capability/witcher3.exe.4488.dmp`.

The next driver uses supported menu lifecycle events: requests wait for actual
main-menu configuration, optional account connection uses stock Skip Connect,
and pre-existing telemetry choices are preserved. PID 18032 reached the main
menu but exited before an entry readback. Its dump remains separately at
`E:/MaleModBuilds/isolation-capability/witcher3.exe.18032.dmp`. Its proper exception
context identifies retail RVA `0xdafee3`; a unique SDK instruction match places
this in Scaleform `GFx::MovieImpl::Advance`, reading a deleted-memory marker.
The movie owner/cause remains unproven. The next bounded driver delegates the
request/closure to the actual native debug-menu GUI lifecycle rather than
closing a Flash root directly from game OnTick. All three exact private children are closed, scoped audio restored,
and the five temporary package files plus driver removed. Installed anatomy
and garment runtime remain unchanged. The seven clipmap format fixtures pass.

Launch-to-ready, actual gameplay/frame cost and reliable reset remain
unmeasured because no trial has completed the gameplay gate. The one native
terrain tile is an unavoidable measured engine dependency in the present
recipe; no gameplay-world layers were imported. Plain grey material and simple
lighting remain pending after reliable native entry.

The native debug-menu lifecycle driver compiled successfully (source SHA
`8124681b4db3ed40811f3d27577aacde9b4166da1227f64cbd1ef27e69bf4ed6`).
Private PID 1144 persisted an accepted own-world request at tick 121, engine
time 2.372 seconds, after the main menu configured at tick 67. Loading then
stalled before another game tick. A bounded read-only thread snapshot is
`E:/MaleModBuilds/isolation-capability/witcher3-1144-live-threads.dmp` (628640
bytes), with candidate stacks in the sibling `.json`. The main thread is in
an object visitation/serialization loop resembling the SDK legacy garbage
collector; three workers spin on the same allocation-related lock. This is a
semantic diagnostic lead, not an unwound stack or a proven lock owner/cause.
The process and temporary files were closed/removed, audio restored, and all
35 runtime files plus 24 original save files rehash exactly. No extra launch
is justified by guessing terrain settings or suppressing that lock.

The dedicated five-file compressed package is 82992 bytes. This does not
include installed engine assets, referenced shaders, the source tile, or native
authoring read-through caches. Launch-to-ready and active frame cost are still
unmeasured; the request's 2.372 seconds are engine time after initialization,
not an end-to-end ready measurement.

## Current entry repair and distinct loading crash

The loading crash in PID 4644 was independently matched to native
`CClipMap::ToggleLoading`: the world lacked the terrain object which retail
`StartGame` accesses unconditionally. The corrected authoring uses the existing
converter's `TerrainTiles` buffer, not a second custom tail. A duplicate empty
buffer was rejected and removed. `tests/test_iteration_clipmap.py` exercises
empty/duplicate tails, invalid hard imports, CRC and bounds failures.

`publish/20261005-015007-321e28` passes official resave, cook, physics cache,
dependencies, pack and exact cooked readback of one native terrain tile and all
six other resource references. Its native receipt is
`build/iteration-storage/world-1860e8684adc/authoring.json`. Only an owned copy
of the terrain physical-material CSV is changed: original rows are byte
preserved and the SDK checker texture maps to the existing `stone_solid` material.
The stock depot and original converter remain unchanged; original converter
output and the temporary research bridge output were byte identical.

Private PID 17784 passed the earlier null-clipmap site but crashed during native
terrain height copying at retail RVA `0x28c2fcd`. The caller requested 1028
two-byte samples starting at grid coordinate (-4,-4) in a 1024-wide grid. Thus
the one-tile topology has not passed the native halo requirements. No player,
grounding, movement or F6 result is claimed. Its exact dump is preserved at
`E:/MaleModBuilds/isolation-capability/witcher3.exe.17784.dmp`. The private child
and its five files/driver are cleaned; all 35 managed runtime hashes still match.
No further launch is justified without resolving this specific terrain boundary.

The earlier packages below are rejected for world entry. Official native
readback showed zero imports and NULL world/player/camera references: the local
writer requires import flag `Soft=4` for soft handles. A successful native
resave/cook command did not establish usable references.

`publish/20261005-003058-22ac4e` now passes exact official readback of resaved
and cooked world, player, camera, own minimal Start quest, floor mesh and
environment references. Evidence:
`build/iteration-storage/world-16911ff9ad14/authoring.json` and
`native-links-cooked.json`. Hard handles use the native `<resource path>` XML
representation; dumpfile must see the complete depot or it reports a missing
import and NULL. The single floor uses measured `ESF_NoCompExtract` to retain
its directly inspectable native component instead of an opaque streaming buffer.
The launcher requires a hash-bound native package sidecar and rejects old
packages without this reference proof.

Private PID 4644 (`build/probe/sealed-session-20261005-003645/receipt.json`)
exited during the first new-game request with access violation at retail RVA
`0x23746ea` (null write at address `0x78`). WER retained its exact dump outside
the repository. This is a distinct loading failure; no player, physical floor,
walk, anatomy solver or F6 rendering success is claimed. The current driver
contains the SDK's real `CAIMoveToPoint`/player action path for a four-meter walk
after a successful physical floor trace; that action was not reached.

Native main-menu lifecycle is handled through matching stock movie/recap skip
events, with no host key injection. Registry filenames are passed exactly as
the native debug Start Quest menu does. The title-menu no-save lock was insufficient; see the current recovery and transaction gate above.
The official native-aware compiler passed this driver.

The crashed private child is closed, child audio restoration is recorded, and
all five temporary sandbox files and the temporary script were removed. All
35 installed runtime files rehash exactly. No ordinary save was loaded. Grey
material, controlled lighting and observed gameplay remain unfinished.

The requested result is a separate retail REDengine world with a grey physical
floor, the real Geralt gameplay player, animation, installed mod physics and F6
controls. Ordinary saves must not be used to enter it. Base owns common test
cases/dimensions in `profiles/iteration-sandbox.json`, pinned here at
`61427b4cb82a510a8262615b53a78aacce340772`. The installed runtime remains `99ff741e`.

## Completed authoring and native build

- Authored `CGameWorld`, layer group/info, floor layer and `CWitcherGameResource`
  from measured native resource types. New version 159 resources pass official
  REDkit resave; stock 162/163 worlds are not forced through the old converter.
- Owned SDK box mesh includes a real `CCollisionShapeBox`. The layer scales it
  to 32 by 32 by 0.5, with its top at zero. Body-relative/world-unit calibration
  still needs observed gameplay.
- Owned reference environment and real player/camera template references.
- Official resave, cook, physical collision cache, dependencies, packing and
  metadata pass. Package integrity passes for five files.
- Temporary bootstrap compiles with the official native-aware script compiler.
  It requests the dedicated game definition, follows SDK title/menu closure,
  and creates a no-save lock only in the private station.
- Private launcher supports correctly quoted engine arguments. The executable's
  observed `-windowed` switch is used. Audio mute is scoped to the child only.

Package: `publish/20261004-220109-9472d2`.
Provenance: `build/iteration-storage/world-9a60e0412411/authoring.json`.
Compiler proof: `build/iteration-script/compile.json`.

## Not a verified playable sandbox

Private trials 18692, 11216 and 12836 initialized the native runtime but produced
no live character/solver checkpoint. The final trial used the compiled menu
closure fix and `-windowed`. This does not prove world entry, grounded player,
animation, rendering or anatomy physics. A zero anatomy-only probe log is not
proof that the game itself rendered nothing. Entry/lifecycle visibility remains
the next gate. Grey material, a controlled single light, navigation/movement,
cameras and the shared test cases are unverified. The default PBR floor and
reference environment are native carriers, not a finished grey studio.

All exact private children were closed; scoped audio restoration was recorded.
Temporary sandbox/driver files were removed. Rehashing the 35 managed installed
files found zero mismatches. No normal save was loaded by this driver. No
anatomy/garment runtime was installed by this work.

## Historical failed standalone-world recipe

This abandoned experiment is not the maintained playable entry and its local
diagnostic drivers are not distributed. Use dev/sandbox/README.md instead.
Use `build/iteration-storage` as an owned junction to ample no-space storage
(E: here). REDkit's read-through views copy about 1 GB of root caches per native
command. Do not recursively delete these views: stock directories are junctions.
Build `native/launch_sealed.cpp` into `build/iteration-launch/launch_sealed.exe`.
Copy the current `probes/native/iteration_world.ws` into
`build/iteration-script/workspace/scripts/local/malemod/iteration_world.ws`.

```powershell
python tools/compile_native_scripts.py --workspace build/iteration-script/workspace --imports MaleModNativeSealedSession MaleModNativeTestCheckpoint MaleModNativePoseSample --output build/iteration-script/compile.json
python tools/prepare_iteration_world.py --cook
python tools/run_iteration_world.py --package publish/20261005-021828-3b56b8
python tools/run_iteration_world.py --close build/probe/<exact-session>/receipt.json
```

The bootstrap is currently private-test-only; there is no verified user-facing
shortcut yet. Changed source cannot pass an older compilation proof.

## Wolverine boundary

The retail executable has editor/commandlet references and cooked Editor/WEditor
packages. These do not establish a working Raven map cooker. PhysX headers are
not a UE3 map SDK; no compatible map editor/cooker executable was located.
A private CookPackages capability launch failed before creating the child with
Win32 error 740 (elevation required). No commandlet ran or Wolverine file changed.
Do not raise a host UAC prompt or substitute the WStart cinematic for gameplay.
Evidence: `E:/MaleModBuilds/wolverine-sandbox-capability-20261004/launcher-errors.txt`.

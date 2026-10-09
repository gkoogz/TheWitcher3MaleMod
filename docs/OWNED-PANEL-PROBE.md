# October 9 owned panel diagnostic

The actual GDI panel and navigation code now have a default-off, sealed-session
development transport. The SDK fixture passed at 1280x720 and 2560x1440. All
21 rows and the footer fit; the parent reviewed the native client captures.
Navigation, Shift adjustment, row wrapping, clinical and clothing actions,
reset, collapse, token/station/parent authorization and normal production stub
were tested. Each fixture exited with child exit code 0, left no exact child
process running and reported no audio sessions to restore.

This is SDK evidence, not Witcher gameplay. Game visibility, input isolation,
focus behavior, attachment, garments, LODs and campaign transitions remain
unverified. No game runtime was installed. The full attachment gate has not
passed; retain the installed runtime and rollback.

Reproduction is in `dev/sandbox/panel_probe/README.md`. Development transport
and fixture source are tracked but excluded from source/release archives.
Normal builds use a production stub and have no file command transport. An
authorized probe verifies the noninteractive station and same-process parent,
binds commands to token/PID/process creation time and never polls physical
host input or changes host focus, including after transport failure.

Private proof: `build/menu-owned-panel-probe-20261009/final-proof.json` records
compiled source and binary hashes, capture hashes, exact process identities,
cleanup and the independent false game/attachment/installation flags. The
SDK header checkout was clean Base revision
`389f6c04e07b290da34a5261356c745f58f3bb1d`; this did not change the adapter pin.

Final fixture identities: 720p PID 10228, creation time
134360583801016738; 1440p PID 21364, creation time
134360583813103927; production stub PID 14620, creation time
134360583824617498. All were absent after their child handles exited.

A sealed native run using adapter 2943cf1 and the isolated shared menu component
rendered the owned grey room at checkpoints 200/201 (both body resources,
49,884 vertices). Its hidden W2ViewportClass parent prevented menu discovery.
The default-off owned probe may now select that hidden engine parent only after
validating the noninteractive station, same-process parent and probe identity.
Normal production builds continue to reject hidden parents. This does not show
or activate the engine window and does not send host input.

The corrected SDK fixture and production-stub guard passed at 1280x720 and
2560x1440; exact child exit codes were zero and audio restoration counts zero.
Private evidence is D:/MaleModBuilds/witcher-menu-parent-guard-20261009/sdk-proof.json.
The 1440p client capture was visually reviewed. Native menu interaction remains
pending; the earlier room run alone does not pass attachment, garment, LOD,
campaign or performance acceptance. Retail runtime and rollback remain intact.

The corrected ccb268d adapter, isolated DLL db52f317f30805b6, subsequently
attached the native panel to Witcher PID4180 / creation134360616148804702
in the sealed private clone. Sixteen token/PID/creation-bound commands verified
expand/collapse, wrapped selection, one-step and Shift five-step adjustments,
reset, collapsed-input rejection and four GDI client captures. The expanded
native client was visually reviewed. This uses the actual overlay instance;
physical keyboard routing, clinical/garment actions and host-focus transitions
were not exercised. No host input or desktop focus was used.

The owned grey room separately reached checkpoints200/201 with both body
resources and49,884 vertices. The final rear-view native room image was
reviewed; it cannot certify the front attachment. The underlying geometry
worker/bindings remain Base431e626/wire6; only the explicit menu component
comes from4d5ef52. No numerical source was repinned to an unaccepted candidate.

Exact child cleanup returned0, restored one muted audio session, verified all
24 preserved saves/settings and37 original installed files. No replacement
retail installation occurred. Private source/runtime/command/capture/cleanup
identities are in D:/MaleModBuilds/witcher-menu-parent-fixed-20261009/native-menu-proof.json.
Attachment, garments, LODs, campaign and performance parity remain unaccepted.

The normal native CMake build now resolves the shared presentation header from
`dependencies/menu.lock.json` into a generated, hash-verified build cache.
The menu pin c75da1a is exactly Base431e626 plus the shared theme and its
presentation document. Configure rejects numerical differences, a different
repository/header or a mismatched header hash. The worker/profile/binding Base
pin remains431e626; this avoids rebuilding or relabeling source-derived wire6
artifacts just to consume a native menu theme. The cache is reproduced from the
pinned Git blob and is not an independently maintained copy of shared source.

The isolated sandbox builds above injected the identical header explicitly.
A clean normal production build using the new dependency resolver remains to
be checked separately. No compiled replacement is installed by this source
change, and native attachment/campaign acceptance remains incomplete.

The clean normal production build at adapter6c9c2e2 passed with the committed
resolver, Base431 numerical pin and theme-onlyc75da1a menu pin. No private CMake
append or explicit header injection was used. Default-off production DLL:
SHA256bf67ed490f1dff02960b4b7e3b1519b212c19725b22f93bb2fb174eebafe0d20.
The actual resolved header matches5c16fe91. The production SDK fixture passed
and emitted no panel-ready transport even with probe environment variables.
Separate configure tests rejected a numerical-changing component pin and an
incorrect header hash. Existing SDK alignment/shadow and historical cloth
initialization warnings remain in the log; compilation success is not a claim
that the full runtime has no warnings or passed gameplay acceptance.

Private evidence: D:/MaleModBuilds/witcher-menu-production-20261009/build-proof.json
and dependency-guards/proof.json. This production DLL remains uninstalled;
native menu command evidence above belongs to its explicitly identified probe
build. Full attachment, campaign and performance gates are still false.

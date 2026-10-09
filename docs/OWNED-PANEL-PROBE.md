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

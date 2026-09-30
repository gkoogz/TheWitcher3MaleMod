# Script-aware headless cooking

## Failure and evidence

Separate WCC processes compile `MaleModPhysicsItem` successfully but the
standalone cook cannot instantiate it. Native output reports `TEMPLATE COOKING
FAILED` / `Unable to create uncached entity`, even with exit code zero. A stock
`W3UsableItem` fixture cooks successfully. Placing the compiled cache under the
writable workspace's `cooked.redscripts` and `x64.release.redscripts` did not
make the custom class available. These failed probes remain local evidence.

`tools/wcc_scripted.py` runs compilation and cooking in the **same official WCC
process**, retaining the compiler's class definitions. The native cooker now
retained the original `MaleModPhysicsItem` and now retains the replacement
`MaleModMotionComponent`, its scripted `dynamicConstraint` handle, the
native dangle component, constraint, mesh and skinning attachment. A subsequent
native `dumpfile` in the same process proves the handle and component reference
the identical constraint object. `verify_cooked_motion.py` enforces this gate.

## Implementation boundary

This is a Windows debugger wrapper for an owned build subprocess. It never
attaches to the game or another running process, modifies SDK files on disk, or
ships a runtime hook. It requires WCC 5.0.1042178/P4CL 13314933 with SHA256:

`56503cf15e29062579ca26531ec8aa387d056590030bf534a878411ad9c5417e`.

The wrapper temporarily breaks at the WCC command dispatcher, allows the normal
compiler command to finish, then invokes the unchanged dispatcher for `cook`
and native inspection while its script RTTI is still live. The version-pinned
dispatcher RVA is `0x5214f0`; native UTF-8 string constructor/destructor RVAs are
`0x293e240` and `0x293e5f0`. Command arguments use the observed 12-byte native
string layout. The wrapper owns the argument table, so it skips that table's
native allocator cleanup at `0x521d45` and individually destroys the native
strings before freeing its own buffer. This is allocator ownership, not an
engine validation bypass. A different executable hash fails before launch.

Compiler and cooker return values, native error signatures, output files and
native object references remain required. Unexpected native assertions fail.
The SDK's existing `scriptCompiledCode.cpp:56` missing-source-filename assertions
and sound-bank startup assertion also occur in standalone compilation and are
recorded separately. No `-noerrors` option is used. On failure only the wrapper's
child WCC process is terminated; partial outputs never become a release.

SDK dependencies, binaries, compiled stock scripts, native dumps and game-derived
packages remain ignored. Build records contain the WCC/wrapper/source/log hashes.
Only authored loose WitcherScript is shipped with the native mod assets.

## Reproduction

`tools/probe_runtime.py` verifies stock and scripted candidates separately.
`tools/build_motion_release.py` uses script-aware cooking and the native dump
gate. `tools/verify_motion_package.py` uses official `unbundle -dir=...` and
compares every resource/buffer byte. `tools/deploy_motion.py` requires that
verification before installation and preserves the prior mod and hotkeys.

Cooking establishes resource compatibility, not observed gameplay. Continue
with `LIVE-MOTION-TEST.md` and keep live size/contacts/performance unverified
until each has its own native and game evidence.

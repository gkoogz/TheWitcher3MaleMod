# Geralt grey development room

This is the repository-only development delta. It is excluded from anatomy
release ZIPs. The maintained source is `probes/native/iteration_platform.ws`;
`iteration_platform_human.ws` is generated from it. No game resources, saves,
captured frames, settings or vendor binaries are distributed in this directory.

## What runs

A physical grey floor, walls, ceiling and neutral environment are created over
the game's stock q002 test world. Real Geralt animation, collision and the
installed MaleMod DX12 output remain active. This is a cheap **iteration entry**;
the campaign world still exists underneath. It is not the smallest standalone
world. The scene disables shadows and stock particles, the latter preventing
opaque black movement puffs. Numerical physics cadence is unchanged.

Use this room before ordinary gameplay for modeling, collars, clothing, controls
and numerical physics. Base owns the cases and numerical behavior; this adapter
owns the room, cooking, input, presentation and launch transactions. Run a final
ordinary-game regression before publishing a runtime change.

## Reproduce from a vanilla installation

1. Use Windows 10/11, retail next-gen **4.04 DX12**, Steam, Python 3.10+, Git,
   CMake, Visual Studio Build Tools (MSVC/Windows SDK/Roslyn), REDkit and its
   uncooked Mod Depot. Other game/compiler builds require new ABI observation;
   the tools reject mismatched executable hashes.
2. Install the repository's released anatomy package using `Install.ps1`.
   The sandbox uses that mod's native imports; vanilla alone does not supply
   them. It does not use or require another person's save. Start the game once
   to accept its EULA and initialize the user's own folders; then close it.
3. Clone this adapter and MaleModBase. Check out the exact development Base
   revision in `dependencies/base.lock.json`. Copy `config/local.example.json`
   to ignored `local/config.json` and edit all four paths for this machine.
   Keep the build checkout/path aliases free of spaces as required by WCC.
4. Obtain the pinned WolvenKit source/archive/DLL inputs described in
   `docs/NATIVE-CONVERTER.md`, and set `MALEMOD_CSC` to your Roslyn `csc.exe`.
   Install Python `numpy` and `pefile`. Add CMake to PATH or set `MALEMOD_CMAKE`
   to its executable. This builder never changes the SDK/depot.
5. From the adapter root:

   ```powershell
   python tools/mod.py doctor
   python tools/sandbox.py adopt-release --manifest C:/Downloads/Witcher3MaleMod/manifest.json
   python tools/build_native_converter.py
   python tools/sandbox.py build
   ```

   `adopt-release` verifies every installed release byte and creates only ignored
   local integration receipts. It refuses mismatched/unknown installations.
   `build` officially cooks fresh platform resources, compiles both script
   drivers, and builds only the private launcher. It writes `build/sandbox.json`.
6. Verify this machine's actual renderer and movement in an invisible Windows
   station, without desktop keys, focus changes or ordinary audio changes:

   ```powershell
   python tools/sandbox.py verify
   ```

   The command prints the exact private-session receipt. Let its automatic walk
   finish. Review the new native screenshot from your own Witcher screenshots
   directory, then bind it to that receipt:

   ```powershell
   python tools/accept_iteration_platform.py --receipt build/probe/sealed-session-<id>/receipt.json --frame "C:/Users/<you>/Documents/The Witcher 3/screenshots/<new-frame>.png" --visual-reviewed
   python tools/run_iteration_world.py --close build/probe/sealed-session-<id>/receipt.json
   python tools/sandbox.py shortcut --acceptance build/probe/sealed-session-<id>/platform-acceptance.json
   ```

   Replace the placeholders with this machine's exact receipt and capture.
   `--visual-reviewed` means a human/agent really inspected that exact capture.
   A cook is not gameplay proof. Never copy another machine's acceptance receipt.
7. Open **Witcher 3 Grey Sandbox** on the desktop. Normal movement/camera/audio
   and F6/arrow/Shift mod controls are retained. Close the game to remove only
   unchanged studio files and verify/restore the original saves.

The stock new-game bootstrap bypasses the intro/title/recap through script APIs.
It never dismisses a first-time EULA/consent choice. Saves are locked and backed
up; private checkpoint rotations are archived/restored. Launchers refuse an
existing Witcher process, edited studio files or missing/stale acceptance.
An interrupted process retains an exact receipt; close it with
`run_iteration_world.py --close <receipt>` before another run.

## Verified reference and limits

The October 5 reference passed a complete two-part 49,884-vertex body, owned-floor
trace, 7.609 metres grounded walking and clean start/middle/end captures. The
reference native runtime is Base `99ff741ea95f18ed84526c35a6c3f38a37d857b6`, DLL
`d475488fefe405213de5df058ccaa5c94190ee2089bead7920e1450fe5750099`.
Measured interval was 72.0192 ms; this scene does not repair solver throughput.
F6 code was unchanged, but interaction was not directly exercised in that pass.
Fresh installs and builds must generate fresh proofs. Shared cloth candidates
documented as failed/source-only are not installed by any sandbox command.

The compact source inventory and donor provenance are in `manifest.json`.
Run `python tools/sandbox.py check-delta` after cloning; source text hashes
normalize CRLF to LF, whereas runtime resources/packages retain exact byte hashes.
Historical standalone-world and render-control experiments are outside this
maintained path; see `docs/ITERATION-SANDBOX.md` for their diagnostic history.

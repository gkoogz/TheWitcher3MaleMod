Witcher 3 MaleMod 0.5.0-beta.1 - verified snapshot beta

Windows 10/11, Witcher 3 next-gen DX12, ordinary Steam/game launcher.
No REDkit, Python, development checkout, injector or additional SDK required.
This is the current tested draft, not a claim of perfect runtime/visual parity.
Known user-reported limitations: collar recruitment, fluid phase/floor behavior
and interactive menu behavior need further refinement. Ray tracing and distant
LOD transitions were not verified. Dialogue asset slots are intentionally empty.
Wolverine is unchanged.

INSTALL
1. Extract the entire ZIP to an ordinary folder.
2. Close Witcher 3. Double-click Install.cmd. Paste the GAME ROOT, for example:
   E:\SteamLibrary\steamapps\common\The Witcher 3
   (Do not choose bin/x64_dx12 or Mods.)
3. Launch the game's DX12 version normally. F6 opens/collapses the live menu;
   arrows select/adjust, Shift takes larger steps.

Install.ps1 -GamePath 'C:\Games\The Witcher 3'
Upgrade.ps1 accepts the same argument. Both retain exact backups and preserve
runtime preference files, game settings, saves and unrelated mods. Known manual
snapshot installations are adopted only when all known managed hashes match.
Keep the game root short enough for Windows PowerShell backup paths; the
installer preflights path length before writes. Unknown proxy DLLs or edited/missing managed files are rejected; the installer
will not silently overwrite or delete them. Move a competing proxy yourself
only after understanding its owning mod. Junction/symlink game paths are rejected.

UNINSTALL / ROLLBACK
Uninstall.cmd removes only hash-verified managed files, retains preferences and
backups, and prints a rollback ID. Rollback.cmd can restore the preceding managed
snapshot. After uninstall or clean-install rollback, pass its printed ID:
Rollback.ps1 -GamePath 'C:\Games\The Witcher 3' -BackupId '<32-character ID>'
Backups are in GAME ROOT/.malemod-installation/backups. Do not delete that folder
if rollback is needed. Only installer metadata/backups remain after uninstall;
empty mod directories are harmless. Rollback checks backup and installed hashes.

The complete payload contains 25 native adapter files and five .31 baseline
files. It includes cooked body/clinical resources, startup proxy, DLL, numerical
worker, bindings and runtime/script data. No private captures, settings or audio
are distributed. The .31 baseline is required even with native full mode.
SHA256SUMS.txt verifies package files; manifest.json lists every payload hash.
Copyright/source provenance and verification are in the source repositories.

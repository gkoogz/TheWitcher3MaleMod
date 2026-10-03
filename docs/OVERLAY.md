# Installed live overlay

F6 expands/collapses the separate native panel. Up/Down selects a control;
Left/Right adjusts; Shift uses five steps. The panel contains the complete Base
18-value contract and defaults reset. The user has confirmed visibility and live
keyboard operation after ordinary startup. It does not require the pause menu.

Every setter feeds the same asynchronous Base runtime used by the automated
range tests; verification requires completed GPU uploads, not setter readback.
Control preferences persist in an atomic native adapter file and are excluded
from managed installation, rollback and isolated testing. Storage/navigation
unit tests pass. The private desktop does not synthesize host keyboard events;
current exclusive fullscreen operation is separately unverified. F12 is unused.


## Historical checkpoints (superseded)

# Separate overlay investigation

## Implemented native panel; gameplay verification pending

`native/overlay_panel.cpp` now implements a separate owned Win32 panel with
17 sliders, the Rigid/Intermediate/Flexible selector, defaults and close.
A compact Anatomy tab opens it with the mouse; no key is assigned. Values use
the Base control contract and native typed setters. Window code uses
NOACTIVATE/MA_NOACTIVATE and hides on owner focus loss without forcing focus.
It rescales its layout for owner height. The rebuilt 420 by 680 preview has been
visually inspected; hit regions and all slider endpoints pass contract checks.
Preview: `build/full-runtime/overlay-panel.bmp`.

`probes/native/runtime.ws` owns the MaleModOverlay pause reason, requests the
cursor and stores/restores EMPTY_CONTEXT. It compiles through real native WCC
imports. The controller also verifies zero-time source/target output while
editing paused controls. Neither native window visibility nor game pause,
context restoration, menu overlap, exclusive fullscreen, DPI behavior or
character-loading lifecycle has been observed. Keyboard/gamepad accessibility
and persistent preferences remain incomplete. Do not describe the native panel
as installed or gameplay-ready.

The DLL enables it only with an explicit `malemod-overlay.enable` marker and
a valid runtime profile. The current installed .31 menu is unchanged.
Supported native computer control currently fails at helper initialization;
there has been no new game launch or install in this checkpoint.

The historical investigation below explains earlier failures and alternative
interfaces; its statements that no panel exists are superseded by this section.

The user requests an overlay instead of the in-game menu and asks for an
assessment because a previous agent struggled. This is the desired UI; the
installed .31 Overall pause-menu row remains the current test interface.

## Prior evidence

HANDOFF.md records that .4.0-.4.2 had unresponsive F6 input. .4.3 displayed
toasts but no visible menu/sliders. The precise input-versus-HUD failure was
never established. .4.4 switched to the stock paused Scaleform menu, which the
user confirmed visible. Compilation alone did not validate the previous HUD.
Do not repeat that debug-text approach or assume the old F6 path works.

## Interfaces inspected on October 2

Official local REDkit script sources:

- game/gui/flashScriptImports.ws: CHud.CreateHudModule/DiscardHudModule and
  CHudModule.GetModuleFlash/GetModuleFlashValueStorage; sprite/object/function
  bridge to existing Flash content.
- game/gui/hud/modules/hudModuleBase.ws: OnConfigUI obtains the module sprite,
  binds authored Flash functions and positions the module using HUD anchors.
- game/gui/hud/modules/hudModuleDebugText.ws: writes a debugtext.text field;
  it is a text display, not a ready-made interactive slider panel.
- game/gui/hud/hud.ws: stock HUD module creation and input-context handling.
- game/gui/menus/overlayMenu.ws: a stock overlay-menu class exists, but the
  name alone does not establish a separate mod panel or non-pausing input.

These interfaces support investigating an authored Scaleform HUD panel. They
do not prove that a custom module's asset registration, mouse interaction,
visibility and packaging work in this installation. A custom Flash asset and
script callback bridge still need authoring and native/runtime verification.

A native graphics overlay is another engineering route. Wolverine's D3D9
overlay cannot be used unchanged for Witcher's DX11/DX12 rendering; this adapter
has no implemented native graphics-overlay backend or verified script bridge.

## Next implementation gate

First establish a small independent panel with visible text, one draggable
Overall slider and an explicit close control. Verify mouse capture/release,
gameplay input restoration, loading/saving lifecycle and reopening before
expanding the UI. Connect edits to the existing .31 Overall controller; keep
geometry/recruitment and physics in pinned Base and native UI in this adapter.
Do not introduce F12 or another arbitrary activation binding. A separate
overlay has not yet been built, installed or observed in gameplay.

October 2 update: custom native global registration and WitcherScript calls
are now observed in the actual game. The full separate overlay remains
unimplemented. Read FULL-RUNTIME.md for the exact ABI correction and evidence.

# Separate overlay investigation

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

# Native keyboard fence

The observed DX12 Witcher executable SHA-256 is
2df765398a3d1f165db418271be7200178320a4466817379f2fa0dc0001fb101.
Its executable import table contains USER32 GetAsyncKeyState (RVA0x298d620),
GetRawInputData (0x298d738), PeekMessageA (0x298d6f0), and DINPUT8
DirectInput8Create (0x298c030). GetKeyState is not imported. The adapter discovers
these names in the verified executable's own x64 import table; it does not use
these observed RVAs as patch offsets or modify an operating-system DLL.

Call OverlayInputInstall(GetModuleHandleW(nullptr)) early in native bootstrap,
before the executable creates its DirectInput keyboard. OverlayPanel publishes
its exact same-process parent HWND and typed open/anatomy-visible state.
OverlayInputPoll bypasses the executable import fence, allowing raw panel
polling. Verified private probes use their logical owned scope and their existing
fake panel key transport; normal use requires that exact game HWND foreground.
Delete the panel, then call OverlayInputShutdown to restore still-owned slots.

F6 is reserved in this scope. F8, arrows and either Shift are neutral while the
panel is expanded and anatomy visible. J is reserved whenever anatomy is visible;
the installed input.settings explicitly binds J to PanelJour. Other keys and
mouse packets remain untouched. F9 is not reserved, matching source fencing; no
F6/F8/F9 binding was found in the current installed input settings/base inputs.

The executable's async polls return neutral values for these controls. Its raw
keyboard packets and window-queue key-down messages are filtered. DirectInput
interception starts only from its observed imported factory, confirms native
keyboard device capabilities, and requires the exact cooperative HWND. Keyboard
state arrays are neutralized; buffered key-down records are removed. Real key-up
records remain available to clear any game state from before the menu opened.
This prevents a held Shift from remaining latched after its physical release.
No global input hook, key injection, focus change or game pause is introduced.

OverlayInputStatus provides import/poll/raw/message/DirectInput/keyboard counts.
These must be recorded in actual native testing to establish which Witcher path
is in use. The separate SDK transport fixture supplies only owned fake input and
focus functions: it checks all paths, visibility/focus/keyboard guards, journal
conflict, raw panel bypass, real-release retention and patch restoration. The
full 21-row GDI fixture still passes on a sealed station. Actual game keyboard
isolation, held-key transitions and journal behavior remain unobserved until the
primary agent's exclusive native test; no Witcher process was launched here.

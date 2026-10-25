# Witcher MaleMod v2

Active branch: `codex/witcher-v2`. Start with [the handoff](docs/HANDOFF.md).

The complete Witcher v1 source, including uncommitted experiments, is archived
on `archive/witcher-v1-20261024`, commit
`79106bbcca4c200ed1c426f21b5f17eb4772106e`. Its corresponding Base source is
archived on the same branch in Base at
`0b489f24e04628408e2f73c614534a571aa7577b`. These are local branches, not pushed.
See [the archive inventory](provenance/v1-archive.json) for recovery.

The grey test room and required native/toolchain/launch support remain at their
original paths. V1 generated files are frozen in place because room and rollback
receipts reference them. Existing game installations are unchanged. This retains
the room bootstrap; it does not accept the rejected v1 anatomy.

V2 starts from untouched stock dry bare Geralt and the actual canonical Wolverine
implementation. The same shape, pelvic blend, controls, numerical physics,
jockstrap and per-frame service are requirements. Geralt-specific changes belong
in the character/engine adapter; shared changes belong in Base.

```powershell
python tools/mod.py status
python tools/mod.py check-reference
python tools/mod.py prepare-body
python tools/mod.py build-reference
python tools/mod.py reference
python tools/play_grey_room.py --check
```

[V2 requirements and evidence](v2/README.md). These commands prepare native input
and an offline canonical reference. No v2 Geralt runtime or installer exists yet;
native fitting, jockstrap and measured per-frame parity remain open.

The retained [grey-room workflow](dev/sandbox/README.md) is development-only.
Licensed exports, binaries, captures, settings and local receipts stay outside
Git under consolidated Work. Read [the educational context](docs/PROJECT-CONTEXT.md).

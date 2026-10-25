# October 24 - v1 archived; Wolverine-parity v2 begun

The latest user instruction retires all Witcher v1 work except the grey room.
Do not continue the frenulum, modular pelvis, recruitment, transport/cadence or
other v1 repairs. Preserve them as reference.

Complete dirty-source archives were created locally before removing any source:

- Witcher `archive/witcher-v1-20261024`:
  `79106bbcca4c200ed1c426f21b5f17eb4772106e`.
- Base `archive/witcher-v1-20261024`:
  `0b489f24e04628408e2f73c614534a571aa7577b`.

They include all tracked/untracked source at that checkpoint; no candidate is
declared accepted. Neither was pushed. Base's active branch/dirty working source
was preserved. Wolverine's unrelated branding edits and installed runtime remain
untouched.

Witcher's active branch is codex/witcher-v2. 409 v1 files were removed from the
active tree only after verifying each against its archived Git blob. The room,
official toolchain and launch dependencies remain at their original paths.
provenance/v1-archive.json records exact removed/retained source inventories.
Private/generated v1 data remains archived in place under Work/witcher because
room and rollback receipts depend on those paths. V2 output is Work/witcher-v2.

tools/mod.py now dispatches to tools/witcher_v2.py. The old runtime build/install
dispatcher is retired; generic helpers remain for the room. The room's portable
source manifest was stale before archival; refresh text hashes without relabeling
native gameplay proof. Its existing driver/package/installation proof remains
authoritative for that unchanged room, not for v2.

v2/geralt-base.json pins the stock dry bare Barbie body: pelvis/legs, matching
torso, hands, feet and stock bare entity. prepare-body uses official WCC and a
fresh stock-only depot view. No old generated anatomy is an input.

v2/wolverine.lock.json pins 548 inputs, canonical Wolverine HEAD f9e19c4 and
its Base dependency47023a7. The installed reference DLL was verified as
25ca1204061a0a7c0bcdc7943031d8ac8263a1d12c9b4c588efb64d3339ba3fa.
The new Base harness includes canonical source directly. It is an offline x86
reference, not a Witcher port or installed-DLL reproduction.

Read v2/README.md for full parity requirements. Native Geralt fitting, per-frame
runtime, jockstrap integration and source/offline/native/visual/performance
acceptance remain open. No v2 runtime is installed. Keep exact installed files
and rollback until a replacement passes review.

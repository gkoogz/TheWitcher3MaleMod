# Geralt voice reset — October 29

The user's recovered 24-line script is `v2/voice-lines-geralt.csv`. Text is copied
exactly from the last Geralt generation manifest's `transcripts_used`; no dialogue
was newly written. IDs MM-VOICE-0001–MM-VOICE-0024 remain the same across retakes
and future characters. All rows are `needs_recording`, with empty recording paths.
The user-facing copy is the CSV attached to the current task.

## Deleted and preserved

- Deleted 192 rejected Geralt MP3 takes: 96 earlier candidates and 96 v3 takes.
- Deleted all 46 current Witcher voice WAVs and their 46 active-preview copies:
  phase1 13, phase2 11, idle22. The actual installed voice pools had been copied
  from Wolverine; they were not the Geralt candidate takes.
- Preserved script/generation metadata, raw Geralt reference material, Wolverine's
  own installed audio, and explicitly protected historical release/restore points.
  Those historical payloads are not current voice-build inputs.
- All 28 remaining managed files match their original hashes. Runtime, numerical
  worker, geometry, bindings, materials, settings and original saves were not edited.

Receipt: `v2/build/voice-reset/reset-1793293789254565400/receipt.json`.
This hash journal records deletion; it is not a backup of the rejected takes.

## Current build policy and future recordings

`v2/voice-profile.json` is explicitly `needs_recording`. `private_sources()` now
includes only the existing TeachingFluid.ini configuration; it never refills the
deleted pools from Wolverine. The resulting private asset inventory has one file,
and the current installed inventory has 28. Custom sequence/idle voice playback
is intentionally silent until the replacement recordings are approved.

Core's `docs/VOICE-PIPELINE.md` describes CSV editing, stable IDs, revisions,
cross-character scaffolding, PCM checking and approved delivery manifests.

```powershell
python ../MaleMod/tools/voice_pipeline.py check --script v2/voice-lines-geralt.csv
python ../MaleMod/tools/voice_pipeline.py check --script v2/voice-lines-geralt.csv --audio-root path/to/new/audio --require-approved --output v2/build/voices/approved-delivery.json
python tools/prepare_v2_voice_pack.py --delivery v2/build/voices/approved-delivery.json --audio-root path/to/new/audio
```

The last command stages files and a local pointer; it does not install them.
Only change the adapter voice state to `approved` after reviewing the intended
pack. Normal installation still requires fresh native audio/feature acceptance;
the old 13/11/22 source-audio assertions cannot certify a different or silent
voice set. Extend the native audio acceptance contract explicitly when admitting
the new recordings. No gate was weakened and no silent build was falsely passed
as identical audio parity. The current reset is an explicit user-requested asset
removal from the otherwise unchanged accepted runtime.

## Separate executable change discovered before deletion

The game executable already differed from the October28 native qualification:
qualified `2df765398a3d1f165db418271be7200178320a4466817379f2fa0dc0001fb101`;
current `05948d7238e1c9620a1cb9b3125520f1c143ce04a8e5718a3735120c37d7bae0`. Its code/data sections and entry point
differ, not only its file signature. Neither executable was changed by this task.
No fresh game launch or native compatibility pass was attempted. The grey-room
entry needs a new native qualification and acceptance receipt for this changed
executable; the former room acceptance and preview manifest remain historical.
Do not bypass the existing executable/receipt guards or overwrite the game EXE.
The updated preview ownership manifest records only the same audio deletions;
its old executable is intentionally not silently replaced.

Validation: Core voice tests and adapter voice-policy/installer checks passed;
CSV round-trip preserves all 24 transcripts and permanent IDs. The deletion
journal verifies every removed path and all unchanged managed hashes.

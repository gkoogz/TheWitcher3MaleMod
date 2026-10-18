# Scrotal skin folds - October 18

The requested neutral teaching-model refinement adds softer irregular scrotal
folds and a shallow longitudinal web beside the raphe. The complete shaft,
pelvic ramp, rear-expanded attachment, low-Hang placement and independent
numerical suspension remain intact. See Base `docs/SCROTAL-SKIN-RELIEF.md` for
the shared design and other-spoke adoption path.

Shared runtime revision: `6432e69b14fa2907c13c1fae9ff8e718d42f0ffd`.
Candidate DLL: `372a3be3222bafe7c36c5cba9e5b2eb43d15117483bc4544cfa1f571b7162b15`.
Authoring remains b734d56; all five coupled geometry/binding/material/transfer
artifacts and the numerical worker are unchanged from the installed baseline.
Four compiler inputs differ: Base modular_asset.hpp, modular_dynamic.hpp,
new skin_relief.hpp, and the adapter modular_dynamic_render.hpp.
The exact113 compiler inputs and hashes are privately archived because the
adapter includes pre-existing uncommitted native work.

The broad web uses protected geometric relief. Fine irregular folds use a
bounded normal field and react to measured local stretch. Where thin strained
triangles limit geometric relief, its remaining normal detail is retained.
The field is anchored to material coordinates with no time-dependent noise.
No new collision bodies, forces, stiffness, or solver scheduling were added.
The source normal maps, UVs, aliases and donor lineage remain in use.

Rejected diagnostics: independent vertex normal/strain estimates made needle
cut triangles suppress almost all relief; shared material-field interpolation
corrects that. The first native detail pattern formed obvious horizontal bands;
those were replaced with shallower, shorter, irregular folds. A capture hash
change in that rejected session is recorded and is not acceptance evidence.
The geometry and detail fields are then cached without changing output geometry.

Seven focused C++ tests pass, including near-coincident donor continuity,
compression gathering, rotation/scale invariance, protected boundaries and
orientation.32 captured-pose replays preserve shaft/body exactly; the minimum
oriented-area ratio is0.244691; cached geometry matches the uncached candidate
exactly. These are offline results, not native acceptance.

Native verification completed for the fixed candidate: 216 staged captures
across full96, close skin24, motion36, angle-resume12, distant9 and campaign39.
All contact sheets were reviewed. Dedicated distant captures supersede the
occluded full-sweep far views. The native path selected all four supported LODs.
56 additional native-captured replay audits preserve the original body and
attachment topology. Moving and resumed poses retain independent suspension.
Three further installed startup/walking screenshots were reviewed after install.

Official installation and startup acceptance are complete. All 49 managed files
and 31 protected settings/save/audio files hash-verify. Steam grey-room
preflight passes. Exact previous runtime retained at:
`C:\Users\Administrator\Documents\ChatGPT\TheWitcher3MaleMod\local\native-backup-modular-20261018-194521`.
The previous DLL is6b456cc9749f29f23417a46f29a36e84396b0d052ddf69d02a5011620c75cc16.

Private evidence: `D:/MaleModBuilds/modular-anatomy-20261015/scrotal-folds-20261018/candidate`.
Acceptance: `delivery/modular-acceptance.json`; source manifests and exact
compiler/tooling archives are retained alongside the captured images.
Actual side/front/underside figure: `native-skin-review.png`.
All private game children are closed; original saves and audio were restored.

Limits: this is a representative matrix, not every Cartesian setting or quest.
Existing distal extreme-state folds/glans defects remain outside this skin edit.
Fine folds are normal detail; the web includes guarded geometry. No global
self-intersection certificate or clinical-anatomy validation is asserted.
Display-surface processing costs more: full-sweep median52.47ms versus earlier
34.30ms, and walking-resume64.60ms versus41.36ms in non-identical runs.
The numerical worker/scheduling are unchanged; no60-Hz/performance-parity claim.
Wolverine/other spokes require their own pinned adoption and native gates.

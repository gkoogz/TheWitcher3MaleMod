# Scrotal neck material continuity - October 18

The generated neck previously used a harmonic UV extension that contracted
its middle toward the boundary average. Its detail density and tangent-space
normal interpretation differed from the retained sac, exposing the attachment.

The replacement has a dedicated closed chart in unused atlas space. It copies
boundary pigment from the retained surfaces, carries measured sac detail through
the neck at retained-surface density, and blends toward the shaft. Boundary
normal samples are taken from retained faces and expressed in the exact new UV
alias tangent frames. Tangents are rebuilt only on generated neck triangles.

Geometry, collar, source donors, mechanical ownership, Hang, worker, DLL,
retained material rows and all texture pixels outside the new chart and gutter
are unchanged. The 113 compiler inputs match the accepted runtime. This is a
material repair; it does not claim a physics cadence or geometry improvement.

Shared implementation: Base ec7374a, `malemod_base/loft_material.py`.
Witcher authoring: `tools/prepare_neck_material.py`, `build_neck_material.py`.
The native build uses the official REDkit importer/cooker and verified character
texture groups/compression. Four texture-package files are coupled to the new
material artifact in previews, acceptance proofs, installation and rollback.
The core package tool's Base pin remains the numerical baseline431e626; the
material authoring revision is independently pinned through modular.lock.json.

The complete material bake reproduces byte-for-byte. The final material hash is
`a731bd099723112aede87381d4bf53454a5ce31ed3b6fef8384df319a72d3a8f`.
The unchanged DLL hash is
`372a3be3222bafe7c36c5cba9e5b2eb43d15117483bc4544cfa1f571b7162b15`.

Eight shared material tests, three package identity tests and five managed
rollback tests pass. The chart contains57,120 triangles, with no reversed UV
faces. Float32 quantization collapses48 microtriangles occupying1.97e-7 of the
patch area; geometric triangles remain untouched. Runtime half-precision UVs
are reviewed natively rather than represented as mathematically exact doubles.

Evidence root:
`D:/MaleModBuilds/modular-anatomy-20261015/scrotal-material-20261018/delivery-candidate`.
Exact bake provenance is in the sibling `reproduction` folder; the texture-only
package is `TheWitcher3MaleMod/publish/20261018-215010-92b99d`.
Generated textures, game packages, source-derived assets, private settings and
captures stay outside Git. Existing uncommitted adapter runtime/tooling remains
archived with hashes; this is not a clean-checkout release claim.

Native review:180 candidate stages across the size/state/angle matrix, close
skin views, walking after angle changes, both body resources and both supported
LODs, and39 outdoor campaign stages. Full-matrix distant wall occlusions were
excluded and superseded by nine unobstructed dedicated distant views. These
checks found no new pelvic attachment regression. Existing distal extreme-state
folding/glans behavior and regional pigment variation remain; no uniform-color,
solver performance or all-world/all-garment claim is made.

Installed after exact-candidate acceptance. Three installed startup/movement
images were reviewed; Steam grey-room preflight passes. All53 managed files and
31 protected files verify. The engine reordered input.settings; identical
section/line multisets were checked before restoring its original bytes. Saves,
controls, preferences and audio remain exact. All owned sessions are closed.
The installed startup images verify launch/movement, not close material detail;
close material acceptance comes from the exact-candidate native review above.

Rollback: `TheWitcher3MaleMod/local/native-backup-modular-20261018-222856`
contains all49 previous managed files and their receipt, hash verified. The
managed restore removes the four newly added texture-package files. Earlier
UV-only/density/tangent trials remain diagnostic and must not be installed.

Wolverine and other spokes can adopt Base's chart and bake with their own
measured source materials and texture formats. No other game was changed.

# Adopting the stable collar and garment-load worker

This phase intentionally changes Base collar behavior. It must not claim that
the new worker reproduces the earlier moving-frame collar. Historical
equivalence remains available in `prepare_runtime_profile.py`; revision 2 uses
an explicit current Base API proof instead.

## Historical diagnostic proof

`build/worker-revision-agent/Release/surface_worker.exe` links the verified
parallel Win32 Base library. `worker_revision_test` compares an independent
direct Base session with that native worker, initialization plus 48 identical
frames. It varies all controls and modes, extreme rest angles, timesteps,
motion forces, clinical projection, target collar queries and enabled garment
support. Complete encoded outputs are byte-identical.

The diagnostic worker SHA256 is
`1ac2309e9d297ba23ec1b7319994fccb57be0707190f91d1fee62051952f5813`.
Its linked Base library SHA256 is
`afb96824d80df4fa12d90c299f7ff0e1d6dc678b6793adfb2312b7944fd6a1ba`.

The diagnostic receipt is
`build/worker-revision-agent/proof-diagnostic/manifest.json`. It explicitly
records dirty Base and cannot be adopted into a runtime profile. These are
offline transport/numerical results, not installed gameplay.

## Clean pin and proof

After the shared changes are committed, intentionally update
`dependencies/base.lock.json`. Configure without dirty/unverified diagnostic
options. Native CMake selects `currentProcessRuntime` for the revised Base,
checks its parallel wire-5 verification and exact library hash, and preserves
the historical gate for older Base revisions.

```powershell
cmake -S native -B build/native-runtime-worker -A Win32 -DMALEMOD_ALLOW_DIRTY_BASE_DIAGNOSTIC=OFF -DMALEMOD_ALLOW_UNVERIFIED_SURFACE_LIBRARY=OFF
cmake --build build/native-runtime-worker --config Release --target surface_worker worker_revision_test
python tools/verify_worker_revision.py --worker build/native-runtime-worker/Release/surface_worker.exe --executable build/native-runtime-worker/Release/worker_revision_test.exe --output build/full-runtime/worker-revision-clean-proof
```

Use the available bundled CMake executable when it is not on PATH. Proof
directories must be fresh. The receipt binds the Base commit/provenance,
library, worker, replay executable, report and recipe hashes. A clean proof is
required even if a diagnostic build already passed.

## Fresh source and target contracts

The old source bank remains historical. Export the new worker's source bank
into a fresh Base build directory (from the Base checkout):

```powershell
python tools/export_overall_bank.py build/overall-collar-revision2 --executable build/surface-process-verified-cmake/Release/surface_runtime_cli.exe
```

Use its UI-50 surface as the new source rest reference. Preserve the measured
character opening, original-edge donors, UV aliases and all 37 waist masters.
The accepted native job already contains measured radial refinement, skin and
normal encoding corrections, ambient matching and its shadow policy. Preserve
that authored job and its exact native package. Generate fresh bindings against
the revised source bank:

```powershell
python tools/export_live_bindings.py --job build/overall/overall-stable-layout --source-bank ../MaleMod/build/overall-collar-revision2 --boundary build/body-boundary/radial-skin-packed-4 --output build/full-runtime/geralt-bindings-collar-revision2
python tools/readopt_body_runtime.py --package publish/body-material-20261003-070008-d54fc1 --job build/body-boundary/radial-skin-packed-4 --output build/full-runtime/body-adoption-collar-revision2
```

The historical overall job supplies measured fit/cage lineage; the explicit
new source bank supplies revised source/body rest surfaces. The binding export
records both independently and carries the new Base pin. The native package
and material receipts retain their original Base pin and official cook/import
commands. The separate adoption receipt proves the complete package bytes,
unchanged reference assets and authoring modules, measured character exports,
37 waist masters, four authored parts, native body buffers, materials and rig.
No new Base commit is assigned to old native resources. The installer requires
`bodyAdoption` for this explicit historical-package/current-runtime pairing.

Using the preserved job's `package.json` cooked path, use
`prepare_body_render_contract.py --job build/body-boundary/radial-skin-packed-4 --cooked <original-package>/cooked
--bindings <fresh-bindings> --output <fresh-render>`, then derive fingerprints
from those exact native resources. Keep the current measured material encodings and skin
correction, both resources/LODs and exact waist constraints.

Stage the profile with the clean current-Base proof:

```powershell
python tools/prepare_runtime_profile.py --worker build/native-runtime-worker/Release/surface_worker.exe --current-base-proof build/full-runtime/worker-revision-clean-proof/manifest.json --bindings build/full-runtime/geralt-bindings-collar-revision2 --output build/full-runtime/runtime-profile-collar-revision2
```

`--worker-parity-proof` remains the historical-worker equivalence path. It and
`--current-base-proof` are mutually exclusive. The profile records the selected
proof hash and still verifies measured character contact calibration, inverse
binds, binding pin and packet hashes.

Before managed selection/install, run source/target collar, render/waist,
worker/profile, garment fit, clinical collision and actual graphics gates on
these exact artifacts. Preserve clinical/garment selections when changing the
managed installation record. Cooking, staging and playback verification are
separate from this diagnostic worker proof.

## Historical 2062b2d clean artifacts, 2026-10-03

The adopted Base pin is `2062b2d795f5544ea181f126cab32537b8ce7c00`.
`build/full-runtime/selection-next.json` stages the revised profile, bindings,
render contract and separate historical-body adoption receipt. It preserves
the accepted body package and job; root integration must supply the final
clinical, garment and fingerprint selections before installation.

The clean worker proof is
`build/full-runtime/worker-proof-2062b2d-clean/manifest.json`. Its worker SHA256
is `720128ce855fced03f63ac6fd6e2efa3c2913a22226b63af53cf24aa1b0cdca3`.
All 48 complete frame outputs match the direct current Base API byte for byte.

`build/full-runtime/render-2062b2d-revision2` was generated after official REDkit
inspection of both accepted native resources. Its payload after the 112-byte
Base-pin/binding-hash header is byte-identical to the accepted historical render
contract. Its generated bone sampler is also byte-identical, SHA256
`c9ce965f6c41b1a847fcad5e3579118163d960df2ec66df4ddab49923f758ee2`.

`build/full-runtime/body-adoption-2062b2d/manifest.json` verifies the five native
package files, ten frozen Base inputs, four character/authoring inputs and 43
native/measured files. `gate-report.json` verifies the valid receipt and rejects
six altered identity or omitted-input cases. `runtime-artifact-proof.json`
records native payload parity and all 22 source-bank hashes. The source bank
remains the clean revision-2 export made at 795f9dd; the numerical library is
unchanged at final 2062b2d. These are offline/native-inspection results. This
agent did not install, launch, capture or claim final gameplay verification.

## Current clean contact-shape adoption, 2026-10-03

The final adopted Base pin is `c49eea156ab3b6e989f22c52a128123850470dae`.
The previous diagnostics and 2062b2d receipts above remain historical; they do
not identify the current worker or numerical archive. The fresh clean proof
is `build/full-runtime/worker-proof-c49eea1-contact-shape/manifest.json`:

- Base dirty flag: false; wire version 5; behavior revision 2.
- Worker SHA-256: `9bd38ac1bb0d39f6ff96406f132bf7b3fe1156cbfc20fbf6995f8d2e79bebb55`.
- Linked Base library SHA-256: `226ad497dbb50dc3020f691714d2c422a5db7fd66a989ced2daea07bce013da9`.
- All 48 complete outputs match an independently initialized direct current
  Base session byte for byte, including controls, extreme angles, clinical
  projection, collar queries and enabled garment support.

Fresh Geralt bindings, render and runtime profile are respectively
`build/full-runtime/geralt-bindings-c49eea1-contact-shape`,
`build/full-runtime/render-c49eea1-contact-shape` and
`build/full-runtime/runtime-profile-c49eea1-contact-shape`. The exact new body
binding hash is `66de8a9387a04c4187abfb16f8edabf3ba1ec5f6961c3e242c8ff3ceb24027d0`;
the render hash is `f2189fa4ae1519b95f809e6cb71ee5d1927078f41c5b0dddfdc651d74d98b339`.
The accepted native body package remains at its original cook pin. Its separate
`build/full-runtime/body-adoption-c49eea1-contact-shape/manifest.json` validates
unchanged package, source and measured authoring inputs against the revised
runtime. No old cook manifest has been relabeled.

Garment binding and clinical follow-up manifests under their corresponding
`*-c49eea1-contact-shape` directories bind this current pin. The shared garment
now has 4,068 vertices/7,764 triangles; native draws must consume its dynamic
output, while owned native carrier topology and fingerprints remain separately
verified cooking inputs. Final selection, installation and the 53-case private
observed proof are the integration owner's pending gates. The 48-frame worker
proof establishes numerical transport, not gameplay appearance or frame rate.

# Installed skin and thigh repairs — October 28

Body-visual-05 is accepted and installed. The actual installed game was reviewed
in naked front/side/oblique views and jockstrap walking, running, sprinting,
turning and stopped views. The grey-room launcher uses this exact installation.
All 74 managed files match the prepared payload. The previous installed build
and the separate v0.6.0 GitHub checkpoint remain preserved.

## Changes

- Excess shine: use Geralt's native reflectance spectrum, roughness and secondary
  lobe. Retain normalized achromatic source specular detail and adapt the source
  diffuse color in linear space. Native views show reduced blue-white glare and
  a closer body match. The stock SSS branch remains independent of diffuse.
- Thigh distortion: bind against both original complementary Wolverine body
  allocations. The former body0-only projection could select an opposite-side
  donor 8.84 cm away; corrected local examples are approximately 0.1–0.26 cm
  away. Original Geralt topology, skin, lighting and stock baseline positions,
  plus the complete canonical anatomy rows, remain unchanged.
- Pale front patch: original canonical triangles sampled flat tan atlas gaps,
  which became pale pink under color adaptation. A bounded diffuse-only sample
  correction interpolates adjacent textured tissue inside those measured gaps.
  Original texture files, mesh UV arrays, normals, specular/SSS branches and
  physical root weld remain unchanged. Fine muted midline creases remain; the
  broad opaque pale bands are absent in the reviewed views.

The canonical numerical worker, controls, menu, source anatomy/garment geometry
and previous running carrier correction remain unchanged. Witcher outfit fitting
is deferred as requested.

Details: [reflectance](BODY-MATCHED-REFLECTANCE.md),
[donor domain](COMPLEMENTARY-BODY-DONORS.md),
[bounded diffuse sampling](RAPHE-DIFFUSE-SAMPLING.md).

## Verified evidence

All evidence paths below are private local build records, excluded from Git.
Raw numeric reports remain immutable; independent visual decisions are sidecars.
Images were hash-checked, PNG-CRC verified, fully decoded and visually inspected.

| Gate | Evidence | Observed result |
| --- | --- | --- |
| Focused source checks | Visual/domain/material and screenshot-preservation tests | 66 passed |
| Official native pipeline | `build/materials/body-visual-05/` | Resave, cook, textures, dependencies, pack, metadata and DX12 cache passed; zero material-processing errors |
| Complete features | `build/features/native-20261028-193729/review.json` | 31 checkpoints, 1,909 frames, 33 reviewed images; all 21 menu rows and native controls/features passed |
| Attachment/resources/LODs | `build/acceptance/body-visual-05-matrix-pair.json` | Production90 + LOD1 90 cases, masks5|10=15; all 186 images validated and reviewed; production metadata restored |
| Motion and actual GPU pose | `build/materials/native-position-20261028-195827/` | 20 reviewed motion images; seven current native components matched the selected CPU/GPU pose |
| Quiet performance | `build/performance/body-visual-05/performance.json` | All six cases passed; every visible SDK tick serviced; source bare/jock surface cadence retained |
| Campaign | `build/campaign/ordinary-save-holding-1793233006945660900/native/review.json` | Walking, clothing, pause, save, load and resumed gameplay observed; six images reviewed |
| Strict installation gate | `build/acceptance/body-visual-05-aggregate.json` | Passed before preparing/installing the exact payload |
| Actual installed showroom | `build/installed-run-frame/body-visual-05-showroom/` | 269 frames, nine reviewed images |
| Actual installed running | `build/installed-run-frame/body-visual-05-motion/` | 902 frames, 20 reviewed images; running/sprinting/turning/stopping passed |
| Final installed launcher | `build/installed-run-frame/body-visual-05-launcher/` | 281 frames, nine reviewed images; exact room accepted and default activated |

Each closed native session verified the 24 original saves and 922 current photos,
restored scoped audio and removed temporary world/driver files. No physical host
input or foreground game launch was used. Historical missing photo hashes remain
recorded separately; they are not claimed recovered.

## Exact delivery and rollback

Runtime SHA-256: `8eb7ea3638ef2a20503d52427783dcb1106edad6937e5dc7a754c2154ee40a66`.
Canonical worker: `723865a6b294ded67146531f7056b0657da80332c40f7c321250597d1971715a`.
Body binding: `e9e94d6c8bb997f9e68e5c1348a552217ba9afbb1e12d255f344f3f25a851197`.
Compiled material: `e3bfb597fceda0b97ed958d0e660e5a07a94a4d54becc2876923630c1d8c662a`.

Install/result: `build/materials/body-visual-05/installed-result.json`.
Delivery/reviews/rebased preview: `build/materials/body-visual-05/delivery-closeout.json`.
Prepared payload: `build/installation/prepared-1793233602587142800/manifest.json`.
Exact previous-install rollback: `build/installation/prepared-1793233602587142800/rollback`.
Prior complete payload: `build/installation/prepared-1793116386719695200/payload`.
Room acceptance: `D:/MaleMod/Work/witcher/build/probe/sealed-session-20261028-204219/v2-room-acceptance.json`.
The room remains excluded from the installation/release payload.

`python tools/play_grey_room.py --check` verifies the active room, reviewed render,
native/manual script proofs and all 74 installed files. F6/menu and ordinary room
controls remain available through the existing shortcut.

## Limits and preserved rejected evidence

Absolute FPS parity between different engines is not established. All six native
performance cases pass their existing gates, and every visible SDK tick is
serviced, but measured frame costs differ from Wolverine. Geralt keeps native
idle/head motion. Existing extreme source folds, angular pouch underside and
slightly scalloped rear garment edge remain; these are not new thigh tearing or
waistband desynchronization. Image review applies to observed cases, not every
possible future pose.

Intermediate03 was rejected for the pale bands. Two earlier03 native exits with
0xC00000FD remain unexplained; subsequent watched03 tests passed without capturing
the cause.04 failed native shader-cache compilation due to float2 helper output
under a float4 native socket. Neither intermediate was installed.05 explicitly
tests the native float4 wrapper and passes all fresh required native runs without
a debugger. Earlier failed reports, a corrupt03 PNG and preservation mismatch
records remain intact; none was coerced into acceptance. The v0.6.0 release is
unchanged, and this repair does not create or retag a release.

# Geralt thigh donor correction

The canonical packet contains an anatomy allocation and **two complementary
body allocations**. They are not body LODs. The original Geralt binding queried
only the first body allocation when choosing stock-body displacement and
lighting donors. That allocation lacks part of the left inner-thigh surface.
Some left thigh vertices consequently followed distant or opposite-side
boundary points while neighboring graft vertices followed their correct exact
anatomy lineage. This creates a discontinuous deformation field even when the
physical weld itself is exact.

The correction in `bind_wolverine_v2.py` queries the union of both original body
triangle banks. Each donor retains its original packet index: body0 begins at
17,528 and body1 at 32,696. Source triangles with exactly zero area are excluded
because they cannot define barycentric surface coordinates. No row welding,
source geometry change, new deformation law, physics coefficient, target rest
position, skin weight, UV or runtime format is introduced. Exact anatomy and
weld CSR lineage still take precedence over independently projected body rows.
The existing B04 runtime already reads both body allocations.

Both parts are the default for new bindings. `--all-source-body-parts` makes that
choice explicit. `--legacy-body0-only` retains historical reproduction. Use the
normal official cook, material contract, precision/lighting and measured waist
calibration pipeline; the thigh correction itself requires no new FBX topology.

CPU diagnosis against the installed `9725f35b...` B04 binding found stock LOD0
row 304 at native `(-4.866,5.196,90.938)` following an opposite-side body0 point
at `(+3.460,4.982,93.902)`, 8.84 native units away. The complete domain chooses
the correct left-side body1 surface. Rows 871 and 860 reduce donor distance from
4.71 and 6.79 units to 0.263 and 0.105 respectively. In the captured default case,
the maximum thigh-face turn from its rest normal drops from 27.42 to 12.05
degrees. At captured Overall 75 it drops from 172.46 to 37.65 degrees.

These are diagnostic values, **not native visual acceptance** or a global
self-intersection certificate. Some extreme combined cases still rotate faces
past 90 degrees relative to rest; a rest-normal comparison alone does not prove
a 3D triangle inversion. Review the actual front/side/oblique native matrix,
including both LODs, extreme controls and movement, before installation. Preserve
the accepted installation until all fresh gates pass.

The CPU-only replay command preserves the original binding and writes an
isolated comparison input and report to a fresh private directory:

```powershell
python tools/verify_v2_body_domain.py --bindings v2/build/materials/waist-join-01/bindings --captures v2/build/acceptance/run-frame-final-production --output v2/build/materials/body-domain-01
```

Its proof checks every baseline position/skin/lighting byte, every source module
row and exact anatomy weld constraint remain identical. It also retains the
measured lower/upper waist aliases and records the hashes of all replay inputs.
The comparison output is never adopted or installed. New production candidates
must be generated through the calibrated binding pipeline.

## October 28 native acceptance

The corrected domain is adopted in installed body-visual-05. Fresh production90
and LOD1 90 front/side/oblique control cases, running/sprinting/turning/stopping,
campaign and actual installed-room review passed. See
[exact delivery and remaining limits](VISUAL-REPAIR-20261028.md). Offline donor
measurements remain separate from those observed visual decisions.

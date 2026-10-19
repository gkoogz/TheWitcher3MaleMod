# Raised pelvic root ramp installed

The user requested a small radial flare that rises from the original pelvis
into the shaft. Base pin `fcb98a4e6386aa70606c31f24a1b1046ef10eeae` adds a
clearance-bounded forward shoulder and changes the reference aperture margin
from0.12 to0.18, retaining the extra0.08 underside allowance. Both initial
stitching and live reposing use the same function. The offset vanishes with its
first two derivatives at both joined edges. See Base's matching document for
the formula, tests and other-spoke adoption requirements. Adapter adoption:b977c39.

Original body coordinates, source boundary donors, both body resources, waist,
UV aliases, suspension geometry, materials and numerical worker are preserved.
Only three of114 compiler inputs differ from the previous installed build: the
shared surface stitch, pelvic aperture and dynamic mount headers. All coupled
assets match the previous installation; only the runtime DLL hash changes.

Eight C++ tests,32 prior-pose replays and68 new captured-pose audits pass. Native
review covers252 captured stages,246 usable views, across representative sizes,
angles, states, Hang, motion, supported LODs and one campaign scene. Six full-run
views688 and691-695 are wall-occluded; a nine-frame unobstructed distance run
supersedes them. Close native side/front/oblique and underside views were reviewed.
The original body remains exact and audited ramps contain no reversed faces or
nonmanifold edges. Native startup and walking after installation were observed.

The preview initially rejected one copied `igxess.dll` because its hash differed
from both the unchanged licensed source and the manifest. The isolated file was
recopied from that verified source, then the entire preview was revalidated. No
hash check was bypassed; the failed pre-launch save transaction was also closed.
No cause of the copied-file discrepancy was established. All owned sessions are
closed, temporary drivers/room files removed, saves/audio restored. The engine
only reordered input.settings; identical bindings were verified before restoring
the exact original.53 managed and31 protected files verify. Steam grey preflight
passes.

- DLL SHA256:fd95ca61331a983788208480b9ecd372b16d61d24751a3274eaaf64c240b0935.
- Material SHA256:72412e7e6d100d83852fd70a5f404c1760c86b8a8298ec2e8ba45b385ac80c5d.
- Numerical worker pin:431e626cae6fb6720b552f8b20206727fe809c80.
- Installed native receipt:build/probe/sealed-session-20261019-114345/receipt.json.
- Exact rollback:local/native-backup-modular-20261019-114157.
- Evidence:D:/MaleModBuilds/modular-anatomy-20261015/root-ramp-20261019/candidate-01.

Coverage is representative, not every Cartesian control combination or world
transition. Existing extreme distal/glans defects remain outside this root
repair; no numerical cadence or performance improvement is claimed. Compiler
inputs include pre-existing uncommitted adapter code and are archived privately;
this local development installation is not a clean-checkout release. Other
spokes must pin Base and pass their own native gates before adoption.

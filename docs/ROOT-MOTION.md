# Root motion participation

The October 20 report of a rigid proximal region was traced to two shared
geometry constraints, rather than missing solver motion. Base's
`AnchorRootPhysics` reset the first section's orientation; `SocketMaterialState`
reset it a second time after socket resampling. The curvature limiter then
spread bending farther down the shaft.

The adapter now consumes Base's corrected modular headers. Position remains
anchored, rotation survives, and the radial ramp follows the resampled moving
socket tangent while its pelvic boundary stays fixed. The numerical worker,
forces, ordered update pipeline and authored rest geometry are unchanged.

The six-case, 240-frame actual-worker probe records raw and driven root rotation.
The old mapping produced zero driven root rotation in all cases. The corrected
mapping retains the measured source rotation in every sample. Shared regression
tests cover positive/negative rotations, three section radii, three socket
stations, fixed socket center, section diameter and independent suspension.

The x64 CMake source check follows the modular pin; x86 follows the numerical
worker pin. Both pins must agree on the numerical revision. This permits a
renderer-only correction without rebuilding or silently repinning the worker.

Native walking/decay review is available through `review_live_controls.py
--case physics-motion --last-stage 635` after preparing the corresponding
officially compiled driver. Full native attachment review and installation
are separately recorded in private Work receipts. A passing replay or build
does not establish those outcomes.

# Native render-pose alignment

The source worker still consumes one SDK tick's physics input and advances once.
Its synchronous x86 work can outlast a native actor/animation update. A rigid
garment posed from the earlier input then trails the body drawn from the native
engine's newer transform.

The owned moving-pause diagnostic proved this without changing source geometry,
offsets, solver or material: actor position advanced 22.93 mm, yaw changed .8175
degrees, and one local bone moved 28.45 mm. The same captured garment had .519 mm
minimum sampled band clearance against its original body pose, but penetrated
the freshly frozen body by 20.911 mm. Reevaluating the original garment against
the fresh pose restored .525 mm clearance. A separate 101-checkpoint turn run
reproduced the visible walking clip, while all saved matching-pose samples
remained outside the body. This does not justify enlarging the waistband.

An immediate second read inside the same game callback returned the same cached
actor transform on all 1,818 frames and still clipped while walking. The owned
late-phase prototype instead used the SDK's observed `TICK_PostUpdateTransform`
timer group. Its 782 successful late publications exposed up to 112.93 mm of
actor movement, zero fallback consumptions or failed refreshes, and a continuous
waistband in the previously failing walking view. Its paused pose reread matched
all actor and bone matrices exactly. One queued frame was explicitly cancelled
when the process entered pause; this was not an extra physics step.

The adapter now defers display publication after the original worker step. A
zero-period player timer in `TICK_PostUpdateTransform` resamples actor inverse
and all required bones, then calls
`MaleModNativeRefreshRenderPose(epoch,seconds)`. That 24th registered native
callback evaluates Meridian exactly once and publishes body, garment and fluid
together under the existing frame publication lock, with the same completed
source serial. It never advances the anatomy solver or motion filtering again.
The existing body receiver update and clinical After run once here with the fresh
pose, preserving the main tick's captured milliseconds and dt. Clinical Before
stays on the main tick; there is no additional fluid update. New collision queries
remain available to the following main tick, as before.
The prior complete frame stays published until this transaction is ready.

Every actor snapshot begins with bone -1, which now resets bone readiness and
increments a capture revision even when its frame token is unchanged. Refresh
requires a complete later revision, the matching actor epoch, source-frame token and
completed source serial. Duplicate, mismatched or cancelled pending work cannot
be replayed. Pause, invalidation, exceptions and shutdown clear pending work.
Existing clinical failure behavior is unchanged; source numerical data and
worker bytes remain pinned.

The script cancels queued work when paused, absent or changing player. An older
queued frame has a guarded main-tick fallback before a new step; the validated
prototype used the late path for every consumption. The source token identifies
the completed physics request; it does not pretend that the later pose was read
at the earlier wall-clock instant. A refresh without pending work is a native
protocol failure, ensuring a stopped script cannot appear healthy merely because
it stopped calling the frame service.

The garment script also preserves the same valid player's existing carrier while
paused. Cached body draws need not update the visibility observer; that absence
must not destroy a retained garment. Player changes, absent player and Naked
still clear the carrier normally.

Sealed checkpoint requests made while publication is pending are bounded and
queued, then written after the matching publication. Suspension, actor change
or failure discards them with a trace record. Metadata distinguishes host source,
garment and published serials plus sampled/published pose revisions. Intentional
paused diagnostic rereads therefore remain identifiable rather than being
mistaken for the published frame.

Timing keeps callback scopes separate from engine scheduling. `callbackMs` is
`mainCallbackMs + lateCallbackMs`; these elapsed scopes include the original
worker wait, reported separately as `sourceWaitMs`. `renderPoseWallDelayMs`
reports the gap from the main callback's end to the late callback's start, while
`simToRenderWallMs` reports the complete span. The intervening engine work is not
counted as adapter callback CPU cost. `clinicalAfterServices` makes the one-After
per successful publication count observable.

The deterministic SDK-free production-gate test covers one step/one cloth
evaluation, fresh pose, complete serial publication, duplicates, stale/mismatched
requests, pause/invalidation and exception cleanup. Causal native artifacts are
under `v2/build/materials/jock-shading-audit/band-fit/moving-pause-proof.json`.
The prototype restored the owned preview script and original manifest exactly;
production integration still requires moving and paused native visual acceptance,
the full matrix, performance and
campaign gates remain required before installation.

# Native body mapping

The canonical numerical worker is unchanged. The native adapter divides two
independent mapping loops into at most four tasks: normal-frame groups, then
unique target rows. It copies material-state aliases only after every unique
row has completed. It retains each row's floating-point operation order.
The change flags use separate bytes so adjacent tasks cannot race on packed bits.

Every borrowed task receives the calling thread's full SSE MXCSR state and
restores its own prior state on normal return or exception. No global scheduler
policy changes. Small ranges execute directly. SourceBinding remains owned by
the existing serial host publication path; this does not make concurrent calls
to Evaluate safe.

The permanent v2_binding_parallel_test covers partition bounds, remainders,
all sixteen rounding/FTZ/DAZ combinations, state restoration and exceptions.
The private production replay compares the actual modified header against its
saved predecessor on all31 captured packets, lighting on/off and cache-hit
publication changes: all1,984 comparisons match all78,337 complete28-byte vertex
records, bone data, resource sections and coverage. The proof is recorded in
v2/build/source-binding-prototype/production-proof.json.

The guarded private paired benchmark reduced this mapping scope from5.21 to
3.34 milliseconds on average over24 paired trials. These are elapsed times;
they do not measure process CPU cycles or establish a native FPS improvement.
Final native cadence, performance and visual gates remain required before
installation. Physics service frequency, solver, constraints and source surface
cadence are unchanged.

# Sealed material-channel diagnostic

The pelvic material boundary remains a failed visual gate. This observer records
five native color targets after an owned lower-body draw, without changing its
material, shader inputs, geometry or draw state. It is disabled by default.

Create `material-capture.request` beside the owned preview DLL before startup:

```
MMGB1 <verified-private-station-name> <request-id> 411 2560 1440
```

The request ID accepts letters, digits, underscore and hyphen, at most 64
characters. The station must exactly match the actual hidden station and
`MALEMOD_SEALED_SESSION`. The fixture's `--station` query obtains a verified
Windows-allocated name without switching the physical desktop. Preserve any
dollar sign literally through structured file writing.

Only an explicit sealed request installs the additional typed SDK observations.
The successful requested checkpoint arms using the current source publication,
not the previous GPU-completed body. Metadata records both requested sequence
and actual latched epoch, sequence, presentation revision, observed Present
interval, draw, section and exact pixel shader. The two material captures must
match the exact publication and Present interval. The window expires after 180
source publications; at most four attempts and two successful captures occur.

CreateRenderTargetView retains plain metadata for at most 4096 full-resolution,
single-sample 2D mip/plane-zero descriptors. Both CopyDescriptors methods preserve
known source provenance and revoke overwritten or unknown destinations. All
sources are snapshotted before destination revocation. Each command list retains
an exact OM5 metadata snapshot. None of these operations AddRefs a render target
at startup or dereferences an unrelated historical pointer.

An AddRef occurs only at an actual observed owned draw using its exact recorded
OM binding. The native application must keep these referenced resources valid
through GPU completion under the [D3D12 resource lifetime contract](https://learn.microsoft.com/en-us/windows/win32/direct3d12/porting-from-direct3d-11-to-direct3d-12).
Unknown provenance fails closed. Draw-time pins are bounded to 128 views and
512 MiB of distinct top-mip copy footprints. Each capture uses at most 256 MiB
of readback buffers. No limit was increased to retain startup scratch targets.

All destinations and resource references are allocated before GPU commands.
Each target transitions RENDER_TARGET -> COPY_SOURCE -> RENDER_TARGET around
its copy. Depth, PSO, root parameters and shader inputs remain unchanged.
The actual submission queue signals a private fence. A background writer maps
only completed copies and releases native source references after that fence.
Reset cancels unsubmitted recordings; submitted resources remain protected.
Shutdown runs outside loader locks. An unsignalled or failed fence retains the
bounded resources through process exit instead of freeing in-flight memory.

Actual swapchain backbuffers are identified through GetDesc/GetBuffer, never
by name or format. A private diagnostic GUID tag has the resource's own lifetime
and retains no COM reference. Both typed ResizeBuffers methods reobserve current
buffers, revoke descriptor/list claims and release fence-completed own source
references before forwarding. Every temporary GetBuffer reference leaves scope
before the original resize call. Unfinished own copies remain protected and log
the blocking condition. Original arguments and HRESULT are preserved; actual
post-call buffer identities and formats are recorded.

The actual hidden-window WARP and AMD fixtures held one GetBuffer reference and
reproduced DXGI_ERROR_INVALID_CALL. Releasing it allowed ResizeBuffers and
ResizeBuffers1 to return S_OK with actual resource formats R8 -> R10 -> R8.
All nine backbuffer RTVs were excluded. Startup resource pins remained zero.
Both real descriptor-copy methods, unknown/null-overwrite revocation, fences,
restored RT state and all five stored pixel formats passed. Startup tests also
survive 1.5 GiB of unused allocation churn plus another 1.5 GiB while the current
five targets remain owned by the fixture. See
`v2/build/materials/gbuffer-capture/capture-only-lifecycle-proof.json`.

The earlier permanent/LRU retention policies are superseded. Native PID21096
showed 883 eligible views but 864 budget rejections and no complete OM5 set.
Native PID21052 showed the same R8 backbuffer objects later requested as R10
RTVs, followed by device removal. The fixture proves the outstanding-reference
resize failure mechanism; a fresh native resize HRESULT/capture is still a
separate gate. Historical proof files remain preserved.

Output names remain `material-<request>-<pid>-mat{0,1}.json`, the exact `.ps`,
and five `.bin` targets per material. These are per-draw captures, not complete
GBuffer frames. Other regions may be unwritten or belong to earlier draws.
Compare only visible regions owned by the named material. Check equal epoch,
sequence, presentationSerial and nativePresentSerial before pairing records.
Target metadata includes native formats, padding, dimensions, resource identity
and actual object name. `tools/read_v2_material_capture.py` displays stored
channels without assigning slot semantics, applying gamma or reconstructing
lighting; the captured PS must establish each channel's meaning.

Use `MMGBD1` instead of `MMGB1` only for explicit GPU-error diagnosis. Before
the first actual device, typed Agility GetConfigurationInterface or the observed
global device path requests DRED breadcrumbs/page-fault/context data and attempts
the debug layer. Normal MMGB1 does not configure or poll GPU debug interfaces.
DRED output is bounded to four devices, 128 breadcrumb nodes, short operation
windows and 64 entries per allocation list. Query occurs after submissions,
on copy Signal/fence failure and in the observer worker.

Actual 619-factory WARP/AMD tests successfully queried DRED after logical removal
of only the fixture's own ID3D12Device5. No adapter reset, GPU hang, TDR or other
application was involved. InfoQueue remains unavailable on this Windows setup;
matching app-local SDKLayers alone does not satisfy Microsoft's [Graphics Tools
feature requirement](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/D3D12Redistributable.md#d3d12-debug-layer).
No Windows capability or permission change was attempted. Native baseline
SDKLayers files were preserved; temporary owned fixture copies were hash-checked
and removed after closure. See `gbuffer-capture/dred-proof.json`.

Bounded logs retain 32 distinct RTV shape/format patterns, 12 missing OM5 sets,
4096 actual full-resolution creation names obtained through read-only A/W
GetPrivateData, and arm/expiry counters. Native material diagnosis, visual
acceptance and installation remain pending. This observer is not a new skin bake.

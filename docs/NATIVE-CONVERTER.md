# Narrow native resource authoring

`python tools/build_native_converter.py` builds an ignored local converter.
It requires these existing local vendor inputs under `build/research/`:

- `WolvenKit-7`: checkout of `https://github.com/WolvenKit/WolvenKit-7`, commit
  `c3c1c2028177de37c97a2706412b499a5c04cbf4`, with `WolvenKit.CR2W` sources.
- `WolvenKit-7.2.0.zip`: release archive SHA256
  `d68d6b04d1bafefd962bb03d784df3784b7ee30744a38349b3769e7496e7d29e`.
- `wkit720`: extracted release DLLs. Keep the original archive for verification.
- Roslyn at `C:/BuildTools/MSBuild/Current/Bin/Roslyn/csc.exe` and the installed
  .NET Framework reference used by the builder. Configure these paths explicitly
  on another machine; do not download an unpinned substitute silently.

The builder derives two narrow patches from the pinned vendor Git revision:
read/write the observed CNode transform buffer, and author CR2W version 159.
It also compiles our `tools/native/MaleModPhysicsItem.cs` serialization schema.
Unknown vendor edits are rejected. Output identity is recorded in the local
`build/research/wkit-current/toolchain.json`; no vendor binaries enter Git or a
game package. Existing output files are protected by the converter front end.

Supported inspection is restricted to version-159 resources and the observed
version-161 skeleton format. Authoring writes version 159. This is **not** a
version-164 entity writer. Use the official dumper to inspect newer resources.
The older unrestricted inspection build must not be used for production output.

## Observed format failures

The unpatched community parser left a 64-byte identity transform in CNode's
unknown bytes. For an entity this also shifted its component-array decoding.
After decoding that block, preserving the source's version 159 was necessary:
writing the same layout under the converter's default version 162 produced
`Invalid name index 32768` and lost components during native cooking.

The patched version-159 stock-shirt fixture cooked with all 12 native objects
intact, including both dynamic components and their skinning attachments. The
new anatomy cage subsequently cooked with its mesh, dynamic resource, skeleton,
item, skinning attachment, component and constraint. These checks establish
resource conversion, not game motion or the custom script item's binding.

WCC can return exit zero for `TEMPLATE COOKING FAILED` and invalid name indices.
`tools/mod.py` now rejects these signatures. Never bypass them with `-noerrors`.

The custom `MaleModPhysicsItem` fixture still fails native template cooking.
Its menu script compiles independently. Do not substitute the stock-class
fixture and claim that this verifies the script-to-constraint handle.

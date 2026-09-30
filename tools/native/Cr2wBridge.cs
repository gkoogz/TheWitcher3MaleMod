// Narrow local authoring converter. Never deploy this executable with the mod.
using System;
using System.IO;
using WolvenKit.CR2W.JSON;
class MaleModCR2W
{
    static int Main(string[] args)
    {
        if (args.Length != 3 || (args[0] != "export" && args[0] != "import")) return 2;
        try
        {
            if (File.Exists(args[2])) throw new IOException("Refusing to overwrite an existing output");
            if (args[0] == "export")
            {
                using (var reader = new BinaryReader(File.OpenRead(args[1])))
                {
                    uint magic = reader.ReadUInt32();
                    uint version = reader.ReadUInt32();
                    bool observedRig = version == 161 && Path.GetExtension(args[1]).ToLowerInvariant() == ".w2rig";
                    if (magic != 0x57325243 || (version != 159 && !observedRig))
                        throw new IOException("Expected CR2W 159 resource or observed 161 skeleton; other versions need a separate calibration");
                }
            }
            var options = new CR2WJsonToolOptions();
            bool ok = args[0] == "export"
                ? CR2WJsonTool.ExportJSON(args[1], args[2], options)
                : CR2WJsonTool.ImportJSON(args[1], args[2], options);
            return ok ? 0 : 1;
        }
        catch (Exception e) { Console.Error.WriteLine(e); return 1; }
    }
}

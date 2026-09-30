// Serialization schema for our authored WitcherScript item. Compile with the
// pinned local WolvenKit converter; this code is not loaded by the game.
using System.Runtime.Serialization;
using WolvenKit.CR2W.Reflection;
using FastMember;
namespace WolvenKit.CR2W.Types
{
    [DataContract(Namespace = "")]
    [REDMeta]
    public class MaleModPhysicsItem : CItemEntity
    {
        [Ordinal(1)] [RED("dynamicConstraint")]
        public CHandle<CAnimDangleConstraint_Dyng> DynamicConstraint { get; set; }
        public MaleModPhysicsItem(CR2WFile file, CVariable parent, string name)
            : base(file, parent, name) { }
        public static new CVariable Create(CR2WFile file, CVariable parent, string name)
            => new MaleModPhysicsItem(file, parent, name);
    }
    [DataContract(Namespace = "")]
    [REDMeta]
    public class MaleModMotionComponent : CSelfUpdatingComponent
    {
        [Ordinal(1)] [RED("dynamicConstraint")]
        public CHandle<CAnimDangleConstraint_Dyng> DynamicConstraint { get; set; }
        public MaleModMotionComponent(CR2WFile file, CVariable parent, string name)
            : base(file, parent, name) { }
        public static new CVariable Create(CR2WFile file, CVariable parent, string name)
            => new MaleModMotionComponent(file, parent, name);
    }
}

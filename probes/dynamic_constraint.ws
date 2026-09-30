// Compiler probe only. Not part of workspace/ or an installed mod.
// These native property declarations were accepted by REDkit 5.0.1042178.
import class IAnimDangleConstraint extends CObject {}
import class CAnimSkeletalDangleConstraint extends IAnimDangleConstraint {}
import class CAnimDangleConstraint_Dyng extends CAnimSkeletalDangleConstraint
{
    import var dampening : float;
    import var gravity : float;
    import var speed : float;
}

class MaleModPhysicsProbe extends CItemEntity
{
    // The native component's `constraint` is ptr:IAnimDangleConstraint, which
    // cannot be imported as a script handle. An authored handle on our item
    // compiles; native serialization and live binding still need verification.
    editable var dynamicConstraint : CAnimDangleConstraint_Dyng;

    public function Tune()
    {
        if (dynamicConstraint)
        {
            dynamicConstraint.gravity = 1.0;
        }
    }
}

// Automatic read-only pose sampling; no ticking entity, menu or key binding.
import function MaleModNativePoseSample(seconds : float, paused : bool,
    pelvisX : Vector, pelvisY : Vector, pelvisZ : Vector, pelvisOrigin : Vector,
    leftA : Vector, leftB : Vector, rightA : Vector, rightB : Vector) : bool;

@addField(CR4Game)
private var maleModNativePoseProbeFinished : bool;

@wrapMethod(CR4Game)
function OnTick()
{
    var actorInverse : Matrix;
    var pelvis : Matrix;
    var p, la, lb, ra, rb : Vector;
    var pi, lai, lbi, rai, rbi : int;
    wrappedMethod();
    if (maleModNativePoseProbeFinished || !thePlayer) { return; }
    if (theGame.IsPaused()) { return; }
    pi = thePlayer.GetBoneIndex('pelvis');
    lai = thePlayer.GetBoneIndex('l_thigh'); lbi = thePlayer.GetBoneIndex('l_shin');
    rai = thePlayer.GetBoneIndex('r_thigh'); rbi = thePlayer.GetBoneIndex('r_shin');
    if (pi != 9 || lai < 0 || lbi < 0 || rai < 0 || rbi < 0) { return; }
    actorInverse = MatrixGetInverted(thePlayer.GetLocalToWorld());
    pelvis = thePlayer.GetBoneWorldMatrixByIndex(pi);
    p = VecTransform(pelvis,Vector(0.0,0.0,0.0,1.0)); p.W = 1.0;
    la = thePlayer.GetBoneWorldPositionByIndex(lai); la.W = 1.0;
    lb = thePlayer.GetBoneWorldPositionByIndex(lbi); lb.W = 1.0;
    ra = thePlayer.GetBoneWorldPositionByIndex(rai); ra.W = 1.0;
    rb = thePlayer.GetBoneWorldPositionByIndex(rbi); rb.W = 1.0;
    maleModNativePoseProbeFinished = !MaleModNativePoseSample(theGame.GetEngineTimeAsSeconds(),false,
        VecTransformDir(actorInverse,pelvis.X),VecTransformDir(actorInverse,pelvis.Y),VecTransformDir(actorInverse,pelvis.Z),VecTransform(actorInverse,p),
        VecTransform(actorInverse,la),VecTransform(actorInverse,lb),VecTransform(actorInverse,ra),VecTransform(actorInverse,rb));
}

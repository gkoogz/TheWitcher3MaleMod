// Full Base solver input and native live overlay. The cooked .31 rig is the
// neutral skin/material carrier; all current morphology comes from Base.
import function MaleModNativeFrame(epoch : int, seconds : float, paused : bool,
    pelvisX : Vector, pelvisY : Vector, pelvisZ : Vector, pelvisOrigin : Vector,
    leftA : Vector, leftB : Vector, rightA : Vector, rightB : Vector) : int;
import function MaleModNativeOverlayOpen() : bool;
import function MaleModNativeSurfaceActive(epoch : int) : bool;
import function MaleModNativeFullMode() : bool;

@wrapMethod(MaleModMotionComponent)
function ApplyOverall()
{
    if (MaleModNativeFullMode()) { overallValue = 50.0; }
    wrappedMethod();
}

@wrapMethod(MaleModMotionComponent)
function OverallReady() : bool
{
    if (MaleModNativeFullMode()) { return false; }
    return wrappedMethod();
}

@addMethod(CR4Game)
function MaleModNativeOutputActive() : bool
{
    return MaleModNativeSurfaceActive(maleModNativeCharacterEpoch);
}

// Retain the proven rig and fallback, but do not also run the superseded
// script solver once the full native surface has completed on this character.
@wrapMethod(MaleModMotionComponent)
function AdvancePhysics(dt : float)
{
    if (theGame.MaleModNativeOutputActive()) { return; }
    wrappedMethod(dt);
}

@addField(CR4Game)
private var maleModNativeLastPlayer : CActor;
@addField(CR4Game)
private var maleModNativeCharacterEpoch : int;
@addField(CR4Game)
private var maleModNativeRuntimeStatus : int;
@addField(CR4Game)
private var maleModNativeInputFault : bool;
@addField(CR4Game)
private var maleModNativeOverlayPauseOwned : bool;

@wrapMethod(CR4Game)
function OnTick()
{
    var inverse, pelvis : Matrix;
    var p, la, lb, ra, rb, zero : Vector;
    var pi, lai, lbi, rai, rbi : int;
    var seconds : float;
    // Native overlay uses the user's F6/arrows and does not pause or replace
    // Witcher's input context. Solver inputs remain live while it is expanded.
    wrappedMethod();
    seconds = theGame.GetEngineTimeAsSeconds();
    if (!thePlayer)
    {
        maleModNativeLastPlayer = NULL;
        maleModNativeInputFault = false;
        maleModNativeRuntimeStatus = MaleModNativeFrame(0,seconds,true,zero,zero,zero,zero,zero,zero,zero,zero);
        return;
    }
    if (maleModNativeLastPlayer != thePlayer)
    {
        maleModNativeLastPlayer = thePlayer;
        maleModNativeCharacterEpoch += 1;
        maleModNativeInputFault = false;
    }
    if (theGame.IsPaused())
    {
        maleModNativeRuntimeStatus = MaleModNativeFrame(maleModNativeCharacterEpoch,seconds,true,zero,zero,zero,zero,zero,zero,zero,zero);
        return;
    }
    // Invalid input stops this character's feed. Ordinary worker backpressure
    // leaves elapsed active time available to the next accepted solver sample.
    if (maleModNativeInputFault) { return; }
    pi = thePlayer.GetBoneIndex('pelvis');
    lai = thePlayer.GetBoneIndex('l_thigh'); lbi = thePlayer.GetBoneIndex('l_shin');
    rai = thePlayer.GetBoneIndex('r_thigh'); rbi = thePlayer.GetBoneIndex('r_shin');
    if (pi != 9 || lai < 0 || lbi < 0 || rai < 0 || rbi < 0) { return; }
    inverse = MatrixGetInverted(thePlayer.GetLocalToWorld());
    MaleModSampleRenderBones(maleModNativeCharacterEpoch,seconds,inverse);
    pelvis = thePlayer.GetBoneWorldMatrixByIndex(pi);
    p = VecTransform(pelvis,Vector(0.0,0.0,0.0,1.0)); p.W = 1.0;
    la = thePlayer.GetBoneWorldPositionByIndex(lai); la.W = 1.0;
    lb = thePlayer.GetBoneWorldPositionByIndex(lbi); lb.W = 1.0;
    ra = thePlayer.GetBoneWorldPositionByIndex(rai); ra.W = 1.0;
    rb = thePlayer.GetBoneWorldPositionByIndex(rbi); rb.W = 1.0;
    maleModNativeRuntimeStatus = MaleModNativeFrame(maleModNativeCharacterEpoch,seconds,false,
        VecTransformDir(inverse,pelvis.X),VecTransformDir(inverse,pelvis.Y),VecTransformDir(inverse,pelvis.Z),VecTransform(inverse,p),
        VecTransform(inverse,la),VecTransform(inverse,lb),VecTransform(inverse,ra),VecTransform(inverse,rb));
    if (maleModNativeRuntimeStatus == 5 || maleModNativeRuntimeStatus == 6)
    {
        maleModNativeInputFault = true;
    }
}

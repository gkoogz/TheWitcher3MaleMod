// V2: current stock Geralt pose and exact canonical per-tick service.
import function MaleModNativeFrame(epoch : int, seconds : float, paused : bool,
    pelvisX : Vector, pelvisY : Vector, pelvisZ : Vector, pelvisOrigin : Vector,
    leftA : Vector, leftB : Vector, rightA : Vector, rightB : Vector) : int;
import function MaleModNativeOverlayOpen() : bool;
import function MaleModNativeSurfaceActive(epoch : int) : bool;
import function MaleModNativeFullMode() : bool;
import function MaleModNativeRefreshRenderPose(epoch : int, seconds : float) : bool;

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
@addField(CR4Game)
private var maleModNativeRenderPoseQueued : bool;
@addField(CR4Game)
private var maleModNativeRenderPoseEpoch : int;
@addField(CR4Game)
private var maleModNativeRenderPoseSeconds : float;
@addField(CR4Game)
private var maleModNativeRenderTimerPlayer : CPlayer;

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
    MaleModClinicalStep();
    MaleModGarmentStep();
    if (!thePlayer)
    {
        MaleModNativeCancelRenderPose(true);
        maleModNativeLastPlayer = NULL;
        maleModNativeInputFault = false;
        maleModNativeRuntimeStatus = MaleModNativeFrame(0,seconds,true,zero,zero,zero,zero,zero,zero,zero,zero);
        return;
    }
    if (maleModNativeLastPlayer != thePlayer)
    {
        MaleModNativeCancelRenderPose(true);
        maleModNativeLastPlayer = thePlayer;
        maleModNativeCharacterEpoch += 1;
        maleModNativeInputFault = false;
    }
    if (theGame.IsPaused())
    {
        MaleModNativeCancelRenderPose(false);
        maleModNativeRuntimeStatus = MaleModNativeFrame(maleModNativeCharacterEpoch,seconds,true,zero,zero,zero,zero,zero,zero,zero,zero);
        return;
    }
    // A guarded fallback consumes older pending work before another step. The
    // normal path uses the observed late transform timer below.
    MaleModNativeCompleteRenderPose();
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
    if (maleModNativeRuntimeStatus == 2)
    {
        maleModNativeRenderPoseEpoch = maleModNativeCharacterEpoch;
        maleModNativeRenderPoseSeconds = seconds;
        maleModNativeRenderPoseQueued = true;
        if (maleModNativeRenderTimerPlayer != thePlayer)
        {
            maleModNativeRenderTimerPlayer = thePlayer;
            thePlayer.AddTimer('MaleModNativeLateRenderPose',0.0,true,false,TICK_PostUpdateTransform,false,true);
        }
    }
    if (maleModNativeRuntimeStatus == 5 || maleModNativeRuntimeStatus == 6)
    {
        maleModNativeInputFault = true;
    }
}

@addMethod(CPlayer)
timer function MaleModNativeLateRenderPose(deltaTime : float, id : int)
{
    theGame.MaleModNativeCompleteRenderPose();
}

@addMethod(CR4Game)
function MaleModNativeCancelRenderPose(removeTimer : bool)
{
    maleModNativeRenderPoseQueued = false;
    if (removeTimer && maleModNativeRenderTimerPlayer)
    {
        maleModNativeRenderTimerPlayer.RemoveTimer('MaleModNativeLateRenderPose',TICK_PostUpdateTransform);
        maleModNativeRenderTimerPlayer = NULL;
    }
}

@addMethod(CR4Game)
function MaleModNativeCompleteRenderPose()
{
    var inverse : Matrix;
    if (!maleModNativeRenderPoseQueued) { return; }
    if (!thePlayer || IsPaused() || maleModNativeRenderTimerPlayer != thePlayer || maleModNativeRenderPoseEpoch != maleModNativeCharacterEpoch)
    {
        maleModNativeRenderPoseQueued = false;
        return;
    }
    maleModNativeRenderPoseQueued = false;
    inverse = MatrixGetInverted(thePlayer.GetLocalToWorld());
    // This timestamp is the completed source-frame token. The actual pose is
    // read now, after native animation and world-transform updates.
    MaleModSampleRenderBones(maleModNativeRenderPoseEpoch,maleModNativeRenderPoseSeconds,inverse);
    if (!MaleModNativeRefreshRenderPose(maleModNativeRenderPoseEpoch,maleModNativeRenderPoseSeconds))
    {
        maleModNativeRuntimeStatus = 6;
        maleModNativeInputFault = true;
    }
}

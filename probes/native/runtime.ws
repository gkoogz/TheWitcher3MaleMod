// Development full-solver input. No graphics replacement or menu is claimed.
import function MaleModNativeFrame(epoch : int, seconds : float, paused : bool,
    pelvisX : Vector, pelvisY : Vector, pelvisZ : Vector, pelvisOrigin : Vector,
    leftA : Vector, leftB : Vector, rightA : Vector, rightB : Vector) : int;
import function MaleModNativeOverlayOpen() : bool;

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
    var overlayOpen : bool;
    overlayOpen = MaleModNativeOverlayOpen();
    if (overlayOpen && !maleModNativeOverlayPauseOwned)
    {
        theGame.Pause("MaleModOverlay");
        theInput.StoreContext('EMPTY_CONTEXT');
        theGame.GetGuiManager().RequestMouseCursor(true);
        maleModNativeOverlayPauseOwned = true;
    }
    else if (!overlayOpen && maleModNativeOverlayPauseOwned)
    {
        theGame.Unpause("MaleModOverlay");
        theInput.RestoreContext('EMPTY_CONTEXT',true);
        theGame.GetGuiManager().RequestMouseCursor(false);
        maleModNativeOverlayPauseOwned = false;
    }
    wrappedMethod();
    if (!thePlayer)
    {
        maleModNativeLastPlayer = NULL;
        maleModNativeInputFault = false;
        maleModNativeRuntimeStatus = MaleModNativeFrame(0,theGame.GetEngineTimeAsSeconds(),true,zero,zero,zero,zero,zero,zero,zero,zero);
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
        maleModNativeRuntimeStatus = MaleModNativeFrame(maleModNativeCharacterEpoch,theGame.GetEngineTimeAsSeconds(),true,zero,zero,zero,zero,zero,zero,zero,zero);
        return;
    }
    // Development input records a fault on overload/invalid state. It does not
    // silently advance the filter or drop physics requests. Renderer/UI pending.
    if (maleModNativeInputFault) { return; }
    pi = thePlayer.GetBoneIndex('pelvis');
    lai = thePlayer.GetBoneIndex('l_thigh'); lbi = thePlayer.GetBoneIndex('l_shin');
    rai = thePlayer.GetBoneIndex('r_thigh'); rbi = thePlayer.GetBoneIndex('r_shin');
    if (pi != 9 || lai < 0 || lbi < 0 || rai < 0 || rbi < 0) { return; }
    inverse = MatrixGetInverted(thePlayer.GetLocalToWorld());
    pelvis = thePlayer.GetBoneWorldMatrixByIndex(pi);
    p = VecTransform(pelvis,Vector(0.0,0.0,0.0,1.0)); p.W = 1.0;
    la = thePlayer.GetBoneWorldPositionByIndex(lai); la.W = 1.0;
    lb = thePlayer.GetBoneWorldPositionByIndex(lbi); lb.W = 1.0;
    ra = thePlayer.GetBoneWorldPositionByIndex(rai); ra.W = 1.0;
    rb = thePlayer.GetBoneWorldPositionByIndex(rbi); rb.W = 1.0;
    maleModNativeRuntimeStatus = MaleModNativeFrame(maleModNativeCharacterEpoch,theGame.GetEngineTimeAsSeconds(),false,
        VecTransformDir(inverse,pelvis.X),VecTransformDir(inverse,pelvis.Y),VecTransformDir(inverse,pelvis.Z),VecTransform(inverse,p),
        VecTransform(inverse,la),VecTransform(inverse,lb),VecTransform(inverse,ra),VecTransform(inverse,rb));
    if (maleModNativeRuntimeStatus >= 3 && maleModNativeRuntimeStatus <= 6)
    {
        maleModNativeInputFault = true;
    }
}

// One settled full-floppy shape, a bounded walk, and its free decay.
import function MaleModNativeSetControl(index : int, value : float) : bool;
@addField(CR4Game)
private var maleModMotionStage : int;
@addField(CR4Game)
private var maleModMotionStarted : float;
@addField(CR4Game)
private var maleModMotionCaptureTime : float;
@addField(CR4Game)
private var maleModMotionSetup : bool;
@addField(CR4Game)
private var maleModMotionWalking : bool;
@addMethod(CR4Game)
function MaleModCollarCaseStep()
{
    var seconds : float;
    var aim, side, cameraPosition : Vector;
    var pelvis : Matrix;
    var rotation : EulerAngles;
    if(!maleModIterationStarted || !thePlayer || IsPaused() || maleModMotionStage>=36){return;}
    seconds=GetEngineTimeAsSeconds();
    if(!maleModMotionSetup){
        MaleModNativeGarmentControl(0);MaleModNativeClinicalControl(0,0.0);
        MaleModNativeSetControl(0,2.0);MaleModNativeSetControl(1,100.0);
        MaleModNativeSetControl(2,100.0);MaleModNativeSetControl(3,97.0);
        MaleModNativeSetControl(4,35.0);MaleModNativeSetControl(5,100.0);
        MaleModNativeSetControl(6,95.0);MaleModNativeSetControl(7,15.0);
        MaleModNativeSetControl(8,100.0);MaleModNativeSetControl(9,50.0);
        MaleModNativeSetControl(10,50.0);MaleModNativeSetControl(11,50.0);
        MaleModNativeSetControl(12,50.0);MaleModNativeSetControl(13,50.0);
        MaleModNativeSetControl(14,50.0);MaleModNativeSetControl(15,50.0);
        MaleModNativeSetControl(16,50.0);MaleModNativeSetControl(17,51.0);
        maleModMotionSetup=true;maleModMotionStarted=seconds;
    }
    pelvis=thePlayer.GetBoneWorldMatrixByIndex(9);
    aim=VecTransform(pelvis,PROFILE_PELVIS_POINT);
    side=VecNormalize(VecTransformDir(pelvis,PROFILE_PELVIS_SIDE));
    cameraPosition=aim+side*1.25;
    rotation=VecToRotation(aim-cameraPosition);rotation.Pitch=-rotation.Pitch;
    EnableFreeCamera(true);MoveFreeCamera(cameraPosition,rotation);
    if(seconds-maleModMotionStarted<18.0){return;}
    if(!maleModMotionWalking){MaleModIterationWalk();maleModMotionWalking=true;maleModMotionCaptureTime=seconds;}
    if(seconds-maleModMotionCaptureTime<0.20){return;}
    if(!MaleModNativeTestCheckpoint(600+maleModMotionStage)){return;}
    TakeScreenshot();maleModMotionStage+=1;maleModMotionCaptureTime=seconds;
    if(maleModMotionStage>=36){thePlayer.SetDefaultLocomotionController();}
}

// Native sagittal profiles. Bone-local camera vectors are generated from the
// hash-bound render palette, not inferred from the actor's facing direction.
import function MaleModNativeSetControl(index : int, value : float) : bool;
@addField(CR4Game)
private var maleModCollarStage : int;
@addField(CR4Game)
private var maleModCollarCaseTime : float;
@addField(CR4Game)
private var maleModCollarCaseSet : bool;
@addMethod(CR4Game)
function MaleModCollarCaseStep()
{
    var caseIndex, view, angle : int;
    var seconds : float;
    var aim, side, cameraPosition : Vector;
    var pelvis : Matrix;
    var rotation : EulerAngles;
    if (!maleModIterationStarted || !thePlayer || IsPaused() || maleModCollarStage >= 8) {return;}
    seconds=GetEngineTimeAsSeconds();caseIndex=maleModCollarStage/2;view=maleModCollarStage%2;
    angle=15;if(caseIndex==1){angle=25;}else if(caseIndex==2){angle=35;}else if(caseIndex==3){angle=50;}
    if(!maleModCollarCaseSet)
    {
        MaleModNativeGarmentControl(0);MaleModNativeClinicalControl(0,0.0);
        MaleModNativeSetControl(0,0.0);MaleModNativeSetControl(1,100.0);
        MaleModNativeSetControl(2,100.0);MaleModNativeSetControl(3,100.0);
        MaleModNativeSetControl(4,35.0);MaleModNativeSetControl(5,100.0);
        MaleModNativeSetControl(6,95.0);MaleModNativeSetControl(7,(float)angle);
        MaleModNativeSetControl(8,100.0);MaleModNativeSetControl(9,50.0);
        MaleModNativeSetControl(10,50.0);MaleModNativeSetControl(11,50.0);
        MaleModNativeSetControl(12,50.0);MaleModNativeSetControl(13,50.0);
        MaleModNativeSetControl(14,50.0);MaleModNativeSetControl(15,50.0);
        MaleModNativeSetControl(16,50.0);MaleModNativeSetControl(17,51.0);
        maleModCollarCaseTime=seconds;maleModCollarCaseSet=true;
    }
    pelvis=thePlayer.GetBoneWorldMatrixByIndex(9);
    aim=VecTransform(pelvis,PROFILE_PELVIS_POINT);
    side=VecNormalize(VecTransformDir(pelvis,PROFILE_PELVIS_SIDE));
    if(view==1){side=side*-1.0;}
    cameraPosition=aim+side*1.25;
    rotation=VecToRotation(aim-cameraPosition);rotation.Pitch=-rotation.Pitch;
    EnableFreeCamera(true);MoveFreeCamera(cameraPosition,rotation);
    if(seconds-maleModCollarCaseTime<3.0){return;}
    if(!MaleModNativeTestCheckpoint(500+maleModCollarStage)){return;}
    if(caseIndex==0 && view==0){MaleModNativeTestCheckpoint(75);}
    else if(caseIndex==1 && view==0){MaleModNativeTestCheckpoint(82);}
    TakeScreenshot();maleModCollarStage+=1;maleModCollarCaseSet=false;
}

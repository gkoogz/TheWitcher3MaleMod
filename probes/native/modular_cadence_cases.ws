// No host input: measure completed native output during continuous pulses,
// then acknowledge each of twenty consecutive width and angle edits.
import function MaleModNativeSetControl(index : int, value : float) : bool;
@addField(CR4Game)
private var maleModCollarStage : int;
@addField(CR4Game)
private var maleModCollarCaseTime : float;
@addField(CR4Game)
private var maleModCollarCaseSet : bool;
@addField(CR4Game)
private var maleModCadenceStart : float;
@addMethod(CR4Game)
function MaleModCollarCaseStep()
{
    var seconds : float;
    var aim, side, cameraPosition : Vector;
    var pelvis : Matrix;
    var rotation : EulerAngles;
    if (!maleModIterationStarted || !thePlayer || IsPaused() || maleModCollarStage >= 140) {return;}
    seconds=GetEngineTimeAsSeconds();
    if(!maleModCollarCaseSet) {
        if(maleModCollarStage==0) {
            MaleModNativeGarmentControl(0);MaleModNativeClinicalControl(0,0.0);
            MaleModNativeSetControl(0,0.0);
            MaleModNativeSetControl(1,70.0);MaleModNativeSetControl(2,70.0);MaleModNativeSetControl(3,70.0);
            MaleModNativeSetControl(4,35.0);MaleModNativeSetControl(5,70.0);MaleModNativeSetControl(6,50.0);
            MaleModNativeSetControl(7,50.0);MaleModNativeSetControl(8,100.0);MaleModNativeSetControl(9,50.0);
            MaleModNativeSetControl(10,50.0);MaleModNativeSetControl(11,50.0);MaleModNativeSetControl(12,50.0);MaleModNativeSetControl(13,50.0);
            MaleModNativeSetControl(14,50.0);MaleModNativeSetControl(15,50.0);MaleModNativeSetControl(16,50.0);MaleModNativeSetControl(17,50.0);
            maleModCadenceStart=seconds;
        }
        if(maleModCollarStage==1) {MaleModNativeClinicalControl(0,3.0);}
        if(maleModCollarStage>=100 && maleModCollarStage<120) {
            MaleModNativeClinicalControl(0,0.0);
            MaleModNativeSetControl(3,50.0+(float)(maleModCollarStage-100));
        }
        if(maleModCollarStage>=120) {MaleModNativeSetControl(7,30.0+2.0*(float)(maleModCollarStage-120));}
        maleModCollarCaseTime=seconds;maleModCollarCaseSet=true;
    }
    pelvis=thePlayer.GetBoneWorldMatrixByIndex(9);
    aim=VecTransform(pelvis,PROFILE_PELVIS_POINT);
    side=VecNormalize(VecTransformDir(pelvis,PROFILE_PELVIS_SIDE));
    cameraPosition=aim+side*.9;
    rotation=VecToRotation(aim-cameraPosition);rotation.Pitch=-rotation.Pitch;
    EnableFreeCamera(true);MoveFreeCamera(cameraPosition,rotation);
    if(maleModCollarStage==0 && seconds-maleModCadenceStart<25.0){return;}
    if(seconds-maleModCollarCaseTime<.10){return;}
    if(!MaleModNativeTestCheckpoint(1100+maleModCollarStage)){return;}
    if(maleModCollarStage==0 || maleModCollarStage==25 || maleModCollarStage==50 || maleModCollarStage==75 || maleModCollarStage==119 || maleModCollarStage==139){
        MaleModNativeTestCheckpoint(600+3*(maleModCollarStage/25));TakeScreenshot();
    }
    maleModCollarStage+=1;maleModCollarCaseSet=false;
    if(maleModCollarStage>=140){MaleModNativeClinicalControl(0,0.0);}
}

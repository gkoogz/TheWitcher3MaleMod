// Native modular acceptance: controls, mechanical states, motion and actual LOD selection.
import function MaleModNativeSetControl(index : int, value : float) : bool;
@addField(CR4Game)
private var maleModCollarStage : int;
@addField(CR4Game)
private var maleModCollarCaseTime : float;
@addField(CR4Game)
private var maleModCollarCaseSet : bool;
@addField(CR4Game)
private var maleModCollarWalkStarted : bool;
@addMethod(CR4Game)
function MaleModCollarCaseStep()
{
    var caseIndex, view, angle, mechanicalState, size, width, length, glans, sack, hang, forward, vertical : int;
    var seconds, distance : float;
    var aim, direction, side, cameraPosition : Vector;
    var pelvis : Matrix;
    var rotation : EulerAngles;
    if (!maleModIterationStarted || !thePlayer || IsPaused() || maleModCollarStage >= 36) {return;}
    seconds=GetEngineTimeAsSeconds();caseIndex=maleModCollarStage/3;view=maleModCollarStage%3;
    angle=50;mechanicalState=0;size=100;width=100;length=100;glans=35;sack=100;hang=50;forward=100;vertical=50;distance=1.25;
    if(caseIndex==1){hang=25;}
    else if(caseIndex==2){hang=10;}
    else if(caseIndex==3){hang=1;}
    else if(caseIndex==4){hang=75;}
    else if(caseIndex==5){hang=100;}
    else if(caseIndex==6){hang=1;angle=15;}
    else if(caseIndex==7){hang=1;angle=90;}
    else if(caseIndex==8){hang=1;size=50;width=50;length=50;sack=50;}
    else if(caseIndex==9){hang=1;size=1;width=1;length=1;sack=1;}
    else if(caseIndex==10){hang=1;}
    else if(caseIndex==11){hang=1;angle=25;}
    if(!maleModCollarCaseSet)
    {
        MaleModNativeGarmentControl(0);MaleModNativeClinicalControl(0,0.0);
        MaleModNativeSetControl(0,(float)mechanicalState);MaleModNativeSetControl(1,(float)size);
        MaleModNativeSetControl(2,(float)length);MaleModNativeSetControl(3,(float)width);
        MaleModNativeSetControl(4,(float)glans);MaleModNativeSetControl(5,(float)sack);
        MaleModNativeSetControl(6,(float)hang);MaleModNativeSetControl(7,(float)angle);
        MaleModNativeSetControl(8,(float)forward);MaleModNativeSetControl(9,(float)vertical);
        MaleModNativeSetControl(10,50.0);MaleModNativeSetControl(11,50.0);
        MaleModNativeSetControl(12,50.0);MaleModNativeSetControl(13,50.0);
        MaleModNativeSetControl(14,50.0);MaleModNativeSetControl(15,50.0);
        MaleModNativeSetControl(16,50.0);MaleModNativeSetControl(17,51.0);
        maleModCollarWalkStarted=false;
        maleModCollarCaseTime=seconds;maleModCollarCaseSet=true;
    }
    pelvis=thePlayer.GetBoneWorldMatrixByIndex(9);
    aim=VecTransform(pelvis,PROFILE_PELVIS_POINT);
    side=VecNormalize(VecTransformDir(pelvis,PROFILE_PELVIS_SIDE));
    direction=side;
    if(view==1){direction=RotForward(thePlayer.GetWorldRotation());}
    else if(view==2){direction=VecNormalize(side+RotForward(thePlayer.GetWorldRotation()));}
    // At long distances a small animated pelvis roll puts a bone-aligned
    // camera below the physical floor. Keep only distant LOD views level;
    // close attachment profiles retain their exact anatomical side plane.
    if(caseIndex>=29){direction.Z=0;direction=VecNormalize(direction);}
    cameraPosition=aim+direction*distance;
    rotation=VecToRotation(aim-cameraPosition);rotation.Pitch=-rotation.Pitch;
    EnableFreeCamera(true);MoveFreeCamera(cameraPosition,rotation);
    // Settled-angle photographs follow completed morphology/physics updates;
    // startup and the minimum-to-maximum jump cannot be judged after one slow
    // solver frame. Motion is started only after its size change has settled.
    if(caseIndex==0 && view==0 && seconds-maleModCollarCaseTime<25.0){return;}
    if(view==0 && (caseIndex<10 || caseIndex>11) && seconds-maleModCollarCaseTime<12.0){return;}
    if((caseIndex==10 || caseIndex==11) && view==0 && !maleModCollarWalkStarted){
        if(seconds-maleModCollarCaseTime<12.0){return;}
        MaleModIterationWalk();maleModCollarCaseTime=seconds;maleModCollarWalkStarted=true;
    }
    if((caseIndex<10 || caseIndex>11) && seconds-maleModCollarCaseTime<3.0){return;}
    if((caseIndex==10 || caseIndex==11) && seconds-maleModCollarCaseTime<1.0){return;}
    if(!MaleModNativeTestCheckpoint(600+maleModCollarStage)){return;}
    if(caseIndex==1 && view==0){MaleModNativeTestCheckpoint(75);}
    else if(caseIndex==3 && view==0){MaleModNativeTestCheckpoint(82);}
    TakeScreenshot();maleModCollarStage+=1;maleModCollarCaseSet=false;
    if(maleModCollarStage>=36){thePlayer.SetDefaultLocomotionController();}
}

// Private measured side/front/oblique collar regression, including locomotion.
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
    var caseIndex, view, angle, mechanicalState, size, width : int;
    var seconds : float;
    var aim, direction, side, cameraPosition : Vector;
    var pelvis : Matrix;
    var rotation : EulerAngles;
    if (!maleModIterationStarted || !thePlayer || IsPaused() || maleModCollarStage >= 81) {return;}
    seconds=GetEngineTimeAsSeconds();caseIndex=maleModCollarStage/3;view=maleModCollarStage%3;
    angle=15;mechanicalState=0;size=100;width=100;
    if(caseIndex==0){angle=1;}
    else if(caseIndex==2){angle=20;}
    else if(caseIndex==3){angle=25;}
    else if(caseIndex==4){angle=35;}
    else if(caseIndex==5){angle=50;}
    else if(caseIndex==6){angle=70;}
    else if(caseIndex==7){angle=100;}
    else if(caseIndex==8 || caseIndex==9){size=75;width=75;angle=1;if(caseIndex==9){angle=100;}}
    else if(caseIndex==10 || caseIndex==11){mechanicalState=1;angle=1;if(caseIndex==11){angle=100;}}
    else if(caseIndex==12 || caseIndex==13){mechanicalState=2;angle=1;if(caseIndex==13){angle=100;}}
    else if(caseIndex==14){width=50;}
    else if(caseIndex==15){size=50;width=50;}
    else if(caseIndex==16){size=1;width=1;}
    else if(caseIndex==18){angle=25;}
    if(caseIndex>=19){mechanicalState=2;angle=15;view=0;}
    if(!maleModCollarCaseSet)
    {
        MaleModNativeGarmentControl(0);MaleModNativeClinicalControl(0,0.0);
        MaleModNativeSetControl(0,(float)mechanicalState);MaleModNativeSetControl(1,(float)size);
        MaleModNativeSetControl(2,(float)size);MaleModNativeSetControl(3,(float)width);
        MaleModNativeSetControl(4,35.0);MaleModNativeSetControl(5,100.0);
        MaleModNativeSetControl(6,95.0);MaleModNativeSetControl(7,(float)angle);
        MaleModNativeSetControl(8,100.0);MaleModNativeSetControl(9,50.0);
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
    cameraPosition=aim+direction*1.25;
    rotation=VecToRotation(aim-cameraPosition);rotation.Pitch=-rotation.Pitch;
    EnableFreeCamera(true);MoveFreeCamera(cameraPosition,rotation);
    // Settled-angle photographs follow completed morphology/physics updates;
    // startup and the minimum-to-maximum jump cannot be judged after one slow
    // solver frame. Motion is started only after its size change has settled.
    if(caseIndex==0 && view==0 && seconds-maleModCollarCaseTime<25.0){return;}
    if(view==0 && caseIndex<17 && seconds-maleModCollarCaseTime<12.0){return;}
    if(caseIndex>=17 && caseIndex<19 && view==0 && !maleModCollarWalkStarted){
        if(seconds-maleModCollarCaseTime<12.0){return;}
        MaleModIterationWalk();maleModCollarCaseTime=seconds;maleModCollarWalkStarted=true;
    }
    if(caseIndex<17 && seconds-maleModCollarCaseTime<3.0){return;}
    if(caseIndex>=17 && seconds-maleModCollarCaseTime<1.0){return;}
    if(!MaleModNativeTestCheckpoint(600+maleModCollarStage)){return;}
    if(caseIndex==1 && view==0){MaleModNativeTestCheckpoint(75);}
    else if(caseIndex==3 && view==0){MaleModNativeTestCheckpoint(82);}
    TakeScreenshot();maleModCollarStage+=1;maleModCollarCaseTime=seconds;
    if(maleModCollarStage<=57){maleModCollarCaseSet=false;}
    if(maleModCollarStage>=81){thePlayer.SetDefaultLocomotionController();}
}

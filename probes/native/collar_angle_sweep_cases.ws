// Composed with the maintained grey-room bootstrap by prepare_collar_session.py.
// Private engine camera and locomotion only; never host input or ordinary saves.
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
    var caseIndex, angleIndex, view, i : int;
    var seconds : float;
    var aim, direction, right, cameraPosition : Vector;
    var rotation : EulerAngles;
    if (!maleModIterationStarted || !thePlayer || IsPaused() || maleModCollarStage >= 192) { return; }
    seconds=GetEngineTimeAsSeconds();
    caseIndex=maleModCollarStage/4;
    view=maleModCollarStage%4;angleIndex=caseIndex%16;
    if (!maleModCollarCaseSet)
    {
        MaleModNativeGarmentControl(0);MaleModNativeClinicalControl(0,0.0);
        MaleModNativeSetControl(0,(float)(caseIndex/16));
        MaleModNativeSetControl(1,100.0);
        MaleModNativeSetControl(2,100.0);
        MaleModNativeSetControl(3,100.0);
        MaleModNativeSetControl(4,35.0);
        MaleModNativeSetControl(5,100.0);
        MaleModNativeSetControl(6,95.0);
        MaleModNativeSetControl(7,15.0);
        MaleModNativeSetControl(8,100.0);
        MaleModNativeSetControl(9,50.0);
        MaleModNativeSetControl(10,50.0);
        MaleModNativeSetControl(11,50.0);
        MaleModNativeSetControl(12,50.0);
        MaleModNativeSetControl(13,50.0);
        MaleModNativeSetControl(14,50.0);
        MaleModNativeSetControl(15,50.0);
        MaleModNativeSetControl(16,50.0);
        MaleModNativeSetControl(17,51.0);
        if(angleIndex==0){MaleModNativeSetControl(7,1.0);}
        else if(angleIndex==1){MaleModNativeSetControl(7,5.0);}
        else if(angleIndex==2){MaleModNativeSetControl(7,10.0);}
        else if(angleIndex==3){MaleModNativeSetControl(7,15.0);}
        else if(angleIndex==4){MaleModNativeSetControl(7,20.0);}
        else if(angleIndex==5){MaleModNativeSetControl(7,25.0);}
        else if(angleIndex==6){MaleModNativeSetControl(7,30.0);}
        else if(angleIndex==7){MaleModNativeSetControl(7,35.0);}
        else if(angleIndex==8){MaleModNativeSetControl(7,40.0);}
        else if(angleIndex==9){MaleModNativeSetControl(7,45.0);}
        else if(angleIndex==10){MaleModNativeSetControl(7,50.0);}
        else if(angleIndex==11){MaleModNativeSetControl(7,60.0);}
        else if(angleIndex==12){MaleModNativeSetControl(7,70.0);}
        else if(angleIndex==13){MaleModNativeSetControl(7,80.0);}
        else if(angleIndex==14){MaleModNativeSetControl(7,90.0);}
        else if(angleIndex==15){MaleModNativeSetControl(7,100.0);}
        maleModCollarCaseTime=seconds;maleModCollarCaseSet=true;
    }
    aim=thePlayer.GetWorldPosition();aim.Z+=.97;
    direction=RotForward(thePlayer.GetWorldRotation());right=RotRight(thePlayer.GetWorldRotation());
    // RotForward is the observed front-facing axis of the actual player.
    // Keep a close front, side and front-oblique view of the sewn attachment.
    if (view==1) {direction=right;}
    else if (view==2) {direction=direction+right*.75;}
    cameraPosition=aim+VecNormalize(direction)*1.05;cameraPosition.Z+=.04;
    if(view==3){cameraPosition=aim+VecNormalize(direction+right*.75)*1.05;cameraPosition.Z-=.24;}
    rotation=VecToRotation(aim-cameraPosition);rotation.Pitch=-rotation.Pitch;
    EnableFreeCamera(true);MoveFreeCamera(cameraPosition,rotation);
    if (seconds-maleModCollarCaseTime<2.5) {return;}
    if (!MaleModNativeTestCheckpoint(300+maleModCollarStage)) {return;}
    // Capture the actual native deformed vertex stream for reproducible inspection.
    if(view==1){if(caseIndex==3){MaleModNativeTestCheckpoint(75);}else if(caseIndex==5){MaleModNativeTestCheckpoint(82);}else if(caseIndex==37){MaleModNativeTestCheckpoint(83);}}
    TakeScreenshot();maleModCollarStage+=1;maleModCollarCaseSet=false;
    if (maleModCollarStage>=192) {thePlayer.SetDefaultLocomotionController();}
}

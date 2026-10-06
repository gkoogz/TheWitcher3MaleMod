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
    var caseIndex, view, i : int;
    var seconds : float;
    var aim, direction, right, cameraPosition : Vector;
    var rotation : EulerAngles;
    if (!maleModIterationStarted || !thePlayer || IsPaused() || maleModCollarStage >= 39) { return; }
    seconds=GetEngineTimeAsSeconds();
    caseIndex=maleModCollarStage/3;
    view=maleModCollarStage%3;
    if (!maleModCollarCaseSet)
    {
        MaleModNativeSetControl(0,2.0);
        MaleModNativeGarmentControl(0);MaleModNativeClinicalControl(0,0.0);
        for (i=1;i<18;i+=1) {MaleModNativeSetControl(i,50.0);}
        if (caseIndex<6)
        {
            MaleModNativeSetControl(0,(float)(caseIndex/2));
            MaleModNativeSetControl(1,100.0);
            MaleModNativeSetControl(3,100.0);
            if (caseIndex%2==0) {MaleModNativeSetControl(7,1.0);}
            else {MaleModNativeSetControl(7,100.0);}
        }
        else if (caseIndex==6 || caseIndex==7)
        {
            MaleModNativeSetControl(0,1.0);MaleModNativeSetControl(1,100.0);
            MaleModNativeSetControl(5,100.0);MaleModNativeSetControl(6,95.0);
            if (caseIndex==6) {MaleModNativeSetControl(3,70.0);MaleModNativeSetControl(7,64.0);}
            else {MaleModNativeSetControl(3,97.0);MaleModNativeSetControl(7,46.0);}
        }
        else if (caseIndex==9) {MaleModNativeSetControl(1,1.0);MaleModNativeSetControl(3,1.0);}
        else if (caseIndex==10) {MaleModNativeSetControl(1,75.0);MaleModNativeSetControl(3,75.0);}
        else if (caseIndex==11) {MaleModNativeSetControl(0,1.0);for (i=1;i<18;i+=1) {MaleModNativeSetControl(i,100.0);}}
        else if (caseIndex==12)
        {
            MaleModNativeSetControl(1,100.0);MaleModNativeSetControl(3,97.0);
            if (!maleModCollarWalkStarted) {MaleModIterationWalk();maleModCollarWalkStarted=true;}
        }
        maleModCollarCaseTime=seconds;maleModCollarCaseSet=true;
    }
    aim=thePlayer.GetWorldPosition();aim.Z+=.97;
    direction=RotForward(thePlayer.GetWorldRotation());right=RotRight(thePlayer.GetWorldRotation());
    // RotForward is the observed front-facing axis of the actual player.
    // Keep a close front, side and front-oblique view of the sewn attachment.
    if (view==1) {direction=right;}
    else if (view==2) {direction=direction+right*.75;}
    cameraPosition=aim+VecNormalize(direction)*1.05;cameraPosition.Z+=.12;
    rotation=VecToRotation(aim-cameraPosition);rotation.Pitch=-rotation.Pitch;
    EnableFreeCamera(true);MoveFreeCamera(cameraPosition,rotation);
    if (caseIndex<12 && seconds-maleModCollarCaseTime<2.5) {return;}
    if (caseIndex==12 && seconds-maleModCollarCaseTime<1.0) {return;}
    if (!MaleModNativeTestCheckpoint(300+maleModCollarStage)) {return;}
    TakeScreenshot();maleModCollarStage+=1;maleModCollarCaseSet=false;
    if (maleModCollarStage>=39) {thePlayer.SetDefaultLocomotionController();}
}

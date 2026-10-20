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
    if (!maleModIterationStarted || !thePlayer || IsPaused() || maleModCollarStage >= 96) {return;}
    seconds=GetEngineTimeAsSeconds();caseIndex=maleModCollarStage/3;view=maleModCollarStage%3;
    angle=15;mechanicalState=0;size=100;width=100;length=100;glans=35;sack=100;hang=95;forward=100;vertical=50;distance=1.25;
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
    if(caseIndex==19){forward=1;vertical=1;}
    else if(caseIndex==20){forward=1;vertical=100;angle=75;}
    else if(caseIndex==21){vertical=100;angle=10;}
    else if(caseIndex==22){vertical=1;angle=90;}
    else if(caseIndex==23){length=1;glans=1;sack=1;hang=1;angle=25;}
    else if(caseIndex==24){length=1;glans=100;sack=100;hang=50;angle=75;}
    else if(caseIndex==25){size=75;width=25;length=75;glans=75;sack=25;hang=25;angle=50;}
    else if(caseIndex==26){size=1;width=1;length=1;sack=1;mechanicalState=2;angle=90;}
    else if(caseIndex==27){size=50;width=50;length=50;glans=50;sack=50;hang=50;forward=50;angle=50;}
    else if(caseIndex==28){width=1;angle=50;}
    else if(caseIndex==29){distance=4.0;}
    else if(caseIndex==30){distance=8.0;}
    else if(caseIndex==31){distance=15.0;}
    if(!maleModCollarCaseSet)
    {
        // Exercise the second supported native LOD explicitly. Distance alone
        // can retain LOD0; acceptance still checks completed GPU resource bits.
        if(caseIndex>=29)
        {
            CPPForceActorLOD(true,1);
            theGame.GetWorld().ForceGraphicalLOD(1);
        }
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
    if(view==0 && (caseIndex<17 || caseIndex>18) && seconds-maleModCollarCaseTime<12.0){return;}
    if((caseIndex==17 || caseIndex==18) && view==0 && !maleModCollarWalkStarted){
        if(seconds-maleModCollarCaseTime<12.0){return;}
        MaleModIterationWalk();maleModCollarCaseTime=seconds;maleModCollarWalkStarted=true;
    }
    if((caseIndex<17 || caseIndex>18) && seconds-maleModCollarCaseTime<3.0){return;}
    if((caseIndex==17 || caseIndex==18) && seconds-maleModCollarCaseTime<1.0){return;}
    if(!MaleModNativeTestCheckpoint(600+maleModCollarStage)){return;}
    if(caseIndex==1 && view==0){MaleModNativeTestCheckpoint(75);}
    else if(caseIndex==3 && view==0){MaleModNativeTestCheckpoint(82);}
    TakeScreenshot();maleModCollarStage+=1;maleModCollarCaseSet=false;
    if(maleModCollarStage>=96){thePlayer.SetDefaultLocomotionController();}
}

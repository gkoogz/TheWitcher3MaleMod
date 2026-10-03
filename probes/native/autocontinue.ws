// Temporary native test session startup through the stock SDK save-loading API.
// Removed from disk after this process compiles it. Does not save a game or
// bypass the game's mod/account/controller checks.
import function MaleModNativeSealedSession() : bool;
import function MaleModNativeSetControl(index : int, value : float) : bool;
import function MaleModNativeGetControl(index : int) : float;
import function MaleModNativeTestCheckpoint(stage : int) : bool;
@addField(CR4Game)
private var maleModVerificationStage : int;
@addField(CR4Game)
private var maleModVerificationStarted : bool;
@addField(CR4Game)
private var maleModVerificationTime : float;
@addField(CR4Game)
private var maleModVerificationOrigin : Vector;
@addField(CR4Game)
private var maleModVerificationHeading : float;
@addField(CR4Game)
private var maleModVerificationCaptured : bool;
@addField(CR4Game)
private var maleModVerificationPauseTicks : int;

@addMethod(CR4Game)
function MaleModPrivateVerificationStep()
{
    var i, control, part : int;
    var terrainGroups : array<name>;
    var value, seconds : float;
    var cameraRotation : EulerAngles;
    var target, cameraPosition, cameraAim, cameraDirection, cameraRight, traceFrom, traceTo, ground, groundNormal : Vector;
    if (!thePlayer || (IsPaused() && maleModVerificationStage != 60) || maleModVerificationStage >= 84) { return; }
    seconds = GetEngineTimeAsSeconds();
    if (!maleModVerificationStarted)
    {
        if (maleModVerificationTime == 0.0) { maleModVerificationTime = seconds; return; }
        if (seconds-maleModVerificationTime < 2.0) { return; }
        theGame.SetGameTime(GameTimeCreate(GameTimeDays(theGame.GetGameTime()),12,0,0),false);
        maleModVerificationOrigin = thePlayer.GetWorldPosition();
        // Query actual loaded terrain and water level; never invent a floor.
        for (i=0;i<32;i+=1)
        {
            target = maleModVerificationOrigin;
            value = 4.0+4.0*(float)(i/4);
            if (i%4==0) { target.X += value; }
            else if (i%4==1) { target.Y += value; }
            else if (i%4==2) { target.X -= value; }
            else { target.Y -= value; }
            traceFrom = target; traceFrom.Z += 15.0; traceTo = target; traceTo.Z -= 15.0;
            terrainGroups.Clear(); terrainGroups.PushBack('Terrain');
            if (GetWorld().StaticTrace(traceFrom,traceTo,ground,groundNormal,terrainGroups) && ground.Z > GetWorld().GetWaterLevel(target,true)+0.15)
            {
                target.Z = ground.Z+0.03; thePlayer.Teleport(target);
                maleModVerificationOrigin = target; break;
            }
        }
        maleModVerificationHeading = thePlayer.GetHeading()+120.0;
        maleModVerificationStarted = true;
        // This session validates the new clinical/material/ramp delivery.
        // Slider and movement coverage is retained in the preceding trace.
        maleModVerificationStage = 64;
        MaleModNativeSetControl(0,2.0);
        for (i=1;i<18;i+=1) { MaleModNativeSetControl(i,50.0); }
        MaleModNativeClinicalControl(0,1.0);
        MaleModNativeTestCheckpoint(64);
        maleModVerificationTime = seconds;
    }
    GetGameCamera().SetManualRotationHorTimeout(1000.0);
    GetGameCamera().SetManualRotationVerTimeout(1000.0);
    GetGameCamera().GetActivePivotRotationController().SetDesiredHeading(maleModVerificationHeading,1.0);
    if (maleModVerificationStage >= 75 && maleModVerificationStage <= 78) { GetGameCamera().GetActivePivotRotationController().SetDesiredHeading(thePlayer.GetHeading()+90.0*(float)(maleModVerificationStage-75),1.0); }
    GetGameCamera().GetActivePivotRotationController().SetDesiredPitch(0.0,1.0);
    if (maleModVerificationStage == 56 || maleModVerificationStage == 57) { GetGameCamera().GetActivePivotDistanceController().SetDesiredDistance(8.0,1.0); }
    else { GetGameCamera().GetActivePivotDistanceController().SetDesiredDistance(2.4,1.0); }
    // Inspect the actual scene camera through its SDK, without OS input.
    if (maleModVerificationStage >= 64)
    {
        cameraAim = thePlayer.GetWorldPosition(); cameraAim.Z += 1.0;
        cameraDirection = RotForward(thePlayer.GetWorldRotation());
        cameraRight = RotRight(thePlayer.GetWorldRotation());
        if ((maleModVerificationStage == 75 || maleModVerificationStage >= 84)) { cameraDirection = cameraDirection * -1.0; }
        else if (maleModVerificationStage == 76) { cameraDirection = cameraRight; }
        else if (maleModVerificationStage == 78) { cameraDirection = cameraRight * -1.0; }
        else { cameraDirection = cameraDirection + cameraRight * 0.35; }
        cameraPosition = cameraAim + VecNormalize(cameraDirection) * 2.6;
        cameraPosition.Z += 0.35;
        // Inspect actual contact deposits from above at sequence completion.
        // Engine camera only; the user's physical desktop is never activated.
        if (maleModVerificationStage == 71 || maleModVerificationStage == 72)
        {
            cameraAim = thePlayer.GetWorldPosition() + RotForward(thePlayer.GetWorldRotation()) * 0.3;
            cameraAim.Z += 0.15;
            cameraPosition = cameraAim + VecNormalize(cameraDirection) * 2.6;
            cameraPosition.Z += 2.2;
        }
        GetGameCamera().EnableManualControl(true);
        GetGameCamera().SetNoclip(true);
        GetGameCamera().SetCameraWorldPosition(cameraPosition);
        cameraRotation = VecToRotation(cameraAim-cameraPosition);
        // Camera pitch convention is opposite the actor-vector conversion.
        cameraRotation.Pitch = -cameraRotation.Pitch;
        GetGameCamera().SetCameraWorldRotation(cameraRotation);
        GetGameCamera().UpdateWithoutInput(true);
    }
    if (seconds < maleModVerificationTime) { maleModVerificationTime = seconds; }
    if (maleModVerificationCaptured) { if (seconds-maleModVerificationTime < 0.75) { return; } }
    else if (maleModVerificationStage == 60)
    {
        maleModVerificationPauseTicks += 1;
        if (maleModVerificationPauseTicks < 80) { return; }
    }
    else if (maleModVerificationStage >= 69 && maleModVerificationStage <= 72) { if (seconds-maleModVerificationTime < 4.0) { return; } }
    else if (seconds-maleModVerificationTime < 2.0) { return; }
    if (!maleModVerificationCaptured)
    {
        if (!MaleModNativeTestCheckpoint(maleModVerificationStage)) { return; }
        TakeScreenshot();
        maleModVerificationCaptured = true; maleModVerificationTime = seconds; return;
    }
    maleModVerificationCaptured = false;

    maleModVerificationStage += 1;
    maleModVerificationTime = seconds;
    // Each test begins at the exact full-floppy reset contract.
    MaleModNativeSetControl(0,2.0);
    for (i=1;i<18;i+=1) { MaleModNativeSetControl(i,50.0); }
    if (maleModVerificationStage <= 2) { value = maleModVerificationStage-1; MaleModNativeSetControl(0,value); }
    else if (maleModVerificationStage <= 53)
    {
        control = 1+(maleModVerificationStage-3)/3;
        part = (maleModVerificationStage-3)%3;
        value = 50.0;
        if (part == 0) { value = 1.0; if (control == 2 || control == 4) { value = 0.0; } }
        else if (part == 2) { value = 100.0; }
        MaleModNativeSetControl(control,value);
    }
    else if (maleModVerificationStage == 54) { for (i=1;i<18;i+=1) { MaleModNativeSetControl(i,100.0); } }
    else if (maleModVerificationStage == 60) { MaleModNativeSetControl(1,100.0); Pause("MaleMod private verification"); }
    else if (maleModVerificationStage == 61) { Unpause("MaleMod private verification"); }
    else if (maleModVerificationStage == 63) { LoadLastGameInit(); }
    if (maleModVerificationStage >= 64 && maleModVerificationStage <= 66) { MaleModNativeClinicalControl(0,(float)(maleModVerificationStage-63)); }
    else if (maleModVerificationStage == 67) { MaleModNativeClinicalControl(0,0.0); MaleModNativeClinicalControl(1,1.0); }
    else if (maleModVerificationStage == 73) { MaleModNativeClinicalControl(1,1.0); }
    else if (maleModVerificationStage == 74) { MaleModNativeClinicalControl(1,0.0); }
    else if (maleModVerificationStage >= 79 && maleModVerificationStage <= 82) { MaleModNativeSetControl(1,25.0*(float)(maleModVerificationStage-78)); }
    // Move through the game's actor API inside the private station. No host
    // keys, mouse or focus changes, and the existing SDK no-save lock remains.
    if (maleModVerificationStage < 63 && maleModVerificationStage != 60)
    {
        target = maleModVerificationOrigin;
        if (maleModVerificationStage%2 == 0) { target.X += 2.0; }
        else { target.X -= 2.0; }
        thePlayer.ActionMoveToAsync(target,MT_Run,3.0,0.25);
    }
}
@addField(CR4Game)
private var maleModStartRequested : bool;
@addField(CR4Game)
private var maleModSealedSaveLock : int;
@addField(CR4Game)
private var maleModSealedSaveLocked : bool;
@addField(CR4Game)
private var maleModPrivateTicks : int;
@addField(CR4Game)
private var maleModPrivateLoadIssued : bool;
@addField(CR4Game)
public var maleModContinueAttempted : bool;
@addField(CR4Game)
public var maleModContinueMenu : CR4IngameMenu;
@addField(CR4Game)
public var maleModContinueTicks : int;

@wrapMethod(CR4IngameMenu)
function OnConfigUI()
{
    wrappedMethod();
    if (isMainMenu && MaleModNativeSealedSession()) { theGame.MaleModQueueContinueForNativeTest(this); }
}

@addMethod(CR4Game)
function MaleModQueueContinueForNativeTest(menu : CR4IngameMenu)
{
    if (!maleModContinueAttempted)
    {
        maleModContinueAttempted = true;
        maleModContinueMenu = menu;
        maleModContinueTicks = 2;
    }
}

@addMethod(CR4IngameMenu)
function MaleModContinueForNativeTest()
{
    if (isMainMenu) { LoadLastSave(true); }
}

@wrapMethod(CR4Game)
function OnTick()
{
    var menu : CR4IngameMenu;
    var start : CR4StartScreenMenuBase;
    var root : CR4Menu;
    wrappedMethod();
    if (MaleModNativeSealedSession())
    {
        MaleModPrivateVerificationStep();
        maleModPrivateTicks += 1;
        if (!maleModSealedSaveLocked)
        {
            CreateNoSaveLock("MaleMod isolated verification",maleModSealedSaveLock,true,false);
            maleModSealedSaveLocked = true;
        }
        root = GetGuiManager().GetRootMenu();
        if (root && !maleModStartRequested)
        {
            start = (CR4StartScreenMenuBase)root;
            if (start && isUserSignedIn())
            {
                maleModStartRequested = true;
                start.startFade();
            }
        }
        // The private desktop can render while its Flash title cannot finish
        // opening. Load the already authorized usual save through the public
        // SDK API after signed-in initialization; no OS input is needed.
        if (!thePlayer && !maleModPrivateLoadIssued && maleModPrivateTicks >= 120 && isUserSignedIn())
        {
            maleModPrivateLoadIssued = true;
            maleModContinueMenu = NULL;
            maleModContinueAttempted = true;
            LoadLastGameInit();
        }
    }
    if (maleModContinueMenu)
    {
        maleModContinueTicks -= 1;
        if (maleModContinueTicks > 0) { return; }
        menu = maleModContinueMenu;
        maleModContinueMenu = NULL;
        menu.MaleModContinueForNativeTest();
    }
}

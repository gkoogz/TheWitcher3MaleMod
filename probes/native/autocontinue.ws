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
private var maleModVerificationPauseTicks : int;

@addMethod(CR4Game)
function MaleModPrivateVerificationStep()
{
    var i, control, part : int;
    var value, seconds : float;
    var target : Vector;
    if (!thePlayer || (IsPaused() && maleModVerificationStage != 60) || maleModVerificationStage >= 64) { return; }
    seconds = GetEngineTimeAsSeconds();
    if (!maleModVerificationStarted)
    {
        maleModVerificationOrigin = thePlayer.GetWorldPosition();
        maleModVerificationHeading = thePlayer.GetHeading()+120.0;
        maleModVerificationStarted = true;
        maleModVerificationTime = seconds;
    }
    GetGameCamera().SetManualRotationHorTimeout(1000.0);
    GetGameCamera().SetManualRotationVerTimeout(1000.0);
    GetGameCamera().GetActivePivotRotationController().SetDesiredHeading(maleModVerificationHeading,1.0);
    GetGameCamera().GetActivePivotRotationController().SetDesiredPitch(0.0,1.0);
    if (maleModVerificationStage == 56 || maleModVerificationStage == 57) { GetGameCamera().GetActivePivotDistanceController().SetDesiredDistance(8.0,1.0); }
    else { GetGameCamera().GetActivePivotDistanceController().SetDesiredDistance(2.4,1.0); }
    if (seconds < maleModVerificationTime) { maleModVerificationTime = seconds; }
    if (maleModVerificationStage == 60)
    {
        maleModVerificationPauseTicks += 1;
        if (maleModVerificationPauseTicks < 80) { return; }
    }
    else if (seconds-maleModVerificationTime < 2.0) { return; }
    if (!MaleModNativeTestCheckpoint(maleModVerificationStage)) { return; }
    if (maleModVerificationStage == 0 || maleModVerificationStage == 5 || maleModVerificationStage == 54 || maleModVerificationStage >= 55) { TakeScreenshot(); }
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

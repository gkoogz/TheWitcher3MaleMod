// V2 owned campaign regression: fresh stock Novigrad hub, no personal save.
// Transient grey floor in the proven stock bootstrap; no world transition.
// The normal save bootstrap is not used: it would replace this test world.
import function MaleModNativeSealedSession() : bool;
import function MaleModNativeTestCheckpoint(stage : int) : bool;
// Existing independent native writer. These packets are explicitly tagged
// iteration lifecycle readback, not anatomical pose or source physics input.
import function MaleModNativePoseSample(seconds : float, paused : bool,
    markerX : Vector, markerY : Vector, markerZ : Vector, position : Vector,
    lifecycle : Vector, menu : Vector, hit : Vector, normal : Vector) : bool;

function MaleModIterationFilterMovies(out menus : array<name>)
{
    var filtered : array<name>;
    var i : int;
    if (!MaleModNativeSealedSession()) { return; }
    for (i=0; i<menus.Size(); i+=1)
    {
        if (menus[i]!='StartupMoviesMenu' && menus[i]!='RecapMoviesMenu')
        {
            filtered.PushBack(menus[i]);
        }
    }
    menus=filtered;
}

@wrapMethod(CR4Game)
function PopulateMenuQueueStartupOnce(out menus : array<name>)
{
    wrappedMethod(menus);
    MaleModIterationFilterMovies(menus);
}

@wrapMethod(CR4Game)
function PopulateMenuQueueMainOnce(out menus : array<name>)
{
    wrappedMethod(menus);
    MaleModIterationFilterMovies(menus);
}

@addField(CR4Game)
private var maleModIterationFloor : CEntity;
@addField(CR4Game)
private var maleModIterationFloorSpawned : bool;
@addField(CR4Game)
private var maleModIterationFloorReady : bool;
@addField(CR4Game)
private var maleModIterationFloorPosition : Vector;
@addField(CR4Game)
private var maleModIterationFloorReadySeconds : float;
@addField(CR4Game)
private var maleModIterationWalls : array<CEntity>;
@addField(CR4Game)
private var maleModIterationWalkTarget : CEntity;
@addField(CR4Game)
private var maleModIterationAppearanceSeconds : float;
@addField(CR4Game)
private var maleModIterationWalkStart : Vector;
@addField(CR4Game)
private var maleModIterationWalkDone : bool;
@addField(CR4Game)
private var maleModIterationTicks : int;
@addField(CR4Game)
private var maleModIterationRequested : bool;
@addField(CR4Game)
private var maleModIterationStarted : bool;
@addField(CR4Game)
private var maleModIterationMidFrameSaved : bool;
@addField(CR4Game)
private var maleModIterationSaveLock : int;
@addField(CR4Game)
private var maleModIterationLockCreated : bool;
@addField(CR4Game)
private var maleModIterationTitleStarted : bool;
@addField(CR4Game)
private var maleModIterationAppearancePrepared : bool;
@addField(CR4Game)
private var maleModIterationWalkIssued : bool;
@addField(CR4Game)
private var maleModIterationGameplayReady : bool;
@addField(CR4Game)
private var maleModIterationGameplayReadySeconds : float;
@addField(CR4Game)
public var maleModIterationMainReadyTick : int;
@addField(CR4Game)
private var maleModIterationQuestMenuQueued : bool;
@addField(CR4Game)
public var maleModIterationMainMenu : CR4IngameMenu;
@addField(CR4Game)
public var maleModIterationQuestMenu : CR4MainDbgStartQuestMenu;
@addField(CR4Game)
private var maleModIterationQuestMenuReadySeconds : float;
@addField(CR4Game)
private var maleModIterationWorldSwitchScheduled : bool;
@addField(CR4StartupExperienceMenu)
private var maleModIterationPriorConsentShown : bool;

// Campaign instruction popups do not belong in the fresh no-save studio.
// The normal game follows its original tutorial path after the launcher removes
// this temporary bootstrap; tutorial preferences and seen-message data survive.
@wrapMethod(CR4TutorialSystem)
function DisplayTutorial(tut : STutorialMessage)
{
    if (MaleModNativeSealedSession()) { return; }
    wrappedMethod(tut);
}

@addMethod(CR4Game)
function MaleModIterationMainMenuReady(menu : CR4IngameMenu)
{
    maleModIterationMainReadyTick = maleModIterationTicks;
    maleModIterationMainMenu = menu;
    MaleModIterationEventReadback(11.0);
}

@wrapMethod(CR4MenuBase)
function OnMenuShown()
{
    var main : CR4IngameMenu;
    var questMenu : CR4MainDbgStartQuestMenu;
    wrappedMethod();
    if (MaleModNativeSealedSession())
    {
        // OnMenuShown runs HandleMenuLoaded before this callback. ConfigUI is
        // still initialization and must not close/destroy its own Flash movie.
        main = (CR4IngameMenu)this;
        if (main && main.IsIterationMainMenu())
        {
            theGame.MaleModIterationMainMenuReady(main);
        }
        questMenu = (CR4MainDbgStartQuestMenu)this;
        if (questMenu)
        {
            // Native Flash is still dispatching OnMenuShown. Do not invalidate
            // its movie by requesting/closing a game from this callback.
            theGame.MaleModIterationQuestMenuReady(questMenu);
        }
    }
}

@addMethod(CR4Game)
function MaleModIterationQuestMenuReady(menu : CR4MainDbgStartQuestMenu)
{
    maleModIterationQuestMenu = menu;
    maleModIterationQuestMenuReadySeconds = GetEngineTimeAsSeconds();
    MaleModIterationEventReadback(12.0);TakeScreenshot();
}

@addMethod(CR4MainDbgStartQuestMenu)
function MaleModIterationCloseRoot()
{
    GetRootMenu().CloseMenu();
}

@addMethod(CR4Game)
function MaleModIterationEnsureSaveLock()
{
    // New-game initialization resets locks established at the title menu.
    // Reacquire from the current native manager, including before callbacks.
    if (MaleModNativeSealedSession() && !v2CampaignSaving && !AreSavesLocked())
    {
        CreateNoSaveLock("MaleMod isolated iteration world",maleModIterationSaveLock,true,false);
        v2CampaignSaveLockOwned=true;
    }
}

@addMethod(CR4IngameMenu)
function IsIterationMainMenu() : bool
{
    return isMainMenu;
}

@addMethod(CR4Game)
function MaleModIterationRequestFromMenu(resource : string) : bool
{
    MaleModIterationEventReadback(13.0);
    maleModIterationRequested = RequestNewGame(resource);
    MaleModIterationEventReadback(14.0);
    MaleModIterationReadback();
    return maleModIterationRequested;
}

@wrapMethod(CR4StartupExperienceMenu)
function OnConfigUI()
{
    maleModIterationPriorConsentShown = theTelemetry.WasConsentWindowShown();
    wrappedMethod();
}

@addMethod(CR4StartupExperienceMenu)
function MaleModIterationSkipOptionalStartup()
{
    // The stock Skip Connect event is the supported offline choice. Existing
    // consent values are never submitted or changed by this private driver.
    if (m_page == "connect") { OnConnectPageSkipConnect(); }
    else if (m_page == "connected" || m_page == "patch_notes") { OnContinue(); }
    else if (m_page == "telemetry" && maleModIterationPriorConsentShown) { OnContinue(); }
}

// Engine locomotion, not repeated Teleport or host input. AI path actions need
// campaign nav data; this bounded controller exercises the physical studio.
class MaleModIterationWalkController extends CR4LocomotionDirectControllerScript
{
    public var startedSeconds : float;
    public var heading : float;
    function Activate() : bool
    {
        startedSeconds=theGame.GetEngineTimeAsSeconds();
        heading=thePlayer.GetHeading();
        thePlayer.SetBehaviorVariable('AIControlled',0.0);
        return true;
    }
    function UpdateLocomotion()
    {
        moveSpeed=0.0;
        if (theGame.GetEngineTimeAsSeconds()-startedSeconds < 4.0) {moveSpeed=0.6;}
        agent.SetGameplayRelativeMoveSpeed(moveSpeed);
        agent.SetGameplayMoveDirection(heading);
        thePlayer.SetBehaviorVariable('test_moveSpeed',moveSpeed);
        thePlayer.SetBehaviorVariable('playerSpeedForOverlay',moveSpeed,true);
        thePlayer.SetBehaviorVariable('actorMoveDirection',0.0);
        thePlayer.SetIsWalking(moveSpeed>0.1);
    }
    function Deactivate()
    {
        agent.ResetMoveRequests();
        agent.UnsetGameplayMoveDirection();
    }
}
function MaleModIterationWalk()
{
    var controller : MaleModIterationWalkController;
    controller=new MaleModIterationWalkController in thePlayer;
    thePlayer.ActionDirectControl(controller);
}

function MaleModIterationDisableStudioShadows(entity : CEntity)
{
    var parts : array<CComponent>;
    var part : CDrawableComponent;
    var i : int;
    if (!entity) {return;}
    parts=entity.GetComponentsByClassName('CComponent');
    for (i=0;i<parts.Size();i+=1)
    {
        part=(CDrawableComponent)parts[i];
        if (part) {part.SetCastingShadows(false);}
    }
}

@addMethod(CPlayer)
function MaleModIterationUnlockFreshCharacter()
{
    SetManualControl(true,true);
    inputHandler.ForceUnlockAllInputActions(true);
    SetShowHud(false);
}

// ASCII menu identifiers are packed losslessly, three bytes per float. The
// diagnostic is a separate tagged packet and is never fed to the solver.
@addMethod(CR4Game)
function MaleModIterationTextWord(text : string, offset : int) : float
{
    var i, j, multiplier, value : int;
    multiplier = 1;
    for (i = 0; i < 3; i += 1)
    {
        if (offset+i >= StrLen(text)) { break; }
        for (j = 32; j < 127; j += 1)
        {
            if (StrMid(text,offset+i,1) == StrChar(j)) { value += j*multiplier; break; }
        }
        multiplier *= 128;
    }
    return (float)value;
}

@addMethod(CR4Game)
function MaleModIterationMenuReadback()
{
    var root : CR4Menu;
    var child : CMenu;
    var text : string;
    var a, b, c, d, e : Vector;
    var worldPath : bool;
    root = GetGuiManager().GetRootMenu();
    if (root)
    {
        text = NameToString(root.GetMenuName());
        child = root.GetSubMenu();
        if (child) { text += "/" + NameToString(child.GetMenuName()); }
    }
    // Once a player exists, preserve the actual native world representation
    // independently instead of assuming a full resource path. The strict
    // identity gate below remains unchanged until this evidence is inspected.
    if (thePlayer)
    {
        if (GetWorld()) { text = GetWorld().GetDepotPath(); }
        else { text = "<NO_WORLD>"; }
        worldPath = true;
    }
    a = Vector((float)StrLen(text),MaleModIterationTextWord(text,0),MaleModIterationTextWord(text,3),MaleModIterationTextWord(text,6));
    b = Vector(MaleModIterationTextWord(text,9),MaleModIterationTextWord(text,12),MaleModIterationTextWord(text,15),MaleModIterationTextWord(text,18));
    c = Vector(MaleModIterationTextWord(text,21),MaleModIterationTextWord(text,24),MaleModIterationTextWord(text,27),MaleModIterationTextWord(text,30));
    d = Vector(MaleModIterationTextWord(text,33),MaleModIterationTextWord(text,36),MaleModIterationTextWord(text,39),MaleModIterationTextWord(text,42));
    e = Vector(MaleModIterationTextWord(text,45),MaleModIterationTextWord(text,48),MaleModIterationTextWord(text,51),MaleModIterationTextWord(text,54));
    if (worldPath)
    {
        MaleModNativePoseSample(GetEngineTimeAsSeconds(),false,
            Vector(1,0,0,-221),Vector(0,1,0,-222),Vector(0,0,1,-223),a,b,c,d,e);
        return;
    }
    MaleModNativePoseSample(GetEngineTimeAsSeconds(),false,
        Vector(1,0,0,-211),Vector(0,1,0,-212),Vector(0,0,1,-213),a,b,c,d,e);
}

@addMethod(CR4Game)
function MaleModIterationOwnWorld() : bool
{
    var path : string;
    if (!GetWorld()) { return false; }
    path = StrLower(GetWorld().GetDepotPath());
    // WitcherScript depot literals use one backslash, as the stock scripts do.
    // Accept only the full authored identity in its two native separator forms.
    return path == "levels\malemod_iteration\malemod_iteration.w2w" || path == "levels/malemod_iteration/malemod_iteration.w2w";
}

@wrapMethod(CR4Game)
function OnGameStarted(restored : bool)
{
    MaleModIterationEnsureSaveLock();
    if (MaleModNativeSealedSession()) { MaleModIterationEventReadback(1.0); }
    wrappedMethod(restored);
    if (MaleModNativeSealedSession()) { MaleModIterationEventReadback(2.0); }
    if(restored){v2CampaignRestored=true;v2CampaignSaving=true;v2CampaignStage=9;v2CampaignAt=GetEngineTimeAsSeconds();MaleModIterationEventReadback(16.0);}
}

@addMethod(CR4Game)
function MaleModIterationEventReadback(eventStage : float)
{
    var position, eventInfo : Vector;
    if (thePlayer) { position = thePlayer.GetWorldPosition(); eventInfo.Y = 1.0; }
    eventInfo.X = eventStage;
    eventInfo.Z = (float)maleModIterationTicks;
    if (MaleModIterationOwnWorld()) { eventInfo.W = 1.0; }
    MaleModNativePoseSample(GetEngineTimeAsSeconds(),false,
        Vector(1,0,0,-231),Vector(0,1,0,-232),Vector(0,0,1,-233),
        position,eventInfo,Vector(0,0,0,0),Vector(0,0,0,0),Vector(0,0,0,0));
}

@wrapMethod(CR4Game)
function OnAfterLoadingScreenGameStart()
{
    MaleModIterationEnsureSaveLock();
    if (MaleModNativeSealedSession()) { MaleModIterationEventReadback(3.0); }
    if (MaleModNativeSealedSession() && FactsQuerySum("tut_stash_fresh_playthrough") <= 0)
    {
        // This new no-save studio has no campaign stash tutorial. The stock
        // callback checks this world fact before opening its Flash popup.
        // It does not alter the user's tutorial preference or ordinary saves.
        FactsAdd("tut_stash_fresh_playthrough",1);
    }
    if (MaleModNativeSealedSession())
    {
        maleModIterationGameplayReady = true;
        maleModIterationGameplayReadySeconds = GetEngineTimeAsSeconds();
    }
    wrappedMethod();
    if (MaleModNativeSealedSession()) { MaleModIterationEventReadback(4.0); }
    if (MaleModNativeSealedSession() && thePlayer) { GetTutorialSystem().TutorialFinish(); }
}

@addMethod(CR4Game)
function MaleModIterationReadback()
{
    var lifecycle, menu, position, hit, normal : Vector;
    var resources : array<string>;
    var i : int;
    var groups : array<name>;
    var root : CR4Menu;
    var movie : CR4StartupMoviesMenu;
    var recap : CR4RecapMoviesMenu;
    var start : CR4StartScreenMenuBase;
    var main : CR4CommonMainMenuBase;
    var ingame : CR4IngameMenu;
    lifecycle.X = (float)maleModIterationTicks;
    if (maleModIterationRequested) { lifecycle.Y = 1.0; }
    if (thePlayer) { lifecycle.Z = 1.0; position = thePlayer.GetWorldPosition(); }
    if (MaleModIterationOwnWorld())
    {
        lifecycle.W = 1.0;
        groups.PushBack('Static');
        if (GetWorld().StaticTrace(Vector(0,0,2,1),Vector(0,0,-2,1),hit,normal,groups)) { menu.W = 1.0; }
    }
    resources = GetGameResourceList();
    normal.X = (float)resources.Size();
    for (i = 0; i < resources.Size(); i += 1)
    {
        if (StrFindFirst(StrLower(resources[i]),"malemod_iteration") >= 0)
        {
            normal.Y += 1.0;
            // Registry labels are not assumed to retain folder or extension.
            if (!lifecycle.W)
            {
                hit.X = (float)StrLen(resources[i]);
                hit.Y = (float)StrFindFirst(resources[i],".redgame");
                hit.Z = (float)StrFindFirst(resources[i],"levels");
                hit.W = (float)maleModIterationMainReadyTick;
            }
        }
        if (StrFindFirst(StrLower(resources[i]),"witcher3") >= 0) { normal.Z = 1.0; }
    }
    root = GetGuiManager().GetRootMenu();
    if (root) { menu.X = 1.0; }
    movie = (CR4StartupMoviesMenu)root;
    recap = (CR4RecapMoviesMenu)root;
    start = (CR4StartScreenMenuBase)root;
    main = (CR4CommonMainMenuBase)root;
    ingame = (CR4IngameMenu)root;
    if (movie) { normal.W = 1.0; }
    if (start) { normal.W = 2.0; }
    if (main) { normal.W = 3.0; }
    if (ingame) { normal.W = 4.0; }
    if (recap) { normal.W = 5.0; }
    if (isUserSignedIn()) { menu.Y = 1.0; }
    if (IsPaused()) { menu.Z = 1.0; }
    MaleModNativePoseSample(GetEngineTimeAsSeconds(),false,
        Vector(1,0,0,-201),Vector(0,1,0,-202),Vector(0,0,1,-203),
        position,lifecycle,menu,hit,normal);
}

@wrapMethod(CR4Game)
function OnTick()
{
    var resources : array<string>;
    var i : int;
    var groups : array<name>;
    var floorTemplate : CEntityTemplate;
    var wallTemplate, targetTemplate : CEntityTemplate;
    var wall : CEntity;
    var wallPosition : Vector;
    var wallRotation : EulerAngles;
    var floorComponent : CComponent;
    var material : name;
    var floorState : Vector;
    var hit, normal, position : Vector;
    var root : CR4Menu;
    var start : CR4StartScreenMenuBase;
    var movie : CR4StartupMoviesMenu;
    var recap : CR4RecapMoviesMenu;
    var startup : CR4StartupExperienceMenu;
    var mainMenu : CR4IngameMenu;
    var questMenu : CR4MainDbgStartQuestMenu;
    var pauseOther : Vector;
    var underwear : array<SItemUniqueId>;
    var equippedPants : SItemUniqueId;
    var pantsName : string;
    var studioEnvironment : CEnvironmentDefinition;
    var studioAgent : CMovingPhysicalAgentComponent;
    var studioMesh : CDrawableComponent;
    MaleModIterationEnsureSaveLock();
    wrappedMethod();
    if (!MaleModNativeSealedSession()) { return; }
    // The grey studio has no campaign particle effects. The retail particle
    // pass produces opaque black movement puffs on this transient surface;
    // a moving, per-pass comparison isolated it from shadows and anatomy.
    // Keep this volatile show flag scoped to the owned studio process.
    if (maleModIterationFloorReady) { SetShowFlag(SHOW_Particles,false); }
    
    if (maleModIterationStarted && !maleModIterationWalkDone && !maleModIterationMidFrameSaved && GetEngineTimeAsSeconds()-maleModIterationAppearanceSeconds > 5.0)
    {
        maleModIterationMidFrameSaved = true;
        theGame.TakeScreenshot();
    }
    // Supported native config disables implicit background pause in the
    // noninteractive test process. The launcher preserves the settings file.
    GetInGameConfigWrapper().SetVarValue('Game','DoNotPauseWhileStopped',"true");
    maleModIterationTicks += 1;
    // Read-only retail pause-array inspection identified CR4MessagePopup, not
    // an inactive-window pause. Close the stock popup through its normal UI
    // lifecycle after our fresh no-save character has a grounded studio floor.
    // Do not submit a dialog action or clear unrelated native pause reasons.
    if (maleModIterationFloorReady && !maleModIterationStarted && IsPausedForReason("CR4MessagePopup"))
    {
        ClosePopup('MessagePopup');
    }
    if (IsPaused() && maleModIterationTicks % 120 == 0)
    {
        floorState = Vector(0,0,0,0);
        if (IsPausedForReason("tutorial")) { floorState.X = 1.0; }
        if (GetTutorialSystem().HasActiveTutorial()) { floorState.Y = 1.0; }
        if (IsPausedForReason("Popup")) { floorState.Z = 1.0; }
        if (IsPausedForReason("IngameMenu")) { floorState.W = 1.0; }
        position = Vector(0,0,0,0);
        if (thePlayer) { position = thePlayer.GetWorldPosition(); }
        pauseOther = Vector(0,0,0,0);
        if (IsPausedForReason("menus")) { pauseOther.X = 1.0; }
        if (IsPausedForReason("MeditationLock")) { pauseOther.Y = 1.0; }
        if (IsActivelyPaused()) { pauseOther.Z = 1.0; }
        if (GetGuiManager().GetRootMenu()) { pauseOther.W = 1.0; }
        MaleModNativePoseSample(GetEngineTimeAsSeconds(),false,
            Vector(1,0,0,-261),Vector(0,1,0,-262),Vector(0,0,1,-263),
            position,floorState,pauseOther,Vector((float)IsActive(),(float)IsStopped(),GetTimeScale(),0),Vector(0,0,0,0));
        if (floorState.X == 1.0 && floorState.Y == 1.0)
        {
            GetTutorialSystem().HideFirstTutorial();
            GetTutorialSystem().TutorialFinish();
        }
        // The temporary debug start menu has already closed. Retire only its
        // measured pause reason after our exact own floor is ready and no menu
        // exists; other pause reasons remain independently diagnosed.
        if (pauseOther.X == 1.0 && pauseOther.W == 0.0 && maleModIterationFloorReady)
        {
            Unpause("menus");
        }
    }
    if (maleModIterationTicks == 1 || maleModIterationTicks % 120 == 0) { MaleModIterationReadback(); }
    if (maleModIterationTicks % 120 == 1 && maleModIterationTicks > 1) { MaleModIterationMenuReadback(); }
    root = GetGuiManager().GetRootMenu();
    startup = (CR4StartupExperienceMenu)root;
    if (!startup && root) { startup = (CR4StartupExperienceMenu)root.GetSubMenu(); }
    if (startup && maleModIterationTicks % 60 == 0)
    {
        startup.MaleModIterationSkipOptionalStartup();
    }
    movie = (CR4StartupMoviesMenu)root;
    if (!movie && root) { movie = (CR4StartupMoviesMenu)root.GetSubMenu(); }
    if (movie && maleModIterationTicks >= 60 && maleModIterationTicks % 60 == 0)
    {
        // Call the native menu's stock skip event, not a keyboard shortcut.
        movie.OnSkipMovie();
    }
    recap = (CR4RecapMoviesMenu)root;
    if (!recap && root) { recap = (CR4RecapMoviesMenu)root.GetSubMenu(); }
    if (recap && !ShouldForceInstallVideo() && maleModIterationTicks >= 60 && maleModIterationTicks % 60 == 0)
    {
        recap.OnSkipMovie();
    }
    if (root && !maleModIterationTitleStarted)
    {
        start = (CR4StartScreenMenuBase)root;
        if (start && isUserSignedIn())
        {
            maleModIterationTitleStarted = true;
            start.startFade();
        }
    }
    if (!thePlayer && !maleModIterationQuestMenuQueued && maleModIterationMainMenu && maleModIterationMainReadyTick > 0 && maleModIterationTicks >= maleModIterationMainReadyTick+2 && maleModIterationTicks % 60 == 0 && isUserSignedIn())
    {
        maleModIterationQuestMenuQueued = true;
        mainMenu = maleModIterationMainMenu;
        maleModIterationMainMenu = NULL;
        mainMenu.OnItemActivated(IGMActionType_DebugStartQuest,0);
    }
    if (!maleModIterationRequested && maleModIterationQuestMenu && GetEngineTimeAsSeconds()-maleModIterationQuestMenuReadySeconds >= 0.5)
    {
        resources = GetGameResourceList();
        if(!v2ResourcesReadback){v2ResourcesReadback=true;for(i=0;i<resources.Size();i+=1){V2CampaignResourceReadback(resources[i],i);}}
        for (i=0; i<resources.Size(); i+=1)
        {
            if (StrFindFirst(StrLower(resources[i]),"novigrad_part1") >= 0)
            {
                questMenu = maleModIterationQuestMenu;
                maleModIterationQuestMenu = NULL;
                if (MaleModIterationRequestFromMenu(resources[i])) { questMenu.MaleModIterationCloseRoot(); }
                break;
            }
        }
    }
    if(thePlayer && maleModIterationGameplayReady)
    {
        if(IsPaused() && maleModIterationTicks%120==0)
        {
            MaleModNativePoseSample(GetEngineTimeAsSeconds(),true,
                Vector(1,0,0,-294),Vector(0,1,0,-295),Vector(0,0,1,-296),thePlayer.GetWorldPosition(),
                Vector((float)IsPausedForReason("CR4MessagePopup"),(float)IsPausedForReason("Constrained"),(float)IsPausedForReason("menus"),(float)IsActivelyPaused()),
                Vector((float)v2CampaignStage,(float)maleModIterationTicks,0,0),Vector(0,0,0,0),Vector(0,0,0,0));
        }
        // The retained grey room retires this exact stock popup only after its
        // floor is ready. A campaign never creates that floor. Use the actual
        // named popup and its supported close lifecycle in this sealed child.
        if((v2CampaignStage==0 || v2CampaignStage==9) && IsPausedForReason("CR4MessagePopup"))
        {
            V2CampaignObserve(315);ClosePopup('MessagePopup');
        }
        V2CampaignStep();
    }
}

import function MaleModNativeSetControl(index : int, value : float) : bool;
@addField(CR4Game)
private var v2CampaignStage : int;
@addField(CR4Game)
private var v2CampaignAt : float;
@addField(CR4Game)
private var v2CampaignSaving : bool;
@addField(CR4Game)
private var v2CampaignRestored : bool;
@addField(CR4Game)
private var v2CampaignPauseTicks : int;
@addField(CR4Game)
private var v2CampaignSaveCompleted : bool;
@addField(CR4Game)
private var v2CampaignSaveLockOwned : bool;
@wrapMethod(CR4Game)
function OnSaveCompleted(type : ESaveGameType, succeeded : bool)
{
 wrappedMethod(type,succeeded);
 if(MaleModNativeSealedSession() && v2CampaignSaving)
 {
  if(succeeded){v2CampaignSaveCompleted=true;V2CampaignObserve(313);}else{V2CampaignObserve(314);}
 }
}
@addMethod(CR4Game)
function V2CampaignObserve(stage : int)
{
 var armor, pants : SItemUniqueId;
 var armorText, pantsText : string;
 if(GetWitcherPlayer().GetItemEquippedOnSlot(EES_Armor,armor)){armorText=NameToString(GetWitcherPlayer().inv.GetItemName(armor));}
 if(GetWitcherPlayer().GetItemEquippedOnSlot(EES_Pants,pants)){pantsText=NameToString(GetWitcherPlayer().inv.GetItemName(pants));}
 MaleModNativePoseSample(GetEngineTimeAsSeconds(),IsPaused(),
  Vector(1,0,0,-291),Vector(0,1,0,-292),Vector(0,0,1,-293),thePlayer.GetWorldPosition(),
  Vector((float)stage,(float)AreSavesLocked(),(float)IsPausedForReason("MaleMod V2 regression"),(float)IsPaused()),
  Vector((float)StrLen(armorText),MaleModIterationTextWord(armorText,0),MaleModIterationTextWord(armorText,3),MaleModIterationTextWord(armorText,6)),
  Vector((float)StrLen(pantsText),MaleModIterationTextWord(pantsText,0),MaleModIterationTextWord(pantsText,3),MaleModIterationTextWord(pantsText,6)),
  Vector((float)v2CampaignStage,(float)v2CampaignSaving,(float)v2CampaignRestored,(float)maleModIterationTicks));
}
@addMethod(CR4Game)
function V2CampaignSetView(stage : int)
{
 var aim,position,direction : Vector;
 var rotation : EulerAngles;
 aim=thePlayer.GetWorldPosition();aim.Z+=1.0;direction=RotForward(thePlayer.GetWorldRotation());position=aim+direction*2.3;
 if(stage==303){position=aim-direction*2.3;}
 position.Z+=.1;rotation=VecToRotation(aim-position);rotation.Pitch=-rotation.Pitch;
 EnableFreeCamera(true);MoveFreeCamera(position,rotation);
}
@addMethod(CR4Game)
function V2CampaignCapture(stage : int)
{
 V2CampaignObserve(stage);V2CampaignSetView(stage);MaleModNativeTestCheckpoint(stage);TakeScreenshot();
}
@addMethod(CR4Game)
function V2CampaignStep()
{
 var now : float;
 var items : array<SItemUniqueId>;
 var save : SSavegameInfo;
 var recent : array<SSavegameInfo>;
 var i : int;
 now=GetEngineTimeAsSeconds();
 if(v2CampaignAt==0){MaleModIterationEventReadback(15.0);v2CampaignAt=now;return;}
 if(v2CampaignStage==0 && now-v2CampaignAt>12.0)
 {
  thePlayer.SetManualControl(true,true);thePlayer.GotoState('Exploration');thePlayer.SetDefaultLocomotionController();GetWitcherPlayer().MaleModIterationUnlockFreshCharacter();
  GetWitcherPlayer().UnequipItemFromSlot(EES_Armor);GetWitcherPlayer().UnequipItemFromSlot(EES_Pants);GetWitcherPlayer().UnequipItemFromSlot(EES_Boots);GetWitcherPlayer().UnequipItemFromSlot(EES_Gloves);
  items=GetWitcherPlayer().inv.AddAnItem('Body underwear 01',1);if(items.Size()>0){GetWitcherPlayer().inv.SetItemTemplateOverride(items[0],'l_01_mg__body_underwear');GetWitcherPlayer().EquipItem(items[0]);}
  for(i=0;i<18;i+=1){if(i==0){MaleModNativeSetControl(i,2.0);}else{MaleModNativeSetControl(i,50.0);}}
  MaleModNativeGarmentControl(0);SetGameTime(GameTimeCreate(0,12,0,0),false);v2CampaignStage=1;v2CampaignAt=now;return;
 }
 if(v2CampaignStage==1 && now-v2CampaignAt>6.0)
 {
  V2CampaignCapture(301);MaleModIterationWalk();v2CampaignStage=2;v2CampaignAt=now;return;
 }
 if(v2CampaignStage==2 && now-v2CampaignAt>8.0)
 {
  thePlayer.SetDefaultLocomotionController();V2CampaignObserve(302);MaleModNativeGarmentControl(1);V2CampaignSetView(303);v2CampaignStage=3;v2CampaignAt=now;return;
 }
 if(v2CampaignStage==3 && now-v2CampaignAt>6.0)
 {
  // Use the stock low-level armor: the enhanced Lynx item is level-gated in
  // this fresh Novigrad character and EquipItem correctly refuses it.
  V2CampaignCapture(303);items=GetWitcherPlayer().inv.AddAnItem('Pants 02',1);if(items.Size()>0){GetWitcherPlayer().EquipItem(items[0]);}items=GetWitcherPlayer().inv.AddAnItem('Starting Armor',1);if(items.Size()>0){if(!GetWitcherPlayer().EquipItem(items[0])){V2CampaignObserve(340);}}else{V2CampaignObserve(341);}
  v2CampaignStage=4;v2CampaignAt=now;return;
 }
 if(v2CampaignStage==4 && now-v2CampaignAt>6.0)
 {
  V2CampaignCapture(304);GetWitcherPlayer().UnequipItemFromSlot(EES_Armor);GetWitcherPlayer().UnequipItemFromSlot(EES_Pants);items=GetWitcherPlayer().inv.AddAnItem('Body underwear 01',1);if(items.Size()>0){GetWitcherPlayer().inv.SetItemTemplateOverride(items[0],'l_01_mg__body_underwear');GetWitcherPlayer().EquipItem(items[0]);}
  v2CampaignStage=5;v2CampaignAt=now;return;
 }
 if(v2CampaignStage==5 && now-v2CampaignAt>6.0)
 {
  V2CampaignCapture(305);Pause("MaleMod V2 regression");v2CampaignPauseTicks=maleModIterationTicks;v2CampaignStage=6;v2CampaignAt=now;return;
 }
 if(v2CampaignStage==6 && maleModIterationTicks-v2CampaignPauseTicks>=30)
 {
  V2CampaignObserve(306);MaleModNativeTestCheckpoint(306);Unpause("MaleMod V2 regression");V2CampaignObserve(312);v2CampaignStage=7;v2CampaignAt=now;return;
 }
 if(v2CampaignStage==7 && now-v2CampaignAt>5.0)
 {
  V2CampaignCapture(307);v2CampaignSaving=true;
  V2CampaignObserve(316);
  if(v2CampaignSaveLockOwned){ReleaseNoSaveLock(maleModIterationSaveLock);v2CampaignSaveLockOwned=false;}
  V2CampaignObserve(317);
  if(AreSavesLocked()){V2CampaignObserve(308);MaleModNativeTestCheckpoint(308);v2CampaignStage=12;return;}
  V2CampaignObserve(310);MaleModNativeTestCheckpoint(310);EnableFreeCamera(false);V2CampaignObserve(318);
  SaveGame(SGT_ForcedCheckPoint,-1);V2CampaignObserve(319);v2CampaignStage=8;v2CampaignAt=now;return;
 }
 if(v2CampaignStage==8 && v2CampaignSaveCompleted && now-v2CampaignAt>8.0 && GetRecentListSG(recent) && recent.Size()==1)
 {
  V2CampaignObserve(311);v2CampaignStage=11;v2CampaignAt=now;LoadGameInit(recent[0],false);return;
 }
 if(v2CampaignStage==9 && v2CampaignRestored && now-v2CampaignAt>8.0)
 {
  V2CampaignCapture(309);v2CampaignStage=10;v2CampaignAt=now;return;
 }
}

@addField(CR4Game)
private var v2ResourcesReadback : bool;
@addMethod(CR4Game)
function V2CampaignResourceReadback(text : string, index : int)
{
 MaleModNativePoseSample(GetEngineTimeAsSeconds(),false,
  Vector(1,0,0,-281),Vector(0,1,0,-282),Vector(0,0,1,-283),
  Vector((float)index,(float)StrLen(text),MaleModIterationTextWord(text,0),MaleModIterationTextWord(text,3)),
  Vector(MaleModIterationTextWord(text,6),MaleModIterationTextWord(text,9),MaleModIterationTextWord(text,12),MaleModIterationTextWord(text,15)),
  Vector(MaleModIterationTextWord(text,18),MaleModIterationTextWord(text,21),MaleModIterationTextWord(text,24),MaleModIterationTextWord(text,27)),
  Vector(MaleModIterationTextWord(text,30),MaleModIterationTextWord(text,33),MaleModIterationTextWord(text,36),MaleModIterationTextWord(text,39)),
  Vector(MaleModIterationTextWord(text,42),MaleModIterationTextWord(text,45),MaleModIterationTextWord(text,48),MaleModIterationTextWord(text,51)));
}

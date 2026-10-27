// V2 static fit review. No runtime/performance/attachment acceptance is asserted.
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
    if (MaleModNativeSealedSession() && !AreSavesLocked())
    {
        CreateNoSaveLock("MaleMod isolated iteration world",maleModIterationSaveLock,true,false);
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
    maleModIterationRequested = RequestNewGame(resource);
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
        for (j = 0; j < 128; j += 1)
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
    if(maleModIterationStarted){V2FitCaptureStep();}
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
        for (i=0; i<resources.Size(); i+=1)
        {
            if (StrFindFirst(StrLower(resources[i]),"q002_fistfight_test") >= 0)
            {
                questMenu = maleModIterationQuestMenu;
                maleModIterationQuestMenu = NULL;
                if (MaleModIterationRequestFromMenu(resources[i])) { questMenu.MaleModIterationCloseRoot(); }
                break;
            }
        }
    }
    if (maleModIterationStarted && thePlayer && !maleModIterationWalkDone && GetEngineTimeAsSeconds()-maleModIterationAppearanceSeconds > 8.0)
    {
        maleModIterationWalkDone = true;
        thePlayer.SetDefaultLocomotionController();
        MaleModIterationReadback();
        MaleModNativeTestCheckpoint(201);
        theGame.TakeScreenshot();
    }
    if (!thePlayer || !GetWorld() || maleModIterationStarted || !maleModIterationGameplayReady) { return; }
    if (!IsActive() || IsPaused() || GetEngineTimeAsSeconds()-maleModIterationGameplayReadySeconds < 2.0) { return; }
    if (!maleModIterationFloorSpawned)
    {
        maleModIterationFloorSpawned = true;
        floorTemplate = (CEntityTemplate)LoadResource("levels/malemod_iteration/transient_floor.w2ent",true);
        maleModIterationFloorPosition = thePlayer.GetWorldPosition();
        maleModIterationFloorPosition.Z += 30.0;
        if (floorTemplate)
        {
            maleModIterationFloor = CreateEntity(floorTemplate,maleModIterationFloorPosition,EulerAngles(0,0,0),false,false,true,PM_DontPersist);
            wallTemplate = (CEntityTemplate)LoadResource("levels/malemod_iteration/wall.w2ent",true);
            if (wallTemplate)
            {
                for (i=0;i<4;i+=1)
                {
                    wallPosition=maleModIterationFloorPosition+Vector(0,0,6,0);
                    wallRotation=EulerAngles(0,0,0);
                    if (i==0) {wallPosition.Y+=14;}
                    if (i==1) {wallPosition.Y-=14;}
                    if (i==2) {wallPosition.X+=14;wallRotation.Yaw=90;}
                    if (i==3) {wallPosition.X-=14;wallRotation.Yaw=90;}
                    wall=CreateEntity(wallTemplate,wallPosition,wallRotation,false,false,true,PM_DontPersist);
                    if (wall)
                    {
                        studioMesh=(CDrawableComponent)wall.GetComponentByClassName('CStaticMeshComponent');
                        if (studioMesh) {studioMesh.SetCastingShadows(false);}
                        maleModIterationWalls.PushBack(wall);
                    }
                }
                // Enclose the upward camera view without blocking studio light.
                wall=CreateEntity(floorTemplate,maleModIterationFloorPosition+Vector(0,0,12,0),EulerAngles(0,0,0),false,false,true,PM_DontPersist);
                if (wall)
                {
                    studioMesh=(CDrawableComponent)wall.GetComponentByClassName('CStaticMeshComponent');
                    if (studioMesh) {studioMesh.SetCastingShadows(false);}
                    maleModIterationWalls.PushBack(wall);
                }
            }
            targetTemplate=(CEntityTemplate)LoadResource("levels/malemod_iteration/walk_target.w2ent",true);
            if (targetTemplate)
            {
                maleModIterationWalkTarget=CreateEntity(targetTemplate,maleModIterationFloorPosition+Vector(0,0,.25,0),EulerAngles(0,0,0),false,false,true,PM_DontPersist);
                if (maleModIterationWalkTarget) {maleModIterationWalkTarget.AddTag('MaleModIterationWalkTarget');}
            }
        }
    }
    groups.PushBack('Static');
    floorState = Vector(0,0,0,0);
    if (maleModIterationFloor) { floorState.X = 1.0; }
    if (GetWorld().StaticTraceWithAdditionalInfo(maleModIterationFloorPosition+Vector(0,0,2,0),maleModIterationFloorPosition-Vector(0,0,2,0),hit,normal,material,floorComponent,groups))
    {
        floorState.Y = 1.0;
        if (floorComponent && floorComponent.GetEntity() == maleModIterationFloor) { floorState.Z = 1.0; }
    }
    if (maleModIterationFloorReady) { floorState.W = 1.0; }
    if (maleModIterationTicks % 120 == 0 || (!maleModIterationFloorReady && floorState.Z == 1.0))
    {
        MaleModNativePoseSample(GetEngineTimeAsSeconds(),false,
            Vector(1,0,0,-251),Vector(0,1,0,-252),Vector(0,0,1,-253),
            thePlayer.GetWorldPosition(),floorState,maleModIterationFloorPosition,hit,normal);
    }
    if (floorState.Z != 1.0) { return; }
    if (!maleModIterationFloorReady)
    {
        thePlayer.Teleport(hit+Vector(0,0,0.05,0)-4.0*thePlayer.GetHeadingVector());
        // The raised physical studio is intentionally outside the campaign
        // navigation mesh. Keep capsule collision, but disable its nav snapping.
        thePlayer.GetMovingAgentComponent().SnapToNavigableSpace(false);
        thePlayer.EnablePhysicalMovement(true);
        thePlayer.GotoState('Exploration');
        thePlayer.MaleModIterationUnlockFreshCharacter();
        thePlayer.SetDefaultLocomotionController();
        thePlayer.SetWeatherDisplayDisabled(true);
        GetWorld().HideLayerGroup("global_ambient_fx");
        GetWorld().HideLayerGroup("skybox");
        studioEnvironment=(CEnvironmentDefinition)LoadResource("levels/malemod_iteration/studio.env",true);
        if (studioEnvironment)
        {
            ActivateEnvironmentDefinition(studioEnvironment,1000,1.0,0.0);
        }
        maleModIterationFloorReady = true;
        maleModIterationFloorReadySeconds = GetEngineTimeAsSeconds();
        return;
    }
    if (GetEngineTimeAsSeconds()-maleModIterationFloorReadySeconds < 2.0) { return; }
    if (!maleModIterationAppearancePrepared)
    {
        // Only the sandbox's newly created player is changed; no ordinary save
        // or installed entity template is edited. Existing underwear carriers
        // are selected by the stock equipment pipeline and installed mod.
        GetWitcherPlayer().UnequipItemFromSlot(EES_Armor);
        GetWitcherPlayer().UnequipItemFromSlot(EES_Pants);
        GetWitcherPlayer().UnequipItemFromSlot(EES_Boots);
        GetWitcherPlayer().UnequipItemFromSlot(EES_Gloves);
        // The q002 test's default bare legs use a different resource. Select
        // the exact stock underwear carrier owned by the installed anatomy mod.
        underwear = GetWitcherPlayer().inv.AddAnItem('Body underwear 01',1);
        if (underwear.Size() > 0)
        {
            GetWitcherPlayer().inv.SetItemTemplateOverride(underwear[0],'l_01_mg__body_underwear');
            GetWitcherPlayer().EquipItem(underwear[0]);
        }
        if (GetWitcherPlayer().GetItemEquippedOnSlot(EES_Pants,equippedPants))
        {
            pantsName = NameToString(GetWitcherPlayer().inv.GetItemName(equippedPants));
            MaleModNativePoseSample(GetEngineTimeAsSeconds(),false,
                Vector(1,0,0,-271),Vector(0,1,0,-272),Vector(0,0,1,-273),
                Vector((float)StrLen(pantsName),MaleModIterationTextWord(pantsName,0),MaleModIterationTextWord(pantsName,3),MaleModIterationTextWord(pantsName,6)),
                Vector(MaleModIterationTextWord(pantsName,9),MaleModIterationTextWord(pantsName,12),MaleModIterationTextWord(pantsName,15),0),
                Vector(0,0,0,0),Vector(0,0,0,0),Vector(0,0,0,0));
        }
        maleModIterationAppearancePrepared = true;
        maleModIterationAppearanceSeconds=GetEngineTimeAsSeconds();
        return;
    }
    if (GetEngineTimeAsSeconds()-maleModIterationAppearanceSeconds<3.0) {return;}
    // Actor group shadows are separate from individual component shadows.
    // Use the same supported API as the stock NPC NoShadows ability.
    SetShowFlag(SHOW_Shadows,false);
    thePlayer.SetGroupShadows(false);
    MaleModIterationDisableStudioShadows(thePlayer);
    if (GetWitcherPlayer().GetItemEquippedOnSlot(EES_Pants,equippedPants))
    {
        MaleModIterationDisableStudioShadows(GetWitcherPlayer().inv.GetItemEntityUnsafe(equippedPants));
    }
    studioAgent=(CMovingPhysicalAgentComponent)thePlayer.GetMovingAgentComponent();
    if (studioAgent)
    {
        MaleModNativePoseSample(GetEngineTimeAsSeconds(),false,
            Vector(1,0,0,-281),Vector(0,1,0,-282),Vector(0,0,1,-283),
            thePlayer.GetWorldPosition(),
            Vector((float)studioAgent.IsPhysicalMovementEnabled(),(float)studioAgent.IsAnimatedMovement(),(float)studioAgent.UseExtractedMotion(),(float)studioAgent.IsOnGround()),
            Vector((float)studioAgent.IsCollidesOnSide(),(float)studioAgent.IsOnNavigableSpace(),(float)(int)studioAgent.GetPhysicalState(),0),
            studioAgent.GetVelocity(),Vector(0,0,0,0));
    }
    position = thePlayer.GetWorldPosition();
    LogChannel('MaleMod', "Iteration player position: " + position.X + "," + position.Y + "," + position.Z);
    if (!maleModIterationWalkIssued)
    {
        // Supported direct locomotion drives the native capsule and animation.
        MaleModIterationWalk();
        maleModIterationWalkStart=position;
        maleModIterationWalkIssued = true;
    }
    SetGameTime(GameTimeCreate(0,12,0,0),false);
    maleModIterationStarted = true; // Live v2 source/garment development fixture; acceptance remains separate.
    if (maleModIterationStarted) { theGame.TakeScreenshot(); }
}

@addField(CR4Game)
private var v2FitView : int;
@addField(CR4Game)
private var v2FitViewSeconds : float;
import function MaleModNativeSetControl(index : int, value : float) : bool;
import function MaleModNativeGetControl(index : int) : float;
@addField(CR4Game)
private var v2CasePrepared : bool;
@addMethod(CR4Game)
function V2PrepareCase(index : int)
{
    var i : int;
    for(i=0;i<18;i+=1){if(i==0){MaleModNativeSetControl(i,2.0);}else{MaleModNativeSetControl(i,50.0);}}
    MaleModNativeGarmentControl(0);
    if(index==0){}
    if(index==1){MaleModNativeSetControl(1,1.0);}
    if(index==2){MaleModNativeSetControl(1,25.0);}
    if(index==3){MaleModNativeSetControl(1,75.0);}
    if(index==4){MaleModNativeSetControl(1,100.0);}
    if(index==5){MaleModNativeSetControl(3,1.0);}
    if(index==6){MaleModNativeSetControl(3,25.0);}
    if(index==7){MaleModNativeSetControl(3,75.0);}
    if(index==8){MaleModNativeSetControl(3,100.0);}
    if(index==9){MaleModNativeSetControl(1,1.0);MaleModNativeSetControl(2,0.0);MaleModNativeSetControl(3,1.0);MaleModNativeSetControl(4,0.0);MaleModNativeSetControl(5,1.0);MaleModNativeSetControl(6,1.0);}
    if(index==10){MaleModNativeSetControl(1,100.0);MaleModNativeSetControl(2,100.0);MaleModNativeSetControl(3,100.0);MaleModNativeSetControl(4,100.0);MaleModNativeSetControl(5,100.0);MaleModNativeSetControl(6,100.0);}
    if(index==11){MaleModNativeSetControl(0,0.0);}
    if(index==12){MaleModNativeSetControl(0,0.0);MaleModNativeSetControl(7,1.0);}
    if(index==13){MaleModNativeSetControl(0,0.0);MaleModNativeSetControl(7,100.0);}
    if(index==14){MaleModNativeSetControl(0,1.0);}
    if(index==15){MaleModNativeSetControl(0,1.0);MaleModNativeSetControl(7,1.0);}
    if(index==16){MaleModNativeSetControl(0,1.0);MaleModNativeSetControl(7,100.0);}
    if(index==17){}
    if(index==18){MaleModNativeSetControl(7,1.0);}
    if(index==19){MaleModNativeSetControl(7,100.0);}
    if(index==20){MaleModNativeSetControl(1,75.0);MaleModNativeSetControl(2,25.0);MaleModNativeSetControl(3,75.0);MaleModNativeSetControl(4,75.0);MaleModNativeSetControl(5,25.0);MaleModNativeSetControl(6,75.0);MaleModNativeSetControl(7,75.0);MaleModNativeSetControl(8,75.0);MaleModNativeSetControl(9,25.0);}
    if(index==21){MaleModNativeSetControl(0,0.0);MaleModNativeGarmentControl(1);}
    if(index==22){MaleModNativeSetControl(0,1.0);MaleModNativeGarmentControl(1);}
    if(index==23){MaleModNativeGarmentControl(1);}
    if(index==24){MaleModNativeSetControl(1,1.0);MaleModNativeSetControl(3,1.0);MaleModNativeGarmentControl(1);}
    if(index==25){MaleModNativeSetControl(1,100.0);MaleModNativeSetControl(3,100.0);MaleModNativeGarmentControl(1);}
    if(index==26){MaleModNativeSetControl(0,0.0);MaleModNativeSetControl(7,1.0);MaleModNativeGarmentControl(1);}
    if(index==27){MaleModNativeSetControl(0,0.0);MaleModNativeSetControl(7,100.0);MaleModNativeGarmentControl(1);}
    if(index==28){}
    if(index==29){MaleModNativeGarmentControl(1);}
}
@addField(CR4Game)
private var v2JockStarted : bool;
@addMethod(CR4Game)
function V2FitCaptureStep()
{
    var seconds, distance : float;
    var index, view : int;
    var aim, direction, right, cameraPosition : Vector;
    var rotation : EulerAngles;
    if(!v2JockStarted){v2FitView=63;v2JockStarted=true;}
    if(!thePlayer || IsPaused() || v2FitView>=72){return;}
    seconds=GetEngineTimeAsSeconds();index=v2FitView/3;view=v2FitView%3;
    if(!v2CasePrepared){if(index>=28){GetWorld().ForceGraphicalLOD(1);}else{GetWorld().ForceGraphicalLOD(-1);}V2PrepareCase(index);v2CasePrepared=true;v2FitViewSeconds=seconds+.6;}
    distance=1.5;
    if(index==4){distance=2.0;}
    if(index==10){distance=2.3;}
    if(index==12){distance=2.0;}
    if(index==13){distance=2.0;}
    if(index==15){distance=2.0;}
    if(index==16){distance=2.0;}
    if(index==18){distance=2.0;}
    if(index==19){distance=2.0;}
    if(index==20){distance=2.0;}
    if(index==25){distance=2.2;}
    if(index==26){distance=2.0;}
    if(index==27){distance=2.2;}
    if(index==28){distance=8.0;}
    if(index==29){distance=8.0;}
    aim=thePlayer.GetWorldPosition();aim.Z+=.98;
    direction=RotForward(thePlayer.GetWorldRotation());right=RotRight(thePlayer.GetWorldRotation());
    if(view==1){direction=right;}else if(view==2){direction+=right*.7;}
    cameraPosition=aim+VecNormalize(direction)*distance;cameraPosition.Z+=.04;
    rotation=VecToRotation(aim-cameraPosition);rotation.Pitch=-rotation.Pitch;
    EnableFreeCamera(true);MoveFreeCamera(cameraPosition,rotation);
    if(seconds-v2FitViewSeconds<.7){return;}
    MaleModNativeTestCheckpoint(v2FitView);TakeScreenshot();v2FitView+=1;v2FitViewSeconds=seconds;
    if(v2FitView%3==0){v2CasePrepared=false;}
}

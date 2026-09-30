// REDengine adapter. Numerical anatomy and shared preferences belong in Base.
// This native backend exposes three engine controls, not Wolverine solver parity.
import class IAnimDangleConstraint extends CObject {}
import class CAnimSkeletalDangleConstraint extends IAnimDangleConstraint {}
import class CAnimDangleConstraint_Dyng extends CAnimSkeletalDangleConstraint
{
    import var dampening : float;
    import var gravity : float;
    import var speed : float;
}

class MaleModMotionComponent extends CSelfUpdatingComponent
{
    editable var dynamicConstraint : CAnimDangleConstraint_Dyng;
    private var panelOpen : bool;
    private var listening : bool;
    private var selected : int;
    private var gravityValue : float;
    private var dampingValue : float;
    private var speedValue : float;
    private var preferencesDirty : bool;
    private var hudOwned : bool;
    private var hudX : float;
    private var hudY : float;

    private var startupElapsed : float;
    private var panelElapsed : float;
    private var playerInventoryOwner : bool;

    // Body-part appearances may transplant components into the player. They do
    // not guarantee a separate CItemEntity or its attachment callback.
    event OnComponentAttached() { startupElapsed = 0.0; StartTicking(); }
    event OnComponentAttachFinished() { InitializeController(); }
    event OnComponentDetached() { StopPanel(); playerInventoryOwner = false; }

    private function IsPlayerOwner() : bool
    {
        var item : CItemEntity;
        if (!thePlayer) { return false; }
        if (GetEntity() == thePlayer || playerInventoryOwner) { return true; }
        item = (CItemEntity)GetEntity();
        return item && item.GetParentEntity() == thePlayer;
    }

    public function InitializeController() : bool
    {
        var keys : array<EInputKey>;
        if (listening) { return true; }
        if (!IsPlayerOwner() || !dynamicConstraint) { return false; }
        gravityValue = dynamicConstraint.gravity;
        dampingValue = dynamicConstraint.dampening;
        speedValue = dynamicConstraint.speed;
        LoadTuning();
        ApplyTuning();
        // Register where gameplay has confirmed this component initializes.
        // One owner, one listener: no player wrapper or per-frame key polling.
        theInput.RegisterListener(this, 'OnMaleModInput', 'MaleModToggle');
        listening = true;
        StopTicking();
        theInput.GetPCKeysForAction('MaleModToggle', keys);
        thePlayer.DisplayHudMessage("MaleMod 0.4.3 ready: F6 | bound keys: " + keys.Size());
        return true;
    }

    event OnComponentTick(dt : float)
    {
        if (!listening)
        {
            startupElapsed += dt;
            if (!InitializeController() && startupElapsed > 5.0) { StopTicking(); }
            return false;
        }
        if (!IsPlayerOwner()) { StopPanel(); return false; }
        if (!panelOpen) { StopTicking(); return false; }
        panelElapsed += dt;
        if (panelElapsed >= 0.1) { panelElapsed = 0.0; DrawPanel(); }
    }

    private function StopPanel()
    {
        panelOpen = false;
        StopTicking();
        if (listening)
        {
            theInput.UnregisterListener(this, 'MaleModToggle');
            theInput.UnregisterListener(this, 'MaleModPrevious');
            theInput.UnregisterListener(this, 'MaleModNext');
            theInput.UnregisterListener(this, 'MaleModDecrease');
            theInput.UnregisterListener(this, 'MaleModIncrease');
            theInput.UnregisterListener(this, 'MaleModReset');
        }
        listening = false;
        ClearPanel();
        if (preferencesDirty && theGame) { theGame.SaveUserSettings(); preferencesDirty = false; }
    }

    event OnDestroyed() { StopPanel(); }

    public function OpenPanel()
    {
        var action : SInputAction;
        if (!InitializeController()) { MaleModShowStatus(); return; }
        action.aName = 'MaleModToggle'; action.value = 1.0; action.lastFrameValue = 0.0;
        OnMaleModInput(action);
    }

    public function ConfirmPlayerInventoryOwner()
    {
        // Called only after resolving this exact component through the player's
        // mounted inventory item. Some appearance entities have no item parent.
        playerInventoryOwner = true;
    }

    public function Status() : string
    {
        return "Native controller attached: " + listening + " | constraint: " + (bool)dynamicConstraint
            + " | gravity " + gravityValue + " | damping " + dampingValue + " | speed " + speedValue;
    }

    event OnMaleModInput(action : SInputAction)
    {
        if (!IsPressed(action)) { return false; }
        if (!IsPlayerOwner()) { StopPanel(); return false; }
        if (action.aName == 'MaleModToggle')
        {
            panelOpen = !panelOpen;
            if (panelOpen)
            {
                theInput.RegisterListener(this, 'OnMaleModInput', 'MaleModPrevious');
                theInput.RegisterListener(this, 'OnMaleModInput', 'MaleModNext');
                theInput.RegisterListener(this, 'OnMaleModInput', 'MaleModDecrease');
                theInput.RegisterListener(this, 'OnMaleModInput', 'MaleModIncrease');
                theInput.RegisterListener(this, 'OnMaleModInput', 'MaleModReset');
                thePlayer.DisplayHudMessage("MaleMod: panel opened");
                panelElapsed = 0.0; StartTicking();
                DrawPanel();
            }
            else
            {
                thePlayer.DisplayHudMessage("MaleMod: panel closed and saved");
                StopTicking();
                theInput.UnregisterListener(this, 'MaleModPrevious');
                theInput.UnregisterListener(this, 'MaleModNext');
                theInput.UnregisterListener(this, 'MaleModDecrease');
                theInput.UnregisterListener(this, 'MaleModIncrease');
                theInput.UnregisterListener(this, 'MaleModReset');
                ClearPanel();
                if (preferencesDirty) { theGame.SaveUserSettings(); preferencesDirty = false; }
            }
            return true;
        }
        if (!panelOpen) { return false; }
        if (action.aName == 'MaleModPrevious') { selected = (selected+2)%3; }
        if (action.aName == 'MaleModNext') { selected = (selected+1)%3; }
        if (action.aName == 'MaleModDecrease') { Adjust(-1.0); }
        if (action.aName == 'MaleModIncrease') { Adjust(1.0); }
        if (action.aName == 'MaleModReset')
        {
            gravityValue = 0.15; dampingValue = 0.65; speedValue = 0.3;
            ApplyTuning();
            StoreTuning();
            thePlayer.ResetClothAndDangleSimulation();
        }
        DrawPanel();
    }

    private function Adjust(direction : float)
    {
        if (selected == 0) { gravityValue = ClampF(gravityValue+direction*0.05,0.0,2.0); }
        if (selected == 1) { dampingValue = ClampF(dampingValue+direction*0.01,0.0,1.0); }
        if (selected == 2) { speedValue = ClampF(speedValue+direction*0.05,0.05,2.0); }
        ApplyTuning();
        StoreTuning();
    }

    private function ApplyTuning()
    {
        if (!dynamicConstraint) { return; }
        dynamicConstraint.gravity = gravityValue;
        dynamicConstraint.dampening = dampingValue;
        dynamicConstraint.speed = speedValue;
    }

    private function LoadTuning()
    {
        var cfg : CInGameConfigWrapper;
        cfg = theGame.GetInGameConfigWrapper();
        if (cfg.GetRawConfigValueByStr("MaleModNative", "Version") != "2") { return; }
        gravityValue = ClampF(StringToFloat(cfg.GetRawConfigValueByStr("MaleModNative", "Gravity")),0.0,2.0);
        dampingValue = ClampF(StringToFloat(cfg.GetRawConfigValueByStr("MaleModNative", "Damping")),0.0,1.0);
        speedValue = ClampF(StringToFloat(cfg.GetRawConfigValueByStr("MaleModNative", "Speed")),0.05,2.0);
    }

    private function StoreTuning()
    {
        var cfg : CInGameConfigWrapper;
        cfg = theGame.GetInGameConfigWrapper();
        cfg.SetRawConfigValueByStr("MaleModNative", "Version", "2");
        cfg.SetRawConfigValueByStr("MaleModNative", "Gravity", FloatToString(gravityValue));
        cfg.SetRawConfigValueByStr("MaleModNative", "Damping", FloatToString(dampingValue));
        cfg.SetRawConfigValueByStr("MaleModNative", "Speed", FloatToString(speedValue));
        preferencesDirty = true;
    }

    private function DrawPanel()
    {
        var color : Color;
        var prefix : string;
        var hud : CR4ScriptedHud;
        var module : CR4HudModuleDebugText;
        var label : string;
        if (!thePlayer) { return; }
        hud = (CR4ScriptedHud)theGame.GetHud();
        if (hud) { module = (CR4HudModuleDebugText)hud.GetHudModule("DebugTextModule"); }
        if (module && (hudOwned || !module.bCurrentShowState))
        {
            if (!hudOwned)
            {
                hudX = module.GetModuleFlash().GetX(); hudY = module.GetModuleFlash().GetY(); hudOwned = true;
            }
            label = "MALEMOD | Native motion\n";
            prefix = "  "; if (selected==0) { prefix = "> "; }
            label += prefix + "Gravity  " + gravityValue + "\n";
            prefix = "  "; if (selected==1) { prefix = "> "; }
            label += prefix + "Momentum retention  " + dampingValue + "\n";
            prefix = "  "; if (selected==2) { prefix = "> "; }
            label += prefix + "Speed    " + speedValue + "\n\n";
            label += "Arrows: select / adjust\nF8: reset | F6: close and save";
            module.ShowDebugText(label);
            module.GetModuleFlash().SetPosition(30.0,240.0);
            return;
        }
        color = Color(210,220,230,255);
        thePlayer.GetVisualDebug().AddBar('MaleModTitle',24,230,340,24,0.0,color,"MaleMod native motion test - F6 close",0.3);
        prefix = "  "; if (selected==0) { prefix = "> "; }
        thePlayer.GetVisualDebug().AddBar('MaleModGravity',24,258,340,22,gravityValue/2,color,prefix+"Gravity: "+gravityValue,0.3);
        prefix = "  "; if (selected==1) { prefix = "> "; }
        thePlayer.GetVisualDebug().AddBar('MaleModDamping',24,282,340,22,dampingValue,color,prefix+"Momentum retention: "+dampingValue,0.3);
        prefix = "  "; if (selected==2) { prefix = "> "; }
        thePlayer.GetVisualDebug().AddBar('MaleModSpeed',24,306,340,22,speedValue/2,color,prefix+"Simulation speed: "+speedValue,0.3);
        thePlayer.GetVisualDebug().AddBar('MaleModHelp',24,334,340,24,0.0,color,"Arrows select/adjust | F8 reset",0.3);
    }

    private function ClearPanel()
    {
        var hud : CR4ScriptedHud;
        var module : CR4HudModuleDebugText;
        if (hudOwned && theGame)
        {
            hud = (CR4ScriptedHud)theGame.GetHud();
            if (hud) { module = (CR4HudModuleDebugText)hud.GetHudModule("DebugTextModule"); }
            if (module)
            {
                module.HideDebugText(); module.GetModuleFlash().SetPosition(hudX,hudY);
            }
            hudOwned = false;
        }
        if (!thePlayer) { return; }
        thePlayer.GetVisualDebug().RemoveBar('MaleModTitle');
        thePlayer.GetVisualDebug().RemoveBar('MaleModGravity');
        thePlayer.GetVisualDebug().RemoveBar('MaleModDamping');
        thePlayer.GetVisualDebug().RemoveBar('MaleModSpeed');
        thePlayer.GetVisualDebug().RemoveBar('MaleModHelp');
    }
}

function MaleModFindController() : MaleModMotionComponent
{
    var controller : MaleModMotionComponent;
    var inventory : CInventoryComponent;
    var items : array<SItemUniqueId>;
    var entity : CItemEntity;
    var i : int;
    if (!thePlayer) { return NULL; }
    controller = (MaleModMotionComponent)thePlayer.GetComponent("MaleModController");
    if (controller) { return controller; }
    inventory = thePlayer.GetInventory();
    inventory.GetAllItems(items);
    for (i=0; i<items.Size(); i+=1)
    {
        if (!inventory.IsItemMounted(items[i])) { continue; }
        entity = inventory.GetItemEntityUnsafe(items[i]);
        if (!entity) { continue; }
        controller = (MaleModMotionComponent)entity.GetComponent("MaleModController");
        if (controller) { controller.ConfirmPlayerInventoryOwner(); return controller; }
    }
    return NULL;
}

function MaleModTogglePanel()
{
    var controller : MaleModMotionComponent;
    controller = MaleModFindController();
    if (controller) { controller.OpenPanel(); }
    else { MaleModShowStatus(); }
}

function MaleModShowStatus()
{
    var controller : MaleModMotionComponent;
    var status : string;
    var components : array<CComponent>;
    var i : int;
    controller = MaleModFindController();
    status = "F6 input reached MaleMod 0.4.3. No active controller was found. Equip/remove trousers.\n";
    if (controller) { status = controller.Status(); }
    else if (thePlayer)
    {
        components = thePlayer.GetComponentsByClassName('CComponent');
        status += "Player component count: " + components.Size() + "\n";
        for (i=0; i<components.Size(); i+=1) { status += components[i].GetName() + "\n"; }
    }
    theGame.GetGuiManager().ShowUserDialogAdv(90260931,"MaleMod motion status",status,false,UDB_Ok);
}

exec function MaleModMenu() { MaleModTogglePanel(); }
exec function MaleModPhysicsStatus() { MaleModShowStatus(); }

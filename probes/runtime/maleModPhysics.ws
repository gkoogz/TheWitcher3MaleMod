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
        if (listening) { return true; }
        if (!IsPlayerOwner() || !dynamicConstraint) { return false; }
        gravityValue = dynamicConstraint.gravity;
        dampingValue = dynamicConstraint.dampening;
        speedValue = dynamicConstraint.speed;
        LoadTuning();
        ApplyTuning();
        theInput.RegisterListener(this, 'OnMaleModInput', 'MaleModToggle');
        listening = true;
        StopTicking();
        return true;
    }

    event OnComponentTick(dt : float)
    {
        if (!listening)
        {
            startupElapsed += dt;
            if (!InitializeController() && startupElapsed > 5.0) { StopTicking(); }
        }
        else { StopTicking(); }
    }

    private function StopPanel()
    {
        StopTicking();
        if (listening) { theInput.UnregisterListener(this, 'MaleModToggle'); }
        listening = false;
        SaveTuning();
    }

    event OnDestroyed() { StopPanel(); }

    public function OpenPanel()
    {
        var data : MaleModMenuData;
        if (!InitializeController()) { MaleModShowStatus(); return; }
        if (theGame.GetGuiManager().GetRootMenu()) { return; }
        data = new MaleModMenuData in theGame;
        data.controller = this;
        data.setDefaultState('MaleModMotion');
        theGame.RequestMenu('CommonIngameMenu', data);
    }

    public function SaveTuning()
    {
        if (preferencesDirty && theGame) { theGame.SaveUserSettings(); preferencesDirty = false; }
    }

    public function GetTuning(control : name) : float
    {
        if (control == 'MaleModGravity') { return gravityValue; }
        if (control == 'MaleModDamping') { return dampingValue; }
        return speedValue;
    }

    public function SetTuning(control : name, value : float)
    {
        if (!InitializeController()) { return; }
        if (control == 'MaleModGravity') { gravityValue = ClampF(value,0.0,2.0); }
        else if (control == 'MaleModDamping') { dampingValue = ClampF(value,0.0,1.0); }
        else if (control == 'MaleModSpeed') { speedValue = ClampF(value,0.05,2.0); }
        else { return; }
        ApplyTuning();
        StoreTuning();
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
        if (!IsPressed(action) || action.aName != 'MaleModToggle') { return false; }
        if (!IsPlayerOwner()) { StopPanel(); return false; }
        OpenPanel();
        return true;
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
    status = "F6 input reached MaleMod 0.4.4. No active controller was found. Equip/remove trousers.\n";
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

// Native Scaleform menu objects follow igmOptions.ws. No debug HUD, XML file-list
// edits, global polling, or independent copy of a stock script is needed.
class MaleModMenuData extends W3MenuInitData
{
    var controller : MaleModMotionComponent;
}

function MaleModMenuController(menu : CR4IngameMenu) : MaleModMotionComponent
{
    var data : MaleModMenuData;
    data = (MaleModMenuData)menu.GetMenuInitData();
    if (data && data.controller) { return data.controller; }
    return MaleModFindController();
}

function MaleModSlider(storage : CScriptedFlashValueStorage, control : name, label : string,
    value : float, minimum : float, maximum : float, steps : int) : CScriptedFlashObject
{
    var row : CScriptedFlashObject;
    var range : CScriptedFlashArray;
    row = storage.CreateTempFlashObject();
    row.SetMemberFlashString("id", "" + control);
    row.SetMemberFlashString("label", label);
    row.SetMemberFlashUInt("type", IGMActionType_Slider);
    row.SetMemberFlashUInt("tag", NameToFlashUInt(control));
    row.SetMemberFlashInt("groupID", NameToFlashUInt('MaleModNativeSliderGroup'));
    row.SetMemberFlashString("current", FloatToString(value));
    row.SetMemberFlashString("startingValue", FloatToString(value));
    row.SetMemberFlashBool("disabled", false);
    range = storage.CreateTempFlashArray();
    range.PushBackFlashString(FloatToString(minimum));
    range.PushBackFlashString(FloatToString(maximum));
    range.PushBackFlashString(IntToString(steps));
    row.SetMemberFlashArray("subElements", range);
    return row;
}

@wrapMethod(IngameMenuStructureCreator)
function PopulateMenuData() : CScriptedFlashArray
{
    var entries : CScriptedFlashArray;
    var controls : CScriptedFlashArray;
    var group : CScriptedFlashObject;
    var controller : MaleModMotionComponent;
    entries = wrappedMethod();
    controller = MaleModMenuController(parentMenu);
    if (!controller || !controller.InitializeController()) { return entries; }
    controls = m_flashValueStorage.CreateTempFlashArray();
    controls.PushBackFlashObject(MaleModSlider(m_flashValueStorage, 'MaleModGravity',
        "Gravity", controller.GetTuning('MaleModGravity'),0.0,2.0,40));
    controls.PushBackFlashObject(MaleModSlider(m_flashValueStorage, 'MaleModDamping',
        "Momentum retention", controller.GetTuning('MaleModDamping'),0.0,1.0,100));
    controls.PushBackFlashObject(MaleModSlider(m_flashValueStorage, 'MaleModSpeed',
        "Simulation speed", controller.GetTuning('MaleModSpeed'),0.05,2.0,39));
    group = m_flashValueStorage.CreateTempFlashObject();
    group.SetMemberFlashString("id", "MaleModMotion");
    group.SetMemberFlashString("label", "MaleMod - motion controls");
    group.SetMemberFlashString("listTitle", "MaleMod - motion controls");
    group.SetMemberFlashUInt("tag", NameToFlashUInt('MenuSelector'));
    group.SetMemberFlashUInt("type", IGMActionType_MenuLastHolder);
    group.SetMemberFlashArray("subElements", controls);
    entries.PushBackFlashObject(group);
    return entries;
}

@wrapMethod(CR4IngameMenu)
function OnOptionValueChanged(groupId : int, optionName : name, optionValue : string)
{
    var controller : MaleModMotionComponent;
    if (groupId == NameToFlashUInt('MaleModNativeSliderGroup'))
    {
        controller = MaleModMenuController(this);
        if (controller) { controller.SetTuning(optionName, StringToFloat(optionValue)); }
        return true;
    }
    wrappedMethod(groupId, optionName, optionValue);
}

@wrapMethod(CR4IngameMenu)
function OnCancelOptionValueChange(groupId : int, optionName : name)
{
    if (groupId == NameToFlashUInt('MaleModNativeSliderGroup')) { return true; }
    wrappedMethod(groupId, optionName);
}

@wrapMethod(CR4IngameMenu)
function OnClosingMenu()
{
    var controller : MaleModMotionComponent;
    controller = MaleModMenuController(this);
    if (controller) { controller.SaveTuning(); }
    wrappedMethod();
}

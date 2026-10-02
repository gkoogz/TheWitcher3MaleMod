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
        if (controller) { return controller; }
    }
    return NULL;
}

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
    row.SetMemberFlashInt("groupID", NameToFlashUInt('MaleModOverallGroup'));
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
    if (!controller || !controller.OverallReady()) { return entries; }
    controls = m_flashValueStorage.CreateTempFlashArray();
    controls.PushBackFlashObject(MaleModSlider(m_flashValueStorage, 'MaleModOverall',
        "Overall", controller.GetOverall(),1.0,100.0,99));
    group = m_flashValueStorage.CreateTempFlashObject();
    group.SetMemberFlashString("id", "MaleModMotion");
    group.SetMemberFlashString("label", "MaleMod - anatomy");
    group.SetMemberFlashString("listTitle", "MaleMod - anatomy");
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
    if (groupId == NameToFlashUInt('MaleModOverallGroup'))
    {
        controller = MaleModMenuController(this);
        if (controller) { if (optionName == 'MaleModOverall') { controller.SetOverall(StringToFloat(optionValue)); } }
        return true;
    }
    wrappedMethod(groupId, optionName, optionValue);
}

@wrapMethod(CR4IngameMenu)
function OnCancelOptionValueChange(groupId : int, optionName : name)
{
    if (groupId == NameToFlashUInt('MaleModOverallGroup')) { return true; }
    wrappedMethod(groupId, optionName);
}

@wrapMethod(CR4IngameMenu)
function OnClosingMenu()
{
    var controller : MaleModMotionComponent;
    controller = MaleModMenuController(this);
    if (controller) { theGame.SaveUserSettings(); }
    wrappedMethod();
}

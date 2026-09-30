// Native candidate. Excluded from workspace and installation until the entity
// binding and render path have passed the native resource verification gates.
import class IAnimDangleConstraint extends CObject {}
import class CAnimSkeletalDangleConstraint extends IAnimDangleConstraint {}
import class CAnimDangleConstraint_Dyng extends CAnimSkeletalDangleConstraint
{
    import var dampening : float;
    import var gravity : float;
    import var speed : float;
}

class MaleModPhysicsItem extends CItemEntity
{
    editable var dynamicConstraint : CAnimDangleConstraint_Dyng;
    private var panelOpen : bool;
    private var listening : bool;
    private var selected : int;
    private var gravityValue : float;
    private var dampingValue : float;
    private var speedValue : float;

    event OnAttachmentUpdate(parentEntity : CEntity, itemName : name)
    {
        super.OnAttachmentUpdate(parentEntity, itemName);
        StopPanel();
        if (parentEntity != thePlayer || !dynamicConstraint) { return false; }
        gravityValue = dynamicConstraint.gravity;
        dampingValue = dynamicConstraint.dampening;
        speedValue = dynamicConstraint.speed;
        theInput.RegisterListener(this, 'OnMaleModInput', 'MaleModToggle');
        listening = true;
    }

    private function StopPanel()
    {
        panelOpen = false;
        RemoveTimer('MaleModPanelTick');
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
    }

    event OnDestroyed() { StopPanel(); }

    event OnMaleModInput(action : SInputAction)
    {
        if (!IsPressed(action)) { return false; }
        if (GetParentEntity() != thePlayer) { StopPanel(); return false; }
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
                AddTimer('MaleModPanelTick', 0.1, true);
                DrawPanel();
            }
            else
            {
                RemoveTimer('MaleModPanelTick');
                theInput.UnregisterListener(this, 'MaleModPrevious');
                theInput.UnregisterListener(this, 'MaleModNext');
                theInput.UnregisterListener(this, 'MaleModDecrease');
                theInput.UnregisterListener(this, 'MaleModIncrease');
                theInput.UnregisterListener(this, 'MaleModReset');
                ClearPanel();
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
            gravityValue = 0.3; dampingValue = 0.95; speedValue = 0.4;
            ApplyTuning();
        }
        DrawPanel();
    }

    private function Adjust(direction : float)
    {
        if (selected == 0) { gravityValue = ClampF(gravityValue+direction*0.05,0.0,2.0); }
        if (selected == 1) { dampingValue = ClampF(dampingValue+direction*0.01,0.0,1.0); }
        if (selected == 2) { speedValue = ClampF(speedValue+direction*0.05,0.05,2.0); }
        ApplyTuning();
    }

    private function ApplyTuning()
    {
        if (!dynamicConstraint) { return; }
        dynamicConstraint.gravity = gravityValue;
        dynamicConstraint.dampening = dampingValue;
        dynamicConstraint.speed = speedValue;
    }

    timer function MaleModPanelTick(dt : float, id : int)
    {
        if (!panelOpen || GetParentEntity() != thePlayer) { StopPanel(); return; }
        DrawPanel();
    }

    private function DrawPanel()
    {
        var color : Color;
        var prefix : string;
        if (!thePlayer) { return; }
        color = Color(210,220,230,255);
        thePlayer.GetVisualDebug().AddBar('MaleModTitle',24,230,340,24,0.0,color,"MaleMod native motion test - F6 close",0.3);
        prefix = "  "; if (selected==0) { prefix = "> "; }
        thePlayer.GetVisualDebug().AddBar('MaleModGravity',24,258,340,22,gravityValue/2,color,prefix+"Gravity: "+gravityValue,0.3);
        prefix = "  "; if (selected==1) { prefix = "> "; }
        thePlayer.GetVisualDebug().AddBar('MaleModDamping',24,282,340,22,dampingValue,color,prefix+"Damping: "+dampingValue,0.3);
        prefix = "  "; if (selected==2) { prefix = "> "; }
        thePlayer.GetVisualDebug().AddBar('MaleModSpeed',24,306,340,22,speedValue/2,color,prefix+"Simulation speed: "+speedValue,0.3);
        thePlayer.GetVisualDebug().AddBar('MaleModHelp',24,334,340,24,0.0,color,"Arrows select/adjust | F8 reset",0.3);
    }

    private function ClearPanel()
    {
        if (!thePlayer) { return; }
        thePlayer.GetVisualDebug().RemoveBar('MaleModTitle');
        thePlayer.GetVisualDebug().RemoveBar('MaleModGravity');
        thePlayer.GetVisualDebug().RemoveBar('MaleModDamping');
        thePlayer.GetVisualDebug().RemoveBar('MaleModSpeed');
        thePlayer.GetVisualDebug().RemoveBar('MaleModHelp');
    }
}

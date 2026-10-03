// Scene queries and nonpersistent native material carriers. Numerical sequence,
// emission and liquid geometry remain in the pinned Base.
import function MaleModNativeClinicalControl(index : int, value : float);
import function MaleModNativeClinicalState() : Vector;
import function MaleModNativeClinicalQuery(which : int) : Vector;
import function MaleModNativeClinicalHit(token : int, hit : bool, point : Vector, normal : Vector);
import function MaleModNativeClinicalCue() : Vector;
import function MaleModNativeClinicalCarrier(origin : Vector, valid : bool);

@addField(CR4Game)
private var maleModClinicalEntity : CEntity;
@addField(CR4Game)
private var maleModClinicalPlayer : CActor;

// Empty by default. Future authored Wwise events are bound explicitly through
// this setter; no replacement dialogue or audio assets are installed.
@addField(CR4Game)
private var maleModDialoguePhase0 : string;
@addField(CR4Game)
private var maleModDialoguePhase1 : string;
@addMethod(CR4Game)
function MaleModSetDialogueSlots(phase0 : string, phase1 : string)
{
    maleModDialoguePhase0 = phase0; maleModDialoguePhase1 = phase1;
}

@addMethod(CR4Game)
function MaleModClinicalStep()
{
    var clinicalStatus, from, to, p, n, origin, zero, cue : Vector;
    var template : CEntityTemplate;
    var rot : EulerAngles;
    var i : int;
    var hit : bool;
    var radius : float;
    clinicalStatus = MaleModNativeClinicalState();
    if (maleModClinicalPlayer != thePlayer || !thePlayer || (clinicalStatus.X == 0.0 && clinicalStatus.Y == 0.0 && clinicalStatus.W == 0.0))
    {
        if (maleModClinicalEntity) { maleModClinicalEntity.Destroy(); maleModClinicalEntity = NULL; }
        MaleModNativeClinicalCarrier(zero,false);
    }
    maleModClinicalPlayer = thePlayer;
    if (!thePlayer || IsPaused()) { return; }
    for (i=0;i<2;i+=1)
    {
        cue = MaleModNativeClinicalCue();
        if (cue.X == 0.0) { break; }
        if (cue.X == 1.0 && maleModDialoguePhase0 != "") { thePlayer.SoundEvent(maleModDialoguePhase0); }
        else if (cue.X == 2.0 && maleModDialoguePhase1 != "") { thePlayer.SoundEvent(maleModDialoguePhase1); }
    }
    if (!maleModClinicalEntity && (clinicalStatus.X > 0.0 || clinicalStatus.Y > 0.0 || clinicalStatus.W > 0.0))
    {
        template = (CEntityTemplate)LoadResource("characters\malemod\clinical\carrier.w2ent",true);
        if (!template) { return; }
        origin = thePlayer.GetWorldPosition();
        maleModClinicalEntity = CreateEntity(template,origin,rot,false,false,true,PM_DontPersist);
        if (maleModClinicalEntity) { MaleModNativeClinicalCarrier(origin,true); }
        else { MaleModNativeClinicalCarrier(origin,false); }
    }
    // Bounded VM budget; deferred Base paths retain untested crossings.
    for (i=0;i<96;i+=1)
    {
        from = MaleModNativeClinicalQuery(0);
        if (from.W == 0.0) { break; }
        to = MaleModNativeClinicalQuery(1);
        radius = to.W; from.W = 1.0; to.W = 1.0;
        hit = GetWorld().SweepTest(from,to,radius,p,n);
        from = MaleModNativeClinicalQuery(2); // previously issued token only
        MaleModNativeClinicalHit((int)from.W,hit,p,n);
    }
}

// Native scene receivers and nonpersistent material carriers; source numerical
// timing, liquid and moving body anchors are owned by the pinned Base runtime.
import function MaleModNativeClinicalControl(index : int, value : float);
import function MaleModNativeClinicalState() : Vector;
import function MaleModNativeClinicalDeposits() : Vector;
import function MaleModNativeClinicalQuery(which : int) : Vector;
import function MaleModNativeClinicalHit(token : int, hit : bool, point : Vector, normal : Vector);
import function MaleModNativeClinicalCue() : Vector;
import function MaleModNativeClinicalCarrier(origin : Vector, valid : bool);

@addField(CR4Game)
private var maleModClinicalEntity : CEntity;
@addField(CR4Game)
private var maleModClinicalPlayer : CActor;

@addMethod(CR4Game)
function MaleModClinicalStep()
{
    var status, from, to, p, n, origin, zero, cue : Vector;
    var template : CEntityTemplate;
    var rot : EulerAngles;
    var i : int;
    var hit : bool;
    var radius : float;
    status = MaleModNativeClinicalState();
    if (maleModClinicalPlayer != thePlayer || !thePlayer || (status.X == 0.0 && status.Y == 0.0 && status.W == 0.0))
    {
        if (maleModClinicalEntity) { maleModClinicalEntity.Destroy(); maleModClinicalEntity = NULL; }
        MaleModNativeClinicalCarrier(zero,false);
    }
    maleModClinicalPlayer = thePlayer;
    if (!thePlayer || IsPaused()) { return; }
    // Cue playback uses the canonical local PCM transport in the native host.
    for (i=0;i<2;i+=1) { cue = MaleModNativeClinicalCue(); if (cue.X == 0.0) { break; } }
    origin = thePlayer.GetWorldPosition();
    if (!maleModClinicalEntity && (status.X > 0.0 || status.Y > 0.0 || status.W > 0.0))
    {
        template = (CEntityTemplate)LoadResource("characters\malemod\clinical\carrier.w2ent",true);
        if (template) { maleModClinicalEntity = CreateEntity(template,origin,rot,false,false,true,PM_DontPersist); }
    }
    if (maleModClinicalEntity)
    {
        maleModClinicalEntity.Teleport(origin);
        origin = maleModClinicalEntity.GetWorldPosition();
        MaleModNativeClinicalCarrier(origin,true);
    }
    else { MaleModNativeClinicalCarrier(origin,false); }
    for (i=0;i<96;i+=1)
    {
        from = MaleModNativeClinicalQuery(0);
        if (from.W == 0.0) { break; }
        to = MaleModNativeClinicalQuery(1);
        radius = to.W; from.W = 1.0; to.W = 1.0;
        hit = GetWorld().SweepTest(from,to,radius,p,n);
        from = MaleModNativeClinicalQuery(2);
        MaleModNativeClinicalHit((int)from.W,hit,p,n);
    }
}

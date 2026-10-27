import function MaleModNativeGarmentControl(style : int);
import function MaleModNativeGarmentState() : Vector;
import function MaleModNativeGarmentCarrier(origin : Vector, valid : bool);
@addField(CR4Game)
private var maleModGarmentEntity : CEntity;
@addField(CR4Game)
private var maleModGarmentPlayer : CActor;
@addMethod(CR4Game)
function MaleModGarmentStep()
{
    var garmentState, origin, zero : Vector;
    var template : CEntityTemplate;
    var rot : EulerAngles;
    garmentState = MaleModNativeGarmentState();
    // Paused/cached body passes need not refresh the visibility observer.
    // Retain this same player's valid carrier and published feed while paused.
    if (maleModGarmentPlayer != thePlayer || !thePlayer || garmentState.X == 0.0 || (!IsPaused() && !MaleModNativeSurfaceActive(maleModNativeCharacterEpoch)))
    {
        if (maleModGarmentEntity) { maleModGarmentEntity.Destroy(); maleModGarmentEntity = NULL; }
        MaleModNativeGarmentCarrier(zero,false);
    }
    maleModGarmentPlayer = thePlayer;
    if (!thePlayer || IsPaused() || garmentState.X == 0.0 || !MaleModNativeSurfaceActive(maleModNativeCharacterEpoch)) { return; }
    origin = thePlayer.GetWorldPosition();
    if (!maleModGarmentEntity)
    {
        template = (CEntityTemplate)LoadResource("characters\malemod\garments\carrier.w2ent",true);
        if (!template) { return; }
        maleModGarmentEntity = CreateEntity(template,origin,rot,false,false,true,PM_DontPersist);
    }
    if (maleModGarmentEntity)
    {
        // CEntity.Teleport is the SDK position setter. Update the scene bounds
        // before NativeFrame freezes this tick's matching garment origin.
        maleModGarmentEntity.Teleport(origin);
        origin = maleModGarmentEntity.GetWorldPosition();
        MaleModNativeGarmentCarrier(origin,true);
    }
    else { MaleModNativeGarmentCarrier(origin,false); }
}

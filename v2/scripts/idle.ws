// The actual native Geralt idle-bridge animation is the trigger. This observes
// its transition, preserving the engine's own idle eligibility, motion, 30-second
// cooldown, completion notification, and BlendOut interruption. No audio timer
// is introduced. Native control3 gates the source22-clip pool on Idle chatter
// enabled and no active teaching sequence.
@wrapMethod(CExplorationStateIdle)
function SetPlayIdleBridge(en : bool, optional behParamOnly : bool)
{
    var wasPlaying : bool;
    wasPlaying = playingIdleBridge;
    wrappedMethod(en,behParamOnly);
    if (!en || behParamOnly || wasPlaying || !playingIdleBridge) { return; }
    if (!thePlayer || thePlayer.IsCiri() || theGame.IsPaused()) { return; }
    if (m_ExplorationO.m_OwnerE != thePlayer) { return; }
    MaleModNativeClinicalControl(3,1.0);
}



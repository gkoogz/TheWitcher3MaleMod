// Stage only with the native launcher. Never add this import to the installed
// vanilla-script package until runtime registration and invocation are verified.
import function MaleModNativeReady() : bool;
import function MaleModNativeSetControl(index : int, value : float) : bool;
import function MaleModNativeGetControl(index : int) : float;
import function MaleModNativeTypedProbe(index : int, scale : float, point : Vector) : Vector;
import function MaleModNativeTypedProbeResult(success : bool);

exec function MaleModNativeProbe()
{
    LogChannel('MaleMod', "Native bridge ready: " + MaleModNativeReady());
}

function MaleModRunTypedProbe()
{
    var ready : bool;
    var point : Vector;
    var accepted : bool;
    var success : bool;
    var i : int;
    ready = MaleModNativeReady();
    point = MaleModNativeTypedProbe(-73, 1.25, Vector(1.5, -2.25, 3.75, 0.5));
    success = ready && point.X == -71.125 && point.Y == -2.8125 && point.Z == 4.6875 && point.W == 0.625;
    // Exercise the complete shared preference order, including range rejection.
    for (i = 0; i < 18; i += 1)
    {
        if (i == 0) { accepted = MaleModNativeSetControl(i, 1.0); }
        else { accepted = MaleModNativeSetControl(i, 73.25); }
        if (i == 0) { success = success && accepted && MaleModNativeGetControl(i) == 1.0; }
        else { success = success && accepted && MaleModNativeGetControl(i) == 73.25; }
        accepted = MaleModNativeSetControl(i, 101.0);
        success = success && !accepted;
        if (i == 0) { success = success && MaleModNativeGetControl(i) == 1.0; accepted = MaleModNativeSetControl(i, 2.0); }
        else { success = success && MaleModNativeGetControl(i) == 73.25; accepted = MaleModNativeSetControl(i, 50.0); }
        success = success && accepted;
    }
    accepted = MaleModNativeSetControl(-1, 50.0);
    success = success && !accepted && MaleModNativeGetControl(-1) == -1.0;
    MaleModNativeTypedProbeResult(success);
}

// Observe the actual main-menu setup lifecycle, rather than waiting for a
// profile getter that need not run while the menu is idle. No keys are assigned.
@wrapMethod(CR4CommonMainMenuBase)
function OnConfigUI()
{
    wrappedMethod();
    MaleModRunTypedProbe();
}

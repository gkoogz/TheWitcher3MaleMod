// Fixed rest scale. No menu, sliders, tuning preferences or hotkey binding.
import class IAnimDangleConstraint extends CObject {}
import class CAnimSkeletalDangleConstraint extends IAnimDangleConstraint {}
import class CAnimDangleConstraint_Dyng extends CAnimSkeletalDangleConstraint {}

struct MaleModPDBendData { var alpha, gamma, factor : float; var oldValue : Vector; }

class MaleModMotionComponent extends CSelfUpdatingComponent
{
    editable var dynamicConstraint : CAnimDangleConstraint_Dyng;
    editable var deformationGraph : CBehaviorGraph;
    private var deformationRoot : CAnimatedComponent;
    private var attached : bool;
    private var ownsLayer : bool;
    private var initialized : bool;
    private var bootStarted : bool;
    private var physicsEnabled : bool;
    private var bootTime : float;
    private var bootAttempts : int;
    private var reason : string;
    private var physicsTime : float;
    private var physicsSteps : int;
    private var physicsContacts : int;
    private var physicsResets : int;
    private var physicsMotion : float;
    private var physicsAccepted : bool;
    private var pelvisIndex : int;
    private var thighIndices : array<int>;
    private var restPoints : array<Vector>;
    private var jointRestPoints : array<Vector>;
    private var restFrames : array<Matrix>;
    private var restDirections : array<Vector>;
    private var lengths : array<float>;
    private var radii : array<Vector>;
    private var thighRadii : array<float>;
    private var physicsPosition : array<Vector>;
    private var physicsOld : array<Vector>;
    private var physicsVelocity : array<Vector>;
    private var physicsInvMass : array<float>;
    private var targets : array<Vector>;
    private var oldTargets : array<Vector>;
    private var capsules : array<Vector>;
    private var oldCapsules : array<Vector>;
    private var bendLambda : array<Vector>;
    private var materialLambda : array<Vector>;
    private var lengthLambda : array<float>;
    private var bends : array<MaleModPDBendData>;
    private var bendCompliance : array<float>;
    private var attachmentRestTangent : Vector;
    private var anchorOffsets, materialOffsets, previousAnchors, previousMaterial : array<Vector>;
    private var lobeRotations : array<Vector>;
    private var tetherRest, tetherLimit, suspensionLambda, shearLambdaX, shearLambdaY : array<float>;
    private var worldToPelvis : Matrix;
    private var pelvis : Matrix;
    private var previousRoot : Vector;
    private var previousPelvis : Matrix;
    private var frameSamples : int;
    private var previousFrameVelocity, previousAngularVelocity : Vector;
    private var linearAcceleration, angularVelocity, angularAcceleration : Vector;
    private var localGravity : Vector;

    event OnComponentAttached() { bootTime = 0.0; StartTicking(); }
    event OnComponentAttachFinished() { StartTicking(); }
    event OnComponentDetached() { Cleanup(); GotoState(); }
    event OnDestroyed() { Cleanup(); GotoState(); }

    private function Cleanup()
    {
        var i : int;
        StopTicking();
        if (ownsLayer && deformationRoot)
        {
            deformationRoot.DetachBehavior('MaleModAnatomyLayer');
            for (i = deformationRoot.runtimeBehaviorInstanceSlots.Size()-1; i >= 0; i -= 1)
            {
                if (deformationRoot.runtimeBehaviorInstanceSlots[i].instanceName == 'MaleModAnatomyLayer')
                { deformationRoot.runtimeBehaviorInstanceSlots.Erase(i); }
            }
        }
        attached = false; ownsLayer = false; initialized = false; bootStarted = false;
    }

    private latent function Boot() : bool
    {
        var slot : SBehaviorGraphInstanceSlot;
        var i : int;
        var item : CItemEntity;
        item = (CItemEntity)GetEntity();
        if (!thePlayer || !(GetEntity() == thePlayer || (item && item.GetParentEntity() == thePlayer)))
        { reason = "waiting for mounted player appearance"; return false; }
        deformationRoot = thePlayer.GetRootAnimatedComponent();
        if (!deformationRoot || !deformationRoot.skeleton) { reason = "waiting for player root"; return false; }
        if (!deformationGraph) { reason = "controller graph handle missing"; return false; }
        if (deformationRoot.skeleton.bones.Size() != 104) { reason = "unexpected player rig"; return false; }
        // OBSERVED_RIG_CHECKS
        for (i = 0; i < deformationRoot.runtimeBehaviorInstanceSlots.Size(); i += 1)
        {
            if (deformationRoot.runtimeBehaviorInstanceSlots[i].instanceName == 'MaleModAnatomyLayer')
            { reason = "pose slot already present"; return false; }
        }
        slot.instanceName = 'MaleModAnatomyLayer'; slot.graph = deformationGraph; slot.alwaysOnTopOfStack = true;
        deformationRoot.runtimeBehaviorInstanceSlots.PushBack(slot); ownsLayer = true;
        attached = deformationRoot.AttachBehavior('MaleModAnatomyLayer');
        if (!attached) { reason = "AttachBehavior rejected slot"; Cleanup(); return false; }
        pelvisIndex = thePlayer.GetBoneIndex('pelvis');
        if (pelvisIndex != 9) { reason = "pelvis mapping mismatch"; Cleanup(); return false; }
        // INITIALIZE_CONSTANTS
        reason = "fixed rest attached";
        return true;
    }

    public latent function BootController()
    {
        var attempt : int;
        var success : bool;
        for (attempt = 0; attempt < 10; attempt += 1)
        {
            Sleep(0.5); bootAttempts += 1;
            success = Boot();
            if (success) { if (!physicsEnabled) { StopTicking(); } return; }
        }
        StopTicking();
    }

    event OnComponentTick(dt : float)
    {
        if (!attached)
        {
            if (!bootStarted) { bootStarted = true; GotoState('MaleModPhysicsStartup'); }
            return true;
        }
        if (!thePlayer || !deformationRoot || dt <= 0.0) { return true; }
        AdvancePhysics(dt);
        return true;
    }

    private function Point(matrix : Matrix, point : Vector) : Vector
    {
        point.W = 1.0; point = VecTransform(matrix, point); point.W = 0.0; return point;
    }

    private function UpdateTargets()
    {
        var i : int;
        pelvis = thePlayer.GetBoneWorldMatrixByIndex(pelvisIndex);
        worldToPelvis = MatrixGetInverted(pelvis);
        targets = restPoints;
        localGravity = VecTransformDir(worldToPelvis,Vector(0.0,0.0,-1.0,0.0));
        for (i = 0; i < 4; i += 1)
        { capsules[i] = Point(worldToPelvis,thePlayer.GetBoneWorldPositionByIndex(thighIndices[i])); }
    }

    private function UpdateFrameMotion(dt : float)
    {
        var velocity, omega, zero : Vector;
        zero = Vector(0.0,0.0,0.0,0.0);
        velocity = (Point(pelvis,zero)-Point(previousPelvis,zero))/dt;
        omega = (VecCross(previousPelvis.X,pelvis.X)+VecCross(previousPelvis.Y,pelvis.Y)+VecCross(previousPelvis.Z,pelvis.Z))*(0.5/dt);
        if (frameSamples > 0)
        {
            linearAcceleration = FilterMotion(linearAcceleration,(velocity-previousFrameVelocity)/dt,20.0,@linear_acceleration_limit@,dt);
            angularAcceleration = FilterMotion(angularAcceleration,(omega-previousAngularVelocity)/dt,20.0,40.0,dt);
        }
        angularVelocity = FilterMotion(angularVelocity,omega,20.0,10.0,dt);
        previousFrameVelocity = velocity; previousAngularVelocity = omega;
        previousPelvis = pelvis; frameSamples += 1;
    }

    private function ResetPhysics()
    {
        var i : int;
        physicsTime = 0.0;
        for (i = 0; i < 14; i += 1)
        { physicsPosition[i] = targets[i]; physicsOld[i] = targets[i]; physicsVelocity[i] = Vector(0.0,0.0,0.0,0.0); }
        oldTargets = targets; oldCapsules = capsules;
        for (i = 0; i < 2; i += 1)
        { lobeRotations[i] = Vector(0.0,0.0,0.0,1.0); previousAnchors[i] = AttachmentTarget(i,false); previousMaterial[i] = AttachmentTarget(i,true); }
        previousRoot = Point(pelvis,targets[0]); previousPelvis = pelvis; frameSamples = 0;
        previousFrameVelocity = Vector(0.0,0.0,0.0,0.0); previousAngularVelocity = previousFrameVelocity;
        linearAcceleration = previousFrameVelocity; angularVelocity = previousFrameVelocity; angularAcceleration = previousFrameVelocity;
        initialized = true; physicsResets += 1;
    }

    private function AdvancePhysics(dt : float)
    {
        var steps, j, i : int;
        var frameTargets, frameCapsules, startTargets, startCapsules : array<Vector>;
        var fraction : float;
        UpdateTargets();
        if (!initialized || dt > 0.15 || VecDistance(previousRoot, Point(pelvis,targets[0])) > 1.0) { ResetPhysics(); }
        else { UpdateFrameMotion(dt); }
        previousRoot = Point(pelvis,targets[0]); physicsTime += MinF(dt,0.05);
        steps = Min(FloorF((physicsTime+0.0000001) / 0.0166666667),3);
        frameTargets = targets; frameCapsules = capsules;
        startTargets = oldTargets; startCapsules = oldCapsules;
        for (j = 0; j < steps; j += 1)
        {
            fraction = (j+1.0)/steps;
            for (i = 0; i < 14; i += 1) { targets[i] = startTargets[i]+(frameTargets[i]-startTargets[i])*fraction; }
            for (i = 0; i < 4; i += 1) { capsules[i] = startCapsules[i]+(frameCapsules[i]-startCapsules[i])*fraction; }
            PhysicsStep(0.0166666667); physicsSteps += 1;
            oldTargets = targets; oldCapsules = capsules;
        }
        targets = frameTargets; capsules = frameCapsules;
        physicsTime = MaxF(0.0,physicsTime-steps*0.0166666667);
        PublishPose();
    }

    // PHYSICS_METHODS

    private function PublishPose()
    {
        var i : int;
        var localPoint, delta, direction, rotation, position : Vector;
        var angles : Vector;
        physicsAccepted = true;
        for (i = 0; i < 10; i += 1)
        {
            if (i < 8)
            {
                SampleGuide(12,i/7.0,position,direction);
                direction = VecNormalize(direction);
                rotation = q_SetShortestRotation(restDirections[i],direction);
            }
            else { position = physicsPosition[i+4]; rotation = lobeRotations[i-8]; }
            localPoint = position;
            delta = VecTransformDir(MatrixGetInverted(restFrames[i]),localPoint-jointRestPoints[i]);
            angles = QuaternionAngles(rotation);
            PublishJoint(i,delta,angles);
            physicsMotion = MaxF(physicsMotion,VecDistance(localPoint,jointRestPoints[i]));
        }
        if (!physicsAccepted) { reason = "physics pose variables rejected"; StopTicking(); }
    }

    private function QuaternionAngles(q : Vector) : Vector
    {
        var result : Vector;
        result.X = Rad2Deg(AtanF(2.0*(q.W*q.X+q.Y*q.Z),1.0-2.0*(q.X*q.X+q.Y*q.Y)));
        result.Y = Rad2Deg(AsinF(ClampF(2.0*(q.W*q.Y-q.Z*q.X),-1.0,1.0)));
        result.Z = Rad2Deg(AtanF(2.0*(q.W*q.Z+q.X*q.Y),1.0-2.0*(q.Y*q.Y+q.Z*q.Z)));
        return result;
    }

    private function PublishJoint(i : int, delta : Vector, angles : Vector)
    {
        // PUBLISH_JOINTS
    }

    public function Status() : string
    {
        return reason + " | fixed scale: 1 | steps: " + physicsSteps + " | contacts: " + physicsContacts
            + " | motion: " + physicsMotion + " | resets: " + physicsResets + " | pose accepted: " + physicsAccepted;
    }
}

state MaleModPhysicsStartup in MaleModMotionComponent
{
    event OnEnterState(previous : name) { StartGraph(); }
    entry function StartGraph() { parent.BootController(); }
}

exec function MaleModPhysicsStatus()
{
    var controller : MaleModMotionComponent;
    if (!thePlayer) { return; }
    controller = (MaleModMotionComponent)thePlayer.GetComponent("MaleModController");
    if (controller) { theGame.GetGuiManager().ShowUserDialogAdv(90260931,"MaleMod physics",controller.Status(),false,UDB_Ok); }
}

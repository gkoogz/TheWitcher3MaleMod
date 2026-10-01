"""Bounded native pose measurements for the attachment-follow investigation."""
import math


def add_pose_measurement(script, rest_position):
    if len(rest_position) != 3 or not all(math.isfinite(x) for x in rest_position):
        raise ValueError('Expected measured authored root position relative to pelvis')
    expected = ', '.join(format(float(x), '.9f') for x in rest_position)
    marker = '    private var ownsPoseLayer : bool;'
    if script.count(marker) != 1:
        raise ValueError('Player layer declaration changed')
    script = script.replace(marker, marker + '''
    private var poseSamples : int;
    private var posePelvisTravel : float;
    private var poseRootTravel : float;
    private var poseMaxError : float;
    private var poseFirstError : float;
    private var poseParentCount : int;
    private var poseRootIndex : int;
    private var posePelvisIndex : int;
''', 1)
    marker = "        bridgeBooted = deformationRoot.AttachBehavior('MaleModAnatomyLayer');\n        ApplyTuning();"
    if script.count(marker) != 1:
        raise ValueError('Player layer activation changed')
    script = script.replace(marker, marker + '\n        CaptureAttachmentPose();', 1)
    marker = '    private function RemovePoseLayer()'
    code = '''    // Read-only, 60 samples after attachment, then no further polling.
    public latent function CaptureAttachmentPose()
    {
        var i : int;
        var pelvisMatrix : Matrix;
        var actorInverse : Matrix;
        var pelvisPoint : Vector;
        var rootPoint : Vector;
        var localPoint : Vector;
        var firstPelvis : Vector;
        var firstRoot : Vector;
        var error : float;
        poseSamples = 0;
        posePelvisTravel = 0.0;
        poseRootTravel = 0.0;
        poseMaxError = 0.0;
        poseFirstError = 0.0;
        poseParentCount = -1;
        Sleep(2.0);
        if (!listening || !bridgeBooted || !deformationRoot || !thePlayer) { return; }
        posePelvisIndex = thePlayer.GetBoneIndex('pelvis');
        poseRootIndex = thePlayer.GetBoneIndex('mm_shaft_00');
        if (posePelvisIndex != 9 || poseRootIndex != 94) { return; }
        if (deformationRoot.skeleton.parentIndices.Size() != 104) { return; }
        poseParentCount = deformationRoot.skeleton.parentIndices.Size();
        for (i = 0; i < 60; i += 1)
        {
            Sleep(0.1);
            if (!listening || !bridgeBooted || !thePlayer) { return; }
            pelvisMatrix = thePlayer.GetBoneWorldMatrixByIndex(posePelvisIndex);
            rootPoint = thePlayer.GetBoneWorldPositionByIndex(poseRootIndex);
            rootPoint.W = 1.0;
            localPoint = VecTransform(MatrixGetInverted(pelvisMatrix), rootPoint);
            error = VecDistance(localPoint, Vector(EXPECTED, 1.0));
            actorInverse = MatrixGetInverted(thePlayer.GetLocalToWorld());
            rootPoint = VecTransform(actorInverse, rootPoint);
            pelvisPoint = MatrixGetTranslation(pelvisMatrix);
            pelvisPoint.W = 1.0;
            pelvisPoint = VecTransform(actorInverse, pelvisPoint);
            if (poseSamples == 0)
            {
                firstPelvis = pelvisPoint;
                firstRoot = rootPoint;
                poseFirstError = error;
            }
            posePelvisTravel = MaxF(posePelvisTravel, VecDistance(firstPelvis, pelvisPoint));
            poseRootTravel = MaxF(poseRootTravel, VecDistance(firstRoot, rootPoint));
            poseMaxError = MaxF(poseMaxError, error);
            poseSamples += 1;
        }
    }

    public function PoseMotionDetail() : string
    {
        return "Samples: " + poseSamples + " | pelvis motion: " + posePelvisTravel
            + " | added root motion: " + poseRootTravel;
    }

    public function PoseErrorDetail() : string
    {
        return "Parent-follow error | first: " + poseFirstError + " | max: " + poseMaxError;
    }

    public function PoseBindingDetail() : string
    {
        return "Player bone indices | pelvis: " + posePelvisIndex + " | root: " + poseRootIndex
            + " | parent entries: " + poseParentCount;
    }

'''.replace('EXPECTED', expected)
    script = script.replace(marker, code + marker, 1)
    marker = '    group = m_flashValueStorage.CreateTempFlashObject();'
    if script.count(marker) != 1:
        raise ValueError('Player menu insertion changed')
    script = script.replace(marker, '''    controls.PushBackFlashObject(MaleModDiagnosticRow(m_flashValueStorage,'MaleModPoseMotion',controller.PoseMotionDetail()));
    controls.PushBackFlashObject(MaleModDiagnosticRow(m_flashValueStorage,'MaleModPoseError',controller.PoseErrorDetail()));
    controls.PushBackFlashObject(MaleModDiagnosticRow(m_flashValueStorage,'MaleModPoseBinding',controller.PoseBindingDetail()));
''' + marker, 1)
    return script

    private function PhysicsStep(dt : float)
    {
        var i, iteration, lobe : int;
        var gravity, drag, t, lambda, stretch : float;
        var zero, cord, axisX, axisY, current, desired, anchor, material, linear, omega, alpha : Vector;
        zero = Vector(0.0,0.0,0.0,0.0);
        linear = VecTransformDir(worldToPelvis,linearAcceleration);
        omega = VecTransformDir(worldToPelvis,angularVelocity);
        alpha = VecTransformDir(worldToPelvis,angularAcceleration);
        for (i = 0; i < 21; i += 1)
        {
            physicsOld[i] = physicsPosition[i];
            if (i < 2) { physicsPosition[i] = targets[i]; }
            else
            {
                if (i < 12 || i >= 14) { gravity = @shaft_gravity@; drag = @shaft_drag@; }
                else { gravity = @lobe_gravity@; drag = @lobe_drag@; }
                IntegrateRelative(i,localGravity*gravity,linear,omega,alpha,@total_acceleration_limit@,drag,dt);
            }
        }
        for (i = 0; i < 11; i += 1) { lengthLambda[i] = 0.0; }
        for (i = 0; i < 10; i += 1)
        {
            bends[i] = PrepareBend(i+1,bendCompliance[i],dt,0.5);
            bendLambda[i] = zero;
        }
        for (i = 0; i < 2; i += 1)
        { suspensionLambda[i] = 0.0; shearLambdaX[i] = 0.0; shearLambdaY[i] = 0.0; }
        for (iteration = 0; iteration < 24; iteration += 1)
        {
            for (i = 1; i < 11; i += 1)
            { lambda = lengthLambda[i]; SolveDistance(i,i+1,lengths[i],0.0000001,lambda,dt); lengthLambda[i] = lambda; }
            for (i = 0; i < 8; i += 1)
            {
                current = bendLambda[i]; SolveBendPrepared(i+1,bends[i],current); bendLambda[i] = current;
            }
            for (lobe = 0; lobe < 2; lobe += 1)
            {
                i = lobe+12; anchor = AttachmentTarget(lobe,false); material = AttachmentTarget(lobe,true);
                cord = VecNormalize(material-anchor);
                axisX = VecNormalize(VecCross(cord,Vector(0.0,1.0,0.0,0.0)));
                axisY = VecNormalize(VecCross(cord,axisX));
                lambda = shearLambdaX[lobe]; SolveMaterialAxis(i,material,previousMaterial[lobe],axisX,@suspension_shear_compliance@,dt,lambda); shearLambdaX[lobe] = lambda;
                lambda = shearLambdaY[lobe]; SolveMaterialAxis(i,material,previousMaterial[lobe],axisY,@suspension_shear_compliance@,dt,lambda); shearLambdaY[lobe] = lambda;
                lambda = suspensionLambda[lobe]; SolveSuspension(i,anchor,previousAnchors[lobe],tetherRest[lobe],@suspension_compliance@,@suspension_damping_ratio@,dt,lambda); suspensionLambda[lobe] = lambda;
                SolveReach(i,anchor,tetherLimit[lobe]);
            }
            // Broad phase prevents support queries for separated resources.
            ResolveContacts();
            // The distal body carries actual off-axis material supports. Fit
            // four times per step; project its solid shape every iteration.
            if (iteration == 0 || iteration == 8 || iteration == 16 || iteration == 23)
            { headRotation = FitCluster(restPoints,headRestCenter,8,4,14,7,headRotation); }
            ProjectCluster(restPoints,headRestCenter,8,4,14,7,headRotation);
        }
        for (i = 2; i < 21; i += 1)
        {
            physicsVelocity[i] = (physicsPosition[i]-physicsOld[i])/dt;
            stretch = VecDistance(physicsPosition[i],targets[i]);
            if (!(stretch >= 0.0) || stretch > 1.0) { ResetPhysics(); return; }
        }
        for (lobe = 0; lobe < 2; lobe += 1)
        {
            cord = materialOffsets[lobe]-anchorOffsets[lobe];
            current = physicsPosition[lobe+12]-AttachmentTarget(lobe,false);
            desired = q_SetShortestRotation(VecNormalize(cord),VecNormalize(current));
            lobeRotations[lobe] = q_SetSlerp(lobeRotations[lobe],desired,1.0-ExpF(-@lobe_torsion@*dt));
            previousAnchors[lobe] = AttachmentTarget(lobe,false); previousMaterial[lobe] = AttachmentTarget(lobe,true);
        }
    }

    private function AttachmentTarget(lobe : int, material : bool) : Vector
    {
        var center, tangent, offset, rotation : Vector;
        SampleGuide(12,0.12,center,tangent);
        tangent = VecNormalize(tangent);
        rotation = q_SetShortestRotation(attachmentRestTangent,tangent);
        if (material) { offset = materialOffsets[lobe]; } else { offset = anchorOffsets[lobe]; }
        return center+v_SetRotatedDir(rotation,offset);
    }

    private function SegmentPart(p, a, b : Vector) : float
    {
        var ab : Vector;
        var d : float;
        ab = b-a; d = VecDot(ab,ab);
        if (d < 0.00000001) { return 0.0; }
        return ClampF(VecDot(p-a,ab)/d,0.0,1.0);
    }

    private function LobeSupport(i : int, n : Vector) : Vector
    {
        var localPoint : Vector;
        localPoint = n;
        localPoint = v_SetRotatedDir(q_SetInv(lobeRotations[i-12]),localPoint);
        localPoint = VecTransformDir(MatrixGetInverted(restFrames[i-4]),localPoint);
        localPoint = OvoidSupport(localPoint,radii[i]);
        localPoint = VecTransformDir(restFrames[i-4],localPoint);
        localPoint = v_SetRotatedDir(lobeRotations[i-12],localPoint);
        return localPoint;
    }

    private function ResolveContacts()
    {
        var i, side, a, j : int;
        var t, distance, gap, radius : float;
        var closest, delta, normal, support, surfaceMove : Vector;
        for (i = 2; i < 21; i += 1)
        {
            radius = MaxF(radii[i].X,MaxF(radii[i].Y,radii[i].Z))*1.15;
            for (side = 0; side < 2; side += 1)
            {
                a = side*2;
                t = SegmentPart(physicsPosition[i],capsules[a],capsules[a+1]);
                closest = capsules[a]+(capsules[a+1]-capsules[a])*t;
                delta = physicsPosition[i]-closest; distance = VecLength(delta);
                if (distance > radius+thighRadii[side] || distance < 0.000001) { continue; }
                normal = delta/distance;
                if (i < 12 || i >= 14) { gap = distance-radii[i].X-thighRadii[side]; }
                else
                {
                    support = LobeSupport(i,-normal);
                    gap = VecDot(delta+support,normal)-thighRadii[side];
                }
                if (gap < 0.0)
                {
                    surfaceMove = closest-(oldCapsules[a]+(oldCapsules[a+1]-oldCapsules[a])*t);
                    ProjectMovingContact(i,normal,gap,surfaceMove); physicsContacts += 1;
                }
            }
        }
        // Off-axis distal supports supply contact torque in all three axes.
        for (j = 14; j < 21; j += 1)
        {
            for (i = 12; i < 14; i += 1)
            {
                delta = physicsPosition[i]-physicsPosition[j]; distance = VecLength(delta);
                radius = MaxF(radii[i].X,MaxF(radii[i].Y,radii[i].Z))*1.15;
                if (distance < 0.000001 || distance > radius+radii[j].X) { continue; }
                normal = delta/distance;
                gap = VecDot(delta+LobeSupport(i,-normal),normal)-radii[j].X;
                if (gap < 0.0) { ProjectPairContact(j,i,normal,gap); physicsContacts += 1; }
            }
        }
        delta = physicsPosition[13]-physicsPosition[12]; distance = VecLength(delta);
        if (distance > 0.000001)
        {
            normal = delta/distance;
            gap = VecDot(delta+LobeSupport(13,-normal)-LobeSupport(12,normal),normal)-@padding@;
            if (gap < 0.0) { ProjectPairContact(12,13,normal,gap); physicsContacts += 1; }
        }
        for (i = 12; i < 14; i += 1)
        {
            radius = MaxF(radii[i].X,MaxF(radii[i].Y,radii[i].Z))*1.15;
            for (j = 1; j < 11; j += 1)
            {
                t = SegmentPart(physicsPosition[i],physicsPosition[j],physicsPosition[j+1]);
                closest = physicsPosition[j]+(physicsPosition[j+1]-physicsPosition[j])*t;
                delta = physicsPosition[i]-closest; distance = VecLength(delta);
                if (distance < 0.000001 || distance > radius+MaxF(radii[j].X,radii[j+1].X)*1.25) { continue; }
                normal = delta/distance;
                gap = VecDot(delta+LobeSupport(i,-normal),normal)-(radii[j].X*(1.0-t)+radii[j+1].X*t)*1.25;
                if (gap < 0.0) { ProjectRodContact(j,j+1,i,t,normal,gap); physicsContacts += 1; }
            }
        }
    }

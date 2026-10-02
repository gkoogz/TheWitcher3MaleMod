    private function InitializeOverall()
    {
        var cfg : CInGameConfigWrapper;
        // BANK_INITIALIZERS
        overallValue = 50.0;
        cfg = theGame.GetInGameConfigWrapper();
        if (cfg.GetRawConfigValueByStr("MaleModOverall", "Version") == "1")
        { overallValue = ClampF(RoundF(StringToFloat(cfg.GetRawConfigValueByStr("MaleModOverall", "Overall"))),1.0,100.0); }
        ApplyOverall();
    }

    public function OverallReady() : bool
    { return attached && overallMeshes.Size() == 10 && overallMeshes[5]; }
    public function GetOverall() : float { return overallValue; }
    public function SetOverall(value : float)
    {
        var cfg : CInGameConfigWrapper;
        value = ClampF(RoundF(value),1.0,100.0);
        if (!OverallReady() || value == overallValue) { return; }
        overallValue = value;
        ApplyOverall();
        cfg = theGame.GetInGameConfigWrapper();
        cfg.SetRawConfigValueByStr("MaleModOverall", "Version", "1");
        cfg.SetRawConfigValueByStr("MaleModOverall", "Overall", FloatToString(overallValue));
    }
    private function ApplyOverall()
    {
        var i, slot : int;
        var fraction : float;
        slot = 0;
        for (i = 1; i < overallKeys.Size()-1; i += 1)
        { if (overallValue >= overallKeys[i]) { slot = i; } }
        fraction = ClampF((overallValue-overallKeys[slot])/(overallKeys[slot+1]-overallKeys[slot]),0.0,1.0);
        // INTERPOLATE
        for (i = 0; i < overallMeshes.Size(); i += 1)
        { if (overallMeshes[i]) { overallMeshes[i].SetVisible(false); } }
        if (overallMeshes[slot])
        {
            overallMeshes[slot].morphRatio = fraction;
            overallMeshes[slot].SetVisible(true);
        }
        UpdateTargets(); ResetPhysics(); PublishPose();
    }

"""Measure direct control presentation in the owned native grey room.

Accept only explicit local inputs. Keep one current report/capture set under
the configured Work tree; this tool never installs the candidate.
"""
from pathlib import Path
import argparse
import json
import statistics
import time
from mod import ROOT, read_json, write_json, digest
from native_preview import prepare
from run_iteration_world import launch, finish


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dll", type=Path, required=True)
    p.add_argument("--worker", type=Path)
    p.add_argument("--artifacts", type=Path, required=True)
    p.add_argument("--materials", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--package", type=Path)
    p.add_argument("--preview", type=Path, help="Reuse an already prepared, verified preview")
    p.add_argument("--resume", type=Path, help="Resume monitoring an exact unfinished campaign receipt")
    p.add_argument("--case", default="modular-cadence", choices=("modular-cadence", "modular-review", "shape-review", "campaign"))
    p.add_argument("--last-stage", type=int, default=1239)
    a = p.parse_args()
    a.output = a.output.resolve()
    work = (ROOT / "build").resolve().parent
    if not a.output.is_relative_to(work):
        raise ValueError("Evidence must stay in the consolidated Witcher Work directory")
    a.output.mkdir(parents=True, exist_ok=True)
    if (a.output / "native-session.json").exists():
        raise ValueError("Existing session must be reviewed and closed before replacement")
    n = a.artifacts.resolve()
    preview = a.preview or prepare(
        dll=a.dll, worker=a.worker, modular_geometry=n / "geralt.modular",
        modular_native=n / "geralt.modular-native",
        modular_dynamic=n / "geralt.modular-dynamic",
        modular_materials=n / "geralt.modular-materials",
        modular_transfer=n / "geralt.modular-transfer",
        material_package=a.materials,
    )
    case = ROOT / "build/collar-sessions" / a.case
    package = a.package or Path(read_json(ROOT / "local/grey-room-launch.json")["package"])
    if a.resume and a.case != "campaign":
        raise ValueError("Only an existing campaign monitor can be resumed")
    if a.case == "campaign":
        from run_sealed_session import run
        from iteration_save_transaction import begin
        if a.resume:
            receipt = a.resume.resolve()
            if not receipt.is_relative_to((ROOT/"build/probe").resolve()):
                raise ValueError("Campaign receipt leaves owned sessions")
            session = read_json(receipt)
            transaction = a.output/"save-transaction/receipt.json"
            if (session.get("closed") or session["moduleSHA256"] != digest(a.dll)
                    or session["nativePreviewSHA256"] != digest(preview)
                    or Path(session["driver"]).resolve() != (case/"workspace/scripts/local/malemod/collar_integrity.ws").resolve()
                    or session["driverCompileProofSHA256"] != digest(case/"compile.json")
                    or read_json(transaction).get("finishedUnixSeconds")):
                raise ValueError("Campaign identity or original save transaction differs")
        else:
            transaction = begin(Path.home()/"Documents/The Witcher 3/gamesaves",
                                a.output/"save-transaction")
            session = run(native_preview=preview,
                          launcher_path=ROOT/"build/iteration-launch/launch_sealed.exe",
                          game_arguments=("-windowed",),
                          driver_source=case/"workspace/scripts/local/malemod/collar_integrity.ws",
                          compile_proof=case/"compile.json")
            matches = [p for p in (ROOT/"build/probe").glob("sealed-session-*/receipt.json")
                       if read_json(p)["observations"] == session["observations"]]
            if len(matches) != 1:
                raise RuntimeError("Exact campaign receipt is ambiguous")
            receipt = matches[0]
        session["campaignSaveTransaction"] = str(transaction)
        write_json(receipt,session)
    else:
        receipt = launch(
            package, native_preview=preview,
            driver_source=case / "workspace/scripts/local/malemod/collar_integrity.ws",
            compile_proof=case / "compile.json",
        )
    session = read_json(receipt)
    write_json(a.output / "native-session.json", dict(
        receipt=str(receipt), preview=str(preview), dllSHA256=digest(a.dll),
        installed=False,
    ))
    trace = Path(session["modulePath"]).parent / (
        f'verification-{session["observations"]["processID"]}.jsonl')
    deadline = time.monotonic() + (900 if a.case in ("modular-review","campaign") else 600)
    rows = []
    shots = []
    try:
        while time.monotonic() < deadline:
            if trace.exists():
                # A writer can be partway through its last line.
                rows = [json.loads(line) for line in
                        trace.read_text().splitlines() if line.endswith("}")]
            stages = {r["stage"] for r in rows}
            if a.last_stage in stages:
                # The script requests its last screenshot after recording the
                # checkpoint. Do not close the game before the PNG completes.
                expected_shots = {"modular-cadence": 7, "modular-review": 97, "shape-review": 19, "campaign": 39}[a.case]
                capture_deadline = time.monotonic() + 30
                while time.monotonic() < capture_deadline:
                    shots = sorted((p for p in (Path.home() / "Documents/The Witcher 3/screenshots").glob("*.png")
                                    if p.stat().st_mtime >= session["launchedUnixSeconds"]),
                                   key=lambda p: p.stat().st_mtime)
                    complete = len(shots) == expected_shots
                    for shot in shots:
                        with shot.open("rb") as stream:
                            if shot.stat().st_size < 12:
                                complete = False
                                break
                            stream.seek(-12, 2)
                            complete &= stream.read() == b"\0\0\0\0IEND\xaeB`\x82"
                    if complete:
                        break
                    time.sleep(.25)
                else:
                    raise RuntimeError("Final native screenshot did not finish")
                break
            lifecycle = [json.loads(line) for line in
                         (receipt.parent / "launcher.txt").read_text().splitlines()
                         if line.endswith("}")]
            exited = [item["exitCode"] for item in lifecycle if "exitCode" in item]
            if exited:
                raise RuntimeError(f"Native review exited before completion: {exited[-1]}")
            time.sleep(1)
        else:
            raise RuntimeError("Native cadence review did not finish")
    finally:
        (a.output / "native-trace.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in rows))
        if a.case == "campaign":
            from close_sealed_session import close
            from iteration_save_transaction import restore
            closed = close(receipt)
            saved = restore(transaction, closed_private_session=closed.get("closed",False))
            closed["campaignSaveOriginalsVerified"] = saved["originalsVerified"]
            write_json(receipt,closed)
        else:
            finish(receipt)
    if a.case != "modular-cadence":
        write_json(a.output / "native-review.json", dict(
            installed=False, receipt=str(receipt), stages=sorted({r["stage"] for r in rows}),
            screenshots=len(shots), visualReview=False, attachmentGatePassed=False))
        return
    report = dict(installed=False, receipt=str(receipt), phases={})
    for name, lo, hi in [("pulse", 1110, 1200), ("width", 1200, 1220),
                         ("angle", 1220, 1240)]:
        samples = [r for r in rows if lo <= r["stage"] < hi]
        seconds = samples[-1]["poseSeconds"] - samples[0]["poseSeconds"]
        report["phases"][name] = dict(
            samples=len(samples), seconds=seconds,
            meanAcknowledgedInterval=seconds / (len(samples) - 1),
            directControlSamples=sum(r.get("liveControlDeformed", False) for r in samples),
            medianDirectControlMs=statistics.median(r.get("liveControlMs", 0) for r in samples),
            distinctMeshes=len({r["modularUploadFNV64"] for r in samples}),
        )
    write_json(a.output / "native-cadence.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

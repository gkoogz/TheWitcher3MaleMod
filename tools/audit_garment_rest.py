"""Adapter entry point for the shared SDK-free garment geometry audit."""
from pathlib import Path
import sys
base = Path(__file__).resolve().parents[2] / "MaleMod"
if not (base / "malemod_base/garment_geometry_audit.py").is_file():
    raise RuntimeError("Shared Base geometry auditor is unavailable; use the pinned Base checkout.")
sys.path.insert(0, str(base))
from malemod_base.garment_geometry_audit import main
if __name__ == "__main__":
    main()

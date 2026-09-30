#!/usr/bin/env python3
"""Export the Wolverine anatomy rest cage as an unrigged OBJ reference.

This reads source headers only. It does not read game packages or produce a
Witcher 3 mod. Keep the original vertex order for later deformation mapping.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


ARRAY = re.compile(
    r"static const (?:float|uint16_t)\s+(?P<name>\w+)\[(?P<count>\d+|LIVE_COUNT\*3)\]\s*=\s*\{(?P<body>.*?)\};",
    re.DOTALL,
)
NUMBER = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?")


def read_array(path: Path, name: str, expected_count: int, integer: bool = False) -> list[float] | list[int]:
    source = path.read_text(encoding="utf-8")
    match = next((m for m in ARRAY.finditer(source) if m.group("name") == name), None)
    if match is None:
        raise ValueError(f"{name} was not found in {path}")
    values = [int(x) if integer else float(x) for x in NUMBER.findall(match.group("body"))]
    if len(values) != expected_count:
        raise ValueError(f"{name}: expected {expected_count} values, found {len(values)}")
    return values


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export(source: Path, output: Path) -> dict:
    runtime = source / "src" / "runtime"
    positions_file = runtime / "morph_targets.h"
    topology_file = runtime / "graft_normals.h"
    positions = read_array(positions_file, "morph_base", 2388 * 3)
    uvs = read_array(topology_file, "graftUVs", 2388 * 2)
    indices = read_array(topology_file, "graftTriangleIndices", 13788, integer=True)
    if any(not 0 <= i < 2388 for i in indices):
        raise ValueError("Triangle index outside the vertex range")

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as obj:
        obj.write("# Wolverine 2.0 beta rest cage; reference geometry only\n")
        obj.write("# Original model coordinates and vertex order are preserved\n")
        obj.write("o WolverineAnatomyRestCage\n")
        for i in range(0, len(positions), 3):
            obj.write(f"v {positions[i]:.9g} {positions[i+1]:.9g} {positions[i+2]:.9g}\n")
        for i in range(0, len(uvs), 2):
            obj.write(f"vt {uvs[i]:.9g} {uvs[i+1]:.9g}\n")
        for i in range(0, len(indices), 3):
            a, b, c = (indices[i + k] + 1 for k in range(3))
            obj.write(f"f {a}/{a} {b}/{b} {c}/{c}\n")

    report = {
        "purpose": "Unrigged source reference for manual retopology and REDkit fitting",
        "vertex_count": 2388,
        "triangle_count": len(indices) // 3,
        "uv_count": 2388,
        "coordinates": "Original Wolverine model space; units and axes not converted",
        "source_sha256": {
            "morph_targets.h": sha256(positions_file),
            "graft_normals.h": sha256(topology_file),
        },
        "obj_sha256": sha256(output),
    }
    report_path = output.with_suffix(".json")
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Wolverine source checkout")
    parser.add_argument("--output", type=Path, required=True, help="Output OBJ path")
    args = parser.parse_args()
    print(json.dumps(export(args.source, args.output), indent=2))


if __name__ == "__main__":
    main()

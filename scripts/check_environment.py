from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis_scene.runtime import RuntimeConfig, configure_runtime, runtime_report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Genesis and RayTracer prerequisites.")
    parser.add_argument("--strict-raytracer", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    configured = configure_runtime(RuntimeConfig(project_root=ROOT, backend="gpu"))
    report = runtime_report()
    report["configured_environment"] = configured
    report["nvoptix_present"] = (
        Path(os.environ.get("WINDIR", r"C:\Windows"), "System32", "nvoptix.dll").exists()
        if platform.system() == "Windows"
        else None
    )
    blockers = []
    if report.get("genesis_world_version") is None:
        blockers.append("genesis-world is not installed")
    if args.strict_raytracer and not report.get("torch_cuda_available"):
        blockers.append("PyTorch cannot see an NVIDIA CUDA device")
    if args.strict_raytracer and report.get("luisa_render_backend") != "cuda":
        blockers.append("LUISA_RENDER_BACKEND is not cuda")
    if args.strict_raytracer and not report.get("luisa_render_py_available"):
        blockers.append("LuisaRenderPy is not importable; build LuisaRender and set GENESIS_SOURCE_ROOT")
    report["strict_raytracer_ready"] = not blockers
    report["blockers"] = blockers
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())

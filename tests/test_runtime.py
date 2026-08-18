from __future__ import annotations

import os
from pathlib import Path

from genesis_scene.rendering import CameraSpec, camera_manifest
from genesis_scene.runtime import RuntimeConfig, configure_runtime


def test_runtime_paths_are_scoped_to_project(tmp_path: Path, monkeypatch) -> None:
    for key in (
        "XDG_CACHE_HOME",
        "GS_CACHE_FILE_PATH",
        "QD_OFFLINE_CACHE_FILE_PATH",
        "OPTIX_CACHE_PATH",
        "CUDA_CACHE_PATH",
        "MPLCONFIGDIR",
        "NUMBA_CACHE_DIR",
        "LUISA_RENDER_BACKEND",
        "LUISA_RENDER_INTEGRATOR",
    ):
        monkeypatch.delenv(key, raising=False)
    result = configure_runtime(RuntimeConfig(project_root=tmp_path, backend="gpu"))
    assert result["LUISA_RENDER_BACKEND"] == "cuda"
    assert Path(result["GS_CACHE_FILE_PATH"]).is_relative_to(tmp_path)
    assert os.environ["LUISA_RENDER_INTEGRATOR"] == "wavepath"


def test_camera_manifest_is_json_ready() -> None:
    payload = camera_manifest(CameraSpec(pos=(1.0, 2.0, 3.0), lookat=(0.0, 0.0, 0.0)))
    assert payload["pos"] == (1.0, 2.0, 3.0)
    assert payload["width"] == 1280

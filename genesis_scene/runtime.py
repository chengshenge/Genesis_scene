from __future__ import annotations

import importlib.metadata
import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


BackendName = Literal["gpu", "cpu"]


@dataclass(frozen=True)
class RuntimeConfig:
    project_root: Path
    backend: BackendName = "gpu"
    seed: int = 0
    precision: str = "32"
    logging_level: str = "warning"
    luisa_backend: str | None = None
    luisa_integrator: str = "wavepath"
    genesis_source_root: Path | None = None
    luisa_build_bin: Path | None = None
    cuda_bin: Path | None = None


def _set_path(name: str, path: Path) -> str:
    path.mkdir(parents=True, exist_ok=True)
    value = str(path.resolve())
    os.environ.setdefault(name, value)
    return os.environ[name]


def _optional_path(explicit: Path | None, env_name: str, default: Path) -> Path | None:
    if explicit is not None:
        return Path(explicit).resolve()
    env_value = os.environ.get(env_name)
    if env_value:
        return Path(env_value).resolve()
    return default.resolve() if default.exists() else None


def _prepend_runtime_directory(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    resolved = str(path.resolve())
    current = os.environ.get("PATH", "")
    if resolved.lower() not in current.lower().split(os.pathsep):
        os.environ["PATH"] = resolved + os.pathsep + current
    if resolved not in sys.path:
        sys.path.insert(0, resolved)
    if platform.system() == "Windows" and hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(resolved)
        except OSError:
            pass
    return resolved


def configure_runtime(config: RuntimeConfig) -> dict[str, str]:
    """Configure cache and LuisaRender variables before importing Genesis."""
    root = Path(config.project_root).resolve()
    cache_root = root / ".cache"
    tmp_root = root / ".tmp"
    mapping = {
        "XDG_CACHE_HOME": _set_path("XDG_CACHE_HOME", cache_root),
        "GS_CACHE_FILE_PATH": _set_path("GS_CACHE_FILE_PATH", cache_root / "genesis"),
        "QD_OFFLINE_CACHE_FILE_PATH": _set_path(
            "QD_OFFLINE_CACHE_FILE_PATH", cache_root / "quadrants" / "qdcache"
        ),
        "OPTIX_CACHE_PATH": _set_path("OPTIX_CACHE_PATH", cache_root / "optix"),
        "CUDA_CACHE_PATH": _set_path("CUDA_CACHE_PATH", cache_root / "cuda"),
        "MPLCONFIGDIR": _set_path("MPLCONFIGDIR", tmp_root / "matplotlib"),
        "NUMBA_CACHE_DIR": _set_path("NUMBA_CACHE_DIR", cache_root / "numba"),
    }
    os.environ.setdefault(
        "LUISA_RENDER_BACKEND",
        config.luisa_backend or ("cuda" if config.backend == "gpu" else "cpu"),
    )
    os.environ.setdefault("LUISA_RENDER_INTEGRATOR", config.luisa_integrator)
    mapping["LUISA_RENDER_BACKEND"] = os.environ["LUISA_RENDER_BACKEND"]
    mapping["LUISA_RENDER_INTEGRATOR"] = os.environ["LUISA_RENDER_INTEGRATOR"]

    genesis_root = _optional_path(
        config.genesis_source_root,
        "GENESIS_SOURCE_ROOT",
        root / ".external" / "Genesis",
    )
    if genesis_root is not None and (genesis_root / "genesis" / "__init__.py").exists():
        source_text = str(genesis_root)
        if source_text not in sys.path:
            sys.path.insert(0, source_text)
        mapping["GENESIS_SOURCE_ROOT"] = source_text
        os.environ.setdefault("GENESIS_SOURCE_ROOT", source_text)

    default_luisa_bin = (
        genesis_root / "genesis" / "ext" / "LuisaRender" / "build-win-cuda" / "bin" / "Release"
        if genesis_root is not None and platform.system() == "Windows"
        else (
            genesis_root / "genesis" / "ext" / "LuisaRender" / "build" / "bin"
            if genesis_root is not None
            else root / ".missing-luisa-build"
        )
    )
    luisa_bin = _optional_path(config.luisa_build_bin, "LUISA_RENDER_BUILD_BIN", default_luisa_bin)
    configured_luisa_bin = _prepend_runtime_directory(luisa_bin)
    if configured_luisa_bin:
        os.environ.setdefault("LUISA_RENDER_BUILD_BIN", configured_luisa_bin)
        mapping["LUISA_RENDER_BUILD_BIN"] = os.environ["LUISA_RENDER_BUILD_BIN"]

    default_cuda_bin = root / ".local" / "cuda-cu12-win" / "bin"
    cuda_bin = _optional_path(config.cuda_bin, "CUDA_BIN_DIR", default_cuda_bin)
    configured_cuda_bin = _prepend_runtime_directory(cuda_bin)
    if configured_cuda_bin:
        os.environ.setdefault("CUDA_BIN_DIR", configured_cuda_bin)
        mapping["CUDA_BIN_DIR"] = os.environ["CUDA_BIN_DIR"]
    return mapping


def initialize_genesis(config: RuntimeConfig):
    """Initialize Genesis after runtime variables have been configured."""
    configure_runtime(config)
    import genesis as gs
    from genesis.constants import backend as gs_backend

    backend = gs_backend.gpu if config.backend == "gpu" else gs_backend.cpu
    gs.init(
        seed=config.seed,
        precision=config.precision,
        logging_level=config.logging_level,
        backend=backend,
    )
    return gs


def runtime_report() -> dict[str, Any]:
    report: dict[str, Any] = {
        "python": sys.version,
        "platform": platform.platform(),
        "luisa_render_backend": os.environ.get("LUISA_RENDER_BACKEND"),
        "luisa_render_integrator": os.environ.get("LUISA_RENDER_INTEGRATOR"),
        "genesis_source_root": os.environ.get("GENESIS_SOURCE_ROOT"),
        "luisa_render_build_bin": os.environ.get("LUISA_RENDER_BUILD_BIN"),
        "cuda_bin_dir": os.environ.get("CUDA_BIN_DIR"),
    }
    try:
        report["genesis_world_version"] = importlib.metadata.version("genesis-world")
    except importlib.metadata.PackageNotFoundError:
        report["genesis_world_version"] = None
    try:
        import torch

        report.update(
            {
                "torch_version": torch.__version__,
                "torch_cuda_available": bool(torch.cuda.is_available()),
                "torch_cuda_version": torch.version.cuda,
                "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            }
        )
    except Exception as exc:
        report["torch_error"] = str(exc)
    try:
        import LuisaRenderPy

        report["luisa_render_py_available"] = True
        report["luisa_render_py_file"] = getattr(LuisaRenderPy, "__file__", None)
    except Exception as exc:
        report["luisa_render_py_available"] = False
        report["luisa_render_py_error"] = str(exc)
    return report

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
from PIL import Image


RendererName = Literal["raytracer", "rasterizer"]


@dataclass(frozen=True)
class CameraSpec:
    pos: tuple[float, float, float]
    lookat: tuple[float, float, float]
    up: tuple[float, float, float] = (0.0, 0.0, 1.0)
    fov: float = 39.0
    width: int = 1280
    height: int = 720
    spp: int = 16
    denoise: bool = True


@dataclass(frozen=True)
class RenderSpec:
    renderer: RendererName = "raytracer"
    width: int = 1280
    height: int = 720
    hdr_path: Path | None = None


def make_scene(gs: Any, spec: RenderSpec):
    kwargs: dict[str, Any] = {
        "sim_options": gs.options.SimOptions(dt=2e-4, substeps=1, gravity=(0.0, 0.0, -9.8)),
        "viewer_options": gs.options.ViewerOptions(camera_fov=30, res=(spec.width, spec.height)),
        "vis_options": gs.options.VisOptions(env_separate_rigid=True),
        "show_viewer": False,
    }
    if spec.renderer == "raytracer":
        if spec.hdr_path is not None:
            hdr_path = Path(spec.hdr_path).resolve()
            if not hdr_path.exists():
                raise FileNotFoundError(f"HDR environment map not found: {hdr_path}")
            env_surface = gs.surfaces.Emission(
                emissive_texture=gs.textures.ImageTexture(
                    image_path=hdr_path.as_posix(),
                    image_color=(0.5, 0.5, 0.5),
                    encoding="linear",
                )
            )
        else:
            env_surface = gs.surfaces.Emission(color=(0.34, 0.36, 0.40))
        kwargs["renderer"] = gs.renderers.RayTracer(
            env_radius=200.0,
            env_surface=env_surface,
            lights=[
                {
                    "pos": (0.0, -7.0, 4.0),
                    "color": (255.0, 247.0, 235.0),
                    "radius": 1.8,
                    "intensity": 0.45,
                },
                {
                    "pos": (1.5, 3.0, 3.0),
                    "color": (205.0, 222.0, 255.0),
                    "radius": 1.2,
                    "intensity": 0.20,
                },
            ],
        )
    else:
        kwargs["renderer"] = gs.renderers.Rasterizer()
    return gs.Scene(**kwargs)


def add_camera(scene: Any, spec: CameraSpec):
    return scene.add_camera(
        pos=spec.pos,
        lookat=spec.lookat,
        up=spec.up,
        fov=spec.fov,
        res=(spec.width, spec.height),
        spp=spec.spp,
        denoise=spec.denoise,
        GUI=False,
    )


def render_rgb(camera: Any) -> np.ndarray:
    rgb, _, _, _ = camera.render(rgb=True, depth=False, segmentation=False, force_render=True)
    image = np.asarray(rgb)
    if image.dtype != np.uint8:
        max_value = float(np.nanmax(image)) if image.size else 1.0
        if max_value <= 1.5:
            image = image * 255.0
        image = np.clip(image, 0, 255).astype(np.uint8)
    return image


def save_gif(frames: list[Image.Image], path: Path, duration_ms: int = 160) -> Path:
    if not frames:
        raise ValueError("At least one frame is required")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=duration_ms, loop=0)
    return path


def write_manifest(path: Path, payload: dict[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def camera_manifest(spec: CameraSpec) -> dict[str, Any]:
    return asdict(spec)

from __future__ import annotations

import argparse
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis_scene.rendering import CameraSpec, RenderSpec, add_camera, camera_manifest, make_scene, render_rgb, save_gif, write_manifest
from genesis_scene.runtime import RuntimeConfig, initialize_genesis, runtime_report
from genesis_scene.scene_primitives import add_blocks, add_bowl_and_water, add_table_environment, add_target_outline


def _euler_to_quat(euler: np.ndarray) -> np.ndarray:
    cy, sy = np.cos(euler[2] * 0.5), np.sin(euler[2] * 0.5)
    cp, sp = np.cos(euler[1] * 0.5), np.sin(euler[1] * 0.5)
    cr, sr = np.cos(euler[0] * 0.5), np.sin(euler[0] * 0.5)
    return np.array(
        [
            cy * cp * cr + sy * sp * sr,
            cy * cp * sr - sy * sp * cr,
            sy * cp * sr + cy * sp * cr,
            sy * cp * cr - cy * sp * sr,
        ]
    )


def _as_numpy(value) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "numpy"):
        value = value.numpy()
    return np.asarray(value)


def _add_xarm(scene, gs, robotsmith_root: Path):
    urdf = robotsmith_root / "assets" / "xarm7_with_gripper_reduced_dof.urdf"
    if not urdf.exists():
        raise FileNotFoundError(f"RobotSmith xArm URDF not found: {urdf}")
    return scene.add_entity(
        gs.morphs.URDF(
            file=str(urdf.resolve()),
            pos=(0.0, -0.58, 0.0),
            euler=(0.0, 0.0, 90.0),
            fixed=True,
            collision=False,
            recompute_inertia=True,
            links_to_keep=["link_tcp"],
        ),
        surface=gs.surfaces.Default(vis_mode="visual"),
        name="single_xarm_parallel_gripper",
    )


def _pose_xarm(xarm) -> dict[str, object]:
    hand = np.array([0.34, 0.02, 0.285, 0.0, 86.0, 90.0], dtype=float)
    hand[3:] = np.deg2rad(hand[3:])
    qpos, error = xarm.inverse_kinematics(
        link=xarm.get_link("link_tcp"),
        pos=hand[:3],
        quat=_euler_to_quat(hand[3:]),
        return_error=True,
        respect_joint_limit=False,
    )
    qpos = _as_numpy(qpos).astype(float)
    if qpos.size >= 2:
        qpos[-2:] = 0.0
    xarm.set_qpos(qpos, zero_velocity=True)
    return {"ready_tcp": hand[:3].tolist(), "ik_error": _as_numpy(error).tolist()}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a reusable single-arm Genesis tabletop scene.")
    default_robot_root = Path(os.environ.get("ROBOTSMITH_ROOT", ROOT / ".external" / "RobotSmith"))
    parser.add_argument("--robotsmith-root", type=Path, default=default_robot_root)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "raytraced_tabletop")
    parser.add_argument("--renderer", choices=("raytracer", "rasterizer"), default="raytracer")
    parser.add_argument("--backend", choices=("gpu", "cpu"), default="gpu")
    parser.add_argument("--robot", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--spp", type=int, default=16)
    parser.add_argument("--settle-steps", type=int, default=4)
    parser.add_argument("--seed", type=int, default=1604)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.renderer == "raytracer" and args.backend != "gpu":
        raise RuntimeError("Strict RayTracer mode requires --backend gpu and a working NVIDIA CUDA/OptiX runtime.")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    hdr_path = args.robotsmith_root / "assets" / "hdr.hdr" if args.robot else None
    gs = initialize_genesis(RuntimeConfig(project_root=ROOT, backend=args.backend, seed=args.seed))
    render_spec = RenderSpec(
        renderer=args.renderer,
        width=args.width,
        height=args.height,
        hdr_path=hdr_path if hdr_path and hdr_path.exists() else None,
    )
    scene = make_scene(gs, render_spec)

    entities = add_table_environment(scene, gs)
    entities.update(add_blocks(scene, gs))
    entities.update(add_target_outline(scene, gs))
    entities.update(add_bowl_and_water(scene, gs, generated_asset_dir=output_dir / "generated_assets"))
    xarm = None
    if args.robot:
        xarm = _add_xarm(scene, gs, args.robotsmith_root.resolve())
        entities["xarm"] = xarm

    camera_spec = CameraSpec(
        pos=(2.32, 0.015, 1.92),
        lookat=(0.25, 0.035, 0.065),
        fov=39.0,
        width=args.width,
        height=args.height,
        spp=args.spp,
        denoise=True,
    )
    camera = add_camera(scene, camera_spec)
    started = time.time()
    scene.build()
    robot_pose = _pose_xarm(xarm) if xarm is not None else None

    frames: list[Image.Image] = []
    for _ in range(max(1, args.settle_steps)):
        scene.step()
        scene.visualizer.update()
        frames.append(Image.fromarray(render_rgb(camera)))

    rgb_path = output_dir / "scene_rgb.png"
    frames[-1].save(rgb_path)
    gif_path = save_gif(frames, output_dir / "scene_preview.gif")
    manifest = {
        "renderer_requested": args.renderer,
        "renderer_effective": args.renderer,
        "rasterizer_fallback_allowed": False,
        "rasterizer_fallback_used": False,
        "runtime": runtime_report(),
        "camera": camera_manifest(camera_spec),
        "robot": {
            "enabled": bool(args.robot),
            "source": "RobotSmith xarm7_with_gripper_reduced_dof.urdf" if args.robot else None,
            "robotsmith_root": str(args.robotsmith_root.resolve()) if args.robot else None,
            "pose": robot_pose,
        },
        "entities": sorted(entities),
        "outputs": {"rgb": str(rgb_path), "gif": str(gif_path)},
        "render_seconds": round(time.time() - started, 3),
    }
    manifest_path = write_manifest(output_dir / "scene_manifest.json", manifest)
    print(f"RGB: {rgb_path}")
    print(f"GIF: {gif_path}")
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import numpy as np
import trimesh
from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis_scene.runtime import RuntimeConfig, initialize_genesis, runtime_report
from genesis_scene.task_config import load_task_config, resolve_asset, validate_required_assets


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a JSON-configured Genesis task with strict CUDA/OptiX.")
    parser.add_argument("task", type=Path, help="Task JSON, for example tasks/reference_robot_paper_can_pen.json")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--spp", type=int)
    return parser.parse_args()


def _rotation_matrix(euler_deg: list[float]) -> np.ndarray:
    x, y, z = np.deg2rad(np.asarray(euler_deg, dtype=float))
    cx, sx = math.cos(x), math.sin(x)
    cy, sy = math.cos(y), math.sin(y)
    cz, sz = math.cos(z), math.sin(z)
    rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]], dtype=float)
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], dtype=float)
    rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]], dtype=float)
    return rz @ ry @ rx


def _euler_radians(euler_deg: list[float]) -> tuple[float, float, float]:
    return tuple(float(math.radians(value)) for value in euler_deg)


def _normalized_mesh_pose(mesh_path: Path, target_extent: float, bottom_pos: list[float], euler_deg: list[float]):
    loaded = trimesh.load(str(mesh_path), force="scene", process=False)
    bounds = np.asarray(loaded.bounds, dtype=float)
    extents = bounds[1] - bounds[0]
    if not np.all(np.isfinite(bounds)) or float(extents.max()) <= 1e-9:
        raise ValueError(f"Invalid bounds for task asset: {mesh_path}")
    scale = float(target_extent) / float(extents.max())
    normalized = bounds * scale
    corners = np.array(
        [[normalized[ix, 0], normalized[iy, 1], normalized[iz, 2]] for ix in (0, 1) for iy in (0, 1) for iz in (0, 1)],
        dtype=float,
    )
    rotated = corners @ _rotation_matrix(euler_deg).T
    rotated_bounds = np.stack((rotated.min(axis=0), rotated.max(axis=0)))
    center_xy = rotated_bounds[:, :2].mean(axis=0)
    pos = (
        float(bottom_pos[0]) - float(center_xy[0]),
        float(bottom_pos[1]) - float(center_xy[1]),
        float(bottom_pos[2]) - float(rotated_bounds[0, 2]),
    )
    return scale, pos, normalized.tolist()


def _write_table_maps(normal_source: Path, roughness_source: Path, output_dir: Path) -> dict[str, Path]:
    derived = output_dir / "generated_materials"
    derived.mkdir(parents=True, exist_ok=True)
    normal_path = derived / "robowits_table_normal_subtle.png"
    roughness_path = derived / "robowits_table_roughness_calibrated.png"
    albedo_path = derived / "robowits_table_albedo_subtle.png"

    normal = np.asarray(Image.open(normal_source).convert("RGB"), dtype=np.float32)
    flat = np.empty_like(normal)
    flat[...] = np.asarray([128.0, 128.0, 255.0], dtype=np.float32)
    Image.fromarray(np.clip(flat * 0.58 + normal * 0.42, 0, 255).astype(np.uint8)).save(normal_path)

    source = np.asarray(Image.open(roughness_source).convert("L"), dtype=np.float32)
    roughness = 0.48 + 0.22 * source / 255.0
    Image.fromarray(np.clip(roughness * 255.0, 0, 255).astype(np.uint8)).save(roughness_path)
    grain = (source - float(source.mean())) / (float(source.std()) + 1e-6)
    albedo = np.asarray([184.0, 188.0, 192.0])[None, None, :] + 3.2 * grain[..., None]
    Image.fromarray(np.clip(albedo, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.32)).save(albedo_path)
    return {"albedo": albedo_path, "normal": normal_path, "roughness": roughness_path}


def _write_wall_assets(bounds: dict[str, list[float]], output_dir: Path, seed: int) -> dict[str, Path]:
    generated = output_dir / "generated_environment"
    generated.mkdir(parents=True, exist_ok=True)
    mesh_path = generated / "tiled_wall.obj"
    albedo_path = generated / "wall_albedo.png"
    normal_path = generated / "wall_normal.png"
    roughness_path = generated / "wall_roughness.png"

    lower, upper = np.asarray(bounds["lower"], dtype=float), np.asarray(bounds["upper"], dtype=float)
    x, y0, z0, y1, z1 = upper[0], lower[1], lower[2], upper[1], upper[2]
    mesh_path.write_text(
        f"v {x} {y0} {z0}\nv {x} {y1} {z0}\nv {x} {y1} {z1}\nv {x} {y0} {z1}\n"
        "vt 0 0\nvt 5 0\nvt 5 3\nvt 0 3\nvn 1 0 0\nf 1/1/1 2/2/1 3/3/1 4/4/1\n",
        encoding="ascii",
    )
    rng = np.random.default_rng(seed)
    noise = rng.normal(0.0, 1.0, size=(512, 512)).astype(np.float32)
    texture = Image.fromarray(np.clip(128.0 + 20.0 * noise, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(5.5))
    field = np.asarray(texture, dtype=np.float32) / 255.0
    base = np.asarray([0.34, 0.35, 0.35], dtype=np.float32)
    albedo = np.clip((base[None, None, :] + (field[..., None] - 0.5) * 0.16) * 255.0, 0, 255)
    Image.fromarray(albedo.astype(np.uint8)).save(albedo_path)
    gy, gx = np.gradient(field)
    normal = np.dstack((-gx * 0.8, -gy * 0.8, np.ones_like(field)))
    normal /= np.linalg.norm(normal, axis=2, keepdims=True)
    Image.fromarray(np.clip((normal * 0.5 + 0.5) * 255.0, 0, 255).astype(np.uint8)).save(normal_path)
    Image.fromarray(np.full((512, 512), 232, dtype=np.uint8)).save(roughness_path)
    return {"mesh": mesh_path, "albedo": albedo_path, "normal": normal_path, "roughness": roughness_path}


def _filter_glb_material(source_mesh: Path, destination: Path, want_silver: bool) -> bool:
    from pygltflib import GLTF2

    source = GLTF2().load(str(source_mesh))
    selected = {
        index
        for index, material in enumerate(source.materials or [])
        if ("silver" in str(material.name or "").lower()) == want_silver
    }
    if not selected:
        return False
    gltf = GLTF2().load(str(source_mesh))
    for mesh in gltf.meshes or []:
        mesh.primitives = [primitive for primitive in mesh.primitives if primitive.material in selected]
    kept_meshes = [index for index, mesh in enumerate(gltf.meshes or []) if mesh.primitives]
    if not kept_meshes:
        return False
    mesh_map = {old: new for new, old in enumerate(kept_meshes)}
    gltf.meshes = [gltf.meshes[index] for index in kept_meshes]
    kept_nodes = [index for index, node in enumerate(gltf.nodes or []) if node.mesh is None or node.mesh in mesh_map]
    node_map = {old: new for new, old in enumerate(kept_nodes)}
    gltf.nodes = [gltf.nodes[index] for index in kept_nodes]
    for node in gltf.nodes:
        if node.mesh is not None:
            node.mesh = mesh_map[node.mesh]
        if node.children is not None:
            node.children = [node_map[index] for index in node.children if index in node_map]
    for scene in gltf.scenes or []:
        scene.nodes = [node_map[index] for index in (scene.nodes or []) if index in node_map]
    destination.parent.mkdir(parents=True, exist_ok=True)
    gltf.save(str(destination))
    return True


def _prepare_robot_urdf(source: Path, output_dir: Path) -> Path:
    destination = output_dir / "generated_robot" / "xarm7_photoreal.urdf"
    destination.parent.mkdir(parents=True, exist_ok=True)
    root = ET.parse(source).getroot()
    for mesh in root.findall(".//mesh"):
        filename = mesh.attrib.get("filename")
        if filename:
            path = Path(filename) if Path(filename).is_absolute() else source.parent / filename
            mesh.attrib["filename"] = str(path.resolve())
    for link in root.findall("link"):
        for visual in list(link.findall("visual")):
            mesh = visual.find("./geometry/mesh")
            if mesh is None:
                continue
            source_mesh = Path(str(mesh.attrib.get("filename", "")))
            if source_mesh.suffix.lower() != ".glb" or "xarm7" not in str(source_mesh).lower():
                continue
            insertion = list(link).index(visual)
            link.remove(visual)
            for label, color, silver in (
                ("White", "0.56 0.59 0.63 1.0", False),
                ("Silver", "0.18 0.20 0.23 1.0", True),
            ):
                split_path = destination.parent / "visual_meshes" / source_mesh.stem / f"{label.lower()}.glb"
                if not _filter_glb_material(source_mesh, split_path, silver):
                    continue
                item = copy.deepcopy(visual)
                item.find("./geometry/mesh").attrib["filename"] = str(split_path.resolve())
                old_material = item.find("material")
                if old_material is not None:
                    item.remove(old_material)
                material = ET.SubElement(item, "material", {"name": label})
                ET.SubElement(material, "color", {"rgba": color})
                link.insert(insertion, item)
                insertion += 1
    for material in root.findall("material"):
        name = material.attrib.get("name")
        if name not in {"White", "Silver"}:
            continue
        color = material.find("color")
        if color is None:
            color = ET.SubElement(material, "color")
        color.attrib["rgba"] = (
            "0.56 0.59 0.63 1.0" if name == "White" else "0.18 0.20 0.23 1.0"
        )
    for link_name in ("xarm_gripper_base_link", "left_finger", "right_finger"):
        link = root.find(f"./link[@name='{link_name}']")
        if link is None:
            continue
        material = link.find("./visual/material")
        if material is None:
            continue
        material.attrib["name"] = "Black"
        color = material.find("color")
        if color is None:
            color = ET.SubElement(material, "color")
        color.attrib["rgba"] = "0.015 0.015 0.018 1.0"
    ET.ElementTree(root).write(destination, encoding="utf-8", xml_declaration=True)
    return destination


def _euler_to_quat(euler: np.ndarray) -> np.ndarray:
    cy, sy = np.cos(euler[2] * 0.5), np.sin(euler[2] * 0.5)
    cp, sp = np.cos(euler[1] * 0.5), np.sin(euler[1] * 0.5)
    cr, sr = np.cos(euler[0] * 0.5), np.sin(euler[0] * 0.5)
    return np.array([cy * cp * cr + sy * sp * sr, cy * cp * sr - sy * sp * cr, sy * cp * sr + cy * sp * cr, sy * cp * cr - cy * sp * sr])


def _as_numpy(value: Any) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "numpy"):
        value = value.numpy()
    return np.asarray(value)


def _pose_robot(robot: Any, config: dict[str, Any]) -> dict[str, Any]:
    euler = np.deg2rad(np.asarray(config["tcp_euler_deg"], dtype=float))
    qpos, error = robot.inverse_kinematics(
        link=robot.get_link("link_tcp"),
        pos=np.asarray(config["tcp_pos"], dtype=float),
        quat=_euler_to_quat(euler),
        return_error=True,
        respect_joint_limit=False,
    )
    qpos = _as_numpy(qpos).astype(float)
    if qpos.size >= 2:
        qpos[-2:] = float(config["gripper"])
    robot.set_qpos(qpos, zero_velocity=True)
    return {"qpos": qpos.tolist(), "ik_error": _as_numpy(error).tolist()}


def _camera_response(image: np.ndarray, seed: int) -> np.ndarray:
    rgb = image.astype(np.float32) / 255.0
    linear = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    linear *= np.asarray([0.94, 0.925, 0.90], dtype=np.float32)[None, None, :]
    linear = linear / (1.0 + 0.055 * linear)
    rgb = np.where(linear <= 0.0031308, linear * 12.92, 1.055 * np.power(linear, 1 / 2.4) - 0.055)
    h, w = rgb.shape[:2]
    yy, xx = np.mgrid[-1:1:complex(h), -1:1:complex(w)]
    rgb *= (1.0 - 0.035 * np.clip(xx * xx + yy * yy, 0, 1))[..., None]
    rgb += np.random.default_rng(seed).normal(0, 0.0014, rgb.shape).astype(np.float32)
    output = Image.fromarray(np.clip(rgb * 255, 0, 255).astype(np.uint8))
    return np.asarray(output.filter(ImageFilter.UnsharpMask(radius=0.75, percent=32, threshold=3)))


def main() -> int:
    args = _parse_args()
    print(f"[render-task] Loading task config: {args.task}", flush=True)
    task = load_task_config(args.task)
    renderer = task["renderer"]
    if renderer["name"] != "raytracer" or renderer["backend"] != "gpu" or renderer["rasterizer_fallback_allowed"]:
        raise RuntimeError("Published photoreal tasks require strict GPU RayTracer mode with no fallback")
    assets = validate_required_assets(task, ROOT)
    print(f"[render-task] Validated {len(assets)} required assets", flush=True)
    width = args.width or int(renderer["width"])
    height = args.height or int(renderer["height"])
    spp = args.spp or int(renderer["spp"])
    output_dir = (args.output_dir or ROOT / "outputs" / task["task_id"]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    print("[render-task] Initializing Genesis on the GPU", flush=True)
    gs = initialize_genesis(RuntimeConfig(project_root=ROOT, backend="gpu", seed=int(task["seed"])))
    print("[render-task] Creating strict CUDA/OptiX RayTracer scene", flush=True)
    env_surface = gs.surfaces.Emission(
        emissive_texture=gs.textures.ImageTexture(
            image_path=str(assets["hdr"]),
            image_color=tuple(task["lighting"]["hdr_color_scale"]),
            encoding="linear",
        )
    )
    scene = gs.Scene(
        sim_options=gs.options.SimOptions(dt=2e-4, substeps=1, gravity=(0, 0, -9.8)),
        viewer_options=gs.options.ViewerOptions(camera_fov=30, res=(width, height)),
        vis_options=gs.options.VisOptions(env_separate_rigid=True),
        show_viewer=False,
        renderer=gs.renderers.RayTracer(env_radius=200.0, env_surface=env_surface, lights=task["lighting"]["lights"]),
    )

    table_maps = _write_table_maps(assets["table.normal_texture"], assets["table.roughness_texture"], output_dir)
    scene.add_entity(
        morph=gs.morphs.Mesh(
            file=str(assets["table.mesh"]), pos=tuple(task["table"]["pos"]), scale=tuple(task["table"]["scale"]),
            fixed=True, collision=False, visualization=True, file_meshes_are_zup=bool(task["table"]["file_meshes_are_zup"]),
            convexify=False, decompose_nonconvex=False, decimate=False,
        ),
        surface=gs.surfaces.Rough(
            diffuse_texture=gs.textures.ImageTexture(image_path=str(table_maps["albedo"])),
            normal_texture=gs.textures.ImageTexture(image_path=str(table_maps["normal"]), encoding="linear"),
            roughness_texture=gs.textures.ImageTexture(image_path=str(table_maps["roughness"]), encoding="linear"),
            roughness=None, smooth=True,
        ),
        name="robowits_white_work_table",
    )
    wall = _write_wall_assets(task["environment"]["wall_bounds"], output_dir, int(task["seed"]))
    scene.add_entity(
        morph=gs.morphs.Mesh(file=str(wall["mesh"]), fixed=True, collision=False, align=False, convexify=False, decimate=False),
        surface=gs.surfaces.Rough(
            diffuse_texture=gs.textures.ImageTexture(image_path=str(wall["albedo"])),
            normal_texture=gs.textures.ImageTexture(image_path=str(wall["normal"]), encoding="linear"),
            roughness_texture=gs.textures.ImageTexture(image_path=str(wall["roughness"]), encoding="linear"), roughness=None,
        ),
        name="tiled_pbr_wall",
    )
    scene.add_entity(
        morph=gs.morphs.Mesh(file=str(assets["floor_mesh"]), pos=tuple(task["environment"]["floor_pos"]), scale=float(task["environment"]["floor_scale"]), fixed=True, collision=False),
        surface=gs.surfaces.Rough(color=(0.025, 0.025, 0.027, 1.0), roughness=0.88), name="dark_floor",
    )

    object_manifest: dict[str, Any] = {}
    for item in task["objects"]:
        path = assets[f"object.{item['id']}"]
        scale, pos, normalized_bounds = _normalized_mesh_pose(path, item["target_extent"], item["bottom_pos"], item["euler_deg"])
        scene.add_entity(
            morph=gs.morphs.Mesh(file=str(path), pos=pos, euler=_euler_radians(item["euler_deg"]), scale=scale, fixed=True, collision=False, visualization=True, align=False, convexify=False, decimate=False),
            name=item["id"],
        )
        object_manifest[item["id"]] = {"asset_id": item["asset_id"], "mesh": str(path), "scale": scale, "pos": list(pos), "normalized_bounds": normalized_bounds}

    robot_urdf = _prepare_robot_urdf(assets["robot.urdf"], output_dir)
    robot = scene.add_entity(
        morph=gs.morphs.URDF(
            file=str(robot_urdf), pos=tuple(task["robot"]["base_pos"]), euler=tuple(task["robot"]["base_euler_deg"]),
            scale=float(task["robot"]["scale"]), fixed=True, collision=False, recompute_inertia=True,
            links_to_keep=["link_tcp"], prioritize_urdf_material=True,
        ), name="single_xarm_parallel_gripper",
    )
    camera_cfg = task["camera"]
    camera = scene.add_camera(
        pos=tuple(camera_cfg["pos"]), lookat=tuple(camera_cfg["lookat"]), up=tuple(camera_cfg["up"]), fov=float(camera_cfg["fov"]),
        res=(width, height), spp=spp, denoise=bool(renderer["denoise"]), GUI=False,
    )
    started = time.time()
    print("[render-task] Building scene", flush=True)
    scene.build()
    robot_pose = _pose_robot(robot, task["robot"])
    scene.step()
    scene.visualizer.update()
    print(f"[render-task] Rendering {width}x{height} at {spp} spp", flush=True)
    rgb, _, _, _ = camera.render(rgb=True, depth=False, segmentation=False, force_render=True)
    image = np.asarray(rgb)
    if image.dtype != np.uint8:
        if float(np.nanmax(image)) <= 1.5:
            image = image * 255.0
        image = np.clip(image, 0, 255).astype(np.uint8)
    image = _camera_response(image, int(task["seed"]))
    output_path = output_dir / "scene_rgb.png"
    Image.fromarray(image).save(output_path)
    print(f"[render-task] Wrote RGB image: {output_path}", flush=True)
    manifest = {
        "task_id": task["task_id"], "task_config": task["_config_path"], "task_config_sha256": task["_config_sha256"],
        "renderer_effective": "raytracer", "rasterizer_fallback_allowed": False, "resolution": [width, height], "spp": spp,
        "camera": camera_cfg, "lighting": task["lighting"], "table": task["table"], "robot": {**task["robot"], "prepared_urdf": str(robot_urdf), "pose": robot_pose},
        "objects": object_manifest, "runtime": runtime_report(), "render_seconds": round(time.time() - started, 3), "output_rgb": str(output_path),
    }
    manifest_path = output_dir / "scene_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"rgb": str(output_path), "manifest": str(manifest_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

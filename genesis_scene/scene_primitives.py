from __future__ import annotations

import math
from pathlib import Path
from typing import Any


def add_table_environment(scene: Any, gs: Any) -> dict[str, Any]:
    entities: dict[str, Any] = {}
    wood = gs.surfaces.Rough(color=(0.20, 0.095, 0.045, 1.0), roughness=0.58)
    entities["tabletop"] = scene.add_entity(
        material=gs.materials.Rigid(friction=0.85, rho=650.0),
        morph=gs.morphs.Box(size=(1.06, 1.36, 0.04), pos=(0.0, 0.0, -0.02), fixed=True),
        surface=wood,
        name="tabletop",
    )
    for index, (x, y) in enumerate(((-0.47, -0.62), (-0.47, 0.62), (0.47, -0.62), (0.47, 0.62))):
        entities[f"table_leg_{index}"] = scene.add_entity(
            morph=gs.morphs.Box(size=(0.075, 0.075, 0.76), pos=(x, y, -0.40), fixed=True, collision=False),
            surface=wood,
            name=f"table_leg_{index}",
        )
    entities["floor"] = scene.add_entity(
        morph=gs.morphs.Box(size=(3.0, 3.0, 0.025), pos=(0.0, 0.0, -0.79), fixed=True, collision=False),
        surface=gs.surfaces.Rough(color=(0.20, 0.21, 0.22, 1.0), roughness=0.92),
        name="floor",
    )
    entities["wall"] = scene.add_entity(
        morph=gs.morphs.Box(size=(0.025, 3.0, 2.2), pos=(-0.92, 0.0, 0.20), fixed=True, collision=False),
        surface=gs.surfaces.Rough(color=(0.90, 0.90, 0.87, 1.0), roughness=0.90),
        name="rear_wall",
    )
    return entities


def add_target_outline(
    scene: Any,
    gs: Any,
    *,
    center: tuple[float, float, float] = (0.16, 0.31, 0.003),
    outer_size: tuple[float, float] = (0.21, 0.17),
) -> dict[str, Any]:
    cx, cy, cz = center
    outer_x, outer_y = outer_size
    border = 0.010
    thickness = 0.003
    specs = (
        ((outer_x, border, thickness), (cx, cy - outer_y * 0.5 + border * 0.5, cz)),
        ((outer_x, border, thickness), (cx, cy + outer_y * 0.5 - border * 0.5, cz)),
        ((border, outer_y, thickness), (cx - outer_x * 0.5 + border * 0.5, cy, cz)),
        ((border, outer_y, thickness), (cx + outer_x * 0.5 - border * 0.5, cy, cz)),
    )
    entities: dict[str, Any] = {}
    for index, (size, pos) in enumerate(specs):
        entities[f"target_{index}"] = scene.add_entity(
            material=gs.materials.Rigid(friction=0.9, rho=600.0),
            morph=gs.morphs.Box(size=size, pos=pos, fixed=True),
            surface=gs.surfaces.Rough(color=(0.12, 0.55, 0.17, 1.0), roughness=0.75),
            name=f"green_target_{index}",
        )
    return entities


def add_blocks(scene: Any, gs: Any, *, side: float = 0.07) -> dict[str, Any]:
    entities: dict[str, Any] = {}
    for index, y in enumerate((-0.15, -0.05, 0.05, 0.15)):
        density = 30.0 if index == 0 else 7800.0
        entity = scene.add_entity(
            material=gs.materials.Rigid(friction=0.92, rho=density, sdf_cell_size=0.0015),
            morph=gs.morphs.Box(
                size=(side, side, side),
                pos=(0.31, y, side * 0.5 + 0.0005),
                fixed=False,
                collision=True,
            ),
            surface=gs.surfaces.Metal(color=(0.46, 0.47, 0.48, 1.0), metal_type="aluminium", roughness=0.28),
            name=f"visually_identical_block_{index}",
        )
        entities[f"cube_{index}"] = entity
    return entities


def write_open_bowl_obj(path: Path, *, segments: int = 72) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    outer_bottom, outer_top = 0.086, 0.118
    inner_bottom, inner_top = 0.073, 0.103
    height, bottom_thickness = 0.082, 0.007
    vertices: list[tuple[float, float, float]] = []

    def ring(radius: float, z: float) -> list[int]:
        result = []
        for index in range(segments):
            theta = 2.0 * math.pi * index / segments
            vertices.append((radius * math.cos(theta), radius * math.sin(theta), z))
            result.append(len(vertices))
        return result

    ob = ring(outer_bottom, 0.0)
    ot = ring(outer_top, height)
    ib = ring(inner_bottom, bottom_thickness)
    it = ring(inner_top, height - 0.003)
    faces: list[tuple[int, ...]] = []
    for index in range(segments):
        nxt = (index + 1) % segments
        faces.extend(
            (
                (ob[index], ob[nxt], ot[nxt], ot[index]),
                (ib[nxt], ib[index], it[index], it[nxt]),
                (ot[index], ot[nxt], it[nxt], it[index]),
                (ob[nxt], ob[index], ib[index], ib[nxt]),
            )
        )
    path.write_text(
        "# generated open bowl\n"
        + "".join(f"v {x:.7f} {y:.7f} {z:.7f}\n" for x, y, z in vertices)
        + "".join("f " + " ".join(str(value) for value in face) + "\n" for face in faces),
        encoding="utf-8",
    )
    return path


def add_bowl_and_water(
    scene: Any,
    gs: Any,
    *,
    generated_asset_dir: Path,
    center: tuple[float, float] = (0.56, -0.16),
) -> dict[str, Any]:
    bowl_path = write_open_bowl_obj(Path(generated_asset_dir) / "open_bowl.obj")
    cx, cy = center
    entities: dict[str, Any] = {}
    entities["bowl"] = scene.add_entity(
        morph=gs.morphs.Mesh(
            file=str(bowl_path.resolve()),
            pos=(cx, cy, 0.0),
            fixed=True,
            collision=False,
            visualization=True,
            convexify=False,
            decimate=False,
        ),
        surface=gs.surfaces.Glass(color=(0.78, 0.92, 1.0, 0.30), opacity=0.30, roughness=0.015, thickness=0.004),
        name="transparent_open_bowl",
    )
    entities["water"] = scene.add_entity(
        morph=gs.morphs.Cylinder(pos=(cx, cy, 0.048), radius=0.094, height=0.003, fixed=True, collision=False),
        surface=gs.surfaces.Glass(color=(0.30, 0.57, 0.94, 0.48), opacity=0.48, roughness=0.02, thickness=0.002),
        name="water_surface",
    )
    return entities

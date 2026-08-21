from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REQUIRED_TOP_LEVEL_KEYS = {
    "task_id",
    "camera",
    "renderer",
    "lighting",
    "table",
    "robot",
    "objects",
}


def load_task_config(path: Path) -> dict[str, Any]:
    path = Path(path).resolve()
    # PowerShell and some Windows editors may emit UTF-8 JSON with a BOM.
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    missing = sorted(REQUIRED_TOP_LEVEL_KEYS - set(payload))
    if missing:
        raise ValueError(f"Task config {path} is missing required keys: {missing}")
    if not isinstance(payload["objects"], list) or not payload["objects"]:
        raise ValueError(f"Task config {path} must declare at least one object")
    payload["_config_path"] = str(path)
    payload["_config_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return payload


def resolve_asset(root: Path, relative_path: str) -> Path:
    path = Path(relative_path)
    return path.resolve() if path.is_absolute() else (Path(root).resolve() / path).resolve()


def required_asset_paths(config: dict[str, Any], project_root: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for key in ("mesh", "normal_texture", "roughness_texture"):
        value = config["table"].get(key)
        if value:
            paths[f"table.{key}"] = resolve_asset(project_root, value)
    for key in ("urdf", "hdr", "floor_mesh"):
        value = config["robot"].get(key) if key == "urdf" else config.get("environment", {}).get(key)
        if key == "hdr":
            value = config["lighting"].get("hdr")
        if value:
            paths["robot.urdf" if key == "urdf" else key] = resolve_asset(project_root, value)
    for item in config["objects"]:
        paths[f"object.{item['id']}"] = resolve_asset(project_root, item["mesh"])
    return paths


def validate_required_assets(config: dict[str, Any], project_root: Path) -> dict[str, Path]:
    paths = required_asset_paths(config, project_root)
    missing = {label: path for label, path in paths.items() if not path.exists()}
    if missing:
        formatted = "\n".join(f"  - {label}: {path}" for label, path in missing.items())
        raise FileNotFoundError(
            "Task assets are missing. Download the IDs listed in docs/ASSETS.md and place the prepared files at:\n"
            f"{formatted}"
        )
    return paths

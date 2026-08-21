from pathlib import Path

import pytest

from genesis_scene.task_config import load_task_config, required_asset_paths, validate_required_assets


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks" / "reference_robot_paper_can_pen.json"


def test_reference_task_has_strict_photoreal_contract():
    config = load_task_config(TASK)
    assert config["task_id"] == "reference_robot_paper_can_pen"
    assert config["renderer"]["name"] == "raytracer"
    assert config["renderer"]["backend"] == "gpu"
    assert config["renderer"]["rasterizer_fallback_allowed"] is False
    assert config["renderer"]["width"] == 1600
    assert config["renderer"]["height"] == 1200
    assert config["renderer"]["spp"] == 256
    assert config["camera"]["lookat"][2] == pytest.approx(0.31)
    assert len(config["objects"]) == 3


def test_reference_task_records_all_required_assets():
    config = load_task_config(TASK)
    paths = required_asset_paths(config, ROOT)
    assert "table.mesh" in paths
    assert "robot.urdf" in paths
    assert "hdr" in paths
    assert "floor_mesh" in paths
    assert {key for key in paths if key.startswith("object.")} == {
        "object.white_a4_paper",
        "object.red_food_can",
        "object.black_ballpoint_pen",
    }


def test_missing_downloaded_assets_fail_before_rendering(tmp_path: Path):
    config = load_task_config(TASK)
    with pytest.raises(FileNotFoundError, match="Task assets are missing"):
        validate_required_assets(config, tmp_path)


def test_task_config_accepts_utf8_bom(tmp_path: Path):
    bom_config = tmp_path / "task_with_bom.json"
    bom_config.write_text(TASK.read_text(encoding="utf-8"), encoding="utf-8-sig")

    config = load_task_config(bom_config)

    assert config["task_id"] == "reference_robot_paper_can_pen"

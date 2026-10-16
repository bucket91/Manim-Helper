from __future__ import annotations

import json
from pathlib import Path

import pytest

from bms.project import DEFAULT_SETTINGS, Project, quality_params

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE = REPO_ROOT / "samples" / "demo_project"
SAMPLE_SCENE = SAMPLE / "scenes" / "DemoParabola.scene.json"

_SUBDIRS = (
    "scenes",
    "narration_cache",
    "renders",
    "logs",
    "reports",
    ".bms",
    ".bms/baseline",
    ".bms/original",
    ".bms/history",
)


def test_create_makes_tree_and_defaults(tmp_path):
    root = tmp_path / "p"
    Project.create(root, "X")
    assert (root / "project.json").exists()
    assert (root / "pronunciation.json").exists()
    for sub in _SUBDIRS:
        assert (root / sub).is_dir()
    settings = json.loads((root / "project.json").read_text(encoding="utf-8"))
    assert settings["name"] == "X"
    for key, value in DEFAULT_SETTINGS.items():
        if key == "name":
            continue
        assert settings[key] == value
    assert settings["scene_order"] == []


def test_create_refuses_overwrite(tmp_path):
    root = tmp_path / "p"
    Project.create(root, "X")
    with pytest.raises(FileExistsError):
        Project.create(root, "Y")


def test_open_sample_and_scene_ids():
    project = Project.open(SAMPLE)
    assert project.settings["name"] == "Demo"
    assert project.scene_ids() == ["DemoParabola"]
    scene = project.load_scene("DemoParabola")
    assert scene["scene_id"] == "DemoParabola"


def test_open_fills_missing_defaults_in_memory_only(tmp_path):
    root = tmp_path / "p"
    Project.create(root, "X")
    data = json.loads((root / "project.json").read_text(encoding="utf-8"))
    del data["pad"]
    del data["voice"]
    (root / "project.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    project = Project.open(root)
    assert project.settings["pad"] == 0.25
    assert project.settings["voice"] == "bn-BD-PradeepNeural"
    on_disk = json.loads((root / "project.json").read_text(encoding="utf-8"))
    assert "pad" not in on_disk


def test_open_bad_format_version(tmp_path):
    root = tmp_path / "p"
    Project.create(root, "X")
    data = json.loads((root / "project.json").read_text(encoding="utf-8"))
    data["format_version"] = 2
    (root / "project.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError):
        Project.open(root)


def test_import_scene(tmp_path):
    root = tmp_path / "p"
    project = Project.create(root, "X")
    scene_id = project.import_scene(SAMPLE_SCENE)
    assert scene_id == "DemoParabola"
    assert (root / "scenes" / "DemoParabola.scene.json").exists()
    assert project.settings["scene_order"] == ["DemoParabola"]
    persisted = json.loads((root / "project.json").read_text(encoding="utf-8"))
    assert persisted["scene_order"] == ["DemoParabola"]

    with pytest.raises(FileExistsError):
        project.import_scene(SAMPLE_SCENE)

    assert project.import_scene(SAMPLE_SCENE, overwrite=True) == "DemoParabola"
    assert project.settings["scene_order"] == ["DemoParabola"]


def test_import_scene_requires_scene_id(tmp_path):
    root = tmp_path / "p"
    project = Project.create(root, "X")
    bad = tmp_path / "bad.scene.json"
    bad.write_text(json.dumps({"format_version": 1}), encoding="utf-8")
    with pytest.raises(ValueError):
        project.import_scene(bad)


def test_quality_params():
    settings = {"final_fps": 60}
    assert quality_params(settings, "draft") == (854, 480, 15)
    assert quality_params(settings, "medium") == (1280, 720, 30)
    assert quality_params(settings, "final") == (1920, 1080, 60)
    assert quality_params({"final_fps": 30}, "final") == (1920, 1080, 30)
    with pytest.raises(ValueError):
        quality_params(settings, "nope")


def test_scene_ids_appends_unlisted_sorted(tmp_path):
    root = tmp_path / "p"
    project = Project.create(root, "X")
    project.import_scene(SAMPLE_SCENE)
    (root / "scenes" / "Extra.scene.json").write_text(
        json.dumps({"format_version": 1, "scene_id": "Extra", "objects": {}, "beats": []}),
        encoding="utf-8",
    )
    (root / "scenes" / "Alpha.scene.json").write_text(
        json.dumps({"format_version": 1, "scene_id": "Alpha", "objects": {}, "beats": []}),
        encoding="utf-8",
    )
    assert project.scene_ids() == ["DemoParabola", "Alpha", "Extra"]

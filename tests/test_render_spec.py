from __future__ import annotations

import tempfile
from pathlib import Path

from bms.engine.render import build_render_spec
from bms.project import Project


def test_build_render_spec_draft_scene():
    with tempfile.TemporaryDirectory() as d:
        p = Project.create(Path(d) / "p", "P")
        spec = build_render_spec(p, "s1", "draft", "scene", None, False, False)
        assert spec["project_root"] == str(p.root)
        assert spec["scene_id"] == "s1"
        assert spec["mode"] == "scene"
        assert spec["beat_id"] is None
        assert spec["quality"] == "draft"
        assert (spec["width"], spec["height"], spec["fps"]) == (854, 480, 15)
        assert spec["out_dir"] == str(p.root / "renders" / "s1" / "draft")
        assert spec["continue_on_error"] is False
        assert spec["debug"] is False


def test_build_render_spec_medium_beat():
    with tempfile.TemporaryDirectory() as d:
        p = Project.create(Path(d) / "p", "P")
        spec = build_render_spec(p, "s1", "medium", "beat", "b1", True, True)
        assert (spec["width"], spec["height"], spec["fps"]) == (1280, 720, 30)
        assert spec["mode"] == "beat"
        assert spec["beat_id"] == "b1"
        assert spec["continue_on_error"] is True
        assert spec["debug"] is True


def test_build_render_spec_final_uses_final_fps():
    with tempfile.TemporaryDirectory() as d:
        p = Project.create(Path(d) / "p", "P")
        p.settings["final_fps"] = 30
        spec = build_render_spec(p, "s1", "final", "frame", "b2", False, False)
        assert (spec["width"], spec["height"], spec["fps"]) == (1920, 1080, 30)
        p.settings["final_fps"] = 60
        spec = build_render_spec(p, "s1", "final", "frame", "b2", False, False)
        assert spec["fps"] == 60
        assert spec["beat_id"] == "b2"
        assert spec["mode"] == "frame"

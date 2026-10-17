from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from bms import jsonio
from bms.engine import stitch
from bms.engine.hashing import beat_hash, settings_hash
from bms.project import Project


def _ready_project(root: Path) -> Project:
    p = Project.create(root, "P")
    scene = {
        "format_version": 1,
        "scene_id": "s1",
        "layout": "full",
        "objects": {},
        "beats": [{"id": "b1", "narration": "hi", "steps": []}],
    }
    p.save_scene("s1", scene)
    p.settings["scene_order"] = ["s1"]
    p.save_settings()
    r = p.subdir("renders") / "s1" / "draft"
    r.mkdir(parents=True, exist_ok=True)
    (r / "scene.mp4").write_bytes(b"fake")
    jsonio.save_json_atomic(
        r / "manifest.json",
        {
            "rendered_at": "2020-01-01T00:00:00+00:00",
            "settings_hash": settings_hash(p.settings, p.pronunciation),
            "beat_hashes": {"b1": beat_hash(scene, "b1", p.settings, p.pronunciation)},
        },
    )
    return p


def test_stitch_list_quotes(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        p = _ready_project(Path(d) / "p'x")
        captured: dict = {}

        def fake_run_hidden(cmd):
            list_path = Path(cmd[cmd.index("-i") + 1])
            captured["content"] = list_path.read_text(encoding="utf-8")
            captured["cmd"] = cmd
            return type("R", (), {"returncode": 0})()

        monkeypatch.setattr(stitch, "run_hidden", fake_run_hidden)
        out = stitch.stitch(p, quality="draft")
        assert captured["content"].startswith("file '")
        assert "\\'" in captured["content"]
        assert "-c" in captured["cmd"]
        assert "copy" in captured["cmd"]
        assert out == p.root / "renders" / "_project" / "draft" / "project.mp4"


def test_stitch_missing_raises(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        p = Project.create(Path(d) / "p", "P")
        p.settings["scene_order"] = ["s1"]
        p.save_settings()
        monkeypatch.setattr(
            stitch, "run_hidden", lambda cmd: type("R", (), {"returncode": 0})()
        )
        with pytest.raises(RuntimeError):
            stitch.stitch(p, quality="draft")

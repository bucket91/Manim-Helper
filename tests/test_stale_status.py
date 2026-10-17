from __future__ import annotations

import tempfile
from pathlib import Path

from bms import jsonio
from bms.engine.hashing import beat_hash, settings_hash, stale_status
from bms.project import Project


def _scene() -> dict:
    return {
        "format_version": 1,
        "scene_id": "s1",
        "layout": "full",
        "objects": {},
        "beats": [
            {"id": "b1", "narration": "one", "steps": []},
            {"id": "b2", "narration": "two", "steps": []},
        ],
    }


def _project(root: Path):
    p = Project.create(root, "P")
    scene = _scene()
    p.save_scene("s1", scene)
    return p, scene


def _write_manifest(p: Project, scene: dict, *, settings_hash_value=None, beat_hashes=None):
    r = p.subdir("renders") / "s1" / "draft"
    r.mkdir(parents=True, exist_ok=True)
    (r / "scene.mp4").write_bytes(b"fake")
    if settings_hash_value is None:
        settings_hash_value = settings_hash(p.settings, p.pronunciation)
    if beat_hashes is None:
        beat_hashes = {
            b: beat_hash(scene, b, p.settings, p.pronunciation) for b in ("b1", "b2")
        }
    jsonio.save_json_atomic(
        r / "manifest.json",
        {
            "rendered_at": "2020-01-01T00:00:00+00:00",
            "settings_hash": settings_hash_value,
            "beat_hashes": beat_hashes,
        },
    )
    return r


def test_stale_when_manifest_missing():
    with tempfile.TemporaryDirectory() as d:
        p, _ = _project(Path(d) / "p")
        status = stale_status(p, "s1", "draft")
        assert status["scene_stale"] is True
        assert status["beats"] == {"b1": True, "b2": True}


def test_stale_when_video_missing():
    with tempfile.TemporaryDirectory() as d:
        p, scene = _project(Path(d) / "p")
        r = p.subdir("renders") / "s1" / "draft"
        r.mkdir(parents=True, exist_ok=True)
        jsonio.save_json_atomic(
            r / "manifest.json",
            {
                "rendered_at": "2020-01-01T00:00:00+00:00",
                "settings_hash": settings_hash(p.settings, p.pronunciation),
                "beat_hashes": {
                    b: beat_hash(scene, b, p.settings, p.pronunciation)
                    for b in ("b1", "b2")
                },
            },
        )
        assert stale_status(p, "s1", "draft")["scene_stale"] is True


def test_stale_when_settings_hash_differs():
    with tempfile.TemporaryDirectory() as d:
        p, scene = _project(Path(d) / "p")
        _write_manifest(p, scene, settings_hash_value="deadbeef")
        assert stale_status(p, "s1", "draft")["scene_stale"] is True


def test_fresh_when_everything_matches():
    with tempfile.TemporaryDirectory() as d:
        p, scene = _project(Path(d) / "p")
        _write_manifest(p, scene)
        status = stale_status(p, "s1", "draft")
        assert status["scene_stale"] is False
        assert status["beats"] == {"b1": False, "b2": False}


def test_stale_when_beat_changes():
    with tempfile.TemporaryDirectory() as d:
        p, scene = _project(Path(d) / "p")
        _write_manifest(p, scene)
        scene["beats"][0]["narration"] = "changed"
        p.save_scene("s1", scene)
        status = stale_status(p, "s1", "draft")
        assert status["scene_stale"] is True
        assert status["beats"] == {"b1": True, "b2": False}


def test_stale_when_beat_id_list_differs():
    with tempfile.TemporaryDirectory() as d:
        p, scene = _project(Path(d) / "p")
        _write_manifest(p, scene, beat_hashes={"b1": "x"})
        assert stale_status(p, "s1", "draft")["scene_stale"] is True
